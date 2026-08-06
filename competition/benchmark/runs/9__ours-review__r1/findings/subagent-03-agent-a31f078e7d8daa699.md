# subagent agent-a31f078e7d8daa699

```json
{
  "finding": "#NodeConfig-AddFunc-missing",
  "verdict": "confirmed",
  "reason": "Verified mechanically. config.go:288-294 registers only UpdateFunc/DeleteFunc (no AddFunc). Ordering is confirmed: NewNodeManager (pkg/proxy/node.go:76-79) starts the shared informer factory and calls cache.WaitForNamedCacheSync during newProxyServer construction (server.go:211), while NewNodeConfig + RegisterEventHandler(s.NodeManager) run later inside Run() (server.go:608-609). client-go's AddEventHandlerWithOptions (staging/.../shared_informer.go:697-721) explicitly handles this case: when a handler is added to an already-started informer, it lists the indexer and sends 'synthetic Add events' (comment at line 704) via listener.add(addNotification{...}), which dispatch through handler.OnAdd — a no-op here since AddFunc is nil. So the claimed mechanism is real: any Node state present in cache at NodeConfig-registration time is silently dropped instead of reaching OnNodeChange. However, this is NOT a permanent/critical failure as broad-reviewer's severity implies. Two mitigating facts refute the 'Critical/never invoked' framing: (1) NodeManager.node's baseline is already set from NewNodeManager's own poll (node.go:81-104), not from any Add event, so the dropped replay-Add is only consequential if the Node object changed in the narrow window between that poll and NodeConfig's later registration in Run(); (2) processDeltas (controller.go:565-577) shows periodic resync ('Sync' delta type) hits the 'exists' branch and calls handler.OnUpdate, i.e. UpdateFunc IS invoked periodically — the resync period passed to AddEventHandlerWithResyncPeriod is ConfigSyncPeriod (server.go:608), default 15 minutes (defaults.go:123), so any state missed in the startup race window is caught and OnNodeChange fires within one ConfigSyncPeriod. Net effect: a real but narrow-window, self-bounded gap (missed detection only for a change landing in the startup race window, surfaced within ≤ConfigSyncPeriod via resync), not a permanently broken crash-safety mechanism. Severity should be Medium (matching adversarial-reviewer), not Critical/High — design-reviewer's 'self-healing' dismissal is directionally correct but understates that a real, if bounded, detection gap exists.",
  "corrections": {
    "pre_existing": false
  }
}
```
