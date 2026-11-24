---
# dcc-va4f
version: 1
title: 'batch-dev: decide from --report data whether review groups need a size limit'
status: draft
type: task
created_at: 2026-11-24T13:14:51Z
updated_at: 2026-11-24T13:14:51Z
blocked_by:
    - dcc-crvx
order: zzzzzzzzzw
---

dcc-crvx bounds a review group by conductor judgment alone, with no number, because none could be backed by data. Once grouped runs exist, compare `--report` session reports from grouped and per-nib runs (per-subagent spend from dcc-k163, diffstat, findings per review) and decide whether a combined-diff size, as a soft guide or a hard limit, would protect review quality, and at what value.

## Context

Filed 2026-11-24 while refining dcc-crvx (Q3: size bound). The operator found a nib-count limit unworkable without reading the nibs, and a changed-lines limit dubious without knowing the number.
