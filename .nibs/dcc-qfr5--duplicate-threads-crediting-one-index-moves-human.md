---
# dcc-qfr5
version: 1
title: 'Duplicate threads: crediting one index moves human-axis hits onto the incumbent axis'
status: completed
type: bug
created_at: 2026-08-20T16:52:49Z
updated_at: 2026-08-20T19:49:02Z
parent: dcc-ho2w
order: zzy
---

When a bot reviewer and a human reviewer raise the SAME defect at the same location, the pool holds
one cluster but `threads.json` holds two threads. The grader can set only one `matches_thread`, so one
thread is credited and the other reads as missed. `thread_recall` counts **human** threads and
`incumbent_agreement` counts **bot** threads, so whichever way the grader breaks the tie moves credit
between two axes that are reported separately and must never be merged.

## Measured on PostHog-posthog-55149 ([[dcc-fm7x]])

The grader was told to credit the matching thread's index; nothing told it what to do with duplicates,
and it chose "the earlier index" — which on this subject is almost always the **bot**, because the
scanners comment within days and the human reviewers arrive later.

| human thread | credited instead | the shared defect | arms that found it |
|---|---|---|---|
| T38 `point_in_time_properties.py:80` | T23 (bot) | `except Exception: raise` is a no-op | 4 |
| T44 `api/types.rs:713` | T24 (bot) | `matched` is set to `all_properties_matched` vs its documented meaning | 4 |
| T45 `handler/flags.rs:172` | T4 (bot) | `*flag = override_flag` replaces identity fields wholesale | 2 |

All three defects WERE found — two of them by all four arms. They are recorded as human-axis misses
and as incumbent-axis hits. So `thread_recall` is understated and `incumbent_agreement` is overstated,
on the same subject, from the same three clusters.

## Combined with [[dcc-hw48]], the reported human axis is unrecognizable

Of 20 admitted human threads, `metrics.json` reports 10 hit / 10 missed. Composition of those 10
"misses", by inspection:

- **6** unmatchable at the checkpoint ([[dcc-hw48]]) — T34, T53, T59, T64, T65, T69
- **3** found but credited to a bot duplicate — T38, T44, T45
- **1** (T16) found by arms that then demoted it below their own reporting bar — already visible as
  `threads.demoted_by_every_tool_that_found_it`

**Matchable human threads whose defect no arm surfaced: zero.** That is invisible in the reported
`hit_by_any_tool: 10 / 20`.

## Fix

- Cluster the THREADS before grading: threads asserting the same defect at the same location form one
  ground-truth item, carrying `origins: [human, bot]`. A cluster matching it credits the human axis if
  any constituent thread is human, and the incumbent axis if any is bot — both, independently, since
  the axes are reported separately anyway.
- Failing that, let `matches_thread` be a LIST, and let the grader name every thread a cluster matches.
- Never break the tie by index order: on a review-disciplined repo the scanners are systematically
  earlier than the humans, so "earliest" is a bot-biased rule.

## Acceptance

- [ ] Duplicate threads are grouped, or `matches_thread` accepts several indices
- [ ] A cluster matching a human+bot duplicate pair credits both axes
- [ ] PostHog-posthog-55149's human axis re-derived; the three shifted hits land on the human axis
- [ ] The five previously scored subjects checked for the same pattern and re-derived if present

## Summary

**Completed 2026-08-20** — Reconciled — implemented, and verified rather than assumed.

`score_pooled.py` groups duplicate threads and computes `human_groups` and `bot_groups`
independently over the same group ids, so a mixed pair is in BOTH sets and crediting either member
credits both axes. Covered by a passing test,
`t_crediting_either_duplicate_gives_the_same_answer`.

Measured across the six scored subjects: PostHog-55149 has three duplicate groups and all three are
bot+human pairs ([23,38], [24,44], [27,45]) — exactly the shifted-hit pattern this nib was opened
for, now landing on both axes. grafana#117615 has one group and it is bot+bot, so no axis moves.
The other four subjects have none. The "check the other five for the same pattern" item is therefore
answered: the pattern exists on one subject, and it is the one that reported it.
