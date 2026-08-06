# subagent agent-af3d67fe2c18029da

```json
[
  {
    "file": "pkg/proxy/config/config.go",
    "line": 288,
    "severity": "High",
    "category": "other",
    "issue": "[BUG_LOGIC] NewNodeConfig's merged handler wiring only sets UpdateFunc, dropping AddFunc entirely, so OnNodeChange is never invoked for Add-type informer events — contradicting the just-updated NodeHandler interface doc (\"OnNodeChange is called whenever creation or modification of node object is observed\", config.go L498-500) and RegisterEventHandler's doc (\"called on every node change\").",
    "fix": "Wire AddFunc to the same callback as UpdateFunc, e.g. `AddFunc: func(obj interface{}) { result.handleChangeNode(obj) }, UpdateFunc: func(_, newObj interface{}) { result.handleChangeNode(newObj) },` mirroring how NodeTopologyConfig (added in this same diff, config.go L620-632) wires both Add and Update to handleNodeEvent.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`cmd/kube-proxy/app/server.go` L607 `if s.NodeManager != nil`**: verified this branch is only nil for `HollowProxy`, which constructs `ProxyServer{}` directly (bypassing `newProxyServer`) and never sets `HealthzBindAddress`, so `ProxyHealthServer.NodeEligible()`'s unguarded `hs.nodeManager.Node()` (proxy_health.go L180) is never reached with a nil `nodeManager` in any real code path. Not flagged (anchor 25).
- **`ProxyHealthServer.NodeEligible()` uses `hs.lock.Lock()` (write lock) instead of `RLock()`** (proxy_health.go L177): the method only reads `hs.nodeManager` (unrelated to the fields `hs.lock` actually protects) and calls into `NodeManager`'s own internal mutex; this just adds unnecessary contention with `Updated()`/`QueuedUpdate()`, not a correctness bug — performance-reviewer territory, not flagged here.
- **`NodeManager.OnNodeChange` can call `exitFunc(1)` twice** (once for PodCIDR change, once for NodeIP change) when both change simultaneously: harmless since real `exitFunc` is `os.Exit`, which terminates immediately; only observable in unit tests with a mock exit func, and existing tests already tolerate that. Not flagged.
- **Missing AddFunc's real-world consequence is bounded to the startup window before `NodeConfig`'s handler is registered** (initial state already captured synchronously via polling in `NewNodeManager`) **plus the 15-minute default `ConfigSyncPeriod` resync as a backstop** — genuinely reduces impact severity but doesn't eliminate the defect against the documented contract, hence still reported above rather than dismissed.
- **`reflect.DeepEqual` nil-vs-empty-slice slice comparison in `OnNodeChange`**: pattern carried over unchanged from the pre-existing `NodePodCIDRHandler.OnNodeUpdate` logic being replaced; not newly introduced.
