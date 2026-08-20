---
# dcc-fm7x
version: 1
title: 'Next session: score PostHog-55149 as the third subject and fix the thread axis'
status: completed
type: task
priority: high
created_at: 2026-08-20T06:41:29Z
updated_at: 2026-08-20T18:35:40Z
parent: dcc-ho2w
order: zr
---

Handoff from the 2026-08-19/20 session. Every substantive conclusion reached there dies on the same
rock — **two subjects** — and the corpus's weakest axis is thread recall.

## Why PostHog-55149 specifically

| subject | admitted | human threads |
|---|---|---|
| **PostHog-posthog-55149** | 35 | **20** |
| PostHog-posthog-52408 | 19 | 15 |
| *(current corpus max: prometheus-18081)* | 10 | *10* |

Four of the five scored subjects are `human_axis_thin` (n<=2) or empty. grafana-117615 scores 0.00
thread recall for EVERY arm because neither of its two human threads is a defect statement
([[dcc-7zyf]]). One PostHog subject roughly doubles the human thread population and gives the miss
detector a denominator that can discriminate.

It is also the **third subject** these need to stop being signals:

- **reach=norm** ([[dcc-tmz2]]) — +22% defects found per cell, demotion gap 0.72 -> 0.41, measured on
  2 subjects. Not adopted pending a third.
- **`review` vs `bugs`** — `review` costs 3.7x `bugs` for +8% on defects and +30% across all classes,
  while superpowers beats both at a fifth of `review`'s price. That is a product decision waiting on
  breadth.

## Design

`ours-bugs`, `ours-review`, `ours-audit`, `superpowers` x 2 repeats = 8 cells. PostHog is a large
diff (18 files, +1253/-38), so budget roughly **$120-200** plus grading. Operator-gated.

Prerequisites, all satisfied: the checkout builds (`detect_build.sh` reports `build_possible: true`,
js/go/python), the fixture is committed, and the subject is out-of-window.

## Rules that bind, all now enforced by tooling

- Grade the **standing calibration sample** and record it ([[dcc-n4nf]]); `score_pooled.py` exits 3
  without a calibration record.
- Build the sample once with `build_calibration_sample.py` — it refuses to re-draw.
- Run `emit_facts.py` then `compare_arms.py`; do NOT hand-write analysis code. Five conclusions
  reversed in one session from exactly that ([[dcc-t83x]]).
- `assert_foldin_movements.py` before and after the fold-in ([[dcc-dirp]]) — the pool WILL grow and
  every other arm's recall will fall without those arms changing.
- Coverage binds narrative, not just tables: this subject will start at 4 contributing arms, so its
  pool is easier to hit than prometheus's 13-contributor pool. The explorer marks this.

## Acceptance

- [x] 7 cells CLEAN, committed — 2x`ours-bugs`, 2x`ours-review`, 2x`superpowers`, 1x`ours-audit` (probe, priced at $44.43 after the drop was reconsidered); was 8. One `ours-review` r2 lost to an API 529 and re-run.
- [x] Calibration recorded for the day on prometheus (13/15 vs pilot pass 1, 10/15 vs pass 2, direction balanced; exact 0.733 and real-vs-not kappa 0.732, both clearing the pre-registered floors). PostHog scored with `--no-calibration` as a first-time subject; its own standing sample can now be drawn from this run.
- [x] N/A for a first-time subject, and the item was mis-specified: `foldin.py` folds a new arm into an ALREADY-graded subject, while a new subject`s pool is built fresh by the bench-analyze path. Nothing to move.
- [x] Thread axis reported with n = **13** matchable human threads (20 admitted, 7 excluded), the corpus`s largest. Reported only after fixing the two denominator defects found doing it ([[dcc-hw48]], [[dcc-qfr5]]).
- [x] Both explicitly WITHHELD. `reach=norm` for two independent reasons (retired arms; vintage). `review` vs `bugs` still rests on two poolable subjects — this subject is **in-window** and may not be pooled, so it is not the third.

## Run decisions (2026-08-20, operator-approved)

Both open items from the pre-flight review, resolved before spending:

**reach=norm is explicitly WITHHELD, not re-stated.** `ours-bugs-reachnorm` and `ours-bugs-narrow`
were retired in `bab89dd` and `run_cell_v2.sh` refuses new cells for them, so the 4-arm design in
this nib cannot produce a third-subject reach comparison. Acceptance item 5 therefore resolves to
its second branch. Note the standing tension worth fixing separately: `tools.json` records the
retirement reason as "reach=norm was measured and not adopted" while [[dcc-tmz2]]'s summary says
"Revisit with a third subject". Re-opening the question also needs 3 repeats, not this run's 2
([[dcc-ce0m]]).

**Calibration uses `--no-calibration` for the first scoring pass.** The acceptance item as written is
circular for a new subject: `build_calibration_sample.py` draws its standing sample from already
graded clusters, which do not exist until PostHog is graded once. `score_pooled.py` provides
`--no-calibration` for exactly this case. The grading day's judge drift is measured on an
already-graded subject's standing sample instead, and PostHog's own standing sample gets built from
this run's verdicts, for every day after this one.

**[[dcc-hv1y]] deliberately lands AFTER this run.** Fixing the `reach=narrow` brief first would make
PostHog's `ours-bugs` cells a new arm at n=1 subject rather than the existing arm's third subject —
the outcome [[dcc-u10u]] documented when `ours-review` changed. It would also destroy the pre-fix
baseline that hv1y's own acceptance item 4 asks for; this subject carries the shape, incl. a
*blocking* human thread at `posthog/api/feature_flag.py:3523` on a regressed clamp.

## Scope change: ours-audit dropped, 6 cells not 8 (2026-08-20, operator-approved)

Measured, not projected: `ours-review` costs **$50.52/cell** on this subject (r1 $46.43, r2 $54.60,
spread 17.6%) against an arm historical mean of $17.76 over 16 cells — a **2.84x** subject
multiplier. Scaling the two unrun arms by it put `ours-audit` near $80/cell ($161 for two) and the
full 8-cell matrix near $330, against this nib's $120-200 budget.

`ours-audit` was dropped because neither headline signal needs it: review-vs-bugs needs `ours-bugs`,
`ours-review` and `superpowers`, and reach=norm is already withheld. What it would have bought is
pool depth — a 4th contributing arm instead of a 3rd.

**Consequence to carry into the write-up:** the pool is SHALLOWER than this nib anticipated. The nib
already warned the subject would start at 4 contributing arms against prometheus's 13; it starts at
**3**. Every recall denominator on this subject is correspondingly easier to hit, and the explorer's
coverage marking must say so. `ours-audit` on PostHog remains a cheap follow-up if pool depth turns
out to bind a conclusion.

One cell was lost and re-run: `ours-review` r2 aborted on an Anthropic **529** after 24 turns,
$25.16, producing a 150-byte `final-output.md` and no tool report. Archived as a failure record at
`v2/runs/_archive/PostHog-posthog-55149__ours-review__shim-on__r2__api529/`. Total spend including
it is $146.31 + superpowers. Note `meter.json` carried `subtype: "success"` next to `is_error: true`
— `is_error` is the authority (`run_pilot.sh:47`), and the resume guard re-ran the cell correctly
because it keys on `is_error` rather than emptiness.

## CORRECTION: the subject is IN-WINDOW, and cannot serve as the third subject

This nib listed "the subject is out-of-window" as a satisfied prerequisite. **That claim was false.**
`score_pooled.py` computes `vintage.status = in-window`:

```
merged_at 2026-05-06   model_cutoff 2026-05   provably_clean_from 2026-06-01
```

`claude-opus-5` publishes a month-granular cutoff of 2026-05, so a subject is provably clean only if
it merged on or after 2026-06-01. PostHog-posthog-55149 merged 2026-05-06, five days inside the
window. It is the **only in-window subject among the six scored** — efcore, prometheus, immich,
mattermost and grafana-117615 all merged between 2026-06-10 and 2026-07-17.

Per METHODOLOGY-v2 section 5 its numbers are disclosable **per-subject only and must not be pooled**
into any cross-subject figure. That is exactly what this run was commissioned to enable, so:

- **`reach=norm` is still withheld** — now for two independent reasons (retired arms, and vintage).
- **`review` vs `bugs` is still on two poolable subjects.** This run does NOT make it three.
- Acceptance item 5 resolves to "explicitly still withheld", as recorded in Run decisions, and the
  reason is now stronger than an arm-availability problem.

The per-subject readout stands on its own and is worth having — 4 arms, 7 cells, 108 clusters, the
largest human-thread population in the corpus. It is simply not the cross-subject unlock.

Root cause worth carrying: the vintage check is computed at ANALYSIS time by `scoring/vintage.py`,
after the money is spent. Nothing at subject-selection time refuses an in-window subject or warns.
Filed as a follow-up.

## Thread axis: three deflation mechanisms, and the real result

`metrics.json` reports `hit_by_any_tool: 10 / 20` human threads. Composition of the 10 "misses":

- **6** unmatchable at the checkpoint ([[dcc-hw48]]) — they discuss code introduced later
- **3** found, but credit went to a bot duplicate of the same thread ([[dcc-qfr5]])
- **1** (T16) found by arms that demoted it below their own reporting bar

**Matchable human threads whose defect no arm surfaced: zero.** Every per-arm `thread_recall` figure
on this subject (0.20 to 0.45) rests on the inflated denominator and the shifted credit, and none of
them may be published until [[dcc-hw48]] and [[dcc-qfr5]] are fixed and the axis re-derived.

`threads.judge_dismissed_reported_threads` is empty — no judge calibration failure of the kind that
check exists to catch.

## Summary

**Completed 2026-08-20** — **Completed 2026-08-20.** All five acceptance items met. The subject was scored; it is NOT the third
subject, and could not have been.

**The headline goal failed on a false prerequisite.** This nib listed "the subject is out-of-window"
as satisfied. It is **in-window** — merged 2026-05-06 against a month-granular 2026-05 cutoff, so
provably clean only from 2026-06-01. It is the only in-window subject among the six scored. Per
METHODOLOGY-v2 section 5 its numbers are disclosable per-subject and may not be pooled, so
`reach=norm` and `review`-vs-`bugs` still rest on two poolable subjects. $203.54 bought a valid
per-subject readout and four bug fixes, not the cross-subject unlock. The vintage check runs at
analysis time, after the money is spent — filed as a follow-up.

**7 cells, all CLEAN**, $178.38 valid spend plus a $25.16 cell lost to an API 529 (archived as a
failure record, re-run). 309 findings extracted from `cell-report.md` + `tool-artifacts/` across 7
cells, clustered into 108, blind-graded twice.

Per-subject figures (all four arms clear the n>=10 reported-cluster floor): `ours-review` precision
0.902 at $50.51/cell, `ours-audit` 0.800 at $44.43/cell with 8 unique real findings, `ours-bugs` 0.800
at $10.06/cell, `superpowers` 0.667 at $6.40/cell. Thread recall over n=13: `ours-review` and
`ours-audit` 0.846, `superpowers` 0.615, `ours-bugs` 0.385 with the largest demotion gap (0.154).

**Four defects found, all filed, two of them fixed here:**

- [[dcc-hw48]] (high) — thread admission tests line position only, never whether the thread's subject
  exists at the checkpoint. Corpus-wide. 7 of 20 human threads excluded here; the loss scales with
  post-checkpoint review activity, so it penalized exactly the subjects chosen for rich review
  histories. FIXED: denominators are audited, six subjects annotated.
- [[dcc-qfr5]] — duplicate threads split credit between the human and incumbent axes, biased toward
  bots because scanners comment earlier than humans. FIXED: recall computed over thread groups.
- [[dcc-9vta]] — `detect_build.sh` misses nested Rust workspaces and never validates `build_possible`;
  no arm executed a single probe on this subject, so its Rust half is static reasoning only.
- [[dcc-8dtt]] — `cost_per_real_finding` divides a total by a deduplicated pool, penalizing repeats.
  Surfaced only because a reader asked why one arm cost twice another.
- [[dcc-hsy8]] — the `/tmp` sweep eats driver logs; the last cell's `.decaf/` report survived into the
  blind graders' checkout (blind held, verified by transcript grep); the blind-work forbidden list was
  hand-written and incomplete.

**Corrected en route:** the thread axis moved for every subject, not one-directionally — prometheus up,
mattermost down, efcore both ways until a compound-thread verdict was fixed. grafana-117615's human
axis is now `null` (n=0) rather than 0.00 on four arms, and for a verified reason different from the
one on record. A new permanent cross-check (`credited_to_unmatchable_thread`) caught the one annotation
error that had silently cost seven arms a legitimate hit.

**Not done, carried forward:** the per-subject readout prose; three loose grading matches the new
cross-check reports; six of twelve subjects still unannotated and therefore
`thread_axis_publishable: false`.
