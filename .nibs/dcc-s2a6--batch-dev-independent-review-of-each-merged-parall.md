---
# dcc-s2a6
version: 1
title: 'batch-dev: independent review of each merged parallel cluster before the next starts'
status: completed
type: task
priority: normal
estimate: m
created_at: 2026-09-24T17:02:59Z
updated_at: 2026-09-24T18:48:48Z
parent: dcc-fq6j
order: az
---

## Context

batch-dev's parallel mechanisms (Phase 6b fan-out, 6c workflow, 6d agent team) self-review inline inside their worktrees, because auto-code-review runs from the main context and cannot be invoked from a worktree. Parallel work therefore merges onto the batch branch without an independent reviewer, dropping the separation between whoever wrote the code and whoever grades it, the one point every camp in the research agrees on. batch-dev and auto-deliver both note that these clusters produce no session report under `--report`.

## Evidence (refine, 2026-09-24)

- **code-review cannot see committed work today.** Its local mode reviews uncommitted changes (`git diff HEAD`, `git diff --cached`), a path's uncommitted changes, or, when nothing is uncommitted, the last commit only. Phase 7 merges each lane as its own commit, so a cluster is several commits.
- **A soft reset turns the merged cluster back into staged changes.** Scratch-repo test: two lanes merged onto the batch branch (four commits), then `git reset --soft <pre-merge tag>` left both lanes' files staged, and `git diff HEAD` showed the whole cluster. Phase 7 step 1 already creates that tag (`batch-{slug}-premerge-{cluster}`).
- **auto-code-review needs nothing new.** Its snapshots, repair rounds, fix-verifier and re-reviews all work on uncommitted changes, exactly as for a series nib.

## Decisions

- **When:** in Phase 7, after all of a cluster's merges pass build and tests (step 4), before cleanup (step 6) and before the next cluster starts.
- **How:** `git reset --soft batch-{slug}-premerge-{cluster}`, then run `/decaf-quality:auto-code-review` on the staged cluster, forwarding the caller's `--review` verbatim, `--tracker`, `--models`, `--unattended` and `--report` as Phase 6a does. No `--implementer`: a cluster has several authors, so repairs go to a fresh fixer.
- **Spec:** one file, `.decaf/batch-dev/specs/cluster-<n>.md`, holding every cluster item's `read` output under its own heading (Azure DevOps items included, with their Acceptance Criteria field), passed as `--spec`.
- **Commit:** after the review, the conductor commits the cluster once, code plus tracker files, naming every nib in the message. History becomes one commit per parallel cluster instead of per lane; the pre-merge tag stays as the recovery point.
- **Lane self-review stays** as a cheap first check.
- **Session reports:** parallel clusters now produce one per cluster review, so the "series clusters only" caveats in batch-dev (Phase 6a note, `--report` argument, Phase 8) and auto-deliver (EXECUTE, STOP) are updated.

## Acceptance

- [x] [run] `sed -n '/^## Phase 7/,/^## Phase 8/p' decaf-build/skills/batch-dev/SKILL.md | grep -c 'auto-code-review'` — expect: at least 1 (Phase 7 runs the review)
- [x] [run] `sed -n '/^## Phase 7/,/^## Phase 8/p' decaf-build/skills/batch-dev/SKILL.md | grep -c 'reset --soft'` — expect: at least 1 (the cluster is unstacked onto the pre-merge tag before review)
- [x] [run] `grep -c 'covers series clusters only' decaf-build/skills/batch-dev/SKILL.md` — expect: `0`
- [x] [run] `grep -c -E 'produce none|left uncovered' decaf-build/skills/auto-deliver/SKILL.md` — expect: `0`
- [x] [manual] A fresh agent walking batch-dev through a two-lane fan-out cluster merges both lanes with build and tests after each, soft-resets to the pre-merge tag, runs auto-code-review with a spec file holding both items and the forwarded flags, and commits the cluster once. Reason: the skill is prose an agent executes; no command can run it, so the check is an agent walkthrough.

## Notes
- Phase 7 gains step 6: after every merge in a parallel cluster passes build and tests, `git reset --soft` to the cluster's pre-merge tag, write one spec file holding every cluster item, run auto-code-review with the caller's `--review` and the forwarded `--tracker`, `--models`, `--report` and `--unattended` (no `--implementer`), then commit the cluster once and close its nibs. Cleanup moves to step 7.
- The nib-status rule now closes a nib after its work is committed: Phase 6a step 4 for a series nib, Phase 7 for a parallel cluster. 6c and 6d point at Phase 7 for review, commit and close.
- The "series clusters only" caveats are gone from batch-dev (the `--review` and `--report` arguments, the Phase 6a note, Phase 8, the Notes) and from auto-deliver (EXECUTE, STOP). `conventions/artifacts.md` lists the cluster spec file.
- Tested with fresh agents. Old text: only the lane that wrote the code reviewed it, the caller's `--review` was never applied to the cluster, and `--report` produced nothing for it. New text: an independent review after both merges pass, the review spec applied once to the merged cluster, one commit per cluster with the tag kept, and one session report per cluster.

## Summary

**Completed 2026-09-24** — batch-dev Phase 7 now reviews each merged parallel cluster independently before the next starts: after the merges pass build and tests it soft-resets to the cluster's pre-merge tag, runs auto-code-review on the staged cluster with a spec file holding every cluster item and the caller's flags, then commits the cluster once and closes its nibs. Parallel clusters now produce session reports, so the series-only caveats in batch-dev and auto-deliver are gone. Verified by four acceptance greps and before/after agent walkthroughs.
