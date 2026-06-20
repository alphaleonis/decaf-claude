---
# dcc-09q5
version: 1
title: Port coverage-review + add resolve-coverage-review
status: completed
type: task
priority: normal
created_at: 2026-06-20T18:27:56Z
updated_at: 2026-06-20T19:56:24Z
parent: dcc-2ia9
blocked_by:
    - dcc-wx8i
order: aV
---

## Description
Bring `coverage-review` and the `coverage-reviewer` agent from old/decaf-review into decaf-quality. Rename `handle-coverage` → `resolve-coverage-review`. Align both skills and the agent to the new plugin's consolidation, severity, and persona-authoring conventions.

## Verification
- [x] coverage-review + resolve-coverage-review skills present
- [x] coverage-reviewer agent present, persona aligned
- [x] skills follow the consolidation / severity conventions
- [x] invocations namespaced /decaf-quality:

## Summary of Changes
- Copied `conventions/coverage-config.md` → `decaf-quality/conventions/coverage-config.md` (keeps the plugin standalone).
- **coverage-reviewer agent** — persona-aligned per persona-authoring.md: dispatch gate, scope boundary (names owning personas), In-Scope `COVERAGE_*` category table, **impact-only severity** table, the **five confidence anchors** restated for the coverage domain with a domain bias (lenient on error/security gaps, strict on trivial), standard JSON output contract (+ `pre_existing`), Considered But Not Flagged, `<verification_checkpoint>`. Split the old severity+confidence conflation into the two orthogonal axes. `color: indigo` (free).
- **coverage-review skill** — ported: `@../../conventions/coverage-config.md`, `/decaf-quality:` namespace, `decaf-quality:coverage-reviewer` agent ref, `COVERAGE_*` categories + confidence in the report, pointer to resolve-coverage-review.
- **resolve-coverage-review** (← handle-coverage) — reshaped to the `resolve-*` pattern: added an `auto` mode and a **Verify-First rule** (re-check gaps; on a genuine-bug test failure, ignore the test + defer rather than revert or leave the suite red), state file `.resolve-coverage-state.json`, `/decaf-quality:` namespace.

Design notes:
- `coverage-reviewer` is a standalone agent invoked by the coverage-review skill — deliberately NOT added to the code-review orchestrator's Step 2b gate table or the Domain Ownership Matrix (it is not a diff-review persona).
- README roster update deferred to dcc-bm6k (A4).
