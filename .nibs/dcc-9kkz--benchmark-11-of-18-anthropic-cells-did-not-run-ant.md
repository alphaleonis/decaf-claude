---
# dcc-9kkz
version: 1
title: 'Benchmark: 9 of 18 anthropic cells did not run anthropic — /code-review resolved to decaf-quality'
status: completed
type: bug
priority: critical
estimate: l
tags:
    - benchmark
    - validity
created_at: 2026-07-28T21:15:14Z
updated_at: 2026-07-29T11:07:05Z
order: zzzk
---

# What happened

Runs labelled `anthropic-code-review` did not all run the Anthropic plugin. Auditing
`attributionPlugin` on every sub-agent transcript of all 90 done runs:

| group | cells | $/run | agents | what it actually ran |
|---|---|---|---|---|
| **invalid — ran ours** | **7** | **$20.29** | 11.9 | `decaf-quality` at `high`, under anthropic's label |
| **invalid — degenerate** | **2** | $3.32 | 0.5 | `3__r2` (0 sub-agents, reviewed inline) and `6__r2` (1); no `code-review` attribution at all |
| valid | 9 | **$7.13** | 11.3 | the Anthropic plugin. Includes `5__r1`/`6__r1`, whose mixed attribution (3/15 and 4/10 sub-agents tagged `code-review`) is normal — the command has the orchestrator spawn most agents itself |
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

**Cost — badly wrong.** The published anthropic figure of **$11.82** is a blend. Across the 9
valid cells anthropic averages **$7.13**, so ours is **~3.0× more expensive**, not 1.8×. The gap this whole programme exists to close is roughly
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

# What the contaminated cells actually are — and one further distortion

They ran ours **at `high` mode**, not the benchmarked `mid`. Every parsed cell reports
`**Mode:** high` in its own output and wrote a `.decaf/code-reviews/CODE_REVIEW_*.md`.

| subject | ours `mid` (own cells) | ours `high` (mislabeled cells) |
|---|---|---|
| 2 | $11.25 | $10.28 |
| 3 | $27.97 | $32.25 |
| 9 | $32.11 | $24.24 |
| 10 | $17.35 | $20.37 |
| **mean** | **$22.17** | **$20.29** |

So they are **not poolable with ours' cells** — different mode, and a different invocation
(no `--report`, "print every finding you would post", `gh` framing). They are, accidentally, the
only measurement of ours at `high` in the study. [Inference] `high` ran ~8% *cheaper* than `mid`
on the same subjects, on fewer agents (11.9 vs 13.5) despite the higher model tier. Suggestive
only; the prompt differed, so treat it as a hint for the tier-measurement item in #dcc-e0wj
workstream 2, not a result.

**Further distortion — overlap and uniqueness are inflated.** `unique_true` counts clusters found
by only one tool. On subjects 2, 3, 9 and 10 a cluster found by ours *and* by the mislabeled
"anthropic" cell reads as two tools agreeing when it is **one tool at two settings**. That
understates ours' uniqueness and overstates cross-tool corroboration, for those subjects. Any
overlap/Jaccard figure covering them needs recomputing after the re-runs.

# Fix

- [x] [run] `rg -n "invocation" competition/benchmark/tools.json` — expect: the anthropic entry
      names the plugin unambiguously. Done: it now says run `code-review:code-review` from
      code-review@claude-plugins-official, states it is NOT `decaf-quality:code-review`, and
      instructs aborting rather than substituting if the qualified skill does not resolve
- [x] [manual] Invalid cells quarantined to `runs-invalid/` and reset to `pending`, so
      `/bench-status` no longer counts them and `rebuild_metrics.sh` drops them (90 → 81 rows)
- [x] [run] `python3 competition/benchmark/analysis/scripts/verify_run_provenance.py` — expect:
      exit 0; every done run's dominant `attributionPlugin` matches its declared tool. Done:
      script lives at `scripts/verify_run_provenance.py` and `run_cell.sh` calls it after each
      cell, printing a loud PROVENANCE MISMATCH rather than failing (the output is already
      captured; quarantining is the operator's call)
- [x] [manual] The affected cells re-run and re-graded blind — **9 cells, not 11**: closer reading
      split the four unattributed cells into two faithful runs (`5__r1`, `6__r1`, both carrying
      `code-review` attribution on some sub-agents) and two degenerate ones (`3__r2` with 0
      sub-agents, `6__r2` with 1). All 9 re-run clean; subjects 2, 3, 6, 9 and 10 re-analysed.
      Actual re-run cost ~$74 against the ~$65 estimate
- [x] [manual] Downstream artifacts and the three citing nibs restated — synthesis page rebuilt on
      clean data (commit 85930ab); #dcc-e0wj, #dcc-hyxw, #dcc-gcob and #dcc-05uw restated

# Notes

Found while evaluating anthropic's git-history retrieval channel for #dcc-e0wj workstream 4 —
the roles could not be read from `attributionAgent`, and checking why exposed the mismatch.

The tell was visible earlier and misread: subjects 2, 3, 9 and 10 were exactly the subjects whose
`analysis.json` lacked per-sub-agent persona labels (#dcc-m8ar notes recovering them for *ours*).
That was not an extraction gap for those cells — it was a different tool running.

## Summary

Nine of eighteen anthropic cells did not run anthropic. Seven executed decaf-quality (ours) at
`high` mode under anthropic's label; two were degenerate (0 and 1 sub-agents against a workflow
mandating five reviewers plus scorers). Cause was a naming collision, not a harness bug —
`decaf-quality` ships a skill named `code-review` and the official plugin ships a command of the
same name, so the unqualified invocation in `tools.json` resolved to ours.

Fixed by quarantining the nine cells to `runs-invalid/`, resetting them to `pending`,
plugin-qualifying the invocation, and re-running all nine clean. Subjects 2, 3, 6, 9 and 10 were
re-analysed blind against their frozen answer keys. Added `scripts/verify_run_provenance.py`,
wired into `run_cell.sh`, which checks each cell's dominant `attributionPlugin` against
`tools.json`; it now passes on all 90 runs.

Impact was larger than first assessed, and in one place it reversed a conclusion. Anthropic's
published $11.82/run and 0.88 calibration were a blended column: clean figures are **$7.61 and
0.92**, with 18/18 recall and a 56% substantive share — so ours is **2.8×** more expensive, not
1.8×. Per-agent output was the biggest miss: anthropic emits 9.6k, not the 13.7k recorded, making
the gap to ours **2.0×** rather than 43%. And repo-size sensitivity inverted — anthropic is 0.572,
not 0.119, which means **ours now has the lowest in the field (0.403)**, so #dcc-gcob is defending
a lead rather than chasing one.

Quality conclusions survived; cost and per-agent conclusions did not. The synthesis page was
rebuilt on clean data and #dcc-e0wj, #dcc-hyxw, #dcc-gcob and #dcc-05uw restated.

Two things worth carrying forward. The tell was visible early and misread: subjects 2, 3, 9 and 10
were exactly the subjects lacking per-sub-agent persona labels, which I diagnosed as an extraction
gap and built a recovery around rather than asking why those four. And the re-run cost ~$74 —
trivial against the months the error sat in published conclusions.
