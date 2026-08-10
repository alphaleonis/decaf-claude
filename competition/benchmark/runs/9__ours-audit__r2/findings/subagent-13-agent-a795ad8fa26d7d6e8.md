# subagent agent-a795ad8fa26d7d6e8

I have enough to finalize. Key structural facts confirmed: `n.node` is always a shared informer/lister object (from `nodeLister.Get` at construction and the raw `node` param in `OnNodeChange`), `Node()` deep-copies out but `PodCIDRs()` does not, and current callers only read `s.podCIDRs`.

## Go idiom review — PR #130837

```json
[
  {
    "file": "pkg/proxy/node.go",
    "line": 131,
    "severity": "Medium",
    "category": "other",
    "issue": "[GO_MEMORY_MODEL] PodCIDRs() returns n.node.Spec.PodCIDRs directly, aliasing the backing array of a shared informer/lister object. n.node is never deep-copied on the way in (it is the shared object from nodeLister.Get() at construction and the raw *v1.Node handed to OnNodeChange). Node() deep-copies precisely to honor the client-go 'never mutate shared cache objects' contract; PodCIDRs() (and to a lesser degree the stored node) breaks that contract asymmetrically. A caller that append()s or mutates the returned slice would corrupt the shared informer cache seen by every other consumer in the process.",
    "fix": "Return a copy: append([]string(nil), n.node.Spec.PodCIDRs...). Same treatment for any accessor exposing shared-object internals; keep the deep-copy discipline consistent with Node().",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 76,
    "severity": "Low",
    "category": "async",
    "issue": "[GO_CONTEXT] The node informer factory is started with wait.NeverStop, ignoring the passed ctx. The informer's goroutines are not tied to ctx.Done(), so on context cancellation (kube-proxy shutdown) they keep running. Impact is low because NodeManager is a process-lifetime singleton, but the idiomatic wiring is Start(ctx.Done()) so the watch/reflector goroutines stop with the context.",
    "fix": "Start the factory with ctx.Done() instead of wait.NeverStop so informer goroutines are bound to the manager's context lifecycle.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 154,
    "severity": "Low",
    "category": "resource-management",
    "issue": "[GO_DEFER] Exit path uses klog.Flush() followed by n.exitFunc(1) (os.Exit in prod) in OnNodeChange (x2) and OnNodeDelete, rather than klog.FlushAndExit(klog.ExitFlushTimeout, 1) which the removed NodePodCIDRHandler used. os.Exit bypasses all deferred cleanup, and plain Flush()+Exit is not the sanctioned klog exit sequence (FlushAndExit flushes with a bounded timeout then exits atomically). Low risk of dropped log lines on crash-exit.",
    "fix": "Replace klog.Flush() + n.exitFunc(1) with the klog-idiomatic exit; if exitFunc must stay injectable for tests, have the production exitFunc itself call klog.FlushAndExit(klog.ExitFlushTimeout, code).",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`pollErr` vs `err` returning a nil error on timeout (open thread #31)** — Not a bug. `wait.PollUntilContextCancel(ctx, interval, immediate=true, cond)` runs `cond` once *before* any ctx.Done() check (see `loopConditionUntilContext`), so even an already-expired ctx executes the condition at least once. Every `return false` branch in the condition assigns a non-nil `err`, and the only `return true` branch makes `pollErr` nil. Therefore `pollErr != nil && err == nil` is unreachable, and `return nil, err` cannot hand the caller a `(nil, nil)` that would nil-deref at `s.NodeManager.NodeIPs()`. Safe *because of* `immediate=true`; fragile if that flag ever flips to false.

- **`context.WithTimeout` + `defer cancel()` shadowing in newNodeManager (line 85)** — No leak, no effect on the returned informer. `cancel()` runs at function return; the poll has already completed by then. The informer was started with `wait.NeverStop`, not this ctx, so cancel does not touch it. The shadowing is cosmetic.

- **Lock discipline in OnNodeChange** — Correct. All shared-field access (`oldNodeIPs`, `oldPodCIDRs`, `n.node = node`) is inside the `mu` critical section; everything after unlock touches only the `node` parameter and locals. `n.watchPodCIDRs`/`n.exitFunc` are write-once at construction. `OnNodeChange` is only driven by the single-threaded informer delivery goroutine, so no self-concurrency.

- **NodeEligible() holds hs.lock then acquires nodeManager.mu (proxy_health.go)** — No lock-order inversion (nodeManager methods never call back into the health server), so no deadlock. Minor smell only: it takes the exclusive `hs.lock.Lock()` though it no longer mutates any hs field (a RLock or no lock would do) — a style/efficiency point, not a correctness defect, out of my lane.

- **NodeConfig registers only UpdateFunc/DeleteFunc (no AddFunc) — config.go** — Narrow, low-confidence (~25). When `OnNodeChange` is registered on the already-started informer, the replayed current-store object arrives as an Add and is dropped. Because `newNodeManager` already captured the node via polling, dropping the initial Add is deliberate and normally harmless. There is a tiny window where a NodeIP/PodCIDR change occurring between the poll and handler registration is delivered only as that replayed Add (dropped) and never re-observed unless the object changes again — but this is a design choice on informer replay semantics, not a clear defect.

- **Continue-after-exit in OnNodeChange** — After the PodCIDR-change `n.exitFunc(1)`, control falls through to the NodeIPs check. In production `os.Exit` never returns so this is moot; in tests the injected `exitFunc` returns and a second `exitFunc(1)` may fire. Test-only behavior, no production consequence.

- **NodeManager nil-deref via health server** — `NewProxyHealthServer` is called in `newProxyServer` only after the `NewNodeManager` error check, so `s.NodeManager` is non-nil there; `Run()` guards node-config wiring with `if s.NodeManager != nil`. Hollow-proxy does not build this health server path. No reachable nil-manager deref in `NodeEligible()` from the changed code.

### Probe Requests
None. Findings are grounded in source read from disk; no working-tree mutation needed to demonstrate them.
