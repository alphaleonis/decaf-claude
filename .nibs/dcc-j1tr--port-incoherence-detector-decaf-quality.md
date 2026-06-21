---
# dcc-j1tr
version: 1
title: Port incoherence-detector → coherence-audit (decaf-quality)
status: todo
type: task
priority: normal
created_at: 2026-06-21T09:09:39Z
updated_at: 2026-06-21T09:48:23Z
parent: dcc-f5dj
order: aV
---

## Description

Move old/decaf/skills/incoherence-detector into decaf-quality, **renamed `coherence-audit`** (invokes as /decaf-quality:coherence-audit). A codebase audit that finds where docs / specs / comments / config / names / versions disagree with the actual code, then interactively resolves each (update docs / flag code / accept) and reports. Name rationale: `-detector` was a device/persona noun; `coherence-audit` is the activity (audit) over the domain (coherence), positive framing.

On port: update frontmatter `name`, H1, and self-references to coherence-audit; rewrite the description in plain language; apply the conventions-symlink pattern if it references any shared convention.

Note: this skill both DETECTS and RESOLVES (Phases 4–5) in one go — unlike code-review / resolve-code-review which split those. Port as-is; a future split into coherence-audit + resolve-coherence-audit is possible but out of scope here.

## Verification

[ ] decaf-quality/skills/coherence-audit/SKILL.md present; name=coherence-audit, H1 updated
[ ] no `incoherence-detector` references remain
[ ] convention references plugin-local (symlinked), not escaping
[ ] listed in decaf-quality/README.md and the top-level docs
