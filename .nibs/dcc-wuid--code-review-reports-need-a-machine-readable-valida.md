---
# dcc-wuid
version: 1
title: code-review reports need a machine-readable validation block
status: todo
type: feature
priority: normal
created_at: 2026-08-18T17:44:28Z
updated_at: 2026-08-18T17:45:06Z
parent: dcc-hyxw
order: axk
---

`code-review`'s filed report states its verification outcome in prose, and the wording varies per
run. Across the eight `ours-review` cells on prometheus/efcore:

    3 confirmed, 0 refuted, 0 uncertain, 2 waived (orchestrator-verified empirically), 2 waived (screened clear of bar)
    4 findings confirmed by orchestrator-run differential probes (base vs. head); 7 confirmed by direct code/artifact inspection; validator wave not dispatched
    2 confirmed by executed probe, 1 refuted by executed probe, 1 confirmed by `git blame`; finding-validator wave waived
    empirical — 2 Criticals CONFIRMED by executed probes and by generated-SQL diff against the base commit; 2 reported claims REFUTED by probe

Probe verdicts and validator verdicts are mixed in one sentence, and the wave is sometimes waived
entirely. `dcc-c2uc`'s rubber-stamp question could therefore only be answered directionally on
2026-08-18 (pre-dduy: 1 refutation across 4 cells; post-dduy: 5 across 4) — a **rate** was not
computable, because the denominator (validators actually dispatched) is not recoverable from the
report.

## What to add

A fixed block in the report, emitted always, distinguishing the two evidence sources:

    <!-- validation
    validators_dispatched: 6
    validator_confirmed: 4
    validator_refuted: 2
    validator_uncertain: 0
    probe_confirmed: 3
    probe_refuted: 1
    waived_measured: 3
    waived_screened: 0
    unvalidated: 0
    -->

Machine-readable, stable across reruns, and it costs the orchestrator nothing — it already has
every number.

## Acceptance

- [ ] Block emitted by `code-review` on every `--report` run
- [ ] A scoring helper parses it; a cell missing the block is reported as missing, not as zero
- [ ] `dcc-c2uc`'s rubber-stamp question re-answered as a rate over dispatched validators
