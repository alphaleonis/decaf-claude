---
# dcc-d76g
version: 1
title: auto-deliver ends its turn at a lap boundary when the lap report precedes the next lap's dispatch
status: completed
type: bug
created_at: 2026-08-30T19:46:41Z
updated_at: 2026-08-30T19:47:53Z
order: zzzzzw
---

`/decaf-build:auto-deliver ix4f` (session `681b8c3c`, repo `~/code/nibs`, 2026-08-30) ended its
turn at two of three lap boundaries with nothing in flight, requiring an operator nudge each
time. The skill's `--unattended` contract says it must never stop between phases.

## Evidence — the ordering, not the intent, decides it

Three lap boundaries in one run, same skill, same context, no compaction:

| Boundary | Order of operations | Outcome |
|---|---|---|
| lap 1 → 2 (14:18Z) | `Agent(nibs-eh0a)` dispatched **at 14:17:59**, report written **at 14:18:15** | continued — the agent's task-notification woke the loop |
| lap 2 → 3 (16:10Z) | report written, **nothing dispatched** | dead stop; operator sent "continue with lap 3" 13 min later |
| lap 3 → 4 (18:40Z) | report written, **nothing dispatched** | dead stop; operator asked "Are you still working?" 45 min later |

The one boundary that worked did the next lap's dispatch **before** the lap report. That is the
whole difference. In this harness a turn that ends with text and no running background agent is
a stop regardless of what the text claims, so lap 1's success was an accident of ordering.

## Two distinct failure shapes

1. **Narrating instead of acting** (lap 2 → 3). Final sentence: *"Four laps remain: of2s → 2tkt
   → 5go2 → h7qy. Starting lap 3 now."* It had not started lap 3; the sentence replaced the tool
   call. The model later acknowledged this unprompted: *"no, I'd stopped — and that was my error,
   not a deliberate pause."*
2. **Manufacturing a gate** (lap 3 → 4). Final sentence: *"Lap 4 is the one that ships
   user-visible behavior change... Say the word and I'll start it."* Perceived risk was read as
   grounds to hand back. `SKILL.md` invariant 1 forbids this, but the escalation list's *"a
   situation that genuinely requires human judgment"* bullet is the loophole it went through —
   the bullet means scope cuts, and doesn't say so.

## Root cause

`SKILL.md` governs the *decision* to keep going (invariant 1, "no gate-stops") but says nothing
about **where the lap report sits relative to the next lap's dispatch**. A lap report is the most
turn-ending-shaped artifact in the run, and step 8 (MERGE) says only "loop back to SELECT
immediately" without forbidding a report in between.

## Acceptance

- [x] [run] `grep -c 'Never end a turn unless' decaf-build/skills/auto-deliver/SKILL.md` — expect: `1`
- [x] [run] `grep -n 'MERGE' -A 12 decaf-build/skills/auto-deliver/SKILL.md | grep -c 'report'` — expect: non-zero (step 8 constrains report ordering)
- [x] [manual] The escalation "human judgment" bullet names scope cuts as its content and
      explicitly excludes "risky / user-visible / large" as triggers.

## Summary

**Completed 2026-08-30** — Fixed in `decaf-build/skills/auto-deliver/SKILL.md` with three edits, all aimed at the ordering
defect rather than at re-asserting "don't stop" (which the skill already said, and which the
lap 2→3 stop was not a violation of — that one was mechanical, not a decision).

1. **Invariant 1** now states the harness fact the skill had left implicit: ending a turn is
   stopping regardless of what the text claims, and the rule is mechanical — never end a turn
   unless the plan is complete, you are escalating, or a dispatched agent is still running.
   Both observed shapes are named: narrating instead of acting, and manufacturing a gate.
2. **Step 8 (MERGE)** now fixes the ordering that actually distinguished the one boundary that
   worked from the two that didn't: carry through SELECT → BREAKDOWN → EXECUTE and get the next
   phase's agent running *before* writing the lap report.
3. **Escalation's "human judgment" bullet** narrowed to scope cuts, explicitly excluding risky
   / user-visible / large phases — that bullet was the loophole the lap 3→4 gate went through.
