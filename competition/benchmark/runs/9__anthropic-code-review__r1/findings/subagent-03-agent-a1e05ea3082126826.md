# subagent agent-a1e05ea3082126826

## Findings

```json
[
  {
    "file": "cmd/kube-proxy/app/server.go",
    "line": 607,
    "severity": "High",
    "category": "async",
    "issue": "[BUG_CONCURRENCY] NodeConfig and NodeTopologyConfig register event handlers on an already-started, already-synced shared informer (s.NodeManager.NodeInformer(), started earlier inside NewNodeManager() in newProxyServer()). client-go's AddEventHandlerWithOptions() on an already-started informer spawns new listener goroutines and asynchronously replays the current cache as synthetic Add notifications before returning. NodeTopologyConfig.RegisterEventHandler(s.Proxier) at line 611 runs immediately after config.NewNodeTopologyConfig() returns, appending to the unsynchronized `eventHandlers` slice ([]NodeTopologyHandler in pkg/proxy/config/config.go) with no lock, while the replay goroutine may already be invoking handleNodeEvent() (which iterates that same slice) for the initial node state. If the replay wins the race, s.Proxier.OnTopologyChange never receives the node's initial topology-zone label, and since zone labels rarely change post-registration, the proxier can run with stale/missing topology data for the process lifetime with no error logged. This also constitutes an unsynchronized concurrent slice access (append vs. range) - a genuine Go data race. Every other Config type in this file (ServiceConfig, EndpointSliceConfig, ServiceCIDRConfig) - and the OLD node-handling code in this same PR's diff, which had an explicit comment ('This has to start after the calls to NewNodeConfig because that must configure the shared informer event handler first.') - deliberately register handlers BEFORE starting the informer to avoid exactly this race; the new code breaks that invariant because the informer is started early (inside NewNodeManager, to support the startup poll) and only wired to NodeConfig/NodeTopologyConfig much later in Run().",
    "fix": "Register NodeConfig/NodeTopologyConfig handlers (and the downstream RegisterEventHandler calls) before the node informer's factory Start() is invoked, or add explicit synchronization (mutex) around NodeTopologyConfig.eventHandlers/topologyLabels, or block until RegisterEventHandler calls complete before allowing the informer to redeliver initial state (e.g. build the NodeConfig/NodeTopologyConfig and register their handlers earlier, then defer only the informer's own Start()/poll to happen after registration, mirroring the pattern used for the general informerFactory in the same function).",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 176,
    "severity": "Low",
    "category": "resource-management",
    "issue": "[BUG_CONCURRENCY] NodeEligible() was changed from hs.lock.RLock() to hs.lock.Lock() (a full write lock), but the function body no longer writes any field guarded by hs.lock (the old hs.nodeEligible field write was removed; node state now comes from hs.nodeManager.Node(), which has its own internal mutex). Taking an exclusive write lock here needlessly serializes every /healthz request against Health() (RLock), against other concurrent /healthz requests, and against Updated()/QueuedUpdate() (both take hs.lock.Lock() and are called from the proxier's hot sync-loop path), adding avoidable contention with no correctness benefit.",
    "fix": "Drop hs.lock usage entirely in NodeEligible() (nodeManager.Node() already synchronizes internally and hs.nodeManager is set once at construction and never mutated), or at minimum revert to hs.lock.RLock()/RUnlock() as before.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`cmd/kube-proxy/app/server.go:211` `NewNodeManager` cache-sync wait uses the unbounded outer `ctx` while the subsequent node/IP/PodCIDR poll uses a new 5-minute-bounded context** — a behavior change from the old code (which bounded the *entire* wait, including the initial watch, to 5 minutes via `waitForPodCIDR`'s `context.WithTimeout`). If the informer never syncs (e.g., apiserver unreachable), startup could now block indefinitely on `cache.WaitForNamedCacheSync` before the 5-minute poll timeout even starts. Plausible but speculative — depends on deployment/restart-policy assumptions not verifiable from the diff alone, and arguably a reasonable "keep retrying until apiserver is reachable" design choice. [confidence 25]
- **`pkg/proxy/node.go` `OnNodeChange`'s two independent exit checks (PodCIDR change, then NodeIP change) can both fire in one call** — harmless in production since `os.Exit(1)` terminates on the first call; the mock `exitFunc` in tests just overwrites the same value. Not a bug.
- **`pkg/proxy/config/config.go` `NodeTopologyConfig.handleNodeEvent`'s initial state is a non-nil empty map**, so if a node never carries `topology.kubernetes.io/zone`, `OnTopologyChange` is never invoked (dedup short-circuits immediately). Functionally equivalent to the proxier's zero-value `nil` map default (`CategorizeEndpoints` reads the same `""` either way), so no observable difference. Not a bug.
- **`cmd/kube-proxy/app/kubemark/hollow_proxy.go` comment "we don't create nodeManager for hollow-proxy" (server.go:606)** is slightly indirect — hollow-proxy never calls `newProxyServer` at all (it builds `ProxyServer` directly in `NewHollowProxy`), rather than `newProxyServer` itself skipping NodeManager creation for a "hollow" flag. Comment isn't factually wrong, just imprecise; too trivial to flag.
- Verified via `go build`, `go vet`, and `go test -run '^$'` across `./pkg/proxy/...` and `./cmd/kube-proxy/...` (including cross-compiled `GOOS=windows`) that the diff compiles cleanly with no leftover references to removed symbols (`getNodeIPs`, `waitForPodCIDR`, `NodePodCIDRHandler`, `nodeLabels`, `SyncNode`, `klog.OsExit`), and that `-race`-enabled `node_test.go` tests pass.
