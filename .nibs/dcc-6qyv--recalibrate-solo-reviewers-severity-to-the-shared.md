---
# dcc-6qyv
version: 1
title: Recalibrate solo-reviewer's severity to the shared impact scale
status: in-progress
type: feature
tags:
    - code-review
created_at: 2026-11-03T20:16:35Z
updated_at: 2026-11-03T20:24:06Z
parent: dcc-b578
order: "n"
---

Recalibrate `solo-reviewer`'s severity so its Mediums and Lows match the impact scale the verdict and the auto-code-review re-review gate assume. Follow-up of dcc-6rza.

## Evidence (dcc-6rza, 2026-11-03)

Blind re-rating of 40 single-seat findings against a fixed impact rubric (Critical: must fix before merge; High: should fix before merge, a bug that affects normal use or an explicit standard violation; Medium: minor bug, limited-reach edge case or real maintainability cost; Low: no functional effect):

- Agent raters moved 9 of 25 seat Mediums to High and 8 of 15 seat Lows to Medium; 2 of 40 moved down.
- The operator, on 8 of them, rated 5 higher and none lower: 4 of 5 Mediums went up (three to High, one to Critical).
- Operator and agents agree within one level on 8 of 10; the operator is never lower than the agents.

Cost today: a would-be High arrives as Medium, so the verdict reads APPROVED and its auto-code-review fix gets only `fix-verifier`; a would-be Medium arrives as Low and gets no post-fix check.

## Leads in `decaf-quality/agents/solo-reviewer.md` [Inference, not tested]

- It has no severity definitions: only "Severity is impact" and "Not everything is Critical", which pulls down without saying where High starts.
- Every Critical and High must be verified empirically (build, tests, counterexample); a Medium skips that work, so the cheaper rating may win on borderline findings.

## Approach

- Give the seat the same four impact anchors the re-rating used, with "High starts at: affects functionality in normal use, or violates an explicit project standard" stated plainly.
- Keep the verification requirement, but make it decide confidence, not severity: an unverified High is still High, at a lower anchor.
- Compare the severity mix of the next `bugs` reviews against the corpus's 0% Critical / 4% High / 23% Medium / 73% Low.

## Open questions

- Should the wave reviewers' anchors change too? The agent raters demoted all 5 wave Highs to Medium, but the operator rated the one wave High they saw as Critical, so that half is unresolved.

## Acceptance

- [x] [run] `grep -n -i 'High.*normal use' decaf-quality/agents/solo-reviewer.md` — expect: one match, in a severity definition
- [x] [run] `scripts/check-skill-references.sh` — expect: exit 0
- [ ] [manual] Over the next several `bugs` reviews, the seat's High share is clearly above the corpus's 4%, with no rise in refuted or dismissed findings. Reason: needs real reviews over time.
