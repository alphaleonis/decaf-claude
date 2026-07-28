---
# dcc-9kkz
version: 1
title: 'Benchmark: 11 of 18 anthropic cells did not run anthropic — /code-review resolved to decaf-quality'
status: todo
type: bug
priority: critical
estimate: l
tags:
    - benchmark
    - validity
created_at: 2026-07-28T21:15:14Z
updated_at: 2026-07-28T21:15:44Z
order: zzzk
---

# What happened

Runs labelled `anthropic-code-review` did not all run the Anthropic plugin. Auditing
`attributionPlugin` on every sub-agent transcript of all 90 done runs:

| group | cells | $/run | agents | what it actually ran |
|---|---|---|---|---|
| **contaminated** | **7** | **$20.29** | 11.9 | `decaf-quality` — ours, under anthropic's label |
| unattributed | 4 | $7.44 | 6.5 | no plugin attribution; orchestrator hand-rolled the workflow |
| clean | 7 | **$5.87** | 11.0 | `code-review` — the actual Anthropic plugin |
| *ours (reference)* | 18 | $21.33 | 14.5 | `decaf-quality` |

Contaminated cells carry `attributionPlugin: decaf-quality` on every sub-agent, with
`attributionAgent` values like `decaf-quality:broad-reviewer`, `:adversarial-reviewer`,
`:knowledge-reviewer`, `:go-reviewer`, `:finding-validator`. They are ours' runs.

The cost split corroborates independently: contaminated cells average **$20.29** against ours'
own **$21.33**, while clean anthropic cells average **$5.87**.

**Affected cells** — contaminated: `2__r1`, `2__r2`, `3__r1`, `9__r1`, `9__r2`, `10__r1`,
`10__r2`. Unattributed: `3__r2`, `5__r1`, `6__r1`, `6__r2`. Clean: `1__r1`, `1__r2`, `4__r1`,
`4__r2`, `5__r2`, `7__r1`, `7__r2`. **No other tool is affected** — ours, tag1,
pr-review-toolkit and superpowers all match their expected plugin.

# Cause — the harness was right, the resolution was not

`runs/9__anthropic-code-review__r1/prompt.txt` is correct:

> Use the /code-review workflow to review pull request #130837 of the GitHub repository
> kubernetes/kubernetes…

But `/code-review` is **ambiguous**. `decaf-quality` ships a skill literally named `code-review`,
and the official plugin ships a command of the same name. The agent resolved it to ours. This is
the same naming collision noted in #dcc-05uw's evidence section, where three distinct Anthropic
things are called some variant of code-review.

`tools.json` disambiguates for `ours` (`/decaf-quality:code-review`) but not for anthropic.

# Impact

**Cost — badly wrong.** The published anthropic figure of **$11.82** is a blend of ~$5.87 real
runs and ~$20.29 runs that were actually ours. Clean anthropic is **~$5.87**, so ours is
**~3.6× more expensive**, not 1.8×. The gap this whole programme exists to close is roughly
twice what was believed, which makes #dcc-hyxw more urgent, not less.

**Quality — robust.** Bug-catch and calibration hold across all three groups (7/7, 7/7, 4/4;
calibration 0.89, 0.89, 0.83 against the published 0.88). Conclusions about *what* anthropic
finds survive; conclusions about *what it costs* do not.

**Downstream, needing restatement once cells are re-run:**

- `analysis/synthesis-data.json`, `synthesis-report.html`, per-subject `metrics.json`/reports
- **#dcc-e0wj** — every ours-vs-anthropic cost figure; its ours-only findings (roster yield,
  calibration root cause, diff-vs-repo scaling) are **unaffected**
- **#dcc-hyxw** and children — the anthropic per-agent (13.7k) and repo-sensitivity (0.119)
  baselines they cite
- **#dcc-05uw** — the evidence table
- #dcc-m8ar's token fix is mechanical and unaffected

# Fix

- [ ] [run] `rg -n "invocation" competition/benchmark/tools.json` — expect: the anthropic entry
      names the plugin unambiguously (plugin-qualified, as `ours` already does) so the agent
      cannot resolve to a same-named skill
- [ ] [run] `python3 competition/benchmark/analysis/scripts/verify_run_provenance.py` — expect:
      exit 0; every done run's dominant `attributionPlugin` matches its declared tool. Add this
      to the per-cell recording path so a mismatch fails at run time, not months later
- [ ] [manual] The 11 affected cells re-run and re-graded blind. [Estimate] clean anthropic is
      ~$5.87/run, so ~$65 plus grading — cheap relative to the correction
- [ ] [manual] Downstream artifacts and the three citing nibs restated

# Notes

Found while evaluating anthropic's git-history retrieval channel for #dcc-e0wj workstream 4 —
the roles could not be read from `attributionAgent`, and checking why exposed the mismatch.

The tell was visible earlier and misread: subjects 2, 3, 9 and 10 were exactly the subjects whose
`analysis.json` lacked per-sub-agent persona labels (#dcc-m8ar notes recovering them for *ours*).
That was not an extraction gap for those cells — it was a different tool running.
