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

## 0.5 What is under test (2026-07-29)

The study began as a five-tool comparison. It is now primarily a **preset comparison**: `ours-bugs`,
`ours-review` and `ours-audit` — the three presets of the reworked code-review skill — run on one
subject per size class (1 small, 5 medium, 9 large), with `anthropic-code-review` and `superpowers`
retained as external reference points.

**`pr-review-toolkit` and `tag1-comprehensive-review` are retired as targets** and will not be run
again. Their 36 graded cells stay committed and stay in the analysis: they are the evidence behind
several closed findings — notably the corroboration measurement that scrapped the disjoint-briefs
intervention — and removing them would change cluster membership for every other tool, since
clusters are pooled across whatever tools are present.

**The `ours-*` cells are not comparable to the archived `ours` column.** Those ran the pre-axis
skill at `mid --report`, before `roster`, `models`, `evidence` and `reach` existed. Treat the
archived figures as a different tool, not as a baseline these can be diffed against.

## 1. Inputs (already on disk per cell)

- `runs/<cell>/findings/` — `00-final-output.md` (consolidated) + `subagent-NN-*.md` (each agent's
  full output) + the tool's own report file (the `ours-*` presets write one; the archived tag1 runs did too).
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
| **valid-other** | a real, diff-verifiable defect not in the answer key (bonus signal) — a concrete behavioral consequence or a protection that doesn't protect |
| **valid-minor** | a correct **improvement suggestion**: verifiably true; a specific one-shot fix at a specific location; anchored in something finite and in-repo (the file's own conventions, repo tooling, objective doc/comment/spelling correctness, a documented contract); plausibly accepted by *these* maintainers as a patch without debate. The class converges under a fix-and-rerun loop. |
| **trivia** | true but valueless for attention: taste-only (no in-repo anchor); speculative with no concrete pathway; pre-existing/out-of-scope code the diff didn't touch; duplicative restatement; an unbounded suggestion class that would regenerate forever; meta/process commentary. **Borderline → trivia** (default-down: attention is the scarce resource). |
| **false-positive** | asserts a problem the judge refutes against the code |

(`nitpick` is the legacy name for the union of valid-minor + trivia; old analyses may carry it and it
is folded into trivia by the metrics script. The valid-minor/trivia boundary is deliberately graded
against the subject repo's *own demonstrated bar* — its conventions, lint/analyzer config, and what its
maintainers merged or dismissed in review threads — not against an abstract taste standard.)

Judge also records: judged severity, confidence (0–100), one-line rationale. Blind = tool labels
stripped and clusters shuffled before grading.

## 4. Metrics

**Quality (the point):**
- **Bug-catch rate** *(headline)* = fraction of a tool's subjects with a `TP-primary`. "Did it catch
  the real bug?"
- **Human-issue recall** = `TP-human / |human_issues|` (subjects with threads).
- **Precision** (substantive) = `(TP-primary + TP-human + valid-other) / all findings`. valid-minor does
  NOT count toward precision — it is reported separately so the substantive number stays comparable.
- **Suggestion yield** = valid-minor clusters per cell — correct, actionable improvement suggestions
  (conventions, naming, doc fixes, coverage nits a maintainer would take).
- **Trivia rate** = trivia clusters per cell (replaces the old nitpick/noise rate).
- **FP rate** = false-positives per cell; **FP share** = `FP / all findings`.
- **Signal density** = `(TP + valid-other) / all findings`.
- **Severity calibration** = P(judged substantive | the tool's **consolidated report** ranked the
  cluster critical/high) — "can you trust the tool's top-of-list and stop reading?" Only the severity
  a reader actually sees counts: `reported_by` entries with `subagent: null`. A sub-agent's private
  claim is excluded, because it never reached the reader and so is not evidence about the artifact's
  top-of-list. Counting it (the definition through 2026-07-29) measured sub-agent over-claiming
  instead, which penalized fan-out tools in proportion to how many agents they run — see #dcc-hmp6.

  Aggregated across subjects by **pooling** (`Σ substantive / Σ flagged`), not by averaging the
  per-subject ratios. Per-subject denominators run 0–25 clusters, so a mean of ratios would let a
  subject with one flagged cluster outweigh one with twenty, and would silently drop the subjects
  where a tool flagged nothing — leaving each tool averaged over a different set of subjects.
  Reports publish `k/n` beside the ratio.

  **Read the denominator.** The corpus yields 10–48 flagged clusters per tool over 9 subjects;
  `anthropic-code-review` emits confidence scores rather than severities and lands at n=10, where a
  single cluster moves the figure by 0.10. Treat the column as a direction, not a score, and do not
  rank tools on differences smaller than the interval that n supports. Subject 10's extraction
  captured no severities at all, so every tool is undefined there.

**Overlap & uniqueness:**
- **Unique-true** = TP/valid clusters found by **only this tool**.
- **Inter-tool overlap** = pairwise **Jaccard** over TP/valid clusters (which tools are redundant vs.
  complementary).
- **Subagent redundancy** = within a fan-out tool, `1 − distinct_findings / discovery_reports`,
  counted **inside a single run**; plus **per-agent unique yield** (does agent K ever find something
  no sibling did? — the systematic version of the corpus's "quick-reviewer 0-unique" signal).

  Three categories are excluded, because counting them measures something other than siblings
  re-finding each other (the definition in force through 2026-07-29 counted all three, which put
  `ours` at 77% against a true 44% and made it look like the field's outlier — see #dcc-gcob):
  the **consolidated report's own rows** (the report is not one of the sub-agents); **verification
  agents** (validators, and anthropic's rubric `scorer` — re-examining a raised finding is the job,
  not duplication); and **cross-repeat matches** (keyed by cluster *and* repeat, so an agent finding
  the same real defect in both runs reads as determinism).

  Reports publish `k/n` beside the ratio and a `*` where sub-agent personas could not all be
  resolved — the verifier exclusion is then incomplete and the figure reads high. Persona resolution
  is 100% for `ours` (a per-run persona cache exists) and 77–83% for the other fan-out tools.

  **Redundancy is not straightforwardly waste.** Clusters the judge graded substantive average 2.80
  finders against 1.64 for valid-minor and 1.32 for trivia; 72% of substantive findings are
  multi-finder against 16% of trivia. Agreement is the strongest available signal that a finding is
  real, and consolidation ranks on it — so read a high number as "this tool corroborates", not
  automatically as "this tool wastes tokens".
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
- **overall** — the **cost–quality frontier**: is the fan-out premium *buying* bug-catches and
  unique true findings, or mostly more noise vs. the lean tools? Which tool wins per context.
- **preset × preset** (from 2026-07-29) — the comparison the study now exists for: `bugs` / `review`
  / `audit` on identical code. Cross-tool ranking is secondary; the live question is what each
  preset delivers for what it costs.

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
- **Cell isolation** — every cell starts from a pristine checkout. `repos/<subject_id>` is shared by
  all 16 cells of a subject, so `run_cell.sh` does `checkout -f` + `clean -xfd` before each one and
  refuses to run (exit 77, cell left `pending`) if anything survives. Without this a tool that writes
  artifacts into the tree seeds the next cell: decaf writes `.decaf/code-reviews/` and its
  recurring-findings cross-check reads that directory, so later cells harvested earlier cells'
  findings. Competitor tools write nothing into the tree, making the leak asymmetric and inflating
  decaf-family recall. This invalidated 27 cells and all 9 subject analyses on 2026-08-06 — see
  `quarantine/2026-08-06-decaf-leak/README.md`. **Before grading a subject, confirm no cell's findings
  bundle contains another cell's report file.**

## 8. Pilot first

Run the whole pipeline on **subject 10** (10 cells, already complete) end-to-end → produce its HTML
report → sanity-check the rubric, the clustering tolerance, the metrics, and the bias controls with a
human pass → refine this doc → then apply per subject as the matrix fills, and build the synthesis
page once enough subjects are done.
