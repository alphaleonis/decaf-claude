---
# dcc-fm7x
version: 1
title: 'Next session: score PostHog-55149 as the third subject and fix the thread axis'
status: todo
type: task
priority: high
created_at: 2026-08-20T06:41:29Z
updated_at: 2026-08-20T06:42:06Z
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

- [ ] 8 cells CLEAN, committed
- [ ] Standing calibration sample built and graded; calibration recorded for the day
- [ ] Folded in; movements all explained by `assert_foldin_movements.py`
- [ ] Thread axis reported with n — the first non-thin subject since prometheus
- [ ] reach=norm and review-vs-bugs re-stated on three subjects, or explicitly still withheld
