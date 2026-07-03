---
# dcc-8tbb
version: 1
title: 'code-review: shared pre-flight gates for review waves'
status: completed
type: task
priority: normal
created_at: 2026-07-03T19:59:05Z
updated_at: 2026-07-03T20:04:01Z
order: t
---

Session evidence: all ~10 reviewers per wave independently ran go build / vet / golangci-lint / go test (30 redundant gate runs across the session, est. 150-300k tokens plus wall-clock). Run the standard gates once in the orchestrator and inject the results into every reviewer prompt; targeted execution (repro probes, race detector, focused test runs) stays encouraged — reviewer-executed repros were among the session's highest-value outputs.

## Todo

- [x] Step 3: add pre-flight sub-step — discover gates from project config (Taskfile/Makefile/package.json etc.), run once, summarize pass/fail + failure excerpts
- [x] Base context template: add '## Pre-flight gates' section; instruct reviewers not to re-run the standard suite but keep targeted execution encouraged
- [x] Handle the no-gates-discoverable case (skip, note 'pre-flight: none')


## Summary of Changes

- decaf-quality/skills/code-review/SKILL.md: new Step 3.0 'Shared pre-flight gates' — discover gates from project config, run once per wave, summarize pass/fail with failure excerpts; skip with 'pre-flight: none' when undiscoverable.
- Base context template: added '## Pre-flight gates' section with do-not-re-run instruction; targeted execution (repro probes, race detector, focused test runs) explicitly stays encouraged since reviewer-executed repros were among the session's highest-value outputs.
