---
# dcc-u3vq
version: 1
title: Port note → capture (decaf-plan)
status: todo
type: task
priority: normal
created_at: 2026-06-21T09:09:40Z
updated_at: 2026-06-21T09:55:36Z
parent: dcc-f5dj
order: aw
---

## Description

Move old/decaf/skills/note into decaf-plan, **renamed `capture`** (invokes as /decaf-plan:capture). Lightweight quick-capture: jot a follow-up idea/task as a work-item draft (nib) without interrupting current work. Its output is a work item — plan's currency — so it lives alongside the planning skills; no standalone core plugin. Name rationale: 'note' undersold it (sounds like freeform note-taking); 'capture' is the low-friction grab-this-thought action.

On port: update frontmatter `name`, H1, and self-references to capture; preserve the nibs-based capture behavior; rewrite the description in plain language; conventions-symlink if it references any shared convention.

## Verification

[ ] decaf-plan/skills/capture/SKILL.md present; name=capture, H1 updated
[ ] no `note` skill-name references remain in the ported skill
[ ] behavior preserved (creates a work-item draft without interrupting)
[ ] listed in decaf-plan/README.md and the top-level docs
