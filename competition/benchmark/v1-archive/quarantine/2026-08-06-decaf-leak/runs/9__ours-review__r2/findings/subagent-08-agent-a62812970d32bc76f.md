# subagent agent-a62812970d32bc76f

I have enough to assess the design. Let me verify one detail about the informer being started before handler registration and confirm the NodeConfig has no AddFunc.

The picture is complete. Here is my system model and findings.

## System Model

- **Boundary/ownership**: `NodeManager` (pkg/proxy/node.go) owns a node-scoped informer, creates it, **starts it, and waits for cache sync inside `NewNodeManager`** (node.go:76-79). It also *is* a `NodeHandler` (OnNodeChange/OnNodeDelete/OnNodeSynced) and exposes `NodeInformer()` so `server.go` can build additional configs on top of the same informer.
- **Contracts**: `NodeManager` accessors — `Node()` returns a DeepCopy; `NodeIPs()` returns a freshly-allocated slice; `PodCIDRs()` returns the node's own slice header. `NodeManager.OnNodeChange` crashes the process (`exitFunc(1)`) on any NodeIP/PodCIDR change.
- **Data flow at startup** (server.go Run, 606-614): main goroutine builds `NodeConfig` (handler = NodeManager) and `NodeTopologyConfig` (handler = Proxier) by calling `AddEventHandler…` on the **already-started, already-synced** NodeManager informer, then `RegisterEventHandler(...)`.
- **Concurrency**: NodeManager.mu guards `node`. `NodeConfig.eventHandlers` / `NodeTopologyConfig.eventHandlers` are plain slices with no mutex.

The load-bearing observation: the deleted code started its node informer factory **after** registering all handlers, with an explicit comment ("This has to start after the calls to NewNodeConfig because that must configure the shared informer event handler first"). The new code registers handlers on an informer that is already running.

## Findings

```json
[
  {
    "file": "cmd/kube-proxy/app/server.go",
    "line": 610,
    "severity": "High",
    "category": "design",
    "issue": "[CONCURRENCY_DESIGN] NodeTopologyConfig/NodeConfig register event handlers on the NodeManager informer, which was already Start()ed and cache-synced inside NewNodeManager (node.go:76-79). This drops the ordering guarantee the removed code documented ('This has to start after the calls to NewNodeConfig ... configure the shared informer event handler first'). Two concrete consequences on NodeTopologyConfig (which, unlike NodeConfig, has an AddFunc): (1) the informer asynchronously replays the initial node as an Add on its listener goroutine, and handleNodeEvent ranges over n.eventHandlers while the main goroutine is still appending s.Proxier via RegisterEventHandler(611) — an unsynchronized concurrent read/write of the eventHandlers slice (data race). (2) If that replayed Add is processed before RegisterEventHandler(s.Proxier) runs, handleNodeEvent updates n.topologyLabels from {} to {zone:X} with no handler registered yet; the subsequent reflect.DeepEqual short-circuit then suppresses delivery, so the Proxier never receives the node's initial zone label and topology-aware routing runs with empty labels until the label next changes (rarely, if ever).",
    "fix": "Restore the original ordering: register all event handlers on the node informer before the informer factory is started/synced, or have NodeManager expose a registration API that guarantees handlers are attached prior to the initial cache delivery. Failing that, guard eventHandlers with the same mutex used elsewhere and have handleNodeEvent emit the current topology snapshot on first registration.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 128,
    "severity": "Low",
    "category": "design",
    "issue": "[API_CONTRACT] Accessor contracts are inconsistent about ownership of returned data. Node() returns a DeepCopy (safe to retain/mutate), NodeIPs() returns a freshly-allocated slice, but PodCIDRs() returns n.node.Spec.PodCIDRs directly — an alias into the shared informer-cache node object, released from the lock on return. The lock guards only the pointer read, not the returned data, giving a false impression of a defensive copy. A caller that mutates the returned slice would corrupt the shared cache object. It is currently safe only because the sole caller (server.go:218) assigns without mutating and informer objects are immutable by convention; the contract itself is fragile and asymmetric with Node().",
    "fix": "Make the accessor family consistent: either return a copied slice from PodCIDRs() (append([]string(nil), ...)) or document all three accessors' aliasing/ownership contract explicitly.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 177,
    "severity": "Low",
    "category": "design",
    "issue": "[CONCURRENCY_DESIGN] NodeEligible() acquires hs.lock.Lock() (a write lock) but accesses none of the state that lock protects (lastUpdatedMap/oldestPendingQueuedMap). The eligibility state it used to guard (the nodeEligible field) was removed; the value now comes from hs.nodeManager.Node(), which is independently synchronized by NodeManager.mu. The retained write-lock acquisition protects nothing here and needlessly serializes NodeEligible against the hot-path Updated()/QueuedUpdate()/Health() calls that legitimately contend for hs.lock.",
    "fix": "Drop the hs.lock acquisition from NodeEligible (NodeManager.Node() already returns a synchronized snapshot), or use RLock if any hs-owned state is later read here.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "cmd/kube-proxy/app/server.go",
    "line": 608,
    "severity": "Low",
    "category": "design",
    "issue": "[BOUNDARY_VIOLATION] Ownership of the node informer is split. NodeManager creates, starts, and syncs the informer and is itself a NodeHandler, yet it also exports NodeInformer() so server.go can build two further config objects (NodeConfig, NodeTopologyConfig) directly on that internal informer and re-register NodeManager and Proxier as handlers. server.go thus depends on NodeManager's internal wiring (that the informer is pre-started, and on the timing implications of that) rather than on a cohesive NodeManager API. This is the coupling a prior reviewer raised and is also what makes the ordering issue above possible.",
    "fix": "Encapsulate handler registration inside NodeManager (e.g. NodeManager.RegisterNodeHandler / RegisterTopologyHandler that attach before the informer begins delivering), so callers never touch the raw informer or depend on its start/sync ordering.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Crash-on-change (`OnNodeChange`/`OnNodeDelete` → `exitFunc(1)`), no reconcile path (node.go:150-179)**: This is an intentional, documented design choice that preserves prior kube-proxy behavior (the removed `NewNodePodCIDRHandler` and node-eligibility handling likewise relied on process restart). It is an EVOLUTION_READINESS constraint but not a defect introduced by this change.
- **Nil `nodeManager` panic in `NodeEligible()`**: `NodeEligible` unconditionally dereferences `hs.nodeManager`. I verified this cannot fire today: `HealthzServer` is only constructed in `newProxyServer` (server.go:244), which always creates a non-nil `NodeManager` first (returning early on error); the hollow-proxy path (pkg/proxy/kubemark/hollow_proxy.go:65) leaves both `HealthzServer` and `NodeManager` nil together. The invariant "HealthzServer non-nil ⇒ nodeManager non-nil" is implicit/undocumented but currently holds, so not flagged.
- **`NodeConfig` losing its `AddFunc`** (only `UpdateFunc`/`DeleteFunc` remain): Intentional — NodeManager is seeded with the initial node during polling in `NewNodeManager`, so it only needs update/delete notifications. The narrow window where NodeIPs change between poll and registration and then never update again is too speculative to flag.
- **`handleChangeNode` tombstone handling on the `UpdateFunc` path** (config.go): This is a robustness change in quick-reviewer/edge-case territory, not a system-design concern.

### Probe Requests
None required — all findings are verifiable from the source read above.
