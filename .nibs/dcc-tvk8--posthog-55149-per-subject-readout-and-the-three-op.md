---
# dcc-tvk8
version: 1
title: PostHog-55149 per-subject readout, and the three open grading contradictions
status: completed
type: task
created_at: 2026-08-20T18:35:49Z
updated_at: 2026-08-21T06:52:12Z
parent: dcc-ho2w
order: zzzk
---

Two loose ends from [[dcc-fm7x]], neither blocking but both needed before any PostHog figure is
published outside the nib.

## 1. The per-subject readout

`analysis/` has no write-up for PostHog-posthog-55149. It must lead with `vintage.status: in-window`
and state that the numbers are per-subject only — that is the first line, per the bench-analyze
contract, because five of twelve subjects are in this class and pooling one is the error the rule
exists to prevent.

Must carry: 4 arms / 7 cells / 108 clusters; precision with severity-weighted alongside; thread recall
with **n=13** and the 7 exclusions named; the demotion gap per arm, noting `superpowers`' 0.000 is
structural (it has no demotion section) rather than behavioral; cost **per cell** as well as per arm
([[dcc-8dtt]]); and the coverage caveat — 4 contributing arms, a shallower pool than prometheus's 13.

Also worth recording: no arm executed a single probe on this subject ([[dcc-9vta]]), so every finding
is static reasoning, and 13 of 18 changed files are Rust with no toolchain.

## 2. Three grading contradictions the new cross-check reports

`score_pooled.py` warns `credited_to_unmatchable_thread` on three subjects. Each is a cluster credited
to a thread judged unmatchable, and each looks like a loose GRADING match rather than an annotation
error — but they need resolving, not assuming:

| subject | cluster -> thread | why it looks loose |
|---|---|---|
| `dotnet-efcore-34127` | `e15` -> T1 | a `== true` style cluster credited to a thread asking for `is null` on a line with no `== null` |
| `mattermost-mattermost-36824` | `ma11` -> T6 | a decoder-placement cluster credited to a request for a context-carrying logger |
| `PostHog-posthog-55149` | `c108` -> T15 | an inert-test-values cluster credited to a missing-integration-test request |

Resolution is per case: re-grade the cluster (most likely `valid-other`/`valid-minor` rather than
`matches-thread`), or revise the thread's matchability verdict. `ma11` affects four arms, so it moves
mattermost's numbers.

## 3. Six subjects still unannotated

`element-web#32964`, `sveltejs/kit#15685`, `grafana#124181`, `immich#24627`, `jellyfin#12834`,
`PostHog/posthog#52408` have no matchability verdicts, so they report
`thread_axis_publishable: false`. They are unscored today, so nothing is wrong — but they must be
annotated before their cells are scored, or the same inflated denominator returns.

## Item 2 done 2026-08-20 — and two of the three were annotation errors, not grading errors

`credited_to_unmatchable_thread` is empty on all six scored subjects.

| contradiction | resolution |
|---|---|
| `ma11` -> mattermost T6 | **thread revised to matchable.** Not a loose match: T6's second sentence asks for exactly what ma11 reports — move the `IsValid()` call out of `CommandResponseFromJSON` into commandWebhook and DoCommandRequest, both of which exist at the checkpoint. The exclusion was the error. |
| `e15` -> efcore T1 | **thread revised to matchable.** Same shape: the norm in T1's closing parenthetical has a target at `:633`. |
| `c108` -> PostHog T15 | **cluster's thread credit removed.** T15 asks for tests proving a gate DROPS the override fields; that gate does not exist at the checkpoint — its absence is what `c084` reports. The exclusion is correct and the match is not. |

Both revisions came out of [[dcc-fm8s]]'s second pass under the compound-thread rule, run in the same
session.

### What moved

- **mattermost:** `thread_recall` 0.667 -> **0.750** on all four arms, `hit_by_any_tool` 2 -> 3. The
  nib predicted ma11 would move four arms; it did, **upward** — they regained a legitimate hit.
- **efcore:** `hit_by_any_tool` 6 -> 7; `ours-audit` 0.500 -> 0.556 (it reported e15); the six arms
  that did not gain a hit fell on the larger denominator, 0.125/0.250/0.375 -> 0.111/0.222/0.333.
  Separately, `incumbent_agreement` 0.000 -> 1.000 on seven arms, from an index correction found by
  [[dcc-on93]]'s quote backfill.
- **PostHog, prometheus, grafana, immich:** no per-tool movement. c108 lost a credit to a thread
  already outside the denominator.

Every movement is explained by a named correction.

Write-up: `v2/analysis/GRADING-INTEGRITY-2026-08-20.md` §4.

## Items 1 and 3 done 2026-08-21

### 1. The readout — `analysis/POSTHOG-55149-RESULTS.md`

Leads with `vintage.status: in-window` and the per-subject-only restriction, and notes the subject
is now `role: retired-probe` — the in-window half of a matched vintage pair with PostHog#67924,
which is what its numbers are for. Carries everything this nib listed: 4 arms / 7 cells / 108
clusters, the shallow-pool caveat against prometheus's 13 arms, thread recall at n=13 with all 7
human exclusions named in a table, the per-arm demotion gap with `superpowers`' 0.000 marked
structural, and cost per cell beside per arm ([[dcc-8dtt]]).

**Precision is published as a BAND, not a point**, per [[dcc-sfny]] — the boundary that decides it
measured kappa 0.598 at n=62 on this subject's own two passes. To make the band real rather than
asserted I built and scored `grading/analysis-pass2.json`, which the subject lacked:

| arm | precision band | recall (both passes) |
|---|---|---|
| `ours-review` | 0.90 – 0.95 | 0.846 |
| `ours-audit` | 0.80 – 0.80 | 0.846 |
| `ours-bugs` | 0.80 – 0.90 | 0.385 |
| `superpowers` | 0.67 – 0.67 | 0.615 |

**One ranking is not stable**: `ours-bugs` ties `ours-audit` in pass 1 and beats it in pass 2, so
"bugs vs audit" must not be reported as an ordering on this subject. Recall is identical in both
passes for every arm.

Two things found while writing it. Pass 2 independently made the **same** `c108 -> T15` loose match
pass 1 did, against a doubly-confirmed exclusion — the identical correction is applied to both and
recorded. And `missed_by_every_tool` is 1 on the reported view but **0 on the found view**: nothing
was missed, T16 was found and demoted by everyone who found it.

### 3. The unannotated subjects — all 12 active cells now annotated

The list in this nib was stale: four of its six were retired by [[dcc-ryo4]], and the five new
subjects it could not have known about were also unannotated. Actual scope was **7 active subjects,
126 threads**. All 7 annotated; **only 2 exclusions**, and they are the same absent comment reviewed
twice (grafana#125982 T18/T20).

Corpus-wide the active grid now holds **139 matchable human threads** — against the 30 the census
([[dcc-qwt3]]) counted across the seven then-citable subjects. Write-up:
`analysis/THREAD-DENOMINATORS.md`.

**Annotated before any cell has run on those seven**, which is the strongest form of this blind
available: matchability is decided with no tool output in existence to be influenced by. The reverse
order has already gone wrong once ([[dcc-hsy8]]). Do the annotation first.

The five non-active fixtures are **explicitly deferred** with the reason recorded in a
`matchability_deferred` block on each: none holds a cell, so no recall divides by them, and
`score_pooled.py` already refuses an unannotated subject. They must be annotated before the
memorization probe runs, since it compares recall across a matched pair.

### One thing carried forward, not resolved

Both readings of grafana#125982's two exclusions were authored in the same session by the same
agent. The second is a real re-derivation — enumerate every comment in the function, then widen the
grep repo-wide — but it is a second *method*, not a second *reader*, and it is stamped as such in
`matchability_readings[].independence`. [[dcc-fm8s]]'s guarantee is not fully met for those two;
get an independent opinion before grafana#125982 is scored. Nothing else depends on them.

## Acceptance

## Acceptance

- [x] `analysis/POSTHOG-55149-RESULTS.md` written, leading with the in-window status
- [x] All three `credited_to_unmatchable_thread` entries resolved and the affected subjects re-scored
- [x] The unannotated subjects either annotated or explicitly deferred with the reason recorded —
      7 active subjects annotated (126 threads), 5 non-active deferred in-fixture

## Summary

**Completed 2026-08-21** — All three items done.

**The readout** (`analysis/POSTHOG-55149-RESULTS.md`) leads with the in-window status on both vintage
keys and the per-subject-only restriction, and carries everything the nib specified. Precision is
published as a band rather than a point, per dcc-sfny — which required building and scoring the
second-pass metrics the subject never had. The band is narrow for three arms and 0.80-0.90 for
`ours-bugs`, and it exposed a ranking that does not survive the two passes: bugs ties audit in one
and beats it in the other, so that ordering is not reportable. Recall is identical across both
passes for every arm. Two incidental findings: pass 2 independently made the same c108 -> T15 loose
match pass 1 did, and nothing was actually missed on this subject — T16 was found and demoted by
every arm that found it.

**The annotation** covered 7 active subjects and 126 threads, not the 6 the nib listed — four of
those had been retired by dcc-ryo4 and five new subjects had arrived. Every active cell is now
annotated, with just 2 exclusions corpus-wide from this pass, both reviewing the same comment that
does not exist anywhere in the repo at the checkpoint. The active grid holds 139 matchable human
threads against the 30 the census counted. Seven of the twelve were annotated before any cell has
run on them, which is the only point at which the blind is structurally guaranteed rather than
trusted.

**The five non-active fixtures are deferred, not skipped** — reason recorded in a
`matchability_deferred` block on each, with the condition that they be annotated before the
memorization probe runs.

Carried forward: both readings of grafana#125982's two exclusions share an author, so dcc-fm8s's
independence guarantee is not fully met for those two. Stamped as such in the data and flagged in
the write-up rather than papered over.
