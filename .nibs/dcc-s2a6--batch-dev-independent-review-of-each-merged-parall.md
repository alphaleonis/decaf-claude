---
# dcc-s2a6
version: 1
title: 'batch-dev: independent review of each merged parallel cluster'
status: draft
type: task
priority: normal
estimate: m
created_at: 2026-09-24T17:02:59Z
updated_at: 2026-09-24T17:03:11Z
parent: dcc-fq6j
order: az
---

## Description

batch-dev's parallel mechanisms (Phase 6b fan-out, 6c workflow, 6d agent team) self-review inline inside their worktrees, because auto-code-review runs from the main context and cannot be invoked from a worktree. Parallel work therefore merges onto the batch branch without an independent reviewer. That drops the separation between whoever wrote the code and whoever grades it, the one point every camp in the research agrees on. Phase 8 already admits these clusters get no session report under `--report`.

Proposal: in Phase 7, after a cluster's merges pass build and tests, run auto-code-review from the main context over that cluster's merged changes, before the next cluster starts.

## Open questions

- auto-code-review scopes to uncommitted changes or a path. How should it see work that is already merged: merge with `--no-commit`, pass the cluster's file list, or add a commit-range scope to auto-code-review/code-review?
- Which review preset fits a whole cluster's diff, and how does it interact with the `--review` spec the caller forwarded?
- Who commits review repairs on the batch branch? Conductor-owned commits apply here as in Phase 6a.
- With this in place, `--report` could cover parallel clusters too.
