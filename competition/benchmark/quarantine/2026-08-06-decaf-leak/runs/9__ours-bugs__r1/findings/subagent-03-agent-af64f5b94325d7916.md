# subagent agent-af64f5b94325d7916

I have enough to construct the scenarios. Let me confirm the resync semantics don't rescue the missed Add by checking the read path is guarded (line 938 under `proxier.mu`) — confirmed above. Now the findings.

Depth: deep — node-watch consolidation touches concurrency (informer callbacks vs. main-goroutine registration), external-system (apiserver) assumptions, and os.Exit control flow; ~200 executable lines. Focused on the four flagged hypotheses plus the assumption inventory.

Assumption inventory (changed code): (a) the topology informer's initial Add replay is delivered *after* `RegisterEventHandler(s.Proxier)` runs; (b) `NodeTopologyConfig.eventHandlers` is only accessed by one goroutine; (c) the DeepEqual guard only ever suppresses truly-redundant updates; (d) `hs.nodeManager` is non-nil whenever `NodeEligible()` runs; (e) the map handed to the proxier is never mutated in place.

Findings:

```json
[
  {
    "file": "cmd/kube-proxy/app/server.go",
    "line": 613,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_COMPOSITION] NewNodeTopologyConfig registers its handler on an ALREADY-started/synced informer (NodeManager started it at construction) → informer's listener goroutine replays the existing node as an Add and runs handleNodeEvent BEFORE the main goroutine reaches RegisterEventHandler(s.Proxier) → n.topologyLabels is set to the zone labels with zero eventHandlers, so the proxier is never called with its initial zone → the reflect.DeepEqual guard in handleNodeEvent then matches on every subsequent event (including 15m resyncs, which arrive as UpdateFunc) → proxier.topologyLabels stays empty forever, disabling topology-aware endpoint routing (trafficDistribution/topology hints) until an actual zone-label change or kube-proxy restart. The old code deliberately started the informer AFTER registering all handlers (the removed comment 'This has to start after the calls to NewNodeConfig...').",
    "fix": "Restore the invariant that the informer is not delivering to a handler before its downstream eventHandlers are registered: either register s.Proxier before the informer AddEventHandler call (pass handlers into NewNodeTopologyConfig), or have NodeTopologyConfig replay current state to a handler at RegisterEventHandler time, or gate handleNodeEvent until handlers are registered.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 466,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_ABUSE] Data race on NodeTopologyConfig.eventHandlers: the informer's listener goroutine executes handleNodeEvent → `for i := range n.eventHandlers` (line ~465) at the same time the main goroutine runs RegisterEventHandler → `n.eventHandlers = append(...)` (line ~443), with no mutex. Concrete interleaving: informer already started+synced from NodeManager; NewNodeTopologyConfig's AddEventHandler queues the initial Add and starts the listener goroutine; that goroutine ranges the slice while Run's main goroutine appends s.Proxier — unsynchronized concurrent read/write of the slice header (go test -race would flag it). Unlike NodeConfig, NodeTopologyConfig has no Run/lock and nothing serializes these.",
    "fix": "Guard eventHandlers with a mutex, or (better) register all handlers before the informer can deliver — same structural fix as the ordering finding. NodeConfig avoided this by starting the informer only after handler registration.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **[ADV_COMPOSITION] Map-reference aliasing between `NodeTopologyConfig.topologyLabels` and `proxier.topologyLabels` (hypothesis 3):** the proxier stores the passed map by reference (iptables/ipvs/nftables `OnTopologyChange`), and it aliases the config's `n.topologyLabels`. Scenario fell apart: `handleNodeEvent` never mutates a map in place — it always `make(...)` a fresh map and reassigns `n.topologyLabels`, leaving the proxier's copy untouched. The proxier only reads its map (line 938/1816/1252 under `proxier.mu`). No in-place mutation on either side → no corruption. Would become a bug only if either side started mutating the shared map.

- **[ADV_ASSUMPTION] nil `nodeManager` into `NodeEligible()` → `hs.nodeManager.Node()` panic (hypothesis 4):** not reachable. `NodeEligible()` is only invoked via the healthz handler, and `HealthzServer` is constructed only in `newProxyServer` (server.go:244), which always sets a non-nil `s.NodeManager` (server.go:211). The hollow-proxy path (`pkg/proxy/kubemark/hollow_proxy.go`) builds `ProxyServer` directly with `HealthzServer == nil` and `NodeManager == nil`, and `Run()` guards node config behind `if s.NodeManager != nil`, so the healthz handler never runs there. No constructed path reaches `NodeEligible()` with a nil manager.

- **[ADV_ASSUMPTION] `NodeManager.Node()`/`NodeIPs()`/`PodCIDRs()` nil-`node` deref:** `pre-existing-safe` — `newNodeManager` polls until `nodeLister.Get` returns a non-nil node with IPs before constructing, and `OnNodeChange` only ever assigns informer objects (non-nil). No introduced nil path.

### Probe Requests

- **File/test (new):** `pkg/proxy/config/config_test.go`, `TestNodeTopologyConfig_InitialAddBeforeRegister` — build a `SharedInformerFactory`, add a node carrying `v1.LabelTopologyZone`, `Start` + `WaitForCacheSync` (mirroring NodeManager having already started the informer), THEN call `newNodeTopologyConfig(...)` and `RegisterEventHandler(mockHandler)` in that order (mirroring `server.Run`). Run under `-race`. **Expected failure (proves finding 1 load-bearing):** mock handler's `topologyLabels` is empty (initial zone Add consumed before registration) at least intermittently; the `-race` detector additionally reports a read/write race on `eventHandlers` (proves finding 2). A fix that registers the handler before informer delivery would make the handler observe `{topology.kubernetes.io/zone: ...}` deterministically and clear the race.
