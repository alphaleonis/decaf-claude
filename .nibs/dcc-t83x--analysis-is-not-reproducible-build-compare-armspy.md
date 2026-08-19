---
# dcc-t83x
version: 1
title: 'Analysis is not reproducible: build compare_arms.py, a metric glossary, and a no-interpretation-before-artifact rule'
status: in-progress
type: feature
priority: high
created_at: 2026-08-19T13:44:36Z
updated_at: 2026-08-19T16:10:35Z
parent: dcc-ho2w
order: zq
---

On 2026-08-19 the same 12-cell dataset ([[dcc-tmz2]]) produced five conclusions that reversed within
one session. The operator's judgement — that the analysis could not be trusted for continued work —
is correct, and the cause is mostly process plus two tooling gaps.

## The five reversals and their causes

| # | claimed | corrected to | cause |
|---|---|---|---|
| 1 | efcore's 4:1 new-cluster ratio favours the exploration hypothesis | all trivia | reported a PRE-VERDICT intermediate as signal |
| 2 | `norm` never reached e02 | narrow r1 and norm r2 both reported it | read the new-cluster list as the detection record; hits on EXISTING clusters merge in and never appear there |
| 3 | null — reach does not help | +22% found / +38% reported | same substitution, new clusters instead of the real-defect pool |
| 4 | half of `reachnorm`'s output is not real | 22 of 24 are correct | read `precision` without knowing it excludes `valid_minor` |
| 5 | `review` buys almost nothing over `bugs reach=norm` | +30% across all classes | computed on the defect pool, stated unscoped |

Four of five are one failure repeated: interpreting whichever intermediate artifact the just-finished
stage produced, instead of the metric the experiment pre-registered ("real defects found per cell").

## The two genuine gaps

**`precision` silently excludes `valid_minor`.** `score_pooled.py:34` — `REAL = {matches-key,
matches-thread, valid-other}` — is the only place this is recorded. `/bench-analyze` section 6 says
"report per tool: precision" with no warning that a correct, actionable finding scores as a miss.
`precision 0.50` on an arm whose output is 92% correct is actively misleading.

**Nothing in the pipeline compares arms.** `score_pooled.py` is per-subject-per-tool;
`aggregate_pilot.py` is cross-SUBJECT. No artifact puts arms side by side, so four different ad-hoc
scripts were written during one session with different column definitions each time. That is the
mechanical source of the inconsistency.

## What to build — FACTS FIRST, views second

The mistake would be to build another script that emits tables. Tables are where definitions get
baked in and diverge. Emit **facts**; make every table a grouping over them.

### 1. `v2/scoring/emit_facts.py` — the primary deliverable

Three tidy long-format files under `v2/analysis/facts/`, regenerated from the committed
`analysis.json` + `metrics.json` + `runs/*/meter.json`, never hand-edited:

    clusters.jsonl       one row per cluster
      {subject, cluster_id, verdict, judged_severity, finding_class,
       matches_thread, location, is_real, in_defect_pool}

    observations.jsonl   one row per (cluster x arm x repeat)
      {subject, cluster_id, arm, repeat, disposition, tool_severity}

    cells.jsonl          one row per cell
      {subject, arm, repeat, cost_usd, wall_s, models, isolation, shim, is_error}

Every table produced during the 2026-08-19 session — class breakdown, per-defect matrix, noise%,
the severity x class population grid, per-cell rates, model mix — is a GROUP BY over these three.
Nothing pre-aggregated. A published figure becomes re-derivable by anyone without trusting a script.

### 2. `v2/scoring/compare_arms.py` — ONE default view over the facts

Not a new source of truth; a consumer. Emits the canonical comparison with a printed legend:
- shown / real / valid-minor / trivia / false-positive, and **noise% = (trivia+false+)/shown** as a
  first-class column — the question a developer actually asks
- reported-vs-found by `finding_class` and by `judged_severity`
- per-defect per-cell hit rate against the pool
- cost per cell / per real finding
- **the pool size and the arm set printed beside every recall figure** — the pool is dynamic
  ([[dcc-dirp]]); adding an arm moves every number in the table
- **refuses to rank across different subject-coverage groups.** An arm scored on 2 subjects sits
  against a different pool than one scored on 5; on 2026-08-19 that difference was 53 vs 77 clusters.
- honours the n>=10 floor before any ratio, and refuses when an arm mixes configurations
  (the `ours-bugs` wave/single-seat trap).

### 3. `v2/scoring/METRICS.md` + inline notes

Define real vs found vs reported; what precision counts and excludes; and that **`finding_class` is
what a finding is ABOUT while `verdict` is whether it is RIGHT** — a "checked whether X crashes, it
cannot" note is defect-class and trivia-verdict, which caused reversal 1. `score_pooled.py` emits
`precision_note: "excludes valid_minor; see METRICS.md"` so the caveat travels with the number.

### 4. A reporting rule in `/bench-analyze` and `/bench-run`

**No interpretation of any stage output before the deterministic artifact exists.** Intermediates are
reported as bare counts ("47 new clusters, ungraded") with no reading attached. `new_clusters` is
displayed as "claims not already in the pool — NOT a detection measure" wherever it is surfaced.

Deliberate non-change: `cluster` is not renamed to `issue`. 54% of graded clusters are trivia or
false-positive, so `issue` would smuggle in the verdict. Renaming to `claim` would be more accurate
but touches every artifact and script for no analytic gain; do it in published reports if wanted.

## Acceptance

- [x] `emit_facts.py` + the three jsonl files committed (353 clusters / 1429 observations / 82 cells across five subjects), regenerable, round-trip vs metrics.json asserted and tested
- [x] `compare_arms.py` as a view over the facts + tests: n<10 withheld, incompatible-model-set refusal (fires on `ours-bugs`, correctly does NOT fire on merely nested sets), coverage groups separated
- [x] `METRICS.md`; `precision_note` emitted by score_pooled.py; `t_precision_note_travels_with_the_number` asserts it
- [x] `/bench-analyze` and `/bench-run` carry the no-interpretation rule
- [x] [[dcc-tmz2]] re-derived from the facts: pool hit/cell reachnorm 0.458 > superpowers 0.438 > narrow 0.375 > sp3 0.354 — identical to the ad-hoc figures, confirming the reversals were misreadings rather than arithmetic errors
- [ ] Each of the five reversals is re-checkable from the committed facts
