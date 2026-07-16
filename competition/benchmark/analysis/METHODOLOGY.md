# Benchmark analysis methodology — findings quality

We already capture **cost / tokens / timing** per cell (see `../README.md`). This document defines
how we turn each tool's **findings** into comparable quality metrics: what they find, whether it's
real, overlap, uniqueness, false positives, noise, missed bugs, and how efficiently the fan-out
tools spend their agents. It is applied **per subject** and rolled up to a **cross-benchmark
synthesis + conclusion**.

## 0. Unit of analysis

- **Cell** = one `(tool × subject × repeat)` run — the atom.
- Roll up to: **tool**, **tool × size**, **tool × language**, and **overall**.
- The single most important quality question: **did the tool catch the escaped bug?** Everything
  else (precision, noise, overlap, efficiency) is secondary to that.

## 1. Inputs (already on disk per cell)

- `runs/<cell>/findings/` — `00-final-output.md` (consolidated) + `subagent-NN-*.md` (each agent's
  full output) + the tool's own report file (ours/tag1).
- `runs/<cell>/meta.json` — cost, whole-session + per-subagent tokens, per-subagent + total timing.
- `subjects/NN-*.json` `ground_truth` — the escaped bug, revert/fix PR, regression issue, human threads.
- **The review diff** — `git diff <merge>^1 <merge>` (reconstructable from the pinned SHA). The judge
  reads this to verify claims against the actual code.

## 2. Ground truth — the answer key (frozen BEFORE grading)

For each subject, author a graded answer key once and freeze it (LLM-drafted from the revert/fix PR +
the diff + review threads, human-confirmed):

```json
{
  "subject_id": 10,
  "primary_bug": { "summary": "...", "file": "…/line_buffer.rs", "loc_hint": "fill loop ~L416-437",
                   "must_flag": "the reviewer should flag <X>", "source": "revert #3195 / issue #3194" },
  "human_issues": [ { "id": "h1", "summary": "...", "loc": "file:line", "thread": "<url or quote>" } ],
  "known_safe": [ { "summary": "looks risky but is correct: ...", "loc": "file:line" } ]
}
```

- **`primary_bug`** = the escaped defect a competent reviewer MUST catch (objective — it was really
  reverted). This is the recall target.
- **`human_issues`** = issues raised in the PR's human review threads (SHOULD-catch). **May be empty**
  — 5 of 12 subjects have ≤1 human thread; those cells are scored on `primary_bug` + FP discipline only.
- **`known_safe`** (optional) = diff patterns that look like bugs but aren't, to test false-positive
  discipline.

## 3. Pipeline (repeatable per subject)

```
A. Extract  → normalize each cell's findings (incl. per-subagent attribution)
B. Cluster  → group findings asserting the SAME issue, across tools/repeats/subagents
C. Grade    → blind judge classifies each cluster vs. answer key + diff
D. Metrics  → aggregate
E. Report   → self-contained HTML
```

Stages A–C are LLM passes (run as subagents); the judge in C **reads the real diff** to verify each
claim, and is **blind to tool identity**.

### Stage A — normalized finding schema

```json
{ "finding_id":"10__ours__r1__3", "subject_id":10, "lang":"rust", "size":"small",
  "tool":"ours", "repeat":1, "subagent":"agent-… / persona",
  "severity":"critical|high|medium|low|nit|info", "file":"…", "line":420,
  "category":"logic|bug|security|perf|test|design|style|doc",
  "claim":"one-line assertion", "raw":"verbatim snippet" }
```

### Stage B — clustering (the overlap engine)

Assign every finding a `cluster_id`; a cluster = the same underlying issue (same file, ~same line,
same claim). Each cluster records the set of `(tool, repeat, subagent)` that reported it. This one
structure yields **all** overlap/uniqueness/redundancy metrics.

### Stage C — blind grading rubric (per cluster)

| verdict | meaning |
|---|---|
| **TP-primary** | matches the escaped bug — the key catch |
| **TP-human** | matches a human-raised issue |
| **valid-other** | a real, diff-verifiable defect not in the answer key (bonus signal) |
| **false-positive** | asserts a problem the judge refutes against the code |
| **nitpick** | real but trivial/style/out-of-scope (low value) |

Judge also records: judged severity, confidence (0–100), one-line rationale. Blind = tool labels
stripped and clusters shuffled before grading.

## 4. Metrics

**Quality (the point):**
- **Bug-catch rate** *(headline)* = fraction of a tool's subjects with a `TP-primary`. "Did it catch
  the real bug?"
- **Human-issue recall** = `TP-human / |human_issues|` (subjects with threads).
- **Precision** = `(TP-primary + TP-human + valid-other) / all findings`.
- **FP rate** = false-positives per cell; **FP share** = `FP / all findings`.
- **Signal density** = `(TP + valid-other) / all findings`.

**Overlap & uniqueness:**
- **Unique-true** = TP/valid clusters found by **only this tool**.
- **Inter-tool overlap** = pairwise **Jaccard** over TP/valid clusters (which tools are redundant vs.
  complementary).
- **Subagent redundancy** = within a fan-out tool, `1 − distinct_clusters / subagent_findings`; plus
  **per-agent unique yield** (does agent K ever find something no sibling did? — the systematic
  version of the corpus's "quick-reviewer 0-unique" signal).
- **Repeat stability** = `Jaccard(r1 clusters, r2 clusters)` — determinism.

**Efficiency (quality per resource):**
- **Cost per bug caught**, **cost per TP**, **output-tokens per TP**, **wall per TP**.

**Verdict:**
- **Verdict accuracy** = did the tool's overall verdict (needs-changes vs approve) match "this PR had
  a real regression" (all 12 did → the correct verdict is always needs-changes).

## 5. Cross-benchmark synthesis (the conclusion)

Aggregate over all 12 subjects and slice by the two axes:
- **tool × size** — does bug-catch or precision degrade on large PRs?
- **tool × language** — weak spots (e.g., ours on Rust/Go, its non-primary stacks)?
- **overall** — the **cost–quality frontier**: is the fan-out premium (ours/anthropic/tag1 at
  ~$13–20) *buying* bug-catches and unique true findings, or mostly more noise vs. the lean tools
  (pr-review-toolkit $9, superpowers $3)? Which tool wins per context.

## 6. Report (self-contained HTML)

One page per subject + one aggregate synthesis page. Inline CSS/JS, theme-aware, no external deps
(renderable as a claude.ai Artifact or opened locally). Blocks:
1. **Leaderboard** table — tool × {bug-catch, precision, FP/cell, unique-true, cost, cost/bug-caught, wall}.
2. **Cost–quality scatter** — x=cost, y=bug-catch (or F1); Pareto frontier highlighted.
3. **Bug-catch heatmap** — rows=tools, cols=subjects; green=caught / red=missed (+ human-issue shade).
4. **Overlap matrix** — tool × tool Jaccard heatmap.
5. **Subagent-yield** — per fan-out tool: distinctness bar + per-agent unique contribution.
6. **Per-subject drill-down** — the cluster table (cluster × which tools found it × verdict), so any
   claim is auditable back to the finding.

## 7. Bias controls (non-negotiable)

- **Blind grading** — tool identity stripped; clusters shuffled. Guards against home-field bias for `ours`.
- **Frozen answer key** — authored before any grading; the escaped bug is objective (it was reverted).
- **Verify, don't vibe** — the judge classifies FP / valid-other by reading the actual diff, not opinion.
- **Human spot-check** — review ≥15–20% of verdicts, **including every `TP-primary` decision** and all
  low-confidence ones; log disagreements and the judge↔human agreement rate.
- **One judge model + rubric** across all subjects; record the judge model/version.

## 8. Pilot first

Run the whole pipeline on **subject 10** (10 cells, already complete) end-to-end → produce its HTML
report → sanity-check the rubric, the clustering tolerance, the metrics, and the bias controls with a
human pass → refine this doc → then apply per subject as the matrix fills, and build the synthesis
page once enough subjects are done.
