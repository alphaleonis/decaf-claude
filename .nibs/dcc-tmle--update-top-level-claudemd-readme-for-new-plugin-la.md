---
# dcc-tmle
version: 1
title: Update top-level CLAUDE.md + README for new plugin layout
status: completed
type: task
priority: normal
created_at: 2026-06-20T18:27:57Z
updated_at: 2026-06-20T21:55:35Z
parent: dcc-33j0
blocked_by:
    - dcc-s8di
order: ak
---

## Description
Update the repo's top-level CLAUDE.md and README.md to describe the new layout (decaf-build, decaf-quality; note plan/core/memory/protection still pending). Partial until the deferred plugins are done.

## Verification
- [ ] CLAUDE.md plugin table reflects decaf-build + decaf-quality
- [ ] README install / usage updated
- [ ] no stale decaf-dev / decaf-review references (except historical)

## Summary

Rewrote top-level README.md + CLAUDE.md from the old six-plugin layout to the three shipping vnext plugins (decaf-quality, decaf-build, decaf-plan): current skill/agent rosters, install/usage, directory structure, conventions table, and the conventions-symlink pattern. Noted core/memory/protection as deferred (under old/). No stale decaf-dev/review/planning refs except one historical note. Committed 05ddc99.
