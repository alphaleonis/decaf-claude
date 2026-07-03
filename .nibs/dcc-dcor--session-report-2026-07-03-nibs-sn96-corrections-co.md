---
# dcc-dcor
version: 1
title: 'Session report 2026-07-03 (nibs-sn96): corrections + cost-scrutiny section'
status: completed
type: task
priority: normal
created_at: 2026-07-03T19:59:05Z
updated_at: 2026-07-03T20:04:16Z
order: w
---

Corrections found by analysis: (1) README file table says '5 of 10 + 1 validator' for iteration-1 individual reports — actually 4 of 10 reviewers + 1 validator; (2) §4.1 'final report ~19:11' contradicts the §5 timeline's 18:11 UTC (file 20-11-49 local, UTC+2) and the wall-clock-stretching claim is weak (~26 vs 21 min); (3) '~455k extra orchestrator tokens' is iteration-1 resumes only and counts necessary consolidation work as waste — counterfactual vs iteration 2's clean run gives ~400k; (4) 'each with an executed repro' for the 4 regression finders is only evidenced for broad and adversarial (also in iteration-3-individual-reports.md intro).

## Todo

- [x] Fix the four factual errors (README + iteration-3 file intro)
- [x] Add §6 cost scrutiny: per-agent yield table, verdict-driver concentration, ablation observations, redundant-work inventory, build:review ratio, resulting skill-change nibs


## Summary of Changes

- README file table: '5 of 10 + 1 validator' corrected to '4 of 10 + 1 validator'.
- README §1: 'each with an executed repro' qualified — executed for broad/adversarial, hand-trace for design/knowledge, [Unverified] labeled; cross-reference to §6 added.
- README §4.1: token-cost framing corrected (454k = iteration-1 resumes only; +98k iteration 3; counterfactual overhead ~400k vs iteration 2's clean 161,520) and wall-clock claim fixed (18:11 UTC per file timestamp, not ~19:11; ~26 vs 21 min); inline correction note added; post-analysis note records that the skill already mandated single-message parallel dispatch and the harness default change is what broke it.
- iteration-3-individual-reports.md intro: same executed-repro qualification.
- README §6 added: per-agent yield table across all three waves, verdict-driver concentration (broad/knowledge/design/adversarial), rev-spec natural ablation, redundant-work inventory, iteration-3-was-foreseeable analysis, build:review ratio, caveats, and pointers to dcc-n87o / dcc-n7bm / dcc-6yi4 / dcc-8tbb.
