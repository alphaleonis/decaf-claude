---
# dcc-gdof
version: 1
title: 'Add --report flag: session reports for the review loop (auto-tdd/auto-dev/auto-code-review/code-review)'
status: completed
type: task
priority: normal
created_at: 2026-07-04T15:03:58Z
updated_at: 2026-07-04T15:10:21Z
order: "y"
---

Operator request: produce comparison-grade session reports (like reports/2026-07-03-nibs-sn96 and 2026-07-04-nibs-5a8k on the tuning branch) automatically via a --report flag, instead of manual instructions each time. Design: code-review collects per-wave metrics (it is the only context that sees reviewer/validator Agent tool results, so it can record their tokens/tools/duration — eliminating the biggest [Estimate] in prior analyses); auto-code-review assembles the session report (loop ledger: iterations, fix rounds, triage, anomalies) into .decaf/session-reports/; auto-tdd/auto-dev forward the flag and contribute implementation-phase stats. Template lives in a shared convention file.

## Todo

- [x] conventions/session-report.md: report template + per-skill data-collection duties (verified/[Estimate] labeling discipline)
- [x] Symlink the convention into decaf-quality/conventions and decaf-build/conventions
- [x] code-review: parse --report; record Session Metrics (per-reviewer/validator usage, pre-flight record, wave timing) in the consolidated file
- [x] auto-code-review: parse + forward --report; keep loop ledger; generate .decaf/session-reports/<date>-<slug>/ (README + consolidated-file copies) at the end
- [x] auto-tdd + auto-dev: parse + forward --report; contribute implementation-phase stats
- [x] Update argument-hints in all four skill frontmatters


## Summary of Changes

- New conventions/session-report.md: flag plumbing across the four skills, output location (.decaf/session-reports/<date>-<slug>-code-review-session/), non-negotiable truth discipline (harness figures verbatim; [Estimate]/[Inference]/[Unverified] labels; children-inclusion caveat), per-skill data duties, and the six-section README format matching the manual sn96/5a8k reports.
- Symlinked into decaf-quality/conventions and decaf-build/conventions (both resolve).
- code-review: --report in argument-hint + parsing; Step 3 dispatch and Step 5.6 validators record per-agent usage from tool results at dispatch time (only context that ever sees them); Step 6 template gains the Session Metrics section (wave timing, per-agent usage table, pre-flight record, anomalies).
- auto-code-review: --report in argument-hint + parsing; Step 1.7 starts the session ledger (per-iteration, per-fix-round, triage decisions, delta classification/reReviewMode, anomalies); flag forwarded in codeReviewArgs and the re-review prompt; new Step 6.5 assembles the report folder (byte-identical consolidated-file copies + README).
- auto-tdd / auto-dev: --report in argument-hint + parsing; Step 2 records the implementation subagent's usage + changeset stats as the implementation-phase record; Step 3 forwards --report and hands the record to auto-review.
- conventions/artifacts.md layout + conventions/CLAUDE.md file table updated with the new domain/file.

Note: report *generation* is automated; cross-session *comparison* stays manual by design (the convention says so explicitly) — tuning decisions remain gated on dcc-unre's await-more-samples rule.
