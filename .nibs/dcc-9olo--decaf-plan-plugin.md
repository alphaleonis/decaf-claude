---
# dcc-9olo
version: 1
title: decaf-plan plugin
status: completed
type: epic
priority: normal
created_at: 2026-06-20T18:33:58Z
updated_at: 2026-06-20T21:46:27Z
parent: dcc-33j0
order: aw
---

## Objective
Bring the planning plugin to parity with build/quality: rename decaf-planning → **decaf-plan**, apply the architecture analyze/resolve renames, and port/align the existing planning skills. **Face 1 only** — the autonomous-loop enablement (unattended modes, executable acceptance, verify/learn/replan) is owned by the loop design nib #dcc-c7gu, NOT here.

## Acceptance Criteria
- [ ] Plugin renamed decaf-planning → decaf-plan (identity, internal refs, marketplace)
- [ ] architecture-review + resolve-architecture-review in place (← improve-codebase-architecture / handle-architecture-improvements), aligned to the analyze/resolve convention
- [ ] research, write-a-prd, grill-me, prd-to-plan, breakdown-phase, close-plan, design-an-interface ported + aligned (as-is behavior; NO loop/unattended changes)
- [ ] README + metadata updated; all skills invoke as /decaf-plan:*

## Scope Boundaries
Touches: decaf-plan/ (new, from old/decaf-planning), marketplace.json. Off limits: loop enablement / unattended modes / auto-deliver (owned by #dcc-c7gu), build/quality internals, core/memory/protection.

## Summary

decaf-plan plugin delivered (Face 1). Ported all 9 skills from old/decaf-planning with the analyze/resolve naming convention and plain-language descriptions; added README, plugin.json metadata, and marketplace entry. Cross-cutting decision made during this epic: conventions are shared via symlinks (repo-root conventions/ canonical; each plugin symlinks in) because installed plugins cannot read files outside their own directory — documented in README.md + CLAUDE.md. decaf-quality retrofitted to the same pattern. Shipped in 2 commits on vnext: 9927773 (conventions-symlink infra) and 0503de7 (decaf-plan). main retrofit deliberately deferred (vnext supersedes those plugins).
