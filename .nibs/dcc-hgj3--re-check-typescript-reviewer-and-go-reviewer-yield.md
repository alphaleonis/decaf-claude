---
# dcc-hgj3
version: 1
title: Re-check typescript-reviewer and go-reviewer yield with measured spend
status: draft
type: research
tags:
    - code-review
created_at: 2026-11-03T18:47:37Z
updated_at: 2026-11-03T18:47:37Z
parent: dcc-b578
order: az
---

Re-check whether `typescript-reviewer` and `go-reviewer` earn their default dispatch, once enough `--report` runs record their spend. Split out of dcc-zkwo, which stopped default dispatch of `dotnet-reviewer` only.

## Why

In the dcc-s612 corpus (current presets) `typescript-reviewer` found 7 sole primaries (2 Medium, 5 Low) in 18 runs, all in one project over five days, and `go-reviewer` 1 sole High in 5 runs. `rust-reviewer` and `cpp-reviewer` had no runs. Those samples cannot decide removal either way. Since dcc-k163, `--report` session reports carry each agent's measured spend.

## Open questions

- How many runs per reviewer, across how many projects, are enough to decide?
- Does the decision rule stay the same as for dotnet: sole primaries per run, weighted by severity, against measured spend?
