---
# dcc-wx8i
version: 1
title: Rename decaf-review → decaf-quality
status: completed
type: task
priority: normal
created_at: 2026-06-20T18:27:55Z
updated_at: 2026-06-20T19:47:57Z
parent: dcc-2ia9
order: a0
---

## Description
Rename the active code-review plugin from decaf-review to decaf-quality: directory, plugin.json `name`, every internal `/decaf-review:` skill ref and `decaf-review:` agent ref → `decaf-quality:`, README title, and the marketplace.json entry (source path + name).

## Verification
- [x] `grep -r 'decaf-review' decaf-quality/` returns nothing
- [x] plugin.json name = decaf-quality
- [x] marketplace.json entry points at ./decaf-quality
- [x] directory renamed decaf-review → decaf-quality

## Summary of Changes
- `git mv decaf-review decaf-quality` (history preserved).
- Rewrote all 8 files referencing `decaf-review` → `decaf-quality`: plugin.json name, skill invocations (`/decaf-quality:*`), agent refs (`decaf-quality:*`), README title, persona-authoring convention.
- Updated `.claude-plugin/marketplace.json`: plugin `name` and `source` → decaf-quality.
- Verified no `decaf-review` references remain in the plugin; both JSON files parse.
- Out of scope (handled by dcc-tmle): top-level CLAUDE.md/README still reference the old name.
