---
# dcc-8tjr
version: 1
title: Archive stale v1 benchmark artifacts so they cannot pollute future runs
status: todo
type: task
priority: critical
created_at: 2026-08-10T17:41:58Z
updated_at: 2026-08-10T17:52:18Z
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

- [ ] One archive root with a README stating what the data is, why it is invalid, and what it may
      still be cited for
- [ ] No v2 path convention can reach a v1 key, extract, or findings file
- [ ] Every `repos/*` checkout verified clean of tool-written artifacts
- [x] dcc-z13k and dcc-3v3m each closed or scrapped with a reason — both scrapped 2026-08-10; their hazards carried into [[dcc-y2e6]]
