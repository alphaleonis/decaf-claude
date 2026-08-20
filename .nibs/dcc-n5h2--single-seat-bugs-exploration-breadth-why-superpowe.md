---
# dcc-n5h2
version: 1
title: 'Single-seat bugs: exploration breadth — why superpowers'' seat finds more per cell on large diffs'
status: completed
type: research
priority: normal
created_at: 2026-08-18T08:40:37Z
updated_at: 2026-08-20T06:41:14Z
parent: dcc-hyxw
order: axV
---

The one gap left between the single-seat `bugs` and superpowers' agent that is not disposition:
on prometheus (library/L, deep pool) superpowers' seat *finds* ~5 real defects per cell to ours ~3.7;
on the small non-library diffs of [[dcc-nbgl]] the two are equal (3.8 vs 3.7). Three brief
revisions ([[dcc-1sbc]], [[dcc-pulk]], [[dcc-ce0m]]) moved parking rules and left per-cell yield
flat (3.0/3.0/3.0 on prom); the transcripts showed the seat's *probing choices* vary more between
repeats of one brief than between briefs (efcore e02: SQL Server SQL generated in 2/2 v1 cells,
0/5 afterwards). This is an exploration-breadth question, not a prompt-wording one.

## Questions to answer before designing anything

- What does superpowers' agent do in its ~42 turns that ours does not in ~38, on prometheus?
  Diff the two seats' shell-call sequences on the same cells (transcripts on the machine that
  ran them; `v2/scoring/cost_emit.py` classifies calls) — is it breadth of files read, more
  execution probes, or reporting 19 items keeping it looking longer?
- Does the `narrow` framing ("defect list short enough to read completely") shorten exploration
  once a first Critical is confirmed? Testable: same seat, `reach=norm`, on prom ×3, count real
  defects *found* per cell (not reported).
- Would a cheap second-pass "what did you not look at" turn (no roster, same seat) recover the
  ~1.3/cell without a wave? Design only after the first two questions.

Rules that bind: 3 repeats minimum on prom (2 could not separate brief effect from seat variance);
never compare a changed brief against old cells; the class table + real-defect pool are the
readouts, not precision.

## Acceptance

- [ ] Transcript comparison written up (superpowers seat vs solo-reviewer, prom r1/r2, per-turn)
- [ ] One hypothesis chosen and stated with the measurement that would confirm or refute it
- [ ] If a brief/skill change results: new arm id, 3 repeats, fold-in; else close with the
      finding recorded

## Summary

**Completed 2026-08-20** — The measurable half is answered; write-up in v2/analysis/SINGLE-SEAT-FINDINGS.md.

Question 1 (what superpowers' agent does that ours does not) is answered NEGATIVELY, which is the
useful result: it is not the brief, not the model, and not reach.

- Not the brief. decaf's solo-reviewer brief is 1,916 words to superpowers' 552 and runs ~2:1 against
  searching, but it NAMES the exact defect class it missed ("three-valued logic, coercions, operator
  semantics where the language has traps" = efcore e02) while superpowers' brief never mentions null
  semantics and its agent found it. Coverage is not the gap.
- Not the model. Every cell's modelUsage: both are claude-opus-5 at 100% of cost, one agent each.
- Not reach. dcc-tmz2 measured identical exploration breadth at both settings.

What it IS: detection is stochastic. e02 is found by ~1 cell in 3 in EVERY arm. Repeats recover
0.05-0.19 of the pool, so repeats are a lever with a known exchange rate where three brief revisions
produced 3.0/3.0/3.0.

Bonus measurement, from the wave cells: quick-reviewer is the quietest always-on agent (3.1
clusters/cell) and the most accurate (45% real), and out-contributes its floor partner
broad-reviewer on sole-real findings (0.79 vs 0.50) at lower cost. Of the 16 clusters it alone found,
12 are defect-class. NOT actionable yet — 14% of wave findings carry no agent attribution, and
sole-finder-within-a-cell bounds contribution above rather than measuring drop cost.

Question 3 (a cheap second-pass "what did you not look at" turn) is untouched and remains the live
idea, now better motivated: if detection is stochastic rather than systematic, a second pass is the
mechanism that matches the diagnosis.
