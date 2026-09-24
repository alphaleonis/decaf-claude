---
# dcc-vi86
version: 1
title: 'auto-deliver: --laps exit plus a headless driver that restarts it fresh per phase'
status: completed
type: feature
priority: normal
estimate: l
created_at: 2026-09-24T17:03:06Z
updated_at: 2026-09-24T18:38:51Z
parent: dcc-fq6j
blocked_by:
    - dcc-qdxo
order: ay
---

## Context

auto-deliver runs every phase in one growing context: breakdown, batch-dev, review triage and close-out for phase after phase. `state.json` plus the tracker already make a restart safe, but nothing ever restarts it, and continuing to the next phase depends on the wording of invariant 1; commit aae57af (#dcc-d76g) shows that "lap death" at a phase boundary is a real failure. The late-2026 research recommends the hybrid this item builds: an outer loop picks one bounded unit, a fresh-context worker does it, deterministic gates check it, and the outer loop owns continuation. Unblocked by #dcc-qdxo (auto-code-review can no longer stop a headless run with a question).

## Evidence (refine, 2026-09-24)

- **Resume already works per lap.** Setup reads `state.json` and resumes an in-flight step, otherwise starts a fresh lap at SELECT; after MERGE the state is back at SELECT with no phase in flight. A process that exits there is picked up cleanly by the next one.
- **Headless constraints** (Claude Code docs, via the research notes): `--bare`, recommended for scripts, skips skills, plugins and subagents, so it would break auto-deliver outright; `--permission-prompts none` denies anything that would prompt unless allowed, so the project's allow rules must cover what the loop runs; `--max-turns` exits with an error at its limit; `--max-budget-usd` caps spend including subagents; `--output-format json` reports `total_cost_usd`; agent teams do not form under `-p`; the Workflow tool needs an allow rule there.

## Decisions

1. **auto-deliver `--laps N`.** After N completed laps (MERGE done), write the lap report and end the run. Invariant 1 gains the lap limit as a third legitimate exit next to plan complete and escalation: an operator-chosen bound, not a gate the loop invents. Without `--laps`, behavior is unchanged.
2. **`state.json` gains `exit`**: `lap-limit`, `complete` or `escalated`, written on every exit and cleared when a run starts. `artifact-layout.md` documents it. The driver reads this, never the final message's wording.
3. **Driver script** at `decaf-build/skills/auto-deliver/scripts/drive.sh`, run from the project root as `bash drive.sh <plan> [options]`. Each iteration runs `claude -p "/decaf-build:auto-deliver <plan> --laps 1 …"` with `--permission-prompts none` and `--output-format json`, forwarding `--tracker`, `--models`, `--review` and `--base-branch`; never `--bare`. After each run it reads `exit`: `lap-limit` continues, `complete` stops with success, `escalated` stops with an error. It logs each lap's cost from the JSON.
4. **Caps are optional; unlimited by default**, as auto-deliver runs are today. `--lap-budget USD` passes `--max-budget-usd`, `--max-turns N` passes `--max-turns`, `--max-laps N` bounds the loop. Separately, a **no-progress guard** always applies: the driver stops with an error when a run leaves `state.json` missing, without an `exit`, or with an unchanged `updated_at`, and when `claude` itself exits non-zero (a hit cap included). This is a correctness guard against repeating a failing lap, not a spend cap.
5. **batch-dev headless fallbacks.** An agent-team cluster runs as a series cluster when agent teams are unavailable (disabled, or a headless run). A workflow cluster runs as a series cluster when the Workflow tool is not available or not allowed. Each fallback is logged.
6. **A stub test** at `decaf-build/skills/auto-deliver/scripts/test-drive.sh` puts a fake `claude` on `PATH` that writes scripted `state.json` values, and checks the driver's decisions.

## Acceptance

- [x] [run] `grep -n -- '--laps' decaf-build/skills/auto-deliver/SKILL.md` — expect: matches in the argument-hint, invariant 1's exit list, and the MERGE step
- [x] [run] `grep -n '"exit"' decaf-build/skills/auto-deliver/artifact-layout.md` — expect: the `state.json` schema documents `exit` with `lap-limit | complete | escalated`
- [x] [run] `bash -n decaf-build/skills/auto-deliver/scripts/drive.sh` — expect: exit 0
- [x] [run] `grep -c -E 'claude .*--bare' decaf-build/skills/auto-deliver/scripts/drive.sh` — expect: `0`
- [x] [run] `bash decaf-build/skills/auto-deliver/scripts/test-drive.sh` — expect: exit 0, covering lap-limit then complete (success after two runs), escalated (error), an unchanged `updated_at` (no-progress error), a non-zero `claude` exit (error), and `--max-laps` stopping the loop
- [x] [run] `grep -n -i 'headless' decaf-build/skills/batch-dev/SKILL.md` — expect: the agent-team and workflow mechanisms each state their series fallback
- [ ] [manual] One real headless lap on a scratch plan completes and writes `exit: lap-limit`, and a second run picks up the next phase. Reason: it needs a live Claude Code session spending model budget against a real tracker, which an acceptance check cannot run.

## Notes
- CLI flags checked against the installed Claude Code 2.1.281 before the driver used them: `--permission-prompts none`, `--output-format json`, `--max-budget-usd` and `--bare` appear in `claude --help`. `--max-turns` does not, but the CLI rejects a non-numeric value with `option '--max-turns <turns>' ... must be a number`, so it is a defined, hidden option.
- The driver's progress check compares `updated_at` for every outcome, not only `lap-limit`: a stale `exit: complete` from an earlier run must not read as success when a new run did nothing. The stub test covers that case.
- `scripts/test-drive.sh` fakes `claude` on `PATH` and passes 19 checks: continue then complete, escalated, stale state, missing `exit`, a failing `claude`, `--max-laps`, bad arguments, and flag forwarding with no `--bare`.
- Walkthroughs by fresh agents. Old text: `--laps` unknown, invariant 1 forbade a phase-boundary exit, no machine-readable outcome, no headless flags documented, no batch-dev fallback for unavailable mechanisms. New text: all five answered from the skill, the layout, the driver and batch-dev.
- The manual criterion (a real headless lap) is open. It needs model spend on a scratch plan, and a real run must load this repo's version of the plugin (for example `--plugin-dir`, or a reinstall), because the installed plugin predates `--laps`.

## Summary

**Completed 2026-09-24** — auto-deliver takes `--laps N` and records how every run ended in `state.json` `exit` (lap-limit | complete | escalated); `scripts/drive.sh` runs one `claude -p` lap per phase and continues or stops on it, never with `--bare`, with optional caps and a no-progress guard; batch-dev runs team and workflow clusters as series when those mechanisms are unavailable (7639889). Verified by six acceptance checks, including the driver's 19-check stub test, and before/after agent walkthroughs. The manual acceptance item, one real headless lap on a scratch plan, was not exercised: closed on the operator's call, with a follow-up bug to be filed if real use shows a problem.
