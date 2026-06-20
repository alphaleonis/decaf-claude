---
# dcc-but3
version: 1
title: Port & align remaining planning skills
status: todo
type: task
priority: normal
created_at: 2026-06-20T18:33:58Z
updated_at: 2026-06-20T19:26:06Z
parent: dcc-9olo
blocked_by:
    - dcc-owjh
order: ak
---

## Description
Port the remaining planning skills from old/decaf-planning into decaf-plan, applying the agreed renames and rewriting each skill's `description:` in plain language (see #dcc-kk29). Behavior unchanged — do NOT add unattended / loop modes here (that is the loop design nib's scope, #dcc-c7gu).

Renames (port + rename together):
- write-a-prd → `draft-spec`
- prd-to-plan → `draft-plan`
- design-an-interface → `explore-designs`
- close-plan → `close-out`
- keep as-is: research, grill-me, breakdown-phase
(architecture-review / resolve-architecture-review handled in sibling task #dcc-jje9.)

## Verification
- [ ] /decaf-plan: has draft-spec, draft-plan, explore-designs, close-out, research, grill-me, breakdown-phase
- [ ] no old names remain (write-a-prd, prd-to-plan, design-an-interface, close-plan)
- [ ] each skill's `description:` rewritten in plain language
- [ ] shared conventions/work-items.md references intact
- [ ] no unattended / loop behavior introduced
