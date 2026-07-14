---
# dcc-02j1
version: 1
title: batch-dev fan-out worktrees branch from origin/HEAD, not the batch branch
status: completed
type: bug
priority: high
created_at: 2026-07-14T11:13:03Z
updated_at: 2026-07-14T11:20:09Z
order: zk
---

## Description

`batch-dev` Phase 6b fans out `Agent` calls with `isolation: "worktree"` and assumes each
worktree inherits the **batch branch** (created off current HEAD in Phase 6 Common rules).

It does not. Per the Claude Code docs (code.claude.com/docs/en/worktrees.md) and confirmed
empirically in this repo: **subagent worktrees branch from the repository's default branch
(`origin/HEAD`), NOT the parent's current HEAD**, unless `worktree.baseRef` is set to `"head"`.

### Evidence (empirical, 2026-07-14)
Main tree on throwaway branch `wt-base-test` @ `45d5a4d` (a marker commit NOT on main).
Spawned an `isolation: "worktree"` agent → it came up on `90638c1` (== `main`), with no
marker file; `git merge-base HEAD wt-base-test` = `90638c1` (i.e. based *before* the branch work).

### Impact
- Fan-out lanes build on the wrong base: they miss the batch branch's base commits (e.g. the
  `develop`/`integration` tip the batch was cut from) AND any prior cluster merged onto the batch branch.
- `auto-deliver` makes it worse: it passes `--base-branch integration` (a non-default branch), so the
  gap between the intended base and `origin/HEAD` (main) is exactly the divergence that corrupts merges.
- Phase 7 merges then either conflict, silently reintroduce stale default-branch state, or drop the
  intended base's commits. A real batch-dev session flagged this and had to self-correct/verify manually.

## Fix
- Phase 6b: conductor computes the batch-base SHA at fan-out and passes it to every lane; each lane
  re-anchors its fresh (empty) worktree onto that SHA as step 0 (`git reset --hard <base>` — safe, no
  work yet), verifying HEAD == base before doing anything.
- Rewrite the "Worktree mechanics" note to state the real base behavior + cite the docs + mention the
  optional `worktree.baseRef: "head"` project setting (skill must not depend on it).
- Phase 7: add a base-verification gate — assert each worktree branch descends from the batch base
  (`git merge-base --is-ancestor <base> <sha>`) before merging; rebase/reject if not.
- Apply the same caveat to Phase 6c (workflow) and 6d (team) worktree agents.

## Verification
- [x] Phase 6b instructs conductor to pass batch-base SHA and each lane to re-anchor + verify
- [x] "Worktree mechanics" note states origin/HEAD base behavior with doc reference
- [x] Phase 7 has an ancestry/base-verification gate before merge
- [x] Phase 6c/6d reference the same re-anchor requirement

## Summary

Fixed batch-dev's fan-out worktree base hazard. Root cause (confirmed via Claude Code docs + an empirical probe in this repo): `isolation: "worktree"` branches subagent worktrees from the repo default branch (origin/HEAD), not the parent's current HEAD / the batch branch. Fan-out/workflow/team lanes silently started on main, missing the batch base and any prior merged cluster, so Phase 7 merges would conflict or drop the intended base.

Changes to decaf-build/skills/batch-dev/SKILL.md: Phase 6 common rules note the base mismatch; Phase 6b captures BASE_SHA and each lane re-anchors via `git reset --hard {BASE_SHA}` as step 0 + verifies HEAD; worktree-mechanics note documents the origin/HEAD base and the `worktree.baseRef: "head"` override; Phase 6c/6d cross-reference the re-anchor; Phase 7 gains a `git merge-base --is-ancestor` base-ancestry gate before merging. Stored an erinra gotcha memory for the underlying Claude Code behavior.
