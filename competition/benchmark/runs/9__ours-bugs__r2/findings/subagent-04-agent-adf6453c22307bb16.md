# subagent agent-adf6453c22307bb16

Depth: deep — >400-line concurrency/event-flow refactor touching data-mutation-adjacent kube-proxy routing, healthcheck eligibility, and process-lifecycle (os.Exit) paths. All four techniques applied; scenarios traced end-to-end and grounded on disk.

## Assumption inventory (reference frame)
- NodeTopologyConfig/NodeConfig assume handlers are registered *before* the node informer starts (old code enforced this via ordered `Start`).
- Proxier assumes its *only* topology source (`nodeTopologyConfig`) delivers the initial zone label.
- `handleNodeEvent` assumes any missed notification will be re-delivered later (the `DeepEqual` guard says otherwise).
- NodeManager assumes node-object deletion warrants a hard `os.Exit(1)`.

## Findings

```json
[
  {
    "file": "pkg/proxy/config/config.go",
    "line": 528,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_COMPOSITION] informer already running at RegisterEventHandler → initial-sync Add delivered to handleNodeEvent before proxier is registered → n.topologyLabels set to {zone} with zero handlers notified → DeepEqual guard then suppresses every future unchanged-zone event → proxier runs with nil topologyLabels for its whole lifetime → topology-aware routing (trafficDistribution/topology hints) silently disabled",
    "fix": "Register the proxier handler before the informer is started, OR have NodeTopologyConfig replay current n.topologyLabels to newly-registered handlers in RegisterEventHandler, OR gate delivery on a HasSynced+explicit initial push like the old ordered-Start pattern.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 510,
    "severity": "Medium",
    "category": "async",
    "issue": "[ADV_COMPOSITION] data race: RegisterEventHandler appends n.eventHandlers with no lock while handleNodeEvent (config.go:533) reads the same slice from the informer callback goroutine — and the informer is already started/synced inside NewNodeManager (node.go:76) long before Run() registers handlers. Same pattern in NodeConfig (config.go:303 append vs :333 read).",
    "fix": "Guard eventHandlers with the existing/added mutex, or (preferred) restore the invariant that all RegisterEventHandler calls complete before the node informer is started.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

### Why finding 1 is grounded (dual-path)
Forward: `newNodeManager` starts the node informer factory and waits for cache sync (node.go:76-77) during `newProxyServer`, at startup. Much later, `Run()` builds `nodeTopologyConfig` (constructor immediately calls `AddEventHandlerWithResyncPeriod` on that *already-running* informer, config.go ~500) and only *then* executes `nodeTopologyConfig.RegisterEventHandler(s.Proxier)` (server.go:610-611). client-go delivers the pre-existing cached node to the new listener as an async Add. If that Add runs before the `RegisterEventHandler` line, `handleNodeEvent` sets `n.topologyLabels = {zone}` (config.go:532) and iterates an empty `eventHandlers`. Every later event carries the same (static) zone, so `reflect.DeepEqual` at config.go:528 returns early forever. The proxier is registered *only* on `nodeTopologyConfig` (server.go:611) — no NodeConfig fallback — so `proxier.topologyLabels` stays nil; `CategorizeEndpoints` reads `topologyLabels[v1.LabelTopologyZone]` = "" and skips topology filtering.
Backward: for the bad outcome, the initial Add must land before one slice-append statement — the only unconfirmable step (scheduler-dependent), hence confidence 50. The old code (removed in patch 2) had an explicit `currentNodeInformerFactory.Start(...)` placed *after* handler registration with the comment "This has to start after the calls to NewNodeConfig because that must configure the shared informer event handler first" — the refactor dropped exactly this ordering guarantee, which is strong evidence the invariant was load-bearing.

## Considered But Not Flagged

- **`NodeManager.OnNodeDelete` → `os.Exit(1)` (node.go)**: real behavioral regression — old `NodeEligibleHandler`/`NodePodCIDRHandler`/proxier tolerated node-object deletion (went 503-ineligible, kept running); new code hard-exits. Cascade (transient node delete/recreate → crashloop) is real, but this is the PR's explicit, documented intent ("crashes kube-proxy"), not an accidental defect. Design change, out of "introduced defect" reach.
- **`NodeEligible()` startup semantics (proxy_health.go:171-190)**: old code returned eligible=true until the first contrary event; new code reads the startup-polled node immediately. Behavior differs but the new behavior is arguably more correct (no false-healthy window). Not a regression worth flagging.
- **NodeConfig `AddFunc` removal (config.go:290)**: the initial replay Add of the cached node is ignored by NodeConfig, so a taint present at cache-sync time but not yet re-delivered as an Update leaves `NodeManager.node` (and thus eligibility) stale until the next Update/resync (≤ConfigSyncPeriod). Low severity, self-healing, and a real watch Update for the taint normally arrives promptly — pre-existing-style edge, not flagged.
- **Import cycle proxy_health.go → pkg/proxy**: checked — `pkg/proxy` root no longer imports `healthcheck` (removed with `NodeEligibleHandler`), so no cycle. Not a defect.
- **Shared `topologyLabels` map aliasing (config.go:532 → proxier)**: same map reference handed to ipv4/ipv6 proxiers and retained by NodeTopologyConfig, but every event allocates a fresh map (config.go:522) and consumers only read it — no mutation, no race. Fell apart under construction.

No probe requests — both findings are static-source-grounded; finding 2 is `go test -race` verifiable under the production start-then-register ordering but not required for the verdict.
