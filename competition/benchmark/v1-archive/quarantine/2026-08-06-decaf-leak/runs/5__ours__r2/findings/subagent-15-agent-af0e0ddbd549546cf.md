# subagent agent-af0e0ddbd549546cf

## Verification Summary

I read the actual post-merge code and traced the wiring at all three call sites.

**Doc comment content (lines 299-310):**
```
/**
 * How long to wait (ms) for the first SSE chunk. The model's TTFT is often longer
 * than the subsequent chunks so we give it slightly more time.
 */
export const SSE_FIRST_CHUNK_TIMEOUT_MS = 2 * 60 * 1000;

/**
 * How long to wait (ms) between subsequent SSE chunks once streaming has
 * started. Once the model is actively streaming, gaps this long indicate
 * a hung connection.
 */
export const SSE_IDLE_TIMEOUT_MS = 60 * 1000;
```
Neither comment records why 60s/2min were chosen, nor states the liveness invariant. Citation `fetcherService.ts:305-310` is exact.

**Raw-chunk vs. SSE-parsed claim — verified true.** `Response.body: DestroyableStream<Uint8Array>` (fetcherService.ts:79). All three wiring sites (`stream.ts:323`, `messagesApi.ts:596`, `responsesApi.ts:537`) call `withStreamIdleTimeout(response.body)`/`(this.body)` and only *afterward* pass the raw chunk into SSE parsing (`splitChunk`/`SSEParser`/`parser.feed`). In `stream.ts`, SSE comment lines are explicitly discarded post-parse (`if (dataLine.startsWith(':')) continue;` at line 336) — but by then the raw bytes carrying that comment already reset the watchdog timer inside the `for await (... withStreamIdleTimeout ...)` loop. So the finding's core technical claim — the watchdog resets on any transport bytes, including SSE keepalive/comment lines that get thrown away at parse time — holds.

**No config lever** — confirmed: both constants are hardcoded module-level `const`s with no experimentation/configuration-service read anywhere in the file or its usages.

**Attribution** — confirmed not pre-existing; the entire block (constants, doc comments, `withStreamIdleTimeout`) is new in this diff (`git show --stat ba8d730b` shows `fetcherService.ts` net `+78` lines, all in this hunk).

**Test coverage gap** — `streamIdleTimeout.spec.ts` has no test exercising SSE comment/keepalive lines resetting the timer, and records no rationale for the constants either.

**One caveat.** The finding asserts "the rationale lives only in an inaccessible internal issue (vscode-internalbacklog#7390)." I searched the full diff (`/tmp/pr308517.diff`) and the repo for "7390"/"internalbacklog" and found zero hits — nothing in this changeset references such an issue. This specific detail is unverifiable from any evidence available to me and reads as a fabricated/hallucinated embellishment by the reviewer rather than something derivable from the PR. It doesn't change the substance of the finding (missing rationale, missing invariant documentation), which I independently re-derived from the code itself, but it's a fabricated citation that should not be repeated verbatim to the developer.

```json
{
  "finding": "#1",
  "verdict": "confirmed",
  "reason": "Doc comments at fetcherService.ts:299-310 genuinely omit both the rationale for the 60s/2min values and the liveness invariant; independently traced that withStreamIdleTimeout wraps the raw Uint8Array transport stream (Response.body) at all three sites (stream.ts:323, messagesApi.ts:596, responsesApi.ts:537), resetting the timer before SSE comment/keepalive lines are discarded during parsing, and the constants are hardcoded consts with no config lever. Note: the finding's claim of an 'inaccessible internal issue (vscode-internalbacklog#7390)' has zero support in the diff or repo and appears fabricated — it should be dropped from the writeup, but it doesn't affect the independently-verified core claim.",
  "corrections": {
    "pre_existing": false
  }
}
```
