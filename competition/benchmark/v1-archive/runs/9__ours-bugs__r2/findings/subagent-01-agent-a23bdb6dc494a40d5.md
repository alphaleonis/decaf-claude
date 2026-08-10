# subagent agent-a23bdb6dc494a40d5

Depth: deep — reshapes kube-proxy node-watch lifecycle/concurrency (>200 executable lines changed), touches process-exit control and shared-informer handler wiring.

I traced the informer replay semantics against the two handler-registration paths (`NodeConfig` and `NodeTopologyConfig`) that now attach to an informer already started+synced inside `NewNodeManager`. The NodeManager crash-on-change path is sound (Add-replay is dropped by the UpdateFunc-only `NodeConfig`, but `n.node` was already captured at construction and any real divergence is caught on the next update/resync). The topology path is not sound.

```json
[
  {
    "file": "cmd/kube-proxy/app/server.go",
    "line": 611,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_COMPOSITION] Informer already running (started in NewNodeManager) → NewNodeTopologyConfig registers an AddFunc that triggers an async replay of the existing node → replay's handleNodeEvent races RegisterEventHandler(s.Proxier); if replay wins, proxier misses the initial zone label and the DeepEqual cache permanently suppresses re-delivery → topology-aware routing silently disabled.",
    "fix": "Register the downstream handler before the informer handler observes state: either call RegisterEventHandler(s.Proxier) before NewNodeTopologyConfig adds its informer handler, or guard n.eventHandlers/n.topologyLabels with a mutex and deliver current topologyLabels to handlers at registration time (mirroring the old 'register handlers, then Start informer' ordering).",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 533,
    "severity": "Medium",
    "category": "async",
    "issue": "[ADV_COMPOSITION] handleNodeEvent (runs on the informer's replay/delivery goroutine) iterates n.eventHandlers while RegisterEventHandler appends to it from the Run goroutine, with no synchronization → data race on the slice (go test -race flags it; torn read can skip the proxier). Introduced because the informer is now already started when handlers are attached, unlike the prior 'Start after RegisterEventHandler' ordering.",
    "fix": "Protect n.eventHandlers with the same lock used around handleNodeEvent's topologyLabels state, or finish all RegisterEventHandler calls before the informer can deliver to this handler.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

Both findings share one root: `NodeTopologyConfig` attaches an `AddFunc` to an informer that `NewNodeManager` already started and synced, so client-go schedules an asynchronous synthetic-Add replay of the current node the moment `AddEventHandlerWithResyncPeriod` returns — before `RegisterEventHandler(s.Proxier)` runs and with no lock between the two goroutines. The old code avoided this by creating a fresh informer factory in `Run()` and calling `Start` only after all handlers were registered (server.go, removed lines 50-79 of the diff). The functional worst case (finding 1) is low-probability per scheduling but permanent when it happens, because `reflect.DeepEqual(n.topologyLabels, topologyLabels)` at config.go:528 suppresses any later re-delivery of the unchanged zone label. `NodeConfig` (the NodeManager path) is not affected: it has no `AddFunc`, so no replay is delivered at registration and its handler slice isn't read in that window.

## Considered But Not Flagged

- **NodeManager misses a NodeIP/PodCIDR change that occurred in the T0→T1 window (construction → handler registration).** The Add-replay to `NodeConfig` is dropped (UpdateFunc-only), so `n.node` stays at the construction snapshot. But the next real Update — or the resync (ConfigSyncPeriod) that re-delivers the node as an Update — runs `OnNodeChange`, compares against the stale snapshot, and exits(1). Detection is bounded by one resync period, not permanently lost. Not a strong defect.

- **Crash-on-change does not fire for a change that happened while kube-proxy was down.** By design: `NewNodeManager` polls the current node and captures whatever IP/PodCIDR exists at startup as the baseline; there is nothing to "detect" against a pre-startup change. Correct behavior, not a defect.

- **Eligibility semantics at startup.** `NodeEligible()` now reads `nodeManager.Node()` live instead of a bool defaulting to eligible. If the node already carries `ToBeDeletedTaint` at construction, `/healthz` returns 503 immediately rather than 200-until-first-event. Behavior change, arguably more correct; not a defect.

- **`handleChangeNode` tombstone (`DeletedFinalStateUnknown`) branch is in the Update path (config.go:322-332).** Tombstones are delivered only via `DeleteFunc`, so this branch is unreachable dead defensive code — no wrong behavior.

- **Nil `nodeManager` deref in `NodeEligible()`.** Only reachable if a `ProxyHealthServer` exists with a nil `NodeManager`. `HealthzServer` is created only in `newProxyServer`, which always constructs `NodeManager` first (and returns on error); hollow-proxy leaves `HealthzServer` nil and never reaches `NodeEligible`. Not reachable. `pre-existing, out of reach`.

### Probe Requests

- To substantiate finding 2 (data race): run `go test -race -run TestNewNodeTopologyConfig ./pkg/proxy/config/` — expected: the existing test may not trigger it (it registers the handler before `sharedInformers.Start`), so a targeted probe test that (a) starts+syncs the informer, then (b) calls `NewNodeTopologyConfig` and `RegisterEventHandler` while the node already exists in the store, run under `-race`, would surface the concurrent access on `n.eventHandlers`. I am not adding this test (read-only); nominating it for the author to confirm.
