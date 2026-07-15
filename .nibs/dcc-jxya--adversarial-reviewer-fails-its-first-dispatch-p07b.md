---
# dcc-jxya
version: 1
title: 'adversarial-reviewer fails its first dispatch (p07b: 2/2 stubs, one injection-looking payload)'
status: todo
type: bug
priority: normal
created_at: 2026-07-04T18:25:45Z
updated_at: 2026-07-15T15:42:01Z
order: z
---

## Description

During the p07b code-review session (`reports/2026-07-04-nibs-p07b-code-review-session`), the
`decaf-quality:adversarial-reviewer` agent **failed its first dispatch in BOTH iterations** and had
to be re-dispatched with a hardened prompt each time. Surfaced by cross-session analysis as a new
signal not covered by the parked tuning candidates in #dcc-unre. It ran cleanly in the sn96 and 5a8k
sessions, so this is p07b-local — but two-for-two within one session is a pattern, not noise, and one
of the two failures emitted an injection-looking payload that warrants a closer look.

## Steps to Reproduce

Not yet reliably reproducible — observed twice in one live session. Dispatch
`decaf-quality:adversarial-reviewer` as part of a `mid`/`mid6` review wave (p07b changeset:
interaction/a11y-heavy Svelte non-modal panel, >50 executable lines so adversarial is gated in).

## Expected vs Actual

- **Expected:** adversarial-reviewer reads the changeset, runs tools, returns a findings report.
- **Actual (iter 1):** a memory-context-only **stub** — 0 tool calls, ~2.4s, zero findings.
- **Actual (iter 2):** corrupted output **containing an injection-looking "enable more verbose
  responses" verbosity-toggle string** — 0 tool calls, ~5.5s, zero findings.
- Both recovered via re-dispatch with a hardened prompt. Cost: ~66,789 wasted tokens
  (32,895 + 33,894) and a full re-dispatch each, extending both review waves.

## Root Cause

`[Unverified]`. Open question: is this a prompt-construction defect in adversarial-reviewer (e.g. a
malformed/oversized prompt that trips a fast no-op return), or genuinely injected content reaching the
agent? The iter-2 payload resembling an injected instruction ("enable more verbose responses") is the
part that most needs scrutiny.

## Verification

- [ ] Reproduce or rule out (re-run adversarial-reviewer against the p07b-style changeset)
- [ ] Determine whether the injection-looking iter-2 string is agent-generated or injected input
- [ ] Decide on a fix: prompt hardening, a dispatch retry/guard, or an input-sanitization step
- [ ] Watch subsequent session reports for recurrence before treating as settled (sample of one session)

Evidence: `reports/2026-07-04-nibs-p07b-code-review-session/README.md` §4 (flagged there as the
session's highest-value signal) and `reports/2026-07-04-cross-session-analysis.md` §4.


## Recurrence watch — updated 2026-07-15

Five code-review sessions have run since p07b. The jxya signature — a silent stub or an injection-looking payload on first dispatch, 0 tool calls — has **not** recurred in any of them:

- **2026-07-05** (0xng, bpyh, e9oz, k3zb) — all four record `Review-tool anomalies: none reported by /code-review`.
- **2026-07-14** (batch-buffer-safety, 7 review waves) — `adversarial-reviewer` DID fail a first dispatch (fa69 i2) and was re-dispatched, but on a **server-side 529**. The report distinguishes it explicitly: "Related to `dcc-jxya` (adversarial-reviewer dispatch failures, p07b) but a different cause — transient API error, not payload rejection." The retry completed and its report was used. Not a recurrence of this bug.

**Reading:** the evidence now leans p07b-local, which is what the last verification item asked to watch for. This does **not** close the nib — the root cause is still `[Unverified]`, there is still no reproduction, and 2-for-2 within a single session remains unexplained. But the case for treating this as a live, general defect has weakened, and both anomalies actually seen since are unrelated (the 529 above; an orchestrator fabricating a report section, 07-14). If the next couple of sessions stay clean, `deferred` (parked) is more honest than carrying it as an open bug.

**Instrumentation note:** `conventions/session-report.md` carries an **Anomalies** field (`dispatch retries, unusable returns, injected-content flags — or "none"`), added in `1d85efe` on 2026-07-04 at 15:10 UTC — about 3h before this nib was filed. Every session since has reported against it, which is why this watch has clean data rather than silence. Keep it as the recurrence signal.
