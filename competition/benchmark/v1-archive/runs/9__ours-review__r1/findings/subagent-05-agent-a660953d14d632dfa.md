# subagent agent-a660953d14d632dfa

Based on my analysis of the code, I can now verify this finding.

**Key evidence:**

1. **Informer is genuinely started+synced before Run():**
   - `NewNodeManager()` is called at line 211 in `server.go` during `newProxyServer()`
   - Inside `NewNodeManager()`, lines 76-77 of `node.go` call `Start(wait.NeverStop)` and `WaitForNamedCacheSync()`
   - The informer is synced and running when `NewNodeManager()` returns
   - `Run()` is called separately, after `newProxyServer()` completes

2. **Handlers are registered after the informer is running:**
   - Lines 608-611 of `server.go` show handlers registered AFTER the informer is running
   - This directly violates the documented invariant at lines 579-581: "RegisterHandler() calls need to happen before creation of Sources...initial update may be lost if no handlers are registered yet."
   - By contrast, ServiceConfig/EndpointSliceConfig follow the correct pattern (handlers before factory Start at lines 603-604)

3. **Data race on eventHandlers slice is real:**
   - `config.go:510` does unsynchronized append: `n.eventHandlers = append(...)`
   - `config.go:533` does unsynchronized iteration: `for i := range n.eventHandlers`
   - The listener goroutine (started by `AddEventHandlerWithResyncPeriod`) and main goroutine are unsynchronized

4. **Logic race for initial topology drop is real:**
   - When `NewNodeTopologyConfig()` calls `AddEventHandlerWithResyncPeriod()` on an already-synced informer, client-go's shared_informer.go lines 706-721 show it enqueues synthetic Add notifications and starts listener goroutines
   - If the listener goroutine processes the synthetic Add (calling `handleNodeEvent`) before line 611's `RegisterEventHandler()` completes, the Proxier handler isn't registered yet
   - `handleNodeEvent` at line 533 iterates eventHandlers (which is still empty), so `OnTopologyChange` is never called for the Proxier
   - Because line 528-530 skips calling handlers if topology labels haven't changed, a subsequent resync may not replay this

**Severity assessment:** The finding correctly identifies a High severity issue. This affects topology-aware routing behavior critical for multi-zone clusters. However, it's not universally Critical because: (a) the bug manifests only under specific timing conditions, (b) a resync or label change may eventually deliver the event, and (c) it requires the exact race-condition timing between handler registration and event processing.

```json
{
  "finding": "#1",
  "verdict": "confirmed",
  "reason": "The node informer is genuinely started and synced in NewNodeManager (node.go:76-77) before Run() is called. When Run() registers handlers on lines 608-611, the already-running informer replays cached objects, causing concurrent access to the unprotected eventHandlers slice (data race at config.go:510 vs 533). The listener goroutine processing the synthetic Add event can call handleNodeEvent before RegisterEventHandler completes, causing the Proxier handler to miss the initial topology change — contradicting the documented invariant at server.go:579-581.",
  "corrections": {}
}
```
