---
# dcc-wx8i
version: 1
title: Rename decaf-review → decaf-quality
status: todo
type: task
created_at: 2026-06-20T18:27:55Z
updated_at: 2026-06-20T18:27:55Z
parent: dcc-2ia9
order: a0
---

## Description
Rename the active code-review plugin from decaf-review to decaf-quality: directory, plugin.json `name`, every internal `/decaf-review:` skill ref and `decaf-review:` agent ref → `decaf-quality:`, README title, and the marketplace.json entry (source path + name).

## Verification
- [ ] `grep -r 'decaf-review' decaf-quality/` returns nothing
- [ ] plugin.json name = decaf-quality
- [ ] marketplace.json entry points at ./decaf-quality
- [ ] directory renamed decaf-review → decaf-quality
