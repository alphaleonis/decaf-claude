---
# dcc-gf1x
version: 1
title: 'auto-code-review: gate re-review on fixed-finding severity and named triggers, not raw diff size'
status: completed
type: task
created_at: 2026-08-29T18:46:46Z
updated_at: 2026-08-29T18:47:42Z
order: zzzzzk
---

## Problem

Step 5's re-review gate measured raw size: >=3 findings fixed OR >50 raw `git diff --stat` lines. Four flaws:

- Raw lines count comments/docs/whitespace — 50 lines of README or comment fixes dispatch a review wave.
- All fixes count equally — 3 spelling corrections trip the gate like 3 behavioral fixes.
- Size-only in the risky direction too — a 4-line concurrency/auth fix escapes re-review entirely, even though Step 5.4 names exactly those surfaces as escalation triggers.
- Measurement baseline ambiguous — `git diff --stat` vs HEAD counts the whole changeset under review, and cumulative counting keeps the gate open every round once crossed.

## Decision

Gate on units the loop already computes, per survey of peer autonomous-dev packs:

- **Severity of what was fixed** (BMAD `bmad-build-auto` step-04: follow-up review iff any `high` patched or >=2 `medium` patched): re-review when any Critical/High finding was fixed, or >=2 Medium. Language-independent; a spelling or comment fix is never High, so the false-positive cases vanish by construction.
- **Named triggers admit, not just escalate**: 5.4's trigger list now also warrants the re-review itself — risky-by-kind deltas re-review at any size.
- **Overflow clause only**: `execLines > 50` or `filesTouched > 3` (two-count idea from tag1 comprehensive-review's `TIER=tiny`: `<50 lines AND <=3 files`, lockfiles/vendor excluded), counting executable production lines only. Constants documented in the skill as unmeasured de-minimis bounds, revisit with `--report` data.
- **Fail toward review** (comprehensive-review default-promotes when measurement fails).
- **Per-round measurement** against a `ROUND_SNAPSHOT` taken before each fix dispatch.

Also surveyed: superpowers subagent-driven-development runs NO gate — every fix round gets an unconditionally dispatched but cheap scoped re-review (per-finding ADDRESSED/NOT verdicts + fix-diff breakage, cheap model). That rung idea is captured as a separate draft nib.

## Todo

- [x] Step 4: capture `ROUND_SNAPSHOT` before launching the fix subagent
- [x] Step 5 items 1-3: `sevFixed` + per-round delta classification (`execLines`, `filesTouched`, `triggers`)
- [x] Step 5 gate: trigger | Critical/High fixed | >=2 Medium fixed | overflow; Low/Minor-Consistency never count; fail toward review
- [x] Step 5.4: consume the item-3 classification instead of recomputing
- [x] Step 5 report line names the clause that fired
- [x] Ripples: overview bullet, Step 1 item 4 purpose clause, Step 1 item 7 ledger

## Summary

**Completed 2026-08-29** — Rewrote Step 5's gate: re-review is now warranted by a named 5.4 trigger, any Critical/High fixed, >=2 Medium fixed, or an overflow bound (>50 executable production lines or >3 files, per-round vs a new ROUND_SNAPSHOT captured in Step 4) — never by raw diff-stat size or bare fix count. Low/Minor-Consistency fixes never warrant; measurement failure fails toward review. The delta classification moved from 5.4 up to Step 5 item 3 and feeds both the gate and the preset choice; the re-review report line now names the clause that fired. Constants documented in the skill as unmeasured de-minimis bounds. Peer survey (BMAD bmad-build-auto severity gate, superpowers SDD unconditional cheap re-review, tag1 comprehensive-review two-count + fail-open) recorded in the body; the superpowers cheap-rung idea is captured as draft dcc-di3q.
