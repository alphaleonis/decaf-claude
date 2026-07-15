# Review-Loop Session Reports (tuning corpus)

This directory (on the `tuning` branch, deliberately kept off `main`) collects **session
reports** from runs of the decaf review loop (`auto-tdd`/`auto-dev` →
`auto-code-review` → `code-review`) in real projects. Each report is a self-contained,
comparison-grade record of one run: iteration overview, agent inventory, token accounting
(harness figures verbatim, estimates labeled), process observations, timeline, and per-agent
yield. The corpus is the evidence base for tuning the skills — changes are made on `main`,
their effect shows up in the next reports here.

## Contents

| Report | Session | Role in the story |
|--------|---------|-------------------|
| `2026-07-03-nibs-sn96-code-review-session/` | Go bug fix (`nibs` repo), `auto-tdd`, 3 × uncapped `mid` | The **"before"** picture — surfaced the structural failures |
| `2026-07-04-nibs-5a8k-code-review-session/` | Svelte/Tailwind web-UI refactor (`nibs` repo), `auto-dev` | The **"after"** picture — first run on the tuned skills |
| `2026-07-04-nibs-p07b-code-review-session/` | Svelte non-modal panel re-implementation (interaction/a11y-heavy), `auto-dev` | "After" #2 — first run with **measured** review-child tokens (`--report`); caught a real Escape regression, refuted an over-fix |
| `2026-07-04-nibs-qj7m-code-review-session/` | Svelte radio-group generalization (small declarative), `auto-dev` | "After" #3 — measured tokens; clean small refactor, 3 Medium evolution-readiness catches |
| `2026-07-04-cross-session-analysis.md` | Synthesis across all four sessions | Re-scores the parked tuning candidates once `dcc-unre`'s "wait for 2+ more reports" gate is met |
| `2026-07-14-nibs-batch-buffer-safety-code-review-session/` | **First `batch-dev` session** — 3 nibs (2 Svelte/TS + 1 Go), 7 waves, no `--report` | **New defect class**: all 11 Highs were *false comments on correct code*, in both languages. Corroborates + **extends** candidate #1 (fix rounds add fresh defects — here comments, not tests) and #3 (off-loop inline fixing, now 5/5) |

## What happened so far

1. **sn96 (before).** Background-spawned review orchestrators ended their turns to "wait"
   (3 resumes, 2 nudges, 1 kill, reviewer reports broadcast into the main context), and every
   re-review re-dispatched the full 10-agent roster against small fix deltas. All-in cost
   [Estimate] ~2.5M–4.5M tokens, ~100 min babysat.
2. **Tuning** (on `main`, commit `7e1ba64`): synchronous waves with reports-as-final-message
   (`dcc-n87o`), re-review rosters capped by fix-delta size and complexity — `mid4`/`mid6`
   first re-review, minimal `mid3` from the third round (`dcc-n7bm`), fix-round boundary
   self-check + least-invasive-fix preference (`dcc-6yi4`), shared pre-flight gates
   (`dcc-8tbb`).
3. **5a8k (after).** Zero manual interventions; rosters `mid`(9) → `mid6` → `mid3` with
   recorded drop rationale; reported review-orchestrator tokens down ~49% (918k → 465k),
   all-in [Estimate] ~1.3M–2.4M — while catching two ship-blockers (an app-wide silent-no-op
   bug and a false-positive regression test created by a fix round). Caveat: an
   easy-to-review declarative diff partially confounds the cost comparison.
4. **Report automation** (`main`, commit `1d85efe`, `dcc-gdof`): a `--report` flag on
   `auto-tdd` / `auto-dev` / `auto-code-review` / `code-review` now produces these reports
   automatically, including per-reviewer/validator token usage captured from the tool
   results — the largest [Estimate] in the two manual reports becomes measured data from
   here on. Format and truth discipline: `conventions/session-report.md` on `main`.
5. **p07b + qj7m (after #2, #3).** The first two auto-generated (`--report`) sessions, both
   Svelte/TS web-UI on `auto-dev`. Zero manual interventions again (tuning still holds), and — for
   the first time — **measured** review-child tokens: a single `mid9`-class wave costs ~750k–1M in
   reviewers+validators (qj7m 749,637), confirming the earlier `[Estimate]`s were conservative.
   p07b caught a real non-modal-defeating Escape regression and refuted a plausible-but-wrong
   focus-theft High; qj7m confirmed a clean small refactor + 3 Medium evolution-readiness gaps.
   p07b also surfaced a **new** signal: adversarial-reviewer failed its first dispatch in both
   iterations (one injection-looking payload) → nib `dcc-jxya`.
6. **batch-dev batch (after #4).** First `/decaf-build:batch-dev` run: 3 unrelated nibs as one series
   cluster, 7 review waves, 82 subagents, [Estimate] ~6.5M–7.5M all-in (no `--report`, so the
   reviewer/validator population is unmetered — the report's principal gap). **The result worth
   tuning on: all 11 High findings across all 7 waves were false claims in comments, on code that
   was mechanically correct every time** — across Svelte/TS *and* Go, three changesets, three
   implementation agents. The class reproduced under its own fix (fa69's fix for "`kept` collapses
   two outcomes" introduced "`stale` collapses two outcomes"), and converged only once the fix brief
   named the class and demanded per-clause evidence (3 Highs → 1 Medium → APPROVED). Also: the loop's
   clearest save yet (fa69 #5 — a fix round silently severed a cross-module delegation, leaving a
   proven-deleted nib with zero user feedback), validators demoted 3 "newly introduced" claims to
   pre-existing, one orchestrator self-reported **fabricating** a report section, and `quick-reviewer`
   went 2 found / **0 unique** across all 7 waves.
7. **Cross-session analysis** (`2026-07-04-cross-session-analysis.md`). With p07b + qj7m in, the
   `dcc-unre` gate is met. Re-scoring over four sessions: **act** on candidate #1 (fix-added tests
   must prove they can fail — 4 of 5 re-reviewed fix rounds added a fresh defect) and #3
   (post-APPROVED fixing happened in 4/4 sessions, unmetered in 3/4 — bring it in-loop and metered);
   **act + expand** #4 (pre-flight must run build/lint, not just record); **keep parked** #2
   (family-sweep, still a sample of one). New track: `dcc-jxya`.

## How we continue

- **Generate**: run the loop with `--report` (e.g. `/decaf-build:auto-dev <item> --report`);
  the report lands in the target project's `.decaf/session-reports/`.
- **Collect**: copy each report directory here, commit to this branch (one commit per
  session, subject `Add <item> code-review session report (<date>)`).
- **Compare** across sessions on the stable dimensions: token cost (review-side vs
  build-side, build:review ratio), per-agent yield and verdict-driver concentration,
  roster-cap natural ablation (did any dropped agent's lane produce evidence it was
  missed?), fix-round regression rate, anomalies (zero is a result), wall clock and
  operator interventions.
- **Tune** only on accumulated evidence: candidates are parked in nib `dcc-unre` (this branch).
  **The "hold until 2+ further session reports" gate is now met** (p07b + qj7m), and the
  re-scoring lives in `2026-07-04-cross-session-analysis.md`: act on #1 (fix-added tests must prove
  they can fail) and #3 (post-APPROVED fix pass, in-loop + metered); act + expand #4 (pre-flight
  runs the full build/lint/test gate, not just records it); keep #2 (family-sweep) parked at a
  sample of one. Application of #1/#3/#4 lands on `main`, tracked in `dcc-unre`. A separate track,
  `dcc-jxya`, covers the adversarial-reviewer dispatch failure. The sample is still four (one
  pre-tuning) and all post-tuning sessions are Svelte/TS web-UI — keep accumulating before treating
  any single-session signal as settled.

Skill changes always land on `main`; this branch stays reports + tuning notes only, and is
periodically compared against — never merged into — the skill history it evaluates.
