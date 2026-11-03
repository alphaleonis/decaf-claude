---
# dcc-ysx8
version: 1
title: Rank code-review specialists from the corpus instead of void v1 figures
status: completed
type: feature
tags:
    - code-review
created_at: 2026-11-03T15:18:42Z
updated_at: 2026-11-03T18:49:41Z
parent: dcc-b578
order: as
---

Replace the specialist ranking in `code-review` Step 2b.5, which rests on void benchmark v1 figures, with an order from the dcc-s612 corpus. Recommendation 4 of the dcc-s612 corpus analysis, as decided by the operator on 2026-11-03.

## Evidence

Current presets, sole primaries (found by that reviewer alone) per dispatch, and sole Critical/High:

| specialist | runs | sole / run | sole C/H | sole C/H / run |
|---|---|---|---|---|
| knowledge | 55 | 0.89 | 9 | 0.16 |
| adversarial | 520 | 0.41 | 41 | 0.08 |
| design | 149 | 0.38 | 2 | 0.01 |
| security | 81 | 0.36 | 5 | 0.06 |
| test | 402 | 0.18 | 14 | 0.03 |
| spec-compliance | 123 | 0.16 | 1 | 0.01 |
| consistency | 42 | 0.10 | 0 | 0 |

- About 66 report files record `knowledge-reviewer` as "dropped by the roster cap", more than its 55 dispatches.
- Its 9 sole Critical/High are mostly comments or docs that misstate the code; 2 were behavior bugs reached through a comment (one in ai-journal, one in nibs).

## Decision

Findings where a comment or document misstates the code do not count at full value: that lane belongs to `coherence-audit`. The 2 behavior bugs it reached through comments keep it above `consistency-reviewer`. Under `bugs` and `review`, rank:

1. `adversarial-reviewer`
2. By sole Critical/High per run: `security-reviewer`, `test-reviewer`, `design-reviewer`
3. By category, where samples are thin or the gate is the evidence of fit: `spec-compliance-reviewer`, `performance-reviewer`, the language reviewers, `data-migration-reviewer`, `prior-feedback-reviewer`
4. `knowledge-reviewer`
5. `consistency-reviewer`

Prior: replaces Step 2b.5's v1 drop-cost figures (`roster_yield.py`, 18 archived runs), which may not be cited. Agrees with them on `adversarial` first and on shedding `knowledge`/`consistency` early, for a different reason (lane value, not overlap: the corpus shows knowledge's findings are rarely found by anyone else). Drops the "do not promote `security-reviewer`" rule, which rested on n=3; the corpus has 81 runs.

## Change

- `decaf-quality/skills/code-review/SKILL.md` Step 2b.5: replace the ranking and its v1 figures with the order above. State the figures in the step itself, labeled as measured on a local, unpublished review corpus on 2026-11-03; cite no corpus file, since the corpus never reaches main.
- Keep the "hard-gate agents are not exempt from the cap" rule.

## Resolved

- The `audit` ranking also quoted v1 figures. They are gone; the step keeps its principle without figures (`test-reviewer` and `consistency-reviewer` stay high, since `audit` delivers the suggestion tier). `audit` derives no cap, so the order applies only under an explicit `roster`.
- The size-derived roster cap's rationale also quoted v1 figures (3.20/run against 0.50). It now cites the corpus's sole primaries per run by added-lines bucket (local corpus, current presets, bucketed by added lines).

## Acceptance

- [x] [run] `grep -n -E '1\.85|0\.94|0\.50|0\.17|2\.00/run|18 archived' decaf-quality/skills/code-review/SKILL.md` — expect: no matches
- [x] [run] `scripts/check-skill-references.sh` — expect: exit 0
- [x] [manual] Step 2b.5 states the order above, and each measured position cites a corpus figure. Reason: whether the text matches the decision is a reading judgment.

## Summary

**Completed 2026-11-03** — Replaced code-review Step 2b.5's specialist ranking, which rested on void benchmark v1 drop-cost figures, with an order measured on the local corpus: adversarial first; then security, test and design by sole Critical/High per run; then the category-gated specialists; knowledge second to last (its comment and doc findings count at less than full value, since coherence-audit owns that lane); consistency last. The audit ranking keeps its principle without figures, and the size-derived roster cap now cites the corpus's sole primaries per run by added-lines bucket. Operator read and accepted the text on 2026-11-03.
