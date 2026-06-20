---
# dcc-74g6
version: 1
title: Port refactor + resolve-refactor
status: todo
type: task
priority: normal
created_at: 2026-06-20T18:27:56Z
updated_at: 2026-06-20T18:27:57Z
parent: dcc-2ia9
blocked_by:
    - dcc-wx8i
order: ak
---

## Description
Bring `refactor` and its analysis agents (`structural-analyst`, `coherence-analyst`) from old/decaf-review into decaf-quality. Rename `handle-refactoring` → `resolve-refactor`. Align to the new conventions; reconcile the `.refactoring-plans/` artifact with the plugin's report style.

## Verification
- [ ] refactor + resolve-refactor skills present
- [ ] structural-analyst + coherence-analyst agents present, aligned
- [ ] artifact / report format reconciled
- [ ] invocations namespaced /decaf-quality:
