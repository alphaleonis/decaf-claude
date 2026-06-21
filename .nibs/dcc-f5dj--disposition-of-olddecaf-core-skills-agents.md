---
# dcc-f5dj
version: 1
title: Disposition of old/decaf (core) skills & agents
status: todo
type: epic
priority: normal
created_at: 2026-06-21T09:09:17Z
updated_at: 2026-06-21T09:55:36Z
order: as
---

## Objective

Decide and execute the per-item fate of the old core plugin (old/decaf) — the last deferred piece after decaf-memory and decaf-protection shipped. The boundary model (build = new behavior, quality = improve existing, plan = decide what/how) absorbs the activity-aligned skills; cross-cutting utilities and the agents are handled separately.

## Decisions (locked)

- decision-critic -> decaf-plan, renamed **challenge-decision** (decision support; sits with grill-me / explore-designs).
- incoherence-detector -> decaf-quality, renamed **coherence-audit** (audits existing docs/code/specs for inconsistencies).
- problem-analysis -> decaf-quality, renamed **diagnose** (root-cause investigation; pairs with the debugger agent, split roles — agent placement handled in the agents task).
- note -> decaf-plan, renamed **capture** (lightweight quick work-item capture; its output is a work item, plan's currency). No standalone core plugin.
- DROP powershell-expert (single language-domain skill; out of scope — resolves the kk29 open question).
- DROP commit (project commit conventions / message formats vary too much to generalize; not ported — Claude can commit on request without a dedicated skill).
- DROP planner agent (redundant with decaf-plan's draft-plan + breakdown-phase).
- Agents: skip any not directly dispatched by a skill for now; revisit later (architect, csharp-developer, go-developer, technical-writer, debugger).

## Context

Follows the closed vnext milestone #dcc-33j0 and layout RFC #dcc-kk29 (which left powershell-expert's home open — now resolved as drop). With commit dropped and note moving to decaf-plan, no 'core' plugin is created. old/decaf still holds the originals; ported/dropped items are removed when old/ is pruned. Skills use the conventions-symlink pattern (see conventions/artifacts.md and the symlink note in CLAUDE.md) if they reference any shared convention.

## Acceptance

- [ ] [run] `ls decaf-plan/skills/challenge-decision decaf-plan/skills/capture decaf-quality/skills/coherence-audit decaf-quality/skills/diagnose` — expect: all four exist
- [ ] [run] `ls -d decaf*/skills/commit decaf*/skills/powershell-expert 2>/dev/null` — expect: no output (both dropped, not ported)
- [ ] [manual] the remaining core agents (architect / debugger / planner / csharp-developer / go-developer / technical-writer) have explicit follow-up decisions captured
