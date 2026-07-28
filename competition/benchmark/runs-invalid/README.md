# Quarantined runs — invalid cells (nib dcc-9kkz)

Cells recorded as `anthropic-code-review` that did not run the Anthropic plugin. Moved out of
`runs/` so `rebuild_metrics.sh` (which globs `runs/*/meta.json`) drops them, and reset to
`pending` in `manifest.jsonl` so `/bench-status` shows them as not run.

**Kept, not deleted** — they are evidence for the bug, and the first seven are the study's only
measurement of `ours` at `high` mode.

| cell | why invalid |
|---|---|
| `2__anthropic-code-review__r1` | ran `decaf-quality` (ours) at `high` |
| `2__anthropic-code-review__r2` | ran `decaf-quality` (ours) at `high` |
| `3__anthropic-code-review__r1` | ran `decaf-quality` (ours) at `high` |
| `9__anthropic-code-review__r1` | ran `decaf-quality` (ours) at `high` |
| `9__anthropic-code-review__r2` | ran `decaf-quality` (ours) at `high` |
| `10__anthropic-code-review__r1` | ran `decaf-quality` (ours) at `high` |
| `10__anthropic-code-review__r2` | ran `decaf-quality` (ours) at `high` |
| `3__anthropic-code-review__r2` | 0 sub-agents — orchestrator reviewed inline; not the workflow |
| `6__anthropic-code-review__r2` | 1 sub-agent — degenerate; not the workflow |

**Retained as valid** (in `runs/`): `5__…__r1` and `6__…__r1`. Both carry sub-agents with
`attributionPlugin: code-review` (3 of 15 and 4 of 10) alongside orchestrator-spawned ones, and
both executed the full anthropic role set — history, prior-PR, CLAUDE.md, comments, reviewers,
Haiku scorers. Mixed attribution is normal: the command instructs the orchestrator to spawn most
agents itself. The two quarantined for degeneracy have **no** `code-review` attribution at all
and 0 and 1 sub-agents respectively, against a workflow that mandates five reviewers plus
scorers.

Graded analysis artifacts under `analysis/subject-NN/` still attribute these cells' findings to
anthropic. Re-grading is tracked in dcc-9kkz.
