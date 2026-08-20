---
# dcc-tvk8
version: 1
title: PostHog-55149 per-subject readout, and the three open grading contradictions
status: todo
type: task
created_at: 2026-08-20T18:35:49Z
updated_at: 2026-08-20T18:36:20Z
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

## Acceptance

- [ ] `analysis/POSTHOG-55149-RESULTS.md` written, leading with the in-window status
- [ ] All three `credited_to_unmatchable_thread` entries resolved and the affected subjects re-scored
- [ ] The six unannotated subjects either annotated or explicitly deferred with the reason recorded
