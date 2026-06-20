---
# dcc-74g6
version: 1
title: Port refactor + resolve-refactor
status: completed
type: task
priority: normal
created_at: 2026-06-20T18:27:56Z
updated_at: 2026-06-20T20:17:18Z
parent: dcc-2ia9
blocked_by:
    - dcc-wx8i
order: ak
---

## Description
Bring `refactor` and its analysis agents (`structural-analyst`, `coherence-analyst`) from old/decaf-review into decaf-quality. Rename `handle-refactoring` → `resolve-refactor`. Align to the new conventions; reconcile the `.refactoring-plans/` artifact with the plugin's report style.

## Verification
- [x] refactor + resolve-refactor skills present
- [x] structural-analyst + coherence-analyst agents present, aligned
- [x] artifact / report format reconciled (`.refactoring-plans/` kept — distinct from `.code-reviews/`)
- [x] invocations namespaced /decaf-quality:

## Summary of Changes
- Copied `conventions/refactoring.md` + `conventions/code-quality/` (baseline/coherence/drift) into `decaf-quality/conventions/` (keeps the plugin standalone).
- **structural-analyst + coherence-analyst** (ported via subagent, reviewed): persona-aligned frontmatter (`model: inherit`, free colors lime/maroon), identity + `## Scope Boundary` naming each other. **Preserved the star / impact×effort opportunity model** — refactor is improvement-prioritization, NOT defect detection, so deliberately NOT forced into the code-review severity/confidence model. Marked as standalone refactoring-analysis agents — NOT added to the code-review orchestrator roster / Domain Ownership Matrix.
- **refactor skill**: ported; `@../../conventions/refactoring.md`, `/decaf-quality:` namespace, `decaf-quality:structural-analyst`/`coherence-analyst` refs, star/value-matrix consolidation, `.refactoring-plans/` artifact preserved.
- **resolve-refactor** (← handle-refactoring): reshaped to the `resolve-*` pattern with an `auto` mode + Verify-First rule; kept Apply / Apply (Incremental) / Skip / Dismiss / Defer; state `.refactoring-plans/.resolve-refactor-state.json`.
- **Fixed a dangling `@work-items.md` include in `resolve-coverage-review`** (introduced in dcc-09q5): switched to inline tracking-system detection, matching `resolve-code-review` and `resolve-refactor` — decaf-quality detects the tracker inline, it does not bundle a work-items.md convention.

Notes: README roster deferred to dcc-bm6k (A4). @-paths fixed (skills `@../../conventions/`, agents `@../conventions/`); all resolve to existing files.
