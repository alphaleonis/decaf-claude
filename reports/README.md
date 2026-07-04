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
- **Tune** only on accumulated evidence: candidates are parked in nib `dcc-unre`
  (this branch) — currently: fix-added tests must prove they can fail; vendored-family
  sweep rule; post-APPROVED trivial-residual handling; pre-flight line recorded in every
  report header. **Gate: hold until 2+ further session reports are in** — a sample of one
  (or two) sessions has already proven misleading once (quick-reviewer was dry for all of
  sn96 and then found 5a8k's headline bug).

Skill changes always land on `main`; this branch stays reports + tuning notes only, and is
periodically compared against — never merged into — the skill history it evaluates.
