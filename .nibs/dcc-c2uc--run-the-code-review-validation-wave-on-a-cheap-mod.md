---
# dcc-c2uc
version: 1
title: Run the code-review validation wave on a cheap model tier
status: todo
type: feature
priority: high
estimate: m
tags:
    - code-review
created_at: 2026-07-28T20:41:05Z
updated_at: 2026-07-29T11:24:12Z
parent: dcc-hyxw
order: ak
---

# Why

The validation wave is **17.3% of ours' sub-agent output** — the single largest line item, larger
than any reviewer — and by construction it originates nothing. Its job is to confirm, correct, or
refute findings the reviewers already raised.

Step 2d classifies validators as *volume* agents, so in `mid` they already run mid-tier. But
anthropic does the identical job — score a claim against a fixed 0–100 rubric — on **Haiku**, and
posts the study's best severity calibration (0.88 vs ours' 0.62). That is direct evidence the
task does not need a mid-tier model.

Validators are ~13% of session output, so this is the largest saving available that does not
change what gets reviewed.

# What to change

`decaf-quality/skills/code-review/SKILL.md` Step 2d currently defines two tiers by role. Add a
third, cheap tier and assign the Step 5.6 `finding-validator` wave to it. Keep the existing rule
that tiering only ever lowers cost — never force a cheap tier *up* when the session model is
already at or below it.

# Risk

Low: coverage is unchanged and the task is rubric application.

The thing to watch is named in #dcc-e0wj's `# Preserve` section — validators **correcting their
own findings downward** rather than inflating them (observed on subjects 5 and 7). If a cheaper
tier loses that, the wave becomes a rubber stamp and the change is a net loss even though it is
cheaper. Compare the confirmed/refuted/uncertain distribution against the committed baseline
before accepting.

# Acceptance

- [ ] [run] `rg -n "Step 2d" -A40 decaf-quality/skills/code-review/SKILL.md` — expect: a third
      tier defined by role, with the validation wave assigned to it and the never-tier-up rule
      intact
- [ ] [run] `python3 competition/benchmark/analysis/scripts/roster_yield.py` — expect: exit 0,
      and `finding-validator`'s share of sub-agent output recorded post-change against the
      17.3% baseline
- [ ] [manual] Confirmed/refuted/uncertain distribution compared against the committed baseline
      on a re-run subset, with the downward-correction behaviour specifically checked.
      `[manual]` because it is a judgement on whether verdict quality held, not a threshold.

# Notes

Reasoning and measured basis: #dcc-e0wj → `# Candidate interventions` → item 1. Can share a
benchmark re-run with #dcc-1xtt. [Estimate] a re-run sweep is ~$160 single-repeat / ~$320 full,
plus blind re-grading.
