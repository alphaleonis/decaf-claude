---
# dcc-n7bm
version: 1
title: 'auto-code-review: conservative re-review rosters scaled by fix-delta size and complexity'
status: completed
type: task
priority: normal
created_at: 2026-07-03T19:58:50Z
updated_at: 2026-07-03T20:03:44Z
order: az
---

Session evidence: re-reviews are hard-coded to uncapped mid (10 reviewers) regardless of delta. In iteration 2 four of ten reviewers found nothing; in iteration 3 quick found nothing and perf's only finding was duplicated by broad. Every verdict-driving finding across three rounds came from broad/knowledge/design/adversarial. Operator direction: re-reviews should be quite conservative, scaled by the amount AND complexity of the fix-round changes; a third review should be minimal.

## Todo

- [x] Step 5: classify the fix delta (executable-production lines; behavioral vs docs/comments/tests; complexity signals: concurrency, API contracts, parsing/validation, security surface) and compute reReviewMode
- [x] First re-review: mid4 (docs-only or small behavioral) / mid6 (moderate or complexity signals) / uncapped mid only for large or high-risk deltas
- [x] Third+ re-review: always mid3, scoped to newest fix delta only
- [x] Keep the mid-family invariant (validation wave must run; never low for autonomous fixing)
- [x] Step 2 subsequent-iteration prompt uses {reReviewMode}; update argument-parsing note and Notes section


## Summary of Changes

- decaf-quality/skills/auto-code-review/SKILL.md Step 5: new item 4 classifies the fix delta (executable production lines, excluding docs/comments/tests/generated; complexity signals: concurrency, API/contract surface, parsing/validation, security-adjacent, data mutations) and sets reReviewMode: first re-review mid4 (docs-only or <~25 exec lines, no signals) / mid6 (>=~25 lines or any signal) / uncapped mid (>=~150 lines or high-risk domain); iteration >= 3 always mid3 scoped to the newest fix round's delta.
- Step 2 subsequent-iteration prompt now uses {reReviewMode} and instructs boundary probing of behavior-changing fixes.
- mid-family invariant preserved and documented (validation wave runs; never low for autonomous fixing).
- Argument-parsing note and Notes section updated to match.
