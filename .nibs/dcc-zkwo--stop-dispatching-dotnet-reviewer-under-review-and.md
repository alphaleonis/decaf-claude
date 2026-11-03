---
# dcc-zkwo
version: 1
title: Stop dispatching dotnet-reviewer under review and bugs waves
status: completed
type: feature
tags:
    - code-review
created_at: 2026-11-03T15:16:01Z
updated_at: 2026-11-03T18:47:43Z
parent: dcc-b578
order: ak
---

Stop dispatching `dotnet-reviewer` under `review` and `bugs` waves; keep it under `audit` and when named explicitly. Recommendation 3 of the dcc-s612 corpus analysis, operator decision 2026-11-03.

## Evidence

From the dcc-s612 corpus, current presets only:

- 71 dispatches, all under `review`, 2026-09 to 2026-11, all after the idiom-surface judgment gate was added (2026-08-21): 0 sole primaries in any project.
- 7 two-finder primaries, all bibbla: with `design-reviewer` 4 (Low, Medium, Low, Low), with `adversarial-reviewer` 2 (High, Medium), with `quick-reviewer` 1 (High). Once dcc-zsxg removes `quick-reviewer` from the floor, that last High would have been dotnet's alone: about 1 sole High in 71 runs.
- Median measured spend about 390k per run (31 subagent transcripts on disk, 2026-11-03).
- 63 of 71 runs are bibbla; the other 8 (ai-journal 6, lotsen 1, lacy 1) also found nothing alone. A bibbla-specific effect is possible.

Scope is dotnet only. The other stack reviewers do not show the same pattern: `typescript-reviewer` 7 sole in 18 runs (2 Medium, 5 Low, all mazewebsite), `go-reviewer` 1 sole High in 5 runs; `rust-reviewer` and `cpp-reviewer` have no runs in the corpus.

Prior: contradicts Step 2b.5's rule to rank stack reviewers by category. `dcc-2a8i` found that the stack-reviewer category does not predict contribution, but its figures are benchmark v1 and void.

## Change

- `decaf-quality/skills/code-review/SKILL.md` dispatch table (the `dotnet-reviewer` row): dispatched only under `audit` (hard gate on C# files, judgment gate open) or when requested explicitly; not under `review` or `bugs` waves.
- Step 2b.5: drop dotnet from the "stack reviewer for the dominant changed language" ranking under `review`/`bugs`.
- `decaf-quality/agents/dotnet-reviewer.md` frontmatter description: restate the Dispatch line to match.
- README roster description, if it states dotnet's dispatch.

## Acceptance

- [x] [run] `grep -n 'dotnet-reviewer' decaf-quality/skills/code-review/SKILL.md decaf-quality/agents/dotnet-reviewer.md` — expect: every dispatch rule names `audit` or explicit request as the only paths
- [x] [run] `scripts/check-skill-references.sh` — expect: exit 0
- [x] [manual] A `review` run on a C# diff with async or disposal changes lists `dotnet-reviewer` as not dispatched, with the reason stated. Reason: the roster is resolved by the orchestrator, not by code a test can call.

## Summary

**Completed 2026-11-03** — dotnet-reviewer is dispatched only under audit or when named explicitly; it no longer has a judgment gate, since outside audit it only runs when named. Verified on a bibbla review of an async and await-using heavy C# commit, which listed it as skipped with that reason. The TypeScript/Go re-check moved to dcc-hgj3.
