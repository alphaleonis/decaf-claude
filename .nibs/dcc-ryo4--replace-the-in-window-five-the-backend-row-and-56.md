---
# dcc-ryo4
version: 1
title: 'Replace the in-window five: the backend row and 56 of 86 human threads are locked behind vintage'
status: completed
type: task
priority: high
created_at: 2026-08-11T11:40:22Z
updated_at: 2026-08-20T19:25:53Z
parent: dcc-ho2w
blocked_by:
    - dcc-2gu2
order: 8o
---

[[dcc-vvf0]] chose keep-and-flag for the five subjects merged inside May 2026, to preserve their
audited thread sets at the price of a permanently unreportable `backend` row. **The census
([[dcc-qwt3]]) changed that trade after the fact**: the in-window five hold **56 of the corpus's 86
human threads**, while the seven citable subjects hold **30** — concentrated in two cells, with four
cells at <=2. Most of the miss detector is locked behind the vintage flag.

So replacement now buys two things where it previously bought one: a citable backend row, **and**
human-thread coverage the citable set demonstrably lacks. The keep decision predates this data and
is superseded by it.

## The five

| Cell | Subject | merged | Human threads |
|---|---|---|---|
| backend S | jellyfin#12834 | 2026-05-21 | 8 of 8 |
| backend M | grafana#124181 | 2026-05-08 | 5 of 6 |
| backend L | PostHog#52408 | 2026-05-06 | 15 of 19 |
| contract L | PostHog#55149 | 2026-05-06 | 20 of 35 |
| app-ui M | immich#24627 | 2026-05-11 | 8 of 8 |

Replacements come from the [[dcc-2gu2]] screen candidate list, built per METHODOLOGY-v2 §4c + the §4b
spine: merged >=2026-06-01, >=5 **human** threads, per-thread admission with bot threads segregated
into the second axis ([[dcc-qwt3]]), airtightness verified per build.

**Retire, don't delete.** The five become probe material — §5's retirement policy: matched vintage
pairs measure memorization effect size, and same-repo pairs (jellyfin→jellyfin, grafana→grafana...)
are exactly the matched pairs it calls for. Mark each retired fixture's status; their audited thread
sets stay with them.

## Done 2026-08-20

| Cell | was | is now | merged | admitted human threads |
|---|---|---|---|---|
| backend S | jellyfin#12834 | **mattermost#37874** | 2026-08-14 | 6 (2 reviewers) |
| backend M | grafana#124181 | **grafana#125982** | 2026-06-18 | 20 (4 reviewers) |
| backend L | PostHog#52408 | **jellyfin#17044** | 2026-07-05 | 8 (2 reviewers) |
| contract L | PostHog#55149 | **PostHog#67924** | 2026-07-16 | 62 (1 reviewer — see caveat) |
| app-ui M | immich#24627 | **immich#29965** | 2026-08-10 | 19 (2 reviewers) |

Twelve active subjects, nine distinct repos, at most two per repo — diversity preserved.
`vintage.check_pooling()` passes on the backend row **and on the whole active corpus**.

### Two places the build disagreed with the screen

- **backend L: PostHog#59630 was disqualified after being built.** Its CHECKPOINT diff is
  contract-crossing (10 frontend files, 19 backend) although the merged PR is backend-only — the
  modules moved from `ee/tasks/subscriptions/` to `products/exports/backend/` during review.
  Contract L was taken and PostHog was at its cap, so it has no cell. Kept as probe material. The
  general problem — app_type typed from the merged PR while a tool reviews the checkpoint, which
  also mislabels two ALREADY-SCORED subjects — is filed as [[dcc-acw2]].
- **backend S: the screen's "no viable candidate" was wrong.** A fresh complete jellyfin sweep still
  topped out at 4 human threads, but a complete window-sliced mattermost sweep found #37874, which
  appears only in the `2026-08-11..2026-08-20` window — it did not exist when the screen ran nine
  days earlier. The screen's own advice ("re-screen before deciding — the window shifts") paid off.

### backend L came out of a bug, not a candidate list

Every jellyfin build produced a checkpoint diff of **zero files** and a fixture with zero admitted
threads, written to disk without complaint. `build_pooled_fixture.py` took the merge base against
the live tip of `baseRefName`; jellyfin merges without squashing, so after merge a PR's own commits
are ancestors of `master` and the compare is empty. Fixed to use the PR's own base commit — verified
identical on all 16 pre-existing fixtures, and it turned jellyfin#17044 from 0 files into 19. Empty
is now a hard failure (`require_nonempty_diff`, tested), the tenth instance of the standing rule.

### Caveat that must travel with any contract-L result

**PostHog#67924 has ONE distinct human reviewer at admission** (`vdekrijger`, 62 of 62). The screen
saw two on the raw thread set; admission collapsed it. That misses [[dcc-2gu2]]'s >=2-reviewer
preference and makes one person the author of 62 of the corpus's human threads. Kept because the
alternates were mattermost#36338 (114 files, +15205/-1322 at the checkpoint) or an immich subject
over the 2-per-repo cap.

### Retirement and the matched pairs

Five fixtures carry `role: retired-probe` with `retired.replaced_by`; thread sets and scoring stay
with them. Four same-repo, same-cell matched vintage pairs are now runnable — grafana#124181 ↔
#125982, immich#24627 ↔ #29965, PostHog#55149 ↔ #67924, PostHog#52408 ↔ #59630 (both probe-only).
backend S crosses repos and is NOT a pair; jellyfin#12834 ↔ #17044 is the partial substitute (same
repo, S vs L).

### The thing this does not buy

[[dcc-60qk]]: vintage is keyed on `merged_at`, and **five active subjects were created and reviewed
inside the window** despite merging outside it — efcore#34127's PR was open for nearly two years.
Under a `pr_created_at` key the citability claim above collapses again. Filed, not fixed.

## Acceptance

- [x] 5 replacement subjects built and airtight per §4b, each merged >=2026-06-01 with >=5 human
      threads at admission
- [x] The backend row is citable: `vintage.check_pooling()` passes on a backend figure
- [x] The five retired fixtures marked as probe material (role recorded in the fixture), not deleted
- [x] `CANDIDATES.md` grid updated; the 218-raw/120-admitted corpus figures superseded where cited
- [x] Matched vintage pairs recorded where the replacement is same-repo, so the memorization probe
      becomes runnable

## Summary

**Completed 2026-08-20** — Replaced all five in-window subjects; every active cell now merges >=2026-06-01 and
`vintage.check_pooling()` passes on the backend row and on the whole corpus.

Two departures from the screen: PostHog#59630 was disqualified after being built (contract-crossing
at its checkpoint though backend when merged — filed as dcc-acw2), and backend S was found after all
(mattermost#37874, which did not exist when the screen ran nine days earlier).

backend L required fixing a silent bug: the merge base was taken against the live tip of the base
branch, so on a repo that merges without squashing every build produced a zero-file checkpoint diff
and a fixture with zero admitted threads, written to disk without complaint. Now uses the PR's own
base commit — verified identical on all 16 prior fixtures — and an empty diff is a hard failure.

Five fixtures retired as probe material with four same-repo, same-cell matched vintage pairs
recorded. Caveat carried into CANDIDATES.md: PostHog#67924 has one distinct human reviewer at
admission, missing dcc-2gu2's soft bar.

Filed dcc-60qk: the citability this buys is keyed on `merged_at`, and five active subjects were
public and under review inside the window regardless.
