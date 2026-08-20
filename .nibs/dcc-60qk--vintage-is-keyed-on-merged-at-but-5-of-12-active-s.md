---
# dcc-60qk
version: 1
title: Vintage is keyed on merged_at, but 5 of 12 active subjects were public and reviewed inside the window
status: completed
type: bug
priority: high
created_at: 2026-08-20T19:17:22Z
updated_at: 2026-08-20T19:47:53Z
parent: dcc-ho2w
order: zzzu
---

`vintage.classify()` reads `merged_at`. The reviewable artifact — the PR page, its diff, and its
early review conversation — is public from **creation**, not from merge. Measured on the corpus as
it stands after [[dcc-ryo4]]'s replacement round, against the 2026-06-01 bound:

| Subject | PR created | Checkpoint | Merged | `merged_at` verdict |
|---|---|---|---|---|
| dotnet/efcore#34127 | **2024-06-30** | 2024-07-01 | 2026-06-15 | out-of-window |
| element-hq/element-web#32964 | **2026-03-29** | 2026-03-29 | 2026-07-21 | out-of-window |
| grafana/grafana#117615 | **2026-02-06** | 2026-04-06 | 2026-07-17 | out-of-window |
| prometheus/prometheus#18081 | **2026-02-13** | 2026-03-18 | 2026-06-15 | out-of-window |
| sveltejs/kit#15685 | **2026-04-09** | 2026-04-09 | 2026-07-02 | out-of-window |

The other seven are created, checkpointed and merged after the bound and are unaffected.

efcore#34127 is the extreme case: the PR sat open for **almost two years** before merging. Every
number this corpus has published for that subject rests on a diff that was publicly readable, with
its review threads, long before any cutoff under discussion.

## Why this is not obviously a bug in the rule

`merged_at` is defensible for one thing: the *merged* PR — squashed commit, final state, resolved
conversation, the outcome — only exists after merge. What a model could have memorized from an
**open** PR is the diff and whatever review had accumulated by then, which is exactly the checkpoint
and exactly the thread set this instrument scores. So the conservative key is `pr_created_at`, and
`merged_at` is the permissive one.

[Inference] Whether an open PR was actually in the training data is not observable from here. The
argument is about what was *available*, on the same conservative reading that already pushed the
cutoff from 2026-05-01 to 2026-06-01 ([[dcc-vvf0]]): a subject is provably clean only if the
artifact could not have been seen.

## What it costs to fix

Everything. Under a `pr_created_at >= 2026-06-01` bound the active corpus loses five subjects,
including three whole cells' incumbents (`app-ui S`, `app-ui L`, `library S`) plus `library M` and
`library L` — the entire library row. [[dcc-ryo4]] has just demonstrated the replacement round is
feasible but not cheap, and the screen has never filtered on creation date.

## What to do

1. **Decide the key first, in writing** — `merged_at` (status quo, permissive) or `pr_created_at`
   (conservative). Do not decide it by looking at which answer keeps more subjects.
2. Whatever is chosen, `vintage.py` must record **both** dates and say which one it keyed on, so a
   published figure carries the assumption instead of hiding it.
3. If `pr_created_at` wins: `find_candidates.sh` screens on it, and the five above are retired to
   probe material the way [[dcc-ryo4]] retired the May five.
4. Either way this belongs in METHODOLOGY-v2 section 5 next to the month-granularity reasoning.

## Acceptance

- [ ] The vintage key is chosen and the reasoning is written down before any subject is re-screened
- [ ] `vintage.classify()` names the field it keyed on in its output
- [ ] `find_candidates.sh` screens on the chosen key
- [ ] METHODOLOGY-v2 section 5 states the open-PR exposure argument and the decision

## Summary

**Completed 2026-08-20** — Operator decision 2026-08-20: **key on `merged_at`, report both.**

`vintage.describe()` now takes `pr_created_at` and emits `key`, `status`, `pr_created_at`,
`status_by_pr_created_at`, and an `exposure_note` when the two disagree. `check_pooling()` still
gates on the merge key alone; a new `exposure_warnings()` names the subjects the conservative key
would have dropped, so a pooled figure can state how much of itself rests on the permissive reading.

A missing `pr_created_at` reports `unknown` and `score_pooled.py` refuses it — "unchecked" must not
read as "the two keys agree". Backfilled onto all six scored analyses. `vintage.py` grew a CLI so the
shell can gate without embedding Python, and `run_cell_v2.sh` and `status.sh` both surface the second
key.

Exposed and disclosed, not retired: element-web#32964, sveltejs/kit#15685, grafana#117615,
prometheus#18081, efcore#34127. Switching keys later is a one-line change plus a replacement round.
