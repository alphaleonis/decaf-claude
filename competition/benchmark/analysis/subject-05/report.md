# Subject 5 — microsoft/vscode #308517 (typescript/medium): findings-quality analysis

**The subject, and why it is a trap.** The PR adds `withStreamIdleTimeout`, an SSE idle
watchdog that destroys the streaming body if no chunk arrives within 60s (2min for the first
chunk), wired into three Copilot API consumers. It was reverted the next day (#308779, regression
#308627: users saw "the response hit the length limit" with no actual output) because the watchdog
kills *live* streams — a 60s+ gap between network chunks is legitimate during active generation
(server-side tool calls, extended thinking, slow TTFT, OS suspend). The objective confirmation: the
eventual re-approach to the same hung-stream problem (#321671) is deliberately **observe-only** and
states verbatim "the stream is not aborted." That is the escaped bug: **actively aborting on an
over-aggressive idle timeout terminates legitimately-active streams.**

The trap: the code *looks* like the textbook idle-timeout anti-pattern, and a Copilot review bot on
an earlier commit flagged exactly the "timer measures consumer processing time" bug — but the author
**fixed all three of the bot's comments before merge**. The merged code clears the timer *before*
each `yield` (with a comment and a dedicated passing test), wraps `void stream.destroy().catch()`,
and forwards `await iterator.return?.()`. So the fixture's own one-line mechanism ("measures consumer
time") is *refuted by the merged diff*; the answer key was frozen on the objective reverted outcome,
with those three fixed anti-patterns encoded as false-positive traps.

**The headline result: the traps held.** Of 336 findings across 10 cells, exactly **one** fell for
the refuted consumer-time mechanism — an anthropic-code-review *validator* (of all things) that,
while "confirming" a design finding, asserted the timeout "measured consumer processing time... false
timeouts under slow consumers." That is the lone false positive in the subject (cluster c31, graded
FP at confidence 88). Every other tool read the `clearTimer()`-before-`yield` correctly: they
critiqued the empty `.catch` for lack of *observability* (not as an unhandled rejection), and they
flagged the reader-lock *test* as vacuous (correctly noting `iterator.return?.()` is present, the
test just doesn't verify it). On a subject engineered to bait pattern-matchers, the tools were, with
one exception, careful readers — the opposite of what the fixture's prose predicts.

**Primary recall was uneven — this subject splits the field.** Unlike subject 1's 10/10 sweep, the
false-timeout-kills-live-streams bug was caught by 8 of 10 cells: anthropic ×2, ours ×2, tag1 ×2 —
but only **one repeat each** for superpowers and pr-review-toolkit. superpowers r2 and prt r2 led
with config, test-quality, and error-classification findings and never asserted the core "60s aborts
a legitimately-active stream," so both score 1/2 on bug-catch. A sharper miss hides inside a nominal
hit: pr-review-toolkit *did* find the primary in r1, but rated it **low / design** ("a tuning risk")
— its severity calibration on this subject is 0.20, meaning its critical/high band is almost all
non-substantive (it stamped *critical* on "the timeout error is never logged" while burying the
actual reverted bug at low). anthropic, by contrast, led with it at critical/high in both reps
(severity calibration 1.0) and — via its historical-git and prior-feedback agents — cited the revert
PR and issue numbers directly.

**ours earned the subject's only unique-true findings.** ours was the sole tool to surface two
distinct, diff-verifiable defects nobody else found: the **isFirstChunk collapse** (c2, valid-other,
judged high) — an early administrative/empty CAPI chunk flips `isFirstChunk=false`, collapsing the
2-minute TTFT budget to the 60s idle timeout, so a reasoning model silent >60s after that chunk is
killed — and the **terminal-event-then-hang** case (c10, valid-other) — messagesApi/responsesApi
never return on `message_stop`/`response.completed` (unlike stream.ts's `[DONE]`), so a server that
completes then hangs before closing gets its already-complete response discarded by the watchdog.
Both are concrete mechanisms that *compound* the primary, and both are the kind of finding a
fan-out with an adversarial persona is built to produce. ours also carried a clean valid-other layer
(reader.cancel-rejects skipping the typed throw; telemetry-as-`cancel`) and, notably, **zero false
positives** across 84 findings.

**A rich, largely-shared valid-other layer.** Beyond the primary, seven clusters graded valid-other,
and they are genuinely good: the **reader.cancel-rejects** edge (c4 — if the cancelled read rejects
instead of resolving `{done:true}`, the post-loop `if (timedOut) throw` is skipped and the caller
sees a raw error, not the typed one; found by prt, tag1, ours-as-doc), **telemetry-as-`cancel`**
(c6 — the watchdog kill is indistinguishable from a user cancellation, so its own false-positive
rate is unmeasurable; prescient, since the real fix was *entirely about measuring*), the **same-tick
race** (c11), and the **vacuous reader-lock test** (c13). Inter-tool Jaccard over valid clusters is
low (0.2–0.67), and pr-review-toolkit/tag1 are the most redundant pair (0.67) — the two verbose
tools converge on the same test-and-type-design surface.

**Noise and cost.** The verbose tools paid the usual tax: pr-review-toolkit 11.0 and tag1 10.5
trivia clusters per cell (precision 0.20–0.21), dominated by an unbounded "add more tests" surface
(integration coverage, empty-stream controls, boundary tests, instanceof-vs-name) and a large
type-design bundle (expose `timeoutMs` as a field, narrow the `AsyncGenerator<T>` return type). Much
of it is true-but-low-value or pre-existing/out-of-scope (other unwrapped SSE consumers, the
slow-drip no-cap case). ours ran 6.5 trivia/cell — better, and its trivia skews toward
knowledge-preservation (document the liveness invariant, why 60s) rather than taste. superpowers was
the cleanest (2.0 trivia/cell) but that thrift cost it the primary in r2. On cost: superpowers
$2.03/cell, prt $7.01, anthropic $8.76, tag1 $16.38, and ours $24.02 — the most expensive by far, on
a vscode-scale repo. Cost-per-bug-caught: superpowers $4.06 (1/2 hit), anthropic $8.76, prt $14.03
(1/2), tag1 $16.38, ours $24.02.

**Subagent economics.** Distinctness rose vs subject 1 (anthropic 0.35, tag1 0.32, ours/prt 0.20)
because the finding space here is wide, and ours' fan-out *did* earn its agents: its adversarial and
consistency personas produced the two unique-true catches (isFirstChunk, terminal-event, plus the
completions-core twin) that no single-agent or leaner tool found. This is the clearest subject so far
where the expensive fan-out bought something real — two genuine defects — rather than just
corroboration.

**Cost–quality verdict.** No tool is strictly dominant here. anthropic is the value pick: caught the
primary at correct severity in both reps, cited the revert, 1.0 calibration, one lone validator FP,
at $8.76. ours is the depth pick: only tool to find isFirstChunk and terminal-event-hang, zero FPs,
best knowledge-layer — but at 2.7× anthropic's cost and with noisier severity (calibration 0.57).
superpowers is cheap and clean but unreliable (1/2 primary). pr-review-toolkit and tag1 caught the
substance but drowned it: prt in particular found the primary and then mis-ranked it below a logging
nit, which on a real PR would bury the one finding that mattered.

**Caveats (this subject leans on judgment more than subject 1).** (1) The escaped bug's *mechanism*
is subtle and the fixture's stated mechanism is wrong for the merged code; the answer key was rebuilt
on the objective reverted outcome (verified against the revert, the regression issue, and the
observe-only re-approach #321671), and every TP-primary and FP verdict should be spot-checked against
that reframing. (2) **One grader verdict was human-overridden**: c14 ("tests don't assert teardown")
was graded false-positive because the cluster summary's "would still pass" phrasing is imprecise
(removing `destroy()` makes the tests *hang*, not pass) — but the underlying findings are a real
valid-minor test gap (no explicit teardown/timer-clear assertion), so it was regraded valid-minor;
this is logged. (3) Several trivia calls are borderline valid-minor and were defaulted down per the
rubric: c5 (the new StreamIdleTimeoutError flows out unclassified → generic error / no retry — real
gap, but the specific "firewall message via fetcherId" mechanism several tools asserted is *refuted*,
so the cluster is contaminated), c25 (undocumented liveness invariant), c26 (JSDoc-on-class), c28
(raceTimeout helper — exists but doesn't cleanly fit the per-chunk reset). (4) human_issues is empty
(bot-only PR), so there are no TP-human opportunities and the whole grade rests on primary recall +
FP discipline + valid-other yield. (5) Contamination: anthropic's historical-git and prior-feedback
agents demonstrably retrieved the revert/issue from GitHub, so its primary "catch" partly reflects
retrieval — and, ironically, the same retrieval channel produced the one consumer-time false positive
(parroting the bot's earlier-commit comment without re-verifying it against the merged code).
