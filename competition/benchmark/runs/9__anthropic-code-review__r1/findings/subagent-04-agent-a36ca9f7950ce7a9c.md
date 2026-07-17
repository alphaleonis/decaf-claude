# subagent agent-a36ca9f7950ce7a9c

I now have a complete picture. Let me assemble the review.

## System Model Extraction

**Boundaries/ownership:**
- `NodeManager` (`pkg/proxy/node.go`) owns one node informer + lister, captures a baseline `node` at construction via polling, and is the sole authority on "has the node fundamentally changed → exit."
- `NodeConfig` and `NodeTopologyConfig` (`pkg/proxy/config/config.go`) are two independent handler registrations on that **same** informer. `NodeConfig` drives `NodeManager` (exit path); `NodeTopologyConfig` drives the proxiers (topology-label sync path).
- `ProxyHealthServer` (`pkg/proxy/healthcheck`) now holds a `*proxy.NodeManager` and derives eligibility on demand.
- Proxiers (iptables/ipvs/nftables/meta/winkernel) implement `config.NodeTopologyHandler.OnTopologyChange` only.

**Contracts under change:** `NodeHandler` collapsed to `OnNodeChange`/`OnNodeDelete`/`OnNodeSynced`; new `NodeTopologyHandler.OnTopologyChange(map[string]string)`; `Provider` swaps `NodeHandler` → `NodeTopologyHandler`.

**Concurrency model:** `NodeManager.mu` guards `node`; `Node()` returns a deep copy. `ProxyHealthServer.lock` guards `lastUpdatedMap`/`oldestPendingQueuedMap`. Proxier `mu` guards `topologyLabels`.

Findings below.

```json
[
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 177,
    "severity": "Low",
    "category": "design",
    "issue": "[CONCURRENCY_DESIGN] NodeEligible() acquires the ProxyHealthServer write lock (hs.lock.Lock) but no longer reads or writes any field that lock protects. Before this change the lock guarded the hs.nodeEligible bool; that field is gone. The method now only reads hs.nodeManager (set once at construction, never mutated) and calls hs.nodeManager.Node() (which is self-synchronized by NodeManager.mu). The write lock is purposeless for correctness and actively serializes every /healthz eligibility check against the dataplane hot path — Updated()/QueuedUpdate() (called by the proxier sync loop) take the same lock — while NodeEligible holds it across a full v1.Node DeepCopy.",
    "fix": "Drop hs.lock from NodeEligible entirely; node-object access is already synchronized inside NodeManager.Node(). If any serialization is genuinely wanted, take an RLock, not a write lock, and do not hold it across the DeepCopy.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 290,
    "severity": "Medium",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] The exit-on-change safety mechanism has a startup blind spot created by splitting baseline capture from event registration. NewNodeManager captures the baseline node (and the NodeIPs/PodCIDRs baked into the proxier) at construction time by polling the lister, but the informer keeps running afterward. NodeConfig then registers on that already-started informer with UpdateFunc only (AddFunc was dropped). client-go replays the informer's current store as synthetic Add notifications when a handler is registered, and those Adds are silently dropped here. n.node only advances via OnNodeChange (UpdateFunc). So a NodeIP/PodCIDR change that lands between NewNodeManager and handler registration in Run() is coalesced into the dropped Add and is never compared against the baseline unless a later, unrelated Update happens to fire — if the node then quiesces, the change is missed permanently and kube-proxy runs indefinitely with stale NodeIPs instead of restarting.",
    "fix": "Reconcile the informer's current state against the captured baseline at handler-registration time rather than relying on a future Update: e.g. register an AddFunc that routes into the same change-detection path (making an initial-state==baseline comparison a no-op), or have NodeManager re-read the lister and run OnNodeChange once immediately after RegisterEventHandler. This closes the construction→registration window.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 535,
    "severity": "Medium",
    "category": "design",
    "issue": "[API_CONTRACT] OnTopologyChange hands out NodeTopologyConfig's own internal map (n.topologyLabels) by reference to every registered handler, and each proxier stores that same reference (iptables/ipvs/nftables Proxier.topologyLabels = topologyLabels; metaProxier forwards the identical map to both the ipv4 and ipv6 proxiers). The OnTopologyChange contract does not document ownership or immutability. It is safe today only because handleNodeEvent allocates a fresh map on every event (so the previously handed-out map is replaced, never mutated in place) and because all handlers treat it read-only. Any future handler that mutates the received map — or any future change that mutates n.topologyLabels in place instead of reallocating — would corrupt shared state across the config and all proxiers with no compiler or contract enforcement.",
    "fix": "Make the ownership explicit: document OnTopologyChange as receiving a read-only map the callee must not retain-and-mutate, or defensively pass a copy to each handler. Given the map is tiny (at most the zone label), copying per handler is cheap and removes the aliasing hazard entirely.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/topology.go",
    "line": 44,
    "severity": "Medium",
    "category": "design",
    "issue": "[CROSS_CUTTING_DRIFT] Topology-label filtering is now split across two packages with the coupling enforced only by a code comment. NodeTopologyConfig.handleNodeEvent (pkg/proxy/config) hardcodes a single label (v1.LabelTopologyZone) as the definition of 'proxy-relevant topology,' while CategorizeEndpoints (pkg/proxy/topology) is the consumer that decides which labels actually matter. The new note in CategorizeEndpoints ('If you modify the logic over here ... ensure the filtering logic in NodeTopologyConfig is updated accordingly') documents a real hidden dependency: if CategorizeEndpoints ever begins consuming another label, the config-side filter will silently strip it and the proxier will never see it, with no test or type to catch the drift.",
    "fix": "Make the set of proxy-relevant topology label keys a single shared, exported source of truth (e.g. a var in pkg/proxy consumed by both NodeTopologyConfig and CategorizeEndpoints), so the producer's filter and the consumer's usage cannot diverge without a compile/reference change rather than a comment.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 155,
    "severity": "Medium",
    "category": "design",
    "issue": "[BOUNDARY_VIOLATION] Process-lifecycle control is exercised from deep inside an informer callback in the pkg/proxy library rather than surfaced to the owning command. OnNodeChange/OnNodeDelete call n.exitFunc(1) (os.Exit in production) directly. This means the terminate-and-restart decision is taken in a library-level goroutine with no seam back to cmd/kube-proxy's Run() (which already funnels healthz/metrics failures through error channels in its select). os.Exit(1) bypasses deferred cleanup and gives the command no opportunity to coordinate shutdown, emit an event, or choose a policy; the exitFunc injection makes it testable but does not restore the boundary. The previous design only self-exited for PodCIDR changes; this generalizes hard-exit to NodeIP changes and deletions.",
    "fix": "Consider surfacing the change as a cancellation/error to cmd/kube-proxy (e.g. cancel the root context or send on a nodeChangedCh consumed by Run()'s select) so the command layer owns the exit and can run normal shutdown, instead of calling os.Exit from within the proxy package. If direct exit is intentional for restart-by-supervisor semantics, document that this is deliberately a hard exit and why graceful shutdown is not wanted.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 180,
    "severity": "Low",
    "category": "design",
    "issue": "[API_CONTRACT] ProxyHealthServer now carries an implicit, unenforced non-nil NodeManager requirement. NodeEligible() dereferences hs.nodeManager.Node() with no nil guard, and the constructors accept *proxy.NodeManager without validating it. Previously eligibility defaulted to true ('eligible while starting up until the first event says otherwise'), so a health server could exist and answer before/without node data. The new coupling means any construction path that passes a nil NodeManager turns a /healthz request into a nil-pointer panic in the serving goroutine rather than a benign default.",
    "fix": "Make the dependency explicit: either validate nodeManager != nil in newProxyHealthServer (fail fast at construction), or have NodeEligible handle a nil/absent node manager by returning the documented startup default (true) instead of dereferencing.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 503,
    "severity": "Low",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] NodeTopologyConfig diverges from its sibling configs (NodeConfig, ServiceCIDRConfig) in lifecycle without the difference being expressed anywhere. It stores listerSynced but exposes no Run() method, and server.go never starts it, so listerSynced is dead and there is no OnSynced/'initial state ready' propagation for the topology path. Functionally the initial node still reaches the proxier via the synthetic Add on registration, but the asymmetry (one config on the shared informer gets a Run/sync barrier, the other silently does not) is a maintenance trap for anyone extending topology handling to need a synced signal.",
    "fix": "Either remove the unused listerSynced field to signal intentional 'no sync barrier here,' or add a Run()/sync step consistent with the other *Config types so all handler registrations on the shared node informer follow one lifecycle pattern.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`handleChangeNode` tombstone handling on the UpdateFunc path** (config.go:320-332): `handleChangeNode` decodes `DeletedFinalStateUnknown`, but it is only wired to `UpdateFunc`, which never delivers a tombstone. Harmless defensive dead code, not a design defect. (anchor 25)

- **`PodCIDRs()`/`NodeIPs()` returning slices aliasing `n.node`** (node.go:120-132): `PodCIDRs()` returns `n.node.Spec.PodCIDRs` by reference under the lock. Because `OnNodeChange` replaces `n.node` wholesale rather than mutating it in place, the returned slice never changes underfoot. Safe as written; only a latent hazard if the update path ever switched to in-place mutation. Sound. (anchor 25)

- **Two handler registrations on one informer, ordering between the exit path (NodeConfig→NodeManager) and the sync path (NodeTopologyConfig→Proxier)**: the two registrations are independent; no handler depends on the other's ordering or state, so there is no cross-handler race or ordering contract to violate. Sound. (anchor 25)

- **`OnNodeChange` continuing past `exitFunc(1)`** (node.go:150-172): after a PodCIDR-triggered `exitFunc(1)`, control falls through to the NodeIP check. In production `os.Exit` never returns; in tests `exitFunc` is a no-op and the fall-through is intentional. Not a design gap. (anchor 25)

- **Winkernel `OnTopologyChange` no-op stub** (winkernel/proxier.go): explicitly a TODO stub matching the prior `NoopNodeHandler` behavior; interface conformance is satisfied and no regression is introduced. Sound for this changeset. (anchor 0)

- **`NodeTopologyConfig` DeleteFunc is a no-op** (config.go:499): on node deletion the proxier's topology labels are not cleared, but `NodeManager.OnNodeDelete` exits the process on the same event, so stale labels are unobservable. Sound. (anchor 25)

Note: finding #5 (process exit from the proxy package) is partly a design preference and partly pre-existing (the PodCIDR self-exit predates this PR); I flag it because the mechanism is now newly centralized in this changeset and generalized to NodeIPs and deletions, which is the right moment to reconsider the boundary. Confidence is held at 50 accordingly.
