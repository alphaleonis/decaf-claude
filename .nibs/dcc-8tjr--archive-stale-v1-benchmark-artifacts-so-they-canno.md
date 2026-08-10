---
# dcc-8tjr
version: 1
title: Archive stale v1 benchmark artifacts so they cannot pollute future runs
status: completed
type: task
priority: critical
created_at: 2026-08-10T17:41:58Z
updated_at: 2026-08-10T18:14:57Z
parent: dcc-ho2w
order: I
---

Stale artifacts polluting a later run is the exact failure that started this milestone: `.decaf/`
review reports left in a shared checkout were read by the next cell's recurring-findings check.
Before any v2 measurement, sweep everything that could leak into or be mistaken for v2 data.

## Scope

- `runs/` — 81 v1 cells whose bundles contain `CODE_REVIEW_*.md` and per-subagent findings. Under v2
  these are neither valid nor comparable. Archive, don't delete: they are the evidence base for
  [[dcc-2cxq]] and the contamination analysis.
- `analysis/subject-*/` — v1 keys and graded verdicts. Two of three audited subjects had invalid
  ground truth, so these must not be picked up by a v2 grader by path convention.
- `quarantine/2026-08-06-decaf-leak/` — already isolated; confirm nothing references it.
- `v2/runs/_archive/` — the unlogged arm-B cells. Their LEAK accounting is unsound (output-grepping
  undercounts; see `v2/runs/CONTROLLED-TEST.md`). Keep for detection comparison, mark as unusable
  for leak claims.
- `repos/*` and `v2/repos/*` — verify `.decaf/` and any tool-written artifact is absent, and that the
  per-cell reset in `run_cell.sh` still holds.
- Any `.decaf/` directory anywhere under `competition/`.

## Also decide the fate of these v1 data bugs

Both may be moot once v1 data is archived — scrap them explicitly rather than leaving them open:

- [[dcc-z13k]] — subject 6's anthropic r2 extract and findings.json are two different datasets
- [[dcc-3v3m]] — subject 10's extraction captured no severity labels

## Acceptance

- [x] One archive root with a README stating what the data is, why it is invalid, and what it may
      still be cited for — `v1-archive/README.md`
- [x] No v2 path convention can reach a v1 key, extract, or findings file — `analysis/` holds only scripts now; `gather_inputs.sh` repointed
- [x] Every `repos/*` checkout verified clean of tool-written artifacts — all 13; and `run_cell_v2.sh` now resets per cell
- [x] dcc-z13k and dcc-3v3m each closed or scrapped with a reason — both scrapped 2026-08-10; their hazards carried into [[dcc-y2e6]]

## Summary

**Completed 2026-08-10** — Archived the v1 dataset under `v1-archive/` (88 cells, 9 graded subjects, metrics CSV, run ledger,
and both earlier quarantines) with a README recording the four failures, the opposite-direction leaks
that make even the gap's direction unknown, and the line between what the data may still be cited for
(leak mechanism, cost telemetry) and what it may not (any tool comparison).

The concrete collision the archive breaks: `analysis/scripts/gather_inputs.sh` wrote v1 keys into
`analysis/subject-NN/` — the same shape v2 uses — so a v2 grader could have picked one up by path
convention alone. `analysis/` now holds only machinery. Corpus definition stayed in place because
dcc-5xad needs it, with the caveat that `subjects/*.json` still carries the unaudited ground truth.

`bench_next.sh` refuses without `BENCH_V1_ALLOW=1`; the five bench commands carry the warning; v1
machinery was repointed so a deliberate re-run still works.

Unplanned but in scope: `run_cell_v2.sh` had NO checkout reset — v2 was reproducing the exact v1
contamination design. A stray `ours-review` report sat in `v2/repos/2/` for all eight subsequent
subject-2 cells, including all four of the controlled test. Audited every transcript (9 parents + 18
subagent sidechains + tool-results): `.decaf/` appears in exactly one file, the writer's own. Not
exploited, so CONTROLLED-TEST.md's conclusion stands — but the cell outputs alone could not have
shown that, since cells keep no transcript. v2 now resets before every cell and refuses on a dirty
tree (77) or missing checkpoint (78), smoke-tested to preserve the 129,013-commit history.

Next in the milestone: dcc-5xad (audit ground truth) and dcc-595v (decide the v2 scoring model).
