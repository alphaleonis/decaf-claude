---
# dcc-o5n2
version: 1
title: 'Fix skill inconsistencies: spec hint, erinra setup, integration-branch default'
status: completed
type: task
created_at: 2026-09-25T20:08:44Z
updated_at: 2026-09-25T20:08:49Z
order: zzzzzzk
---

Fix three inconsistencies found while writing the README argument lists (dcc-m0rt), plus one found while fixing them.

- [x] code-review argument-hint: --spec accepts <path|work-item-ID>, as the body says
- [x] erinra setup command: -s user was passed to erinra serve (which rejects it) instead of claude mcp add; add --web, which memory-dashboard needs
- [x] auto-deliver: default integration branch was the repo default branch, contradicting its never-merge-into-main rule
- [x] batch-dev: --base-branch always created a new branch, but auto-deliver passes an existing integration branch

## Summary

**Completed 2026-09-25** — - code-review's argument-hint now shows --spec <path|work-item-ID>, matching the skill body.
- The erinra setup command is now `claude mcp add -s user erinra -- erinra serve --web` in all 8 places (CLAUDE.md, README, four decaf-memory skills, the SessionStart hook). The old form gave `-s user` to `erinra serve`, which fails with "unexpected argument '-s'". The new form matches the operator's working registration (user scope, `serve --web`).
- auto-deliver's default integration branch is now `deliver/<slug>`, derived from the plan reference so every lap resolves the same branch. It refuses a --base-branch that names the repo's default branch.
- batch-dev's --base-branch now reuses an existing branch instead of always running `git switch -c`, and also refuses the default branch.
