---
description: Analyze one benchmark subject's findings quality (blind-graded) → committed markdown + HTML report
argument-hint: "<subject_id>"
---

Run the findings-quality analysis for **subject `$ARGUMENTS`**, following
`competition/benchmark/analysis/METHODOLOGY.md`. Judge with the **current session model**, grade
**blind** (tool identity hidden), verify every claim **against the real diff** (don't vibe). Output
goes to `competition/benchmark/analysis/subject-NN/`: `analysis.json` (structured judgment),
`metrics.json` (computed), `report.md` (narrative, canonical for the later cross-subject synthesis),
`report.html` (readable page). Do NOT hand-compute metrics — the script does that.

## Steps

**1. Gather inputs.**
```
bash competition/benchmark/analysis/scripts/gather_inputs.sh $ARGUMENTS
```
This writes `costs.json` and prints the done cells, their `findings/` bundles, the subject fixture
(`.ground_truth`), and the `git diff` command for the review diff. Read the diff — you need it for
grading. If there are 0 done cells, stop and say so.

**2. Build the answer key** (`subject-NN/answer-key.json`) and freeze it BEFORE looking at any tool's
findings. From the fixture's `ground_truth` + the reverting/fixing PR (fetch with `gh pr view`) + the
diff, write: `primary_bug` (the escaped defect a reviewer MUST catch — pin file + locus + what should
be flagged), `human_issues[]` (issues from the PR's human review threads; may be empty), optional
`known_safe[]` (diff patterns that look buggy but are correct). Schema in METHODOLOGY §2.

**3. Extract findings** — for each done cell, dispatch a subagent (parallel) to read that cell's
`findings/` bundle (`00-final-output.md` + `subagent-*.md`) and emit its findings normalized to:
`{tool, repeat, subagent, severity, file, line, category, claim, raw}` (METHODOLOGY §3A). Attribute
each to its subagent where the bundle makes it clear. Collect all into `findings.jsonl`.

**4. Cluster** — pool all findings and group ones asserting the SAME underlying issue (same file,
~same line, same claim) into clusters. Each cluster: `{cluster_id, summary, file, line, category,
reported_by:[{tool,repeat,subagent,severity}]}`. This is the overlap/uniqueness engine — be careful
that "the same bug described differently" collapses to one cluster.

**5. Blind grade** — dispatch a grader subagent with: the **review diff**, the **answer key**, and the
clusters **with tool identity stripped** (send `cluster_id` + `summary` + `file:line` only; keep the
tool map yourself). For each cluster it returns `{cluster_id, verdict, matches, judged_severity,
confidence, rationale}` where verdict ∈ `TP-primary | TP-human | valid-other | false-positive |
nitpick` (METHODOLOGY §5). It must justify FP / valid-other against the diff. Merge verdicts back onto
the clusters (with the tool map) → write `analysis.json` (METHODOLOGY §3 + compute_metrics.py header
schema), including `judge_model` = the current session model id.

**6. Compute metrics** (deterministic — do not eyeball):
```
python3 competition/benchmark/analysis/scripts/compute_metrics.py \
  competition/benchmark/analysis/subject-$(printf %02d $ARGUMENTS)/analysis.json \
  competition/benchmark/analysis/subject-$(printf %02d $ARGUMENTS)/costs.json \
  -o competition/benchmark/analysis/subject-$(printf %02d $ARGUMENTS)/metrics.json
```

**7. Write `report.md`** — narrative PROSE only (no big metric tables; those live in metrics.json and
render into the HTML). Cover: did each tool catch the escaped bug; notable unique catches and notable
misses; false-positive / noise character per tool; subagent redundancy (did the fan-out earn its
agents?); the cost-vs-catch verdict; and honest caveats (thin human threads, judge-uncertain
clusters). Keep it readable — this file is the canonical input to the cross-subject synthesis.

**8. Render HTML:**
```
python3 competition/benchmark/analysis/scripts/render_report.py \
  .../metrics.json .../report.md .../analysis.json -o .../report.html
```

**9. Report** to the user: the leaderboard (bug-catch, precision, FP/cell, unique-true, cost/bug), the
paths, and a **human spot-check ask** — flag every `TP-primary` verdict and any `confidence < 60`
cluster for the operator to eyeball (bias control). Note the outputs are committed-local.

## Notes
- **Blind grading is non-negotiable** — never tell the grader which tool produced a cluster; it biases
  toward `ours`. Shuffle clusters before sending.
- Nothing here posts anywhere or touches the run data — analysis is read-only over `runs/`.
- Re-running overwrites `subject-NN/`; the answer key, once human-confirmed, should be kept stable
  across re-runs (freeze it).
