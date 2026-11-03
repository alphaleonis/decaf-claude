---
# dcc-zsxg
version: 1
title: Drop quick-reviewer from the code-review floor in every preset
status: completed
type: feature
tags:
    - code-review
created_at: 2026-11-03T15:11:47Z
updated_at: 2026-11-03T18:47:18Z
parent: dcc-b578
order: aV
---

Remove `quick-reviewer` from the code-review floor in every preset, so `broad-reviewer` is the floor and quick's slot goes to the next-ranked gate-matched specialist. Recommendation 2 of the dcc-s612 corpus analysis, widened from the `bugs roster=3` rung to every wave by operator decision on 2026-11-03.

## Evidence

From the dcc-s612 corpus, current presets only:

- `bugs` waves (nearly all `roster=3`): 157 dispatches, 4 sole primaries, 0 Critical/High. Of its two-finder primaries, 9 were with `broad-reviewer` (no confidence promotion under Step 5 rule 4) and 10 with `adversarial-reviewer` (1 Critical, 1 High, 3 Medium, 5 Low); those 10 lose corroboration.
- `review` waves: 410 dispatches, 8 sole primaries, 1 Critical/High.
- Cost: median measured spend about 460k per run (subagent transcripts on disk, 2026-11-03), about a fifth of a `bugs roster=3` wave.
- Confound: under the legacy Mode presets quick found 0.23 sole per dispatch, against 0.03 now; roster size, `models=low`, or both may explain it.

Decision rule: findings are the constraint. Under a roster cap the freed slot goes to a specialist, so this trades quick's run for a specialist's rather than saving tokens; specialists produce far more sole primaries per dispatch (adversarial 0.41, design 0.38).

Prior: contradicts the cross-session analysis's "the floor holds" (`reports/2026-07-04-cross-session-analysis.md`, fewer runs, older presets). `dcc-2a8i` agrees in direction, but its figures are benchmark v1 and void.

## Change

In `decaf-quality/skills/code-review/SKILL.md`:

- Roster table and dispatch rules: the floor is `broad-reviewer` alone; `quick-reviewer` loses "Always — review floor".
- `bugs roster=2`: `broad-reviewer` + the best-fitting specialist, instead of floor only.
- Roster cap rules ("The floor is never dropped", the `N ≤ 2` clamp, the "two-agent floor" model-tier rule): restate for a one-agent floor.
- Step 5 rule 4: drop the "agreement between only quick+broad does not promote" exception.
- Step 2b.5 ranking and anything else naming the floor as two agents.

Elsewhere:

- `decaf-quality/agents/quick-reviewer.md` frontmatter: its Dispatch line no longer says "always; part of the review floor".
- `decaf-quality/skills/auto-code-review/SKILL.md`: the `bugs roster=3` cheap wave is described as "floor + best-fitting specialist"; restate as `broad-reviewer` + two specialists.
- README and CLAUDE.md roster descriptions.

## Decisions (operator, 2026-11-03)

- `quick-reviewer` stays dispatchable under `audit` and when named explicitly, as a second generalist; the "agreement between only the two generalists does not promote" rule stays for those runs.
- Its three matrix lanes (line-level bugs, pattern-level security, documented-convention violations) move to `broad-reviewer`, whose `SECURITY` subcategory now names all six pattern categories `security-reviewer` excludes (it lacked SSRF, TOCTOU races and sensitive data in logs). Every other agent's out-of-scope routing points at `broad-reviewer`.
- The cheap re-review rung keeps `roster=3`: `broad-reviewer` + the two best-fitting specialists.

## Acceptance

- [x] [run] `grep -n "Always — review floor" decaf-quality/skills/code-review/SKILL.md` — expect: one match, the `broad-reviewer` row
- [x] [run] `grep -rn "quick+broad\|two-agent floor" decaf-quality/skills` — expect: no matches
- [x] [run] `scripts/check-skill-references.sh` — expect: exit 0
- [x] [manual] A `review` run's Agent Summary lists no `quick-reviewer`, and its roster cap gives the freed slot to a gate-matched specialist. Reason: the roster is resolved by the orchestrator, not by code a test can call.

## Summary

**Completed 2026-11-03** — Made broad-reviewer the sole review floor and moved quick-reviewer's three matrix lanes (line-level bugs, pattern-level security, documented conventions) to it; broad's SECURITY subcategory now names all six pattern categories security-reviewer excludes, and every agent's routing points at broad-reviewer. quick-reviewer stays available under audit or when named. The cheap re-review rung keeps three seats (broad + two specialists). Verified on a bibbla review re-run of one prose-only commit (2026-11-03): no quick-reviewer, spend 3.03M against 6.80M with it; one Low citation slip that only quick-reviewer had found was missed. The roster cap did not bind in that run (3 agents matched, N=4), so the freed-slot path was accepted on the rule change without a binding-cap run.


## Verification note (2026-11-03)

The freed-slot path was later exercised: a bibbla `review` of a three-file C# commit derived N=6 from 116 executable lines, dropped three matched agents, and ran broad-reviewer plus five specialists with no quick-reviewer.
