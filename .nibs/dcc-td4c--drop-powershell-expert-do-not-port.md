---
# dcc-td4c
version: 1
title: Drop powershell-expert (do not port)
status: completed
type: task
priority: normal
created_at: 2026-06-21T09:09:39Z
updated_at: 2026-06-21T10:17:13Z
parent: dcc-f5dj
order: as
---

## Description

Decision: powershell-expert is NOT ported into the vnext layout (single language-domain skill, out of scope for the decaf suite — resolves the kk29 open question). No action beyond excluding it from the port; remove old/decaf/skills/powershell-expert when old/ is pruned.

## Verification

[ ] powershell-expert absent from all shipping plugins
[ ] removed when old/ is cleaned up

## Summary

powershell-expert dropped: not ported into any shipping plugin; remains in old/ until pruned. Verified absent from decaf-*. Committed (decision recorded in d7adc4c).
