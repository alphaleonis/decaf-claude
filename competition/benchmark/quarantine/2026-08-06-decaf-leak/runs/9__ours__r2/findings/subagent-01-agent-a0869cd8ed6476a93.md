# subagent agent-a0869cd8ed6476a93

I have enough to build the full system model and finalize. Let me verify my understanding of the informer/handler-registration ordering with one targeted check on the interface doc wording versus wiring.

I have all context needed. Here is my design review.

## System Model

- **Boundaries:** `NodeManager` (`pkg/proxy/node.go`) is the single owner of the per-node informer/lister and the cached `*v1.Node`. It sits in `pkg/proxy` and is consumed by (a) `cmd/kube-proxy/app/server.go` (startup NodeIPs/PodCIDRs + wiring `NodeConfig`/`NodeTopologyConfig`), and (b) `pkg/proxy/healthcheck` for node-eligibility. Proxiers now depend only on `config.NodeTopologyHandler` (`OnTopologyChange`) rather than the full node lifecycle.
- **Contracts:** `NodeHandler` (`OnNodeChange`/`OnNodeDelete`/`OnNodeSynced`) is now implemented only by `NodeManager`; `Provider` implements `NodeTopologyHandler`. Accessors `NodeIPs()`, `PodCIDRs()`, `Node()`, `NodeInformer()`.
- **Concurrency:** `NodeManager.mu` guards `node`. `OnNodeChange` mutates under lock, compares outside; `exitFunc` invoked outside the lock (good). Informer delivers events serially per handler, so `OnNodeChange` is not concurrent with itself; accessors are concurrent with it. Health server has its own `hs.lock`.
- **Data flow:** informer → `NodeConfig.handleChangeNode` → `NodeManager.OnNodeChange` (crash-on-IP/CIDR-change); informer → `NodeTopologyConfig.handleNodeEvent` (zone-label filter) → proxier `OnTopologyChange`.
- **Dependency direction flip:** previously `pkg/proxy` → `pkg/proxy/healthcheck` (via `NodeEligibleHandler.HealthServer`). Now `pkg/proxy/healthcheck` → `pkg/proxy` (health server holds `*proxy.NodeManager`). No cycle (no file directly in `pkg/proxy` imports `healthcheck`).

## Findings

```json
[
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 74,
    "severity": "Medium",
    "category": "design",
    "issue": "[BOUNDARY_VIOLATION] ProxyHealthServer now depends on the concrete *proxy.NodeManager solely to read the current node via Node(). The health server only needs a read-only node getter, but it is coupled to the full NodeManager, which also owns the node informer/lister, watchPodCIDRs, and process-exit (os.Exit) lifecycle. This reverses the previous layer dependency (proxy -> healthcheck became healthcheck -> proxy) and creates a wide coupling for a narrow need. Concrete cost is already visible in healthcheck_test.go, which must spin up a real NodeManager (informer + cache-sync + poll) just to exercise node eligibility.",
    "fix": "Depend on a minimal interface at the health-server boundary, e.g. `type nodeGetter interface { Node() *v1.Node }`, and accept that instead of the concrete *proxy.NodeManager. This restores the seam, removes the reversed package dependency, and lets health tests use a trivial fake.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 177,
    "severity": "Low",
    "category": "design",
    "issue": "[CONCURRENCY_DESIGN] NodeEligible() acquires hs.lock.Lock() (exclusive write lock) but no longer reads or writes any hs-protected field under it. The previous implementation used RLock to read the hs.nodeEligible field; that field was deleted, yet the lock acquisition remained and was upgraded to a write lock. The node value now comes from hs.nodeManager.Node(), which is internally synchronized. The lock is therefore vestigial: it guards nothing, serializes every /healthz eligibility check against Updated()/QueuedUpdate() write-lock holders for no reason, and misleads readers into thinking eligibility shares state with the timestamp maps.",
    "fix": "Remove the hs.lock acquisition from NodeEligible() (node consistency is already provided by NodeManager's own mutex). If any hs-level consistency is intended, document what field it protects; otherwise drop it.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 131,
    "severity": "Low",
    "category": "design",
    "issue": "[API_CONTRACT] The three accessors have inconsistent snapshot semantics: Node() returns a DeepCopy, NodeIPs() returns a freshly allocated slice (GetNodeHostIPs builds a new slice), but PodCIDRs() returns n.node.Spec.PodCIDRs directly - a reference into the node object obtained from the shared informer lister. Kubernetes' lister/informer contract forbids mutating objects returned from the cache; a caller that mutates the returned slice would corrupt the object shared with all other informer consumers. No current caller mutates it (server.go reads it once for LocalModeNodeCIDR), so this is a latent hazard rather than a live bug, but the asymmetric contract invites future misuse.",
    "fix": "Return a defensive copy of Spec.PodCIDRs (or document that the result is read-only and aliases shared cache state), making the accessor contract symmetric with Node()/NodeIPs().",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 290,
    "severity": "Low",
    "category": "design",
    "issue": "[API_CONTRACT] The NodeHandler.OnNodeChange doc states it 'is called whenever creation or modification of node object is observed,' but NewNodeConfig wires only UpdateFunc (-> handleChangeNode) and DeleteFunc; there is no AddFunc. Node creation events - including the initial-object replay that the shared informer delivers when a handler registers after the informer has already synced (exactly the case here, since NodeManager starts the informer in its constructor and NodeConfig registers later in Run) - are silently dropped. The sole consumer, NodeManager, self-initializes its baseline at construction so it does not depend on the Add, which masks the mismatch; but the generic exported NodeConfig registry now violates its own documented contract, so any future NodeHandler expecting creation notifications will not receive them.",
    "fix": "Either wire AddFunc to handleChangeNode as well (harmless for NodeManager, which compares and finds no diff) or correct the OnNodeChange documentation to state it fires only on modification, and note that initial state is not replayed.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **NodeManager owns `os.Exit` (data accessor + process-lifecycle in one type).** This mixes a read model (`NodeIPs`/`PodCIDRs`/`Node`) with process control, but the `exitFunc` is injected (testable) and this is the PR's deliberate design. Reads as design preference; capped below the reporting-worthy bar on its own.
- **Behavior change: `OnNodeDelete` now calls `exitFunc(1)` (os.Exit).** Previously node deletion only flipped health-server eligibility to false and did not crash kube-proxy. This is a real behavior change but appears intended ("crashes kube-proxy if there are any changes in NodeIPs or PodCIDRs" plus node removal), and belongs to spec-compliance rather than design; noted here for the consolidator.
- **Unconditional restart on any NodeIP change (not gated by a flag).** New behavior versus the old startup-only `getNodeIPs`. Intended per the NodeManager doc; resilience trade-off is a product decision, not a code-level design gap.
- **`nil` `nodeManager` in `NodeEligible()` would panic.** Traced the wiring: in the real proxy, `NewNodeManager` runs before `NewProxyHealthServer` in `newProxyServer` and returns on error, so a non-nil NodeManager is guaranteed whenever a HealthzServer exists; hollow-proxy sets neither (HealthzServer nil, `serveHealthz` returns early). Not reachable today, so not flagged — though the implicit non-nil contract reinforces finding #1.
- **`NodeTopologyConfig` has no `Run()`/`OnSynced` and is never "started" in server.go.** Verified this is correct: handlers fire directly off the already-started shared informer via `AddEventHandlerWithResyncPeriod`, and the initial Add replay delivers the starting zone label. Asymmetric with `NodeConfig.Run` but functionally sound.
- **`handleChangeNode` handling `DeletedFinalStateUnknown` tombstones in the Update path.** Dead defensive branch (UpdateFunc never receives a tombstone) but harmless; belongs to quick-reviewer scope, not design.
- **`Node()` DeepCopy on every /healthz probe.** Cost concern, not design — performance-reviewer scope.

### Note on shared working tree
I made no modifications to tracked files; all inspection was read-only (`Read`, `grep`, `sed -n` print-only). No probe requests needed — all findings are verifiable from the committed post-merge source.
