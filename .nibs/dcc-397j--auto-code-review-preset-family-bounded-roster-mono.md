---
# dcc-397j
version: 1
title: 'auto-code-review: preset-family-bounded, roster-monotone re-reviews'
status: completed
type: feature
created_at: 2026-08-21T20:33:18Z
updated_at: 2026-08-21T20:34:55Z
order: zzzzz
---

An auto-deliver --review bugs run re-reviewed at review roster=6 — more seats and a costlier models policy than the first pass, triggered by a delta-size heuristic that ignores the caller's preset. Operator decision (2026-08-21): re-reviews narrow within the caller's preset family, roster is monotone non-increasing, and escalation needs a named trigger.

- [x] Step 5.4: rewrite the reReviewPreset ladder — monotonicity ceiling max(3, first-pass resolved roster), named-trigger escalation (closed set), bugs family defaults to the seat, wave family defaults to review roster=4, uncapped rung removed
- [x] Step 2 (line 76): rewrite the fossil rationale — WAVE findings need the screen/validation funnel; the solo seat is exempt by self-calibration (iteration 1 under bugs already feeds the fixer directly)
- [x] Argument-parsing note (line 21): re-reviews narrow within the caller's family and never exceed its roster
- [x] --report ledger (line 42): record the escalation trigger alongside the delta classification
- [x] Notes bullet: update the re-review summary line
- [x] evidence stays norm in re-review waves (dcc-sk3k); state it explicitly
- [x] Cherry-pick to main so the skill surface stays aligned

## Key Decisions
- Fix-delta size alone never raises the roster; a risky delta changes WHICH specialists fill the capped slots (gated dispatch + ranking), not how many.
- Trigger set is closed: concurrency/locking, trust boundary, data mutations in the fix delta; a regression found by a prior re-review; a fix that failed verification and was re-applied.
- Follow-up candidate (not filed yet): tuning-branch benchmark arm measuring seat-vs-wave on fix deltas specifically.

## Summary

**Completed 2026-08-21** — Applied. Re-reviews now narrow within the caller's preset family under two binding rules: roster monotonicity (never above max(3, first-pass resolved roster), read from the first review file's header) and named-trigger escalation (closed set: concurrency/locking, trust boundary, or data mutations in the fix delta; a regression found by a prior re-review; a fix that failed verification and was re-applied). bugs callers re-review with the seat itself, escalating only to bugs roster=3; wave callers default to review roster=4, escalate to review roster=min(6, first-pass N); the uncapped rung is removed; delta size alone never escalates. evidence stays norm in re-review waves (dcc-sk3k). The fossil rationale is rewritten: wave findings need the screen/validation funnel; the solo seat is exempt by self-calibration. Cherry-picked to main so the skill surface stays aligned. Follow-up candidate noted in Key Decisions: benchmark arm measuring seat-vs-wave on fix deltas.
