---
# dcc-6rza
version: 1
title: Measure the single seat's severity calibration by blind re-rating
status: completed
type: research
tags:
    - code-review
created_at: 2026-11-03T15:23:44Z
updated_at: 2026-11-03T20:27:18Z
parent: dcc-b578
order: aw
---

Measure whether the `bugs` single seat (`solo-reviewer`) rates findings lower than the review waves do, by blind re-rating a sample of its Medium and Low findings. Recommendation 6 of the dcc-s612 corpus analysis, operator decision 2026-11-03.

## Why

On first passes in the dcc-s612 corpus:

| shape | reports | median +lines | Critical/High per report | per 1k +lines | approved |
|---|---|---|---|---|---|
| `review` wave | 393 | 512 | 0.58 | 0.71 | 66% |
| `bugs` wave | 110 | 186 | 0.39 | 1.03 | 75% |
| `bugs` single seat | 359 | 412 | 0.09 | 0.11 | 92% |

The seat's 810 primaries are 0% Critical, 4% High, 23% Medium, 73% Low. The corpus cannot separate three explanations: the seat under-rates, it detects fewer serious issues, or the code differed (it became the default later, on a different project mix). The v2 benchmark found the seat's detection at least as good as a wave's, which makes under-rating the one to test.

Severity decides the verdict (any Critical/High is NEEDS_CHANGES) and the auto-code-review re-review gate (a Critical/High fixed, or 2+ Medium fixed). A real High rated Medium still gets `fix-verifier`; rated Low it gets no check.

## Method

- **Sample:** 40 single-seat findings from the local corpus's findings (`bugs` preset, single seat): 25 Medium, 15 Low, spread across projects (pool: 187 Medium, 592 Low; lotsen 288, bibbla 163, nibs 160, mazewebsite 88, lacy 80).
- **Control:** 10 wave findings (5 High, 5 Medium) put through the same blind re-rating, so a rater who rates everything differently from the waves shows up as such.
- **Blinding:** the rater gets the finding's title, description, evidence and `file:line`, with severity, confidence and finder removed, and reads the code at the report's commit, not today's.
- **Rubric:** the severity-by-impact rule in `decaf-quality/agents/solo-reviewer.md` and `conventions/severity.md`, the same for every finding.
- **Raters:** one validator-style agent per finding on the session model; the operator re-rates a subset of about 10 independently.
- **Cost:** about 50 agent runs; at the median `finding-validator` spend of 167k that is roughly 8M tokens [Inference].

## Decision rule

- The seat under-rates if the re-rating raises a clear share of its Mediums to High (or Lows to Medium-or-above) while the control findings keep their wave ratings. Then file a follow-up to change `solo-reviewer`'s severity anchors.
- Otherwise record that the 92% approval rate reflects the code, and close.

## Method as run (2026-11-03)

- Sample drawn by a seeded script on the local corpus: 25 seat Medium, 15 seat Low, 5 wave High, 5 wave Medium from bibbla, lotsen, nibs and mazewebsite. lacy is excluded: no local repository.
- The corpus reviews ran on staged changes, so no commit holds the reviewed code. Raters read the first commit after the review that touches the finding's file and rate the defect as described, since it may be fixed there.
- Blinding strips the severity header, confidence, finder, verification and validation rows, "Severity note" paragraphs and "this is X and not higher" clauses. Impact prose that is part of the finding stays.
- 50 general-purpose raters on the session model, one per item, with a one-paragraph rubric brief; measured spend 8.3M tokens. Operator subset: R10, R13, R23, R24, R35, R36, R39, R47, R48, R49.

## Acceptance

- [x] [run] The sample file lists 40 seat findings and 10 control findings, with project, report and finding number — expect: counts 25 Medium, 15 Low, 5 High control, 5 Medium control
- [x] [manual] A results write-up gives, for seat and control findings separately, the original vs. re-rated severity table, plus agreement between agent and operator on the shared subset. Reason: whether the shift is "clear" is a judgment call.
- [x] [manual] A follow-up nib exists if the decision rule says the seat under-rates; otherwise the write-up says so. Reason: depends on the result.

## Summary

**Completed 2026-11-03** — The single seat under-rates. Blind re-rating of 40 seat findings: agents moved 9 of 25 Mediums to High and 8 of 15 Lows to Medium (2 of 40 down); the operator, on 8 of them, rated 5 higher and none lower, and agreed with the agents within one level on 8 of 10 while never rating below them. Wave control: agents demoted all 5 Highs, but the operator rated the one wave High they saw as Critical, so wave calibration is unresolved. Follow-up: dcc-6qyv recalibrates solo-reviewer's severity. Raters spent 8.3M tokens, measured.

## Results
Agent re-rating, all 50 items:

| original rating | items | rated higher | same | rated lower |
|---|---|---|---|---|
| single seat, Medium | 25 | 9 (to High) | 14 | 2 |
| single seat, Low | 15 | 8 (to Medium) | 7 | 0 |
| wave control, Medium | 5 | 0 | 4 | 1 |
| wave control, High | 5 | 0 | 0 | 5 (to Medium) |

Operator subset (10 items), original → agent → operator:

| shape | original | agent | operator |
|---|---|---|---|
| seat | Medium | Medium | High |
| seat | Low | Medium | Medium |
| seat | Low | Low | Low |
| seat | Medium | Medium | Medium (unsure) |
| wave | Medium | Medium | Medium |
| seat | Medium | High | High |
| wave | High | Medium | Critical |
| seat | Low | Low | Low |
| seat | Medium | Medium | Critical |
| seat | Medium | Medium | High |

Operator and agents agree exactly on 6 of 10 and within one level on 8; where they differ the operator is higher every time. Limits: one rating per item and rater; agents used 3 to 5 tool calls, so they rated mostly from the finding's text; the seat's own impact prose stays in its findings; the wave half rests on 5 agent ratings and 1 operator rating.
