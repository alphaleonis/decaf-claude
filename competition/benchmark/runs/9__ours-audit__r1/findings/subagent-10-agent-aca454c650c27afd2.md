# subagent agent-aca454c650c27afd2

Here is my complete system-level design review.

## Findings

```json
[
  {
    "file": "pkg/proxy/config/config.go",
    "line": 290,
    "severity": "Medium",
    "category": "design",
    "issue": "[API_CONTRACT] NodeHandler.OnNodeChange is documented as 'called whenever creation or modification of node object is observed' (config.go:263-265), but NewNodeConfig wires only UpdateFunc and DeleteFunc onto the informer — there is no AddFunc. Node creation events therefore never invoke OnNodeChange, contradicting the interface contract. Because NodeManager registers as a handler in Run() *after* its own informer was already started and synced in NewNodeManager, the informer's initial-state replay is delivered as an Add and is silently dropped. Any NodeIP change occurring between the startup poll and handler registration is only observed on the next resync (up to one ConfigSyncPeriod later), delaying the intended crash-and-restart that keeps kube-proxy's programmed NodeIPs correct. Any future NodeHandler relying on the documented creation callback also gets nothing.",
    "fix": "Either wire AddFunc to handleChangeNode (so creation is delivered as the contract states), or change the OnNodeChange doc comment to state explicitly that only modifications are delivered and that initial state must be obtained out-of-band (as NodeManager does via its poll). Prefer aligning wiring to the contract to remove the startup detection window.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 177,
    "severity": "Low",
    "category": "design",
    "issue": "[CONCURRENCY_DESIGN] NodeEligible() acquires the exclusive hs.lock (hs.lock.Lock()), but after the refactor the method no longer reads or writes any hs field guarded by that lock — the nodeEligible field it used to protect was removed. It now only dereferences the immutable hs.nodeManager pointer and calls nodeManager.Node(), which performs a DeepCopy under NodeManager's own mutex. The result is a dead lock acquisition that serializes every /healthz request against every other /healthz request and against Health() (which takes RLock), holding the write lock across a node DeepCopy on the health hot path.",
    "fix": "Drop the hs.lock acquisition from NodeEligible() entirely (node-state synchronization already lives in NodeManager), or narrow it to only the region that actually touches hs state (currently none). This removes needless contention on the health endpoint.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 180,
    "severity": "Low",
    "category": "design",
    "issue": "[API_CONTRACT] ProxyHealthServer now has a hard, undocumented dependency on a non-nil NodeManager: NewProxyHealthServer accepts *proxy.NodeManager without validation, and NodeEligible() unconditionally dereferences hs.nodeManager.Node(). Previously the server was self-contained (nodeEligible bool defaulting true) and had no external dependency. Today's only production caller (newProxyServer) constructs NodeManager first and returns on error, so the health server is never built with a nil manager; but the implicit contract is unexpressed and a nil manager (e.g., a future caller, or a test) produces a nil-pointer panic inside the /healthz handler rather than a clear failure.",
    "fix": "Document that NewProxyHealthServer requires a non-nil NodeManager, and either guard NodeEligible() against a nil manager (returning eligible=true, preserving the old startup-eligible semantics) or validate/panic explicitly at construction so the requirement fails loudly and early.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 128,
    "severity": "Low",
    "category": "design",
    "issue": "[DATA_MODEL] PodCIDRs() returns n.node.Spec.PodCIDRs directly — a slice that aliases the shared, informer-cache-owned node object (n.node is set from nodeLister.Get() and from the OnNodeChange event argument, both of which are objects the informer shares read-only across all handlers). This is inconsistent with the sibling accessor Node(), which returns a DeepCopy, and with NodeIPs(), which allocates a fresh slice. A caller that mutates the returned slice would corrupt shared informer state observed by NodeTopologyConfig and other handlers. Current consumers in server.go only read it, so there is no live bug, but the mutation-safety contract is inconsistent and undocumented.",
    "fix": "Return a copy of the PodCIDRs slice (or document PodCIDRs() as read-only), matching the deep-copy contract of Node() so all NodeManager accessors present a uniform ownership boundary.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`healthcheck` → `proxy` dependency reversal.** The PR flips the edge (was `proxy` → `healthcheck` via `NodeEligibleHandler`; now `healthcheck` imports `proxy` for `*NodeManager`). Verified there is no import cycle (`pkg/proxy/*.go` no longer references `proxy/healthcheck`). A child package importing its parent for a shared type is acceptable layering here; sound.

- **NodeManager mixing state-provider and process-lifecycle (crash) responsibilities.** `NodeManager` both exposes node state (`NodeIPs`/`PodCIDRs`/`Node`) and calls `exitFunc` to crash the process on IP/PodCIDR change. This is a mild single-responsibility tension, but it is the type's documented purpose ("handles the life cycle of kube-proxy") and consolidating previously-scattered crash logic is the stated goal of the PR. Design preference, not a defect.

- **Informer started with `wait.NeverStop` inside `newNodeManager`, ignoring `ctx`.** The dedicated node informer factory cannot be shut down via context cancellation and runs for process lifetime. This is a real evolution/testability smell, but it is consistent with the sibling pattern in `ProxyServer.Run` (the main `informerFactory.Start(wait.NeverStop)`), and kube-proxy informers are process-lifetime by design. Not flagged as a defect given the established convention; noted as residual risk.

- **`OnNodeChange` reads old IPs/PodCIDRs and swaps `n.node` under the mutex, then does the DeepEqual comparison outside the lock.** Safe: the informer invokes a single handler registration serially, so `OnNodeChange` is never concurrent with itself; concurrent readers (`Node`/`NodeIPs`/`PodCIDRs` from the health goroutine) all take the same mutex. No race.

- **`handleChangeNode` handling `DeletedFinalStateUnknown` tombstones inside the UpdateFunc path.** Tombstones are a Delete-path concept; the defensive branch is dead on updates but harmless. Cosmetic, not reported.

- **Stale `NodeConfig` doc comment** ("accepts 'set', 'add' and 'remove' operations of node via channels") — there are no channels. Pre-existing coherence drift, outside design scope; belongs to knowledge/coherence review.

### Residual risks
- The removal of `AddFunc` from `NodeConfig` (finding 1) leaves a narrow startup window where a NodeIP change is only caught on the next resync rather than immediately. Detection is delayed, not lost, but the delay can be up to one `ConfigSyncPeriod`.
- `ProxyHealthServer`'s new hard dependency on `NodeManager` (finding 3) is safe only because of construction ordering in `newProxyServer`; it is not enforced by the type.

### Probe Requests
None — findings are grounded in static reading of the wiring and contracts; no revert-probe needed to confirm them.
