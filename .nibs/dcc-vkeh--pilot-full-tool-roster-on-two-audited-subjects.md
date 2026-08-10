---
# dcc-vkeh
version: 1
title: 'Pilot: full tool roster on two audited subjects'
status: todo
type: task
priority: high
created_at: 2026-08-10T17:43:28Z
updated_at: 2026-08-10T17:44:03Z
parent: dcc-ho2w
blocked_by:
    - dcc-5xad
    - dcc-y2e6
order: Zw
---

Everything run under v2 so far is essentially one tool on one subject: four anthropic cells plus one
`ours-review` cell, all on subject 2. There has been NO cross-tool comparison under v2, which is the
benchmark's entire purpose.

Before committing to a full run, pilot the roster on two audited, vintage-safe subjects with keys
rich enough to discriminate.

## Scope

- Full roster: `ours-bugs`, `ours-review`, `ours-audit`, `anthropic-code-review`, `superpowers`,
  plus whichever competitors survive tool-definition rot (`pr-review-toolkit` and
  `tag1-comprehensive-review` are absent from `tools.json` — see [[dcc-gxuk]])
- 2 subjects x 2 repeats, shim ON
- Score through the automated pipeline, not by hand
- Check the discrimination question directly: do the tools separate, or does everyone score the same?
  A key that cannot separate tools is not yet a benchmark.

`superpowers` needs a v2 invocation — it is local-diff-only already, which fits v2 naturally.
`run_cell_v2.sh` currently supports only the three decaf presets and anthropic.

## Acceptance

- [ ] Every roster tool has a working v2 invocation
- [ ] 2 subjects x roster x 2 repeats completed with clean leak audits
- [ ] Tools measurably separate, or a written explanation of why they do not
