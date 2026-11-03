---
# dcc-b578
version: 1
title: Act on the code-review corpus analysis
status: todo
type: epic
tags:
    - code-review
created_at: 2026-11-03T15:25:34Z
updated_at: 2026-11-03T20:16:45Z
order: zzzzzzzzy
---

Act on the recommendations of the code-review corpus analysis (dcc-s612; the corpus and its analysis stay off main), as decided by the operator walking through them on 2026-11-03.

## Goal

Make reviews cheaper in raw tokens without losing findings: findings are the constraint, tokens the primary thing to reduce (subscription), runtime secondary.

## Scope

- dcc-k163: record each subagent's actual spend under `--report` (the precondition for trusting any cost comparison)
- dcc-zsxg: drop `quick-reviewer` from the floor in every preset
- dcc-zkwo: stop dispatching `dotnet-reviewer` under `review` and `bugs` waves
- dcc-ysx8: rank specialists from the corpus instead of void v1 figures
- dcc-6rza: measure the single seat's severity calibration
- dcc-lwo7: revisit batching the evidence screen once spend is measured (draft, blocked by dcc-k163)

Decided against: running the single seat without an orchestrator subagent (recommendation 5; measured overhead 0.33 of the seat), and replacing the trigger re-review wave with a second single seat (recommendation 8).

## Before merging to main
The work happens on the local `analysis` branch, next to the corpus. The branch is never pushed; it reaches main as one squash commit, built after these steps:

- [x] [run] `git ls-files code-review-reports | wc -l` — expect: `0` (corpus, reports, scripts, CSVs and `ANALYSIS.md` removed)
- [x] [run] `git grep -n 'code-review-reports' -- . ':!.nibs/dcc-s612*' ':!.nibs/dcc-b578*'` — expect: no matches; no skill, agent, convention or nib points at a file that will not exist on main
- [x] [manual] Nibs headed for main (this epic, its children, dcc-s612) quote no report content: no finding titles, code or paths from the collected projects. Reason: what counts as confidential is the operator's call.
- [x] [manual] Decide whether project names (bibbla, lotsen, lacy, ai-journal, mazewebsite, …) may stay in those nibs, or are anonymized. Reason: operator's call. Decided 2026-11-03: project names stay; report content does not.
- [x] [manual] The squash is built with `git merge --squash` locally and only main is pushed. Reason: pushing the branch would publish every commit, corpus included.

## Current Focus

Completed dcc-6rza: The single seat under-rates. Blind re-rating of 40 seat findings: agents moved 9 of 25 Mediums to High and 8 of 15 Lows to Medium (2 of 40 down); the operator, on 8 of them, rated 5 higher and none lower, and agreed with the agents within one level on 8 of 10 while never rating below them. Wave control: agents demoted all 5 Highs, but the operator rated the one wave High they saw as Critical, so wave calibration is unresolved. Follow-up: dcc-6qyv recalibrates solo-reviewer's severity. Raters spent 8.3M tokens, measured.
