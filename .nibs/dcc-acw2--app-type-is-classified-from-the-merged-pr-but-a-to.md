---
# dcc-acw2
version: 1
title: app_type is classified from the merged PR, but a tool reviews the checkpoint — two scored subjects are mislabeled
status: todo
type: bug
created_at: 2026-08-20T19:18:01Z
updated_at: 2026-08-20T19:18:20Z
parent: dcc-ho2w
order: zzzz
---

`classify_candidate.sh` types a subject from `repos/<r>/pulls/<pr>/files` — the **merged** PR. A tool
reviews the **checkpoint** diff. Those are different file sets, and on three subjects they are
different application types. Measured 2026-08-20 by re-running the same regexes over
`compare <base>...<checkpoint>` for every fixture:

| Subject | declared | at the checkpoint | frontend / backend files |
|---|---|---|---|
| `PostHog/posthog#55149` | contract | **backend** | 0 / 7 |
| `mattermost/mattermost#36824` | contract | **backend** | 0 / 2 |
| `PostHog/posthog#59630` | backend | **contract** | 10 / 19 |

The other subjects agree.

## Why it matters

Both mislabeled incumbents are **already scored**, and both are the contract row: contract L and
contract M. The corpus's stated reason for that row — *"the only row that exercises multi-specialist
dispatch (`typescript-reviewer` + `dotnet-reviewer` together), because the defect lives in the
mismatch between two files in two languages"* (`analysis/CANDIDATES.md`) — is false for both of them
at the state the tools actually reviewed. Neither presented a reviewer with a single frontend file.
Any claim about how the contract row behaves currently rests on two backend changes and one genuine
contract change (`immich#28886`, contract S, 2/3).

`PostHog#59630` was caught before it cost anything: it was built as [[dcc-ryo4]]'s backend L
replacement, disqualified on this check, and kept only as probe material.

## Fix

- Classify from the **checkpoint** diff, not the merged PR — that is the artifact under review. The
  merged-PR type can stay as a recorded second field; it is what the screen can see cheaply before a
  fixture exists, so the screen keeps using it and the BUILD re-checks and records the real one.
- `build_pooled_fixture.py` writes `app_type_at_checkpoint` and fails loudly when it disagrees with
  the requested `app_type`, the same way the empty-diff guard now does.
- Re-decide the contract row. `mattermost#36824` at 2 files / 53 lines is thin as well as
  mislabeled; `PostHog#55149` is retired probe material already, so contract L is free.

## Acceptance

- [ ] `app_type_at_checkpoint` is computed at build time and stored on every fixture
- [ ] A build whose checkpoint type disagrees with the requested cell fails rather than warns
- [ ] The contract row is re-decided, or the two backend-at-checkpoint subjects are relabeled and
      the row's multi-specialist claim is withdrawn where it is cited
- [ ] `CANDIDATES.md`'s contract-row rationale matches what the subjects actually are
