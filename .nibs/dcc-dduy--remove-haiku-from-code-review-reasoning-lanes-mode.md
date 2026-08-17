---
# dcc-dduy
version: 1
title: Remove Haiku from code-review reasoning lanes (models=low volume+verification -> Sonnet)
status: in-progress
type: feature
priority: high
created_at: 2026-08-16T13:14:58Z
updated_at: 2026-08-17T13:35:35Z
parent: dcc-hyxw
order: arV
---

Operator decision (2026-08-16): stop using Haiku for any reasoning-based task in the code-review
pipeline. Under `models=low`, volume agents AND verification agents move to Sonnet (mid tier).
Judgment agents already inherit the session model everywhere. Haiku remains only for genuinely
non-reasoning work (e.g. the Step 1 trivial-PR classifier).

Accepted consequence: `low`'s model policy may become identical to `norm`'s — fine for now; the
axis gets rearranged later if so.

## Why

- Verification is reasoning, not rubric-matching: the screener must settle "is this claimed defect
  real" (semantic code comprehension); `finding-validator`'s brief is a program-analysis checklist
  ("trace the execution path with concrete values") with destructive verdicts (`refuted` silently
  removes a finding; a low screen score tiers one down).
- The pilot's three wrongly-binned real defects died in the Haiku screen lane under `bugs`
  (confounded with the `evidence=strong` × roster-cap interaction — see TUNING-SIGNALS "Mechanism,
  traced" — but the lane is where the loss occurred).
- The evidence for cheap verification is gone: [[dcc-c2uc]] rested on "anthropic does the identical
  job on Haiku", and METHODOLOGY-v2's model-cutoff table records the opposite — anthropic's review
  agents run Sonnet; Haiku is helpers only. dcc-c2uc's own named risk (rubber-stamp wave) was never
  measured because the re-run was operator-gated.

This partially reverses dcc-c2uc's shipped-but-unverified change (validators to cheap tier under
`norm`): under this decision verification runs Sonnet under `low` and `norm` alike. Update
dcc-c2uc's body when this lands so the two nibs do not disagree.

## Acceptance

- [x] Step 2d in `decaf-quality/skills/code-review/SKILL.md`: `models=low` → volume + verification
      on mid tier; no Haiku assignment remains for reviewer/screener/validator roles at any
      `models` value
- [x] Step 5.6 cross-reference, mode table, and `decaf-quality/README.md` item 12 updated to match
- [x] `competition/benchmark/tools.json` `model_policy` notes updated (archived runs predate this)
- [x] Dev copy synced (`~/.claude/skills/decaf-quality-dev/`)
- [x] dcc-c2uc body annotated with the reversal and the METHODOLOGY-v2 citation
