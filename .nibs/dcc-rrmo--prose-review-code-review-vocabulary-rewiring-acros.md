---
# dcc-rrmo
version: 1
title: 'Prose review: code-review vocabulary rewiring across callers (5cd5e7a)'
status: completed
type: task
created_at: 2026-08-21T07:48:55Z
updated_at: 2026-08-21T07:55:37Z
order: zzzzs
---

## Description

[Describe what needs to be done]

## Verification

- [ ] [How to verify the work is complete]

## Summary

**Completed 2026-08-21** — Prose review of 5cd5e7a (+94b9408 code-review parts) delivered in session. Vocabulary rewiring is incomplete: root README examples still pass --review high/max (now silently reinterpreted as instructions); all hard-gated agent files + persona-authoring.md still key their gates on `max`; code-review-consolidation.md step 8 still says "skipped in low mode" and carries the pre-screen validation-selection rule Step 5.6 retired; decaf-quality/README decision 12 still describes mode keywords and claims evidence/reach are not settable; auto-code-review's Step 6 template has a literal `mid` and its Step 2 re-review cap line contradicts Step 5.4; code-review SKILL retains "mode keyword" intro (l.25), `mode<N>` (l.334), a duplicated stale example (l.911), the bugs-sp alias contradiction (l.16 vs l.129), and a stale models=low parenthetical (evidence=strong vs the wave's evidence=norm). Holistic: Step 4.95 skip condition is circular; Step 5.5 promotions have no screen score so Step 5.6 selection cannot classify them; bugs-path anchor-50 non-Critical findings have no action row in auto-code-review triage; solo-reviewer permits untagged CBNF process notes the orchestrator counts as malformed. Two British spellings introduced (unrecognised, honour). No fixes applied — findings reported to operator.
