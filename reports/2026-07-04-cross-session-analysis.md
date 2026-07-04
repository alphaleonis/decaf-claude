# Cross-Session Analysis — Review-Loop Corpus (4 sessions, through 2026-07-04)

Synthesis across the four session reports collected on this branch. Its job is the thing a single
report can't do: decide whether the patterns the individual reports flagged **recur**, and re-score
the tuning candidates parked in nib `#dcc-unre` against the fuller sample now that its gate
("hold until 2+ more session reports accumulate") is met.

Truth discipline follows `conventions/session-report.md`: harness-reported figures are quoted
verbatim; anything derived is labeled `[Inference]`, `[Estimate]`, or `[Unverified]`. Every number
here traces to one of the four session READMEs.

## The corpus

| | sn96 | 5a8k | p07b | qj7m |
|---|---|---|---|---|
| Date | 2026-07-03 | 2026-07-04 | 2026-07-04 | 2026-07-04 |
| Change character | Go bug fix (logic) | Svelte/Tailwind, declarative | Svelte non-modal panel (interaction/a11y, subtle) | Svelte radio-group generalize (small declarative) |
| Driver | `auto-tdd` | `auto-dev` | `auto-dev` | `auto-dev` |
| Iterations / rosters | 3 × uncapped `mid` | `mid9→mid6→mid3` | `mid9→mid6` | `mid9` (1) |
| Final verdict | merged green | APPROVED | APPROVED | APPROVED |
| Manual interventions | **3 resume, 2 nudge, 1 kill** | 0 | 0 | 0 |
| Review-child token data | [Estimate] | [Estimate] | **measured** | **measured** |
| Tuning role | "before" | "after" #1 | "after" #2 | "after" #3 |

sn96 is pre-tuning; 5a8k / p07b / qj7m all ran on the tuned skills (`dcc-n87o` synchronous waves,
`dcc-n7bm` capped re-review, `dcc-6yi4` fix-round boundary/least-invasive, `dcc-8tbb` shared
pre-flight gates). p07b and qj7m additionally ran with the `--report` automation (`dcc-gdof`), so
their per-reviewer/validator tokens are **measured**, not estimated — a first for the corpus.

## 1. What decisively held

- **`dcc-n87o` (synchronous waves) — 3/3 clean.** No premature "standing by" returns, no
  broken-reply broadcast, **zero manual nudges** in 5a8k, p07b, or qj7m. The single worst sn96
  failure mode (3 resumes + 2 nudges + 1 kill) has not recurred in any post-tuning session. This is
  the strongest confirmation in the corpus.
- **`dcc-n7bm` (capped re-review) — natural ablation clean every time.** 5a8k dropped
  knowledge/consistency/spec/typescript across rounds 2–3; p07b dropped knowledge/consistency/spec
  in `mid6`. In no session did a dropped lane later prove to hold missed evidence. The correctness
  cost of capping remains **zero** across the sample.
- **Validation wave — earns its slot, 4/4.** It refuted a wrong finding in **2 of 4** sessions
  (sn96's ordering-docs item; **p07b's focus-theft High**, refuted by tracing the installed Svelte
  5.55.0 scheduler — a prevented over-fix that would otherwise have driven an unnecessary behavioral
  change), and confirmed cleanly (with an empirical reproduction) in the other two. No autonomous fix
  ever rode on an unvalidated finding.
- **The floor holds — evidence against shrinking it.** quick-reviewer across the four sessions:
  dry (sn96) → **headline bug** (5a8k `cn()` silent no-op) → **co-drove the Escape High** (p07b) →
  corroboration only (qj7m). It drove a verdict in 2 of 4; sn96's "dry all session" is not
  representative. test-reviewer is the standout **unique** finder in every session with tests
  present (5a8k 6/6 + 4/4; p07b 5/5 + sole finder of the iter-2 Medium; qj7m 2/2 unique).

## 2. Token accounting — now measured, three things become visible

The `--report` automation gives p07b/qj7m measured review-child tokens. Comparing measured to the
earlier estimates:

1. **The earlier estimates were conservative.** Measured per-reviewer cost runs ~57k–158k
   (qj7m reviewers 57,031–103,362; p07b iter-2 broad **157,648**, quick 131,733), above the old
   `[Estimate]` band of 40k–90k. A single `mid9`-class wave measures ~750k–1M in reviewers+validators
   alone (qj7m: **749,637** for 7 reviewers + 3 validators). 5a8k's `[Estimate]` all-in ~1.3M–2.4M
   was, if anything, a floor.
2. **A roster-*count* cap is not a proportional *token* cap.** `[Inference]` p07b went 9→6 reviewers
   (`mid9`→`mid6`) but the measured subtotal fell only 997,765 → 791,209 (~21%, not ~33%) — the
   surviving reviewers ran *heavier* on the re-review (broad 120,719 → 157,648). The cap's value is
   **correctness** (nothing missed) more than linear cost savings.
3. **Review still dwarfs build by roughly an order of magnitude.** Metered build : measured
   reviewers+validators = **1 : 10.6** (p07b, 169,212 : 1,788,974) and **1 : 12.4** (qj7m,
   60,565 : 749,637).

⚠️ **Cross-session ratio caveat.** These bases are not identical. p07b/qj7m ratios are
*metered-build : measured-reviewers+validators* — build **excludes** the unmetered inline
post-approval fix passes; review **excludes** orchestrators (300,128 / 141,284, children-inclusion
`[Unverified]`). sn96/5a8k ratios were *reported-build : reported-orchestrators*. Treat the ratios as
directional. The one robust cross-session constant: **review-side dominates cost by ~10×**, now
measured in two sessions rather than only estimated.

- **Named waste:** p07b's two adversarial stub dispatches burned **66,789** tokens (32,895 + 33,894)
  for zero findings (see §4).

## 3. The four parked candidates, re-scored

| # | Candidate | Recurrence across the 4 sessions | Verdict |
|---|---|---|---|
| 1 | Fix-added tests must prove they can fail | **4 of 5 re-reviewed fix rounds introduced a fresh reviewable defect** (sn96 1/2 — the iter-3 charset regression; 5a8k 2/2; p07b 1/1). **2 were specifically bad fix-added tests**: 5a8k's false-positive `cn()` test, p07b's `try/finally` test leak | **Strengthened → act** |
| 2 | Family-sweep rule (vendored primitives) | Only 5a8k (`ui/dropdown-menu/*` whack-a-mole across 3 rounds). p07b and qj7m show nothing comparable | **Still sample-of-1 → keep parked** |
| 3 | Post-APPROVED bounded fix pass | **4 of 4 sessions applied fixes *after* an APPROVED / merge-clean verdict**; **3 of 4 did it inline in main context, unmetered** (5a8k iter-3, p07b iter-2, qj7m). Not always "trivial Low residual" — qj7m applied 3 Mediums intrinsic to the deliverable | **Strongly strengthened → act + broaden** |
| 4 | Record pre-flight gates in report header | qj7m surfaced a deeper hole: pre-flight ran tests but **not build/lint** (filed `nibs-k3zb`) — recording alone won't close it | **Strengthened + expand scope → act** |

**Candidate #3 is the headline cross-session finding.** "APPROVED = done" is contradicted by observed
behavior in *every* session — it's the norm, not an edge case, and the skill has no in-loop lane for
it. Because the pass runs inline it is also **invisible to the token accounting** in 3 of 4 sessions,
so encoding it (a bounded, metered "APPROVED-with-residual → optional fix pass + re-verify gate"
branch) fixes both a process-fidelity gap and a measurement blind spot at once. The broadening the
new samples force: scope it to *deliverable-intrinsic* findings (qj7m's 3 Mediums for a "reusable
primitive" deliverable), not only mechanical Lows.

## 4. New signal, not in the parked set — adversarial-reviewer dispatch failure (p07b)

adversarial-reviewer **failed its first dispatch in *both* p07b iterations** — a 0-tool-call
memory-context-only stub (~2.4s) in iter 1, and in iter 2 an output **containing an injection-looking
"enable more verbose responses" verbosity-toggle string** (0 tool calls, ~5.5s). Both recovered via a
hardened re-dispatch, but burned ~66.8k tokens for zero findings. It ran cleanly in sn96 and 5a8k, so
this is p07b-local — but two-for-two in one session is a pattern, and the iter-2 payload resembling an
injected instruction warrants a closer look at whether it is a prompt-construction defect in that
agent or genuinely injected content. `[Unverified]` root cause — this needs investigation, not a
tuning knob. Spun out as its own nib, `dcc-jxya`.

## 5. Recommendation

The gate on `#dcc-unre` is met. Disposition:

- **Act now (strong, recurring evidence):**
  - **#1** — fix-added-tests-must-fail. Top defect source in the corpus; move the mutation/guard check
    to fix time so a fix round can't add a green-but-worthless test.
  - **#3** — bring the post-approval pass in-loop and metered; broaden framing to
    deliverable-intrinsic findings.
- **Act, cheap + expanded:** **#4** — record the pre-flight line *and* make pre-flight run the full
  build/lint/test gate (qj7m proved recording alone is insufficient).
- **Keep parked:** **#2** — family-sweep, still a sample of one.
- **New, separate track:** investigate the adversarial-reviewer dispatch reliability + the
  injection-looking payload.

All skill changes land on `main`; this branch stays reports + tuning notes.

## 6. Honest limits

- **All three post-tuning sessions are Svelte/TypeScript web-UI.** The corpus still says almost
  nothing about the loop on logic- or data-heavy changes since sn96 (the only non-UI session, and the
  pre-tuning one). Generalization beyond interaction/declarative UI is unproven.
- **The measured cost sessions ran small, subtle (p07b) or small, declarative (qj7m) diffs.** The
  favorable build:review picture still leans partly on easy-to-review changesets, not only on capping.
- **Sample size is four**, one of them pre-tuning. The `#dcc-unre` "wait for more" instinct was right
  once already (quick-reviewer dry in sn96, then found 5a8k's headline). Keep accumulating before
  treating any single-session signal (e.g. the family-sweep, or the adversarial failure) as settled.
