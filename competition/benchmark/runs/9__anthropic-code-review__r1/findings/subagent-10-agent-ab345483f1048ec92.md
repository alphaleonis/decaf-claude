# subagent agent-ab345483f1048ec92

All six sub-claims are verified against the merged working tree. Here is my analysis:

**Sub-claim 1 — informer started before Run() returns from NewNodeManager: CONFIRMED.** `pkg/proxy/node.go:76-79` — `thisNodeInformerFactory.Start(wait.NeverStop)` then `WaitForNamedCacheSync(...)` inside `newNodeManager`. `NewNodeManager` is called in `newProxyServer` (server.go diff, `s.NodeManager, err = proxy.NewNodeManager(...)`), which runs long before `Run()`. So the shared node informer is started AND synced by the time `Run()` executes.

**Sub-claim 2 — handlers registered after AddEventHandler on the already-started informer: CONFIRMED.** `server.go:608-611`: `NewNodeConfig(ctx, s.NodeManager.NodeInformer(), ...)` and `NewNodeTopologyConfig(...)` each call `AddEventHandlerWithResyncPeriod` internally (config.go:288, 485), then `RegisterEventHandler(s.NodeManager)` (609) and `RegisterEventHandler(s.Proxier)` (611) append afterward. The informer is the same already-started one from NodeManager.

**Sub-claim 3 — async replay on the listener's own goroutine: CONFIRMED.** `shared_informer.go:697-721`: with `s.started == true`, the code takes `blockDeltas`, calls `addListener` (which starts `listener.run`/`listener.pop` goroutines because `listenersStarted` is true, line 833-836), then enqueues synthetic `addNotification{isInInitialList: true}` via `listener.add()` (line 719). `processorListener.add()` (line 1021) only pushes onto `p.addCh`; the actual `p.handler.OnAdd(...)` fires later in the free-running `run()` goroutine (line 1076). Delivery is asynchronous, on a separate goroutine, not synchronous within AddEventHandler.

**Sub-claim 4 — data race on the eventHandlers slice: CONFIRMED.** `NodeTopologyConfig` (config.go:465-470) has NO mutex (the only `mu` at line 370 belongs to `ServiceCIDRConfig`). `RegisterEventHandler` (509-511) does a bare `append`; `handleNodeEvent` (533) does a bare `for i := range n.eventHandlers`. The synthetic Add fires `AddFunc → handleNodeEvent` on the listener goroutine while the main goroutine executes `RegisterEventHandler(s.Proxier)` at server.go:611. The channel-send happens-before only covers state written before the enqueue (line 610); the append on line 611 has no happens-before edge to the range read — a genuine unsynchronized concurrent read/write.

**Sub-claim 5 — possible missed initial OnTopologyChange: CONFIRMED (timing-dependent, real).** If the listener goroutine runs `handleNodeEvent` before line 611, `n.eventHandlers` is empty: it sets `n.topologyLabels` to the zone (line 532) but notifies nobody. `NodeTopologyConfig` has no `Run()` method and is never started via `go ...Run()` in server.go, so the only delivery path is `handleNodeEvent`. On subsequent resyncs the `reflect.DeepEqual(n.topologyLabels, topologyLabels)` guard (line 528) short-circuits, so the proxier never receives the initial topology until a real zone-label change (rare) or restart.

**Sub-claim 6 — the ordering invariant comment was dropped for the node path: CONFIRMED.** The diff removes `// This has to start after the calls to NewNodeConfig because that must configure the shared informer event handler first.` plus `currentNodeInformerFactory.Start(wait.NeverStop)`. The analogous service-path invariant is still honored (server.go:601-603 starts the factory after NewServiceConfig+RegisterEventHandler), highlighting that the node path now violates it.

The finding's locations are all accurate (function-name anchors), and the code is introduced by this PR (in the diff), so no attribution correction is needed.

```json
{
  "finding": "#2",
  "verdict": "confirmed",
  "reason": "All sub-claims re-derived: newNodeManager starts+syncs the shared informer before Run() (node.go:76-79); AddEventHandlerWithResyncPeriod on an already-started informer (shared_informer.go:697-721) enqueues synthetic isInInitialList Adds delivered asynchronously on processorListener.run (line 1076); NodeTopologyConfig has no mutex, so its handleNodeEvent range-read of eventHandlers (config.go:533) races the unlocked append in RegisterEventHandler(s.Proxier) at server.go:611; and because handleNodeEvent sets topologyLabels then the reflect.DeepEqual guard (config.go:528) short-circuits later resyncs with no NodeTopologyConfig.Run() recovery path, an initial-topology delivery to the empty handler list is genuinely possible."
}
```
