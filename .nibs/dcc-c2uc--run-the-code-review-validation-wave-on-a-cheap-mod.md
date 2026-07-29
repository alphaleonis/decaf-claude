---
# dcc-c2uc
version: 1
title: Run the code-review validation wave on a cheap model tier
status: in-progress
type: feature
priority: high
estimate: m
tags:
    - code-review
created_at: 2026-07-28T20:41:05Z
updated_at: 2026-07-29T12:10:33Z
parent: dcc-hyxw
order: ak
---

# Why

The validation wave is **17.3% of ours' sub-agent output** — the single largest line item, larger
than any reviewer — and by construction it originates nothing. Its job is to confirm, correct, or
refute findings the reviewers already raised.

Step 2d classifies validators as *volume* agents, so in `mid` they already run mid-tier. But
anthropic does the identical job — score a claim against a fixed 0–100 rubric — on **Haiku**, and
posts the study's best severity calibration (0.90, 9/10, vs ours' 0.70, 21/30 — #dcc-hmp6). That
is direct evidence the
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

- [x] [run] `rg -n "Step 2d" -A40 decaf-quality/skills/code-review/SKILL.md` — expect: a third
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

## Implementation (done) — verification still owed
## Implementation (done) — verification still owed

**Shipped.** `Step 2d` now defines three role tiers instead of two:

| tier | agents | `mid` | `high` | `max` |
|---|---|---|---|---|
| Judgment | knowledge, design, security, spec-compliance, adversarial | session | session | session |
| Volume | quick, broad, consistency, test, performance, data-migration, prior-feedback, stack | mid | session (except quick/consistency) | session |
| **Verification** | **Step 5.6 `finding-validator`** | **cheap** | session | session |

Files: `code-review/SKILL.md` (mode table, Step 2d, Step 5.6 step 3 cross-reference),
`decaf-quality/README.md` item 12, `competition/benchmark/tools.json` (`model_policy`).

The never-tier-up rule was generalized rather than duplicated: it now reads "never dispatched on a
model more expensive than the session model", which covers the cheap tier without a second clause.

### Two deliberate limits on scope

**`high` and `max` keep validators on the session model.** The nib says "assign the Step 5.6
validation wave to [the cheap tier]"; this applies that to `mid` only. The benchmark ran
`mid --report` — every figure behind this change, including the 17.3%, is a `mid` measurement, so
`mid` is the only mode where the evidence reaches. `high` also has a specific reason to decline the
trade, now stated in the doc: a validator's `refuted` verdict *silently removes* a finding, and
`high` is the mode chosen precisely when that risk is least acceptable. If the re-run shows verdict
quality holds, extending it to `high` is a one-line follow-up.

**`low` needs nothing** — it skips validation entirely (Step 5.6).

### What is NOT verified, and why it is not

The remaining two criteria both require a benchmark re-run (~$160 single-repeat / ~$320 full, plus
blind re-grading). That is operator-gated spend, so it has not been started.

- `roster_yield.py` exits 0 and still reports **17.3%** — that is the *archived baseline*, not a
  post-change figure. The script reads committed runs; nothing it can say today reflects this
  change.
- The confirmed/refuted/uncertain distribution is entirely unmeasured under the cheap tier. **The
  named risk is live**: if a cheap validator stops correcting its own findings downward (observed on
  subjects 5 and 7), the wave becomes a rubber stamp and this change is a net loss despite being
  cheaper. Nothing here rules that out.

`tools.json` now carries a `model_policy_note` recording that the 18 archived runs predate this
tier, so a re-run is not silently compared against a differently-configured baseline.

**Do not treat the cost saving as banked.** The change is in the default path from the next session
restart onward; its effect on verdict quality is unknown until the re-run.
