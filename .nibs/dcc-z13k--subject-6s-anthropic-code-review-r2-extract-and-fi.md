---
# dcc-z13k
version: 1
title: Subject 6's anthropic-code-review r2 extract and findings.json are two different datasets
status: todo
type: bug
priority: normal
created_at: 2026-08-05T22:19:46Z
updated_at: 2026-08-05T22:20:03Z
order: zzzw
---

# What

Found while re-keying subject 6's reference clustering (#dcc-xewu). For
`anthropic-code-review` repeat 2 on subject 6, the archived extract and the findings table describe
**different finding sets**:

| source | findings | with a subagent | file+line agreement |
|---|---|---|---|
| `analysis/subject-06/extract/anthropic-code-review__r2.json` | 20 | 0 | — |
| `analysis/subject-06/findings.json` (tool/repeat slice) | 33 | 23 | **1 of 20** |

One pair in common out of twenty. This is not a reordering — it is a re-extraction, evidently one
that started capturing subagent-level findings, which `extract/` and `cluster-assign.json` never
caught up with. Every other run in subject 6 (9 of 10) matches its extract exactly, position by
position, on file+line.

# Why it matters

`analysis/subject-06/analysis.json` clusters cite the **stale** set in `reported_by`. So any
published anthropic-code-review number for subject 6 — cluster membership, corroboration counts,
whatever the synthesis derives from them — rests on a finding set that `findings.json` no longer
contains. The direction and size of the error are unknown; 33 vs 20 means the current extraction
finds materially more, so the stale set likely understates that tool on this subject.

Those 33 are also the only findings in subject 6 left without a `cluster_id` after the
2026-08-06 backfill (661/694 covered).

# Not blocking the clustering test

`cluster_replay.py` filters `tool == "ours"`, and the `ours` runs verified 183/183. #dcc-xewu is
unaffected.

# Open questions

- Which is right — did a later re-extraction fix a real gap in the anthropic extraction, or did it
  double-count subagent output the way validator findings once contaminated the clustering
  experiment (#dcc-xewu, correction 2)? The subagent-vs-null split is the same shape as that bug.
- Do other subjects have the same drift? Only subject 6 was checked, and only because its ids
  forced the comparison. `analysis/scripts/backfill_cluster_ids.py` performs exactly this check —
  running it dry against subjects 1/4/5/7 would answer it cheaply.
- Does anything in the published synthesis actually change?

# Acceptance

- [ ] Determine which extraction is correct for subject 6 / anthropic-code-review r2
- [ ] Check the other subjects for the same extract-vs-findings drift
- [ ] Reconcile `extract/`, `cluster-assign.json` and `analysis.json` against whichever set wins
- [ ] State whether any published number moves, and correct it if so
