---
# dcc-n5h2
version: 1
title: 'Single-seat bugs: exploration breadth — why superpowers'' seat finds more per cell on large diffs'
status: in-progress
type: research
priority: normal
created_at: 2026-08-18T08:40:37Z
updated_at: 2026-08-19T11:11:24Z
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
