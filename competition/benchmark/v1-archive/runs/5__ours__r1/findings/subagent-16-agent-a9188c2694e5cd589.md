# subagent agent-a9188c2694e5cd589

## Performance Review — PR #308517 "Support timing out hung streams"

Scope reviewed: `extensions/copilot/src/platform/networking/common/fetcherService.ts` (`withStreamIdleTimeout`), and its three call sites in `messagesApi.ts`, `responsesApi.ts`, `stream.ts` (`SSEProcessor.processSSEInner`).

### Cost model established from the code

- The `for await` loop in all three call sites iterates over **network-level read chunks** (`Uint8Array` buffers from `ReadableStreamDefaultReader.read()`), not per-token or per-SSE-event. `SSEProcessor.processSSEInner` and the two `*Api.ts` parsers each internally split one chunk into potentially many SSE `data:` lines/events — confirming the wrapped loop's iteration count is bounded by TCP/stream read granularity, not model output granularity. Typical streaming HTTP responses in this codebase produce on the order of tens to low hundreds of such chunks per chat turn.
- Confirmed via grep that `withStreamIdleTimeout` has exactly the three call sites named in the task — no hidden higher-frequency usage (e.g., embeddings/pagination loops).
- Per iteration, the added cost is: one `clearTimeout` (no-op first iteration) + one `setTimeout` (allocates one `Timeout` object, inserted into Node's timer list) before `await iterator.next()`, then one `clearTimeout` after it resolves. That's O(1) per chunk, not per-item-of-an-unbounded-collection multiplication — the timer is created and torn down before the next network wait begins, so at most one live timer per open stream at any instant, not one per chunk held concurrently.
- Additional async-generator indirection: chunks now pass through `withStreamIdleTimeout`'s manual `await iterator.next()` / `yield` instead of directly iterating `DestroyableStream`'s own generator. This adds one extra Promise/microtask hop per chunk (no `yield*` delegation used).

### Timer lifecycle check (leak/GC concern)

- Normal completion: `clearTimer()` runs immediately after `await iterator.next()` returns, before the value is yielded to the consumer — consumer processing time and downstream `parser.feed()` work is correctly excluded from the watchdog window (verified by the "slow consumer" test case).
- Early exit (`break`/`throw`/reject in consumer): the `finally` block runs (`for await...of` invokes the generator's `.return()`), which calls `clearTimer()` and awaits `iterator.return?.()`, propagating cleanup into `DestroyableStream`'s own generator (`reader.releaseLock()`). No path leaves a dangling `Timeout` referencing the stream after the loop exits.
- Timeout-fires case: callback sets `timedOut` and calls `stream.destroy().catch(() => {})` — a single one-shot action per hung stream, not a per-chunk repeated cost.

### Scale verdict

At realistic production chunk counts (tens–hundreds per streaming chat response, one live timer at a time, no cross-request accumulation), the added `setTimeout`/`clearTimeout` pair and the extra generator hop are O(1) constant-factor additions to a loop iteration that already does `JSON.parse`, string splitting, and telemetry work per chunk, and that is inherently I/O-bound (waiting on the network) between iterations. Node's timer subsystem is designed for exactly this create/cancel-per-await pattern and the marginal cost (microseconds) is dwarfed by the network wait and existing per-chunk parsing work. No unbounded growth, no cross-request state, no leak on any exit path (success, early break, or timeout).

No findings clear the anchor-75 bar for this persona.

```json
[]
```

## Considered But Not Flagged

- **Per-chunk `setTimeout`/`clearTimeout` pair (`fetcherService.ts` `withStreamIdleTimeout`, lines ~344-373)**: Real, provable per-chunk cost, but bounded to O(1) work per network-level chunk against a loop count (tens–hundreds per response) that is not unbounded, and dominated by the network I/O wait already inherent to the loop. Anchor 50 (cost is real but scale doesn't rise to a felt/measurable impact) — suppressed per persona threshold.
- **Extra async-generator indirection layer per chunk**: One additional Promise/microtask hop per chunk versus direct iteration of `DestroyableStream`. Same reasoning as above — bounded multiplier, I/O-dominated loop, no scale at which this becomes the bottleneck. Anchor 50 — suppressed.
- **Timer/closure allocation churn (GC)**: Each `startTimer` call allocates a new closure and a new `Timeout` object; old ones become garbage once cleared. This is standard, bounded per-request allocation (not retained across requests, no growth with dataset size) — not a memory-growth finding.
- **Fan-out to three call sites**: Verified via grep this is the only usage; no additional hot loops (e.g., embeddings/pagination) got the wrapper, so the blast radius matches the PR's stated intent (SSE streaming paths only).
- **Timer leak across early-exit/error paths**: Traced `finally` cleanup through both `withStreamIdleTimeout` and the underlying `DestroyableStream` generator; no path leaves a live timer or unreleased reader lock. Not a cost finding (would be a correctness/resource-leak finding if it existed, out of this persona's scope regardless).

### Probe Requests

None — no test removal/revert probe is needed here since there is no performance regression to falsify; the change is cost-negligible by static analysis of loop cardinality and timer lifecycle, not something a runtime probe would newly reveal.
