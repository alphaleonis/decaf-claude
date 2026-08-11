# v2 scoring (nib dcc-y2e6)

Deterministic half of the v2 pipeline. The LLM stages (extract → cluster → blind grade) are driven by
`/bench-analyze-v2`; everything numeric lives here, so no metric is ever produced by a model.

| File | Role |
|---|---|
| `score_pooled.py` | validate `analysis.json`, then compute the three axes → `metrics.json` |
| `check_artifacts.py` | assert `extract/`, `findings.json` and `analysis.json` describe one finding set |
| `judge_stability.py` | two blind grading passes over the same clusters → agreement, kappa, and the disagreement list |
| `test_score_pooled.py` · `test_judge_stability.py` | one self-test per guard below — run them rather than counting from here, since a written-down count drifts (it said 12 when there were 15) |

## Does the grader agree with itself?

Every pooled number rests on one subjective call — `valid-other` versus `trivia` — so the pilot
(`dcc-vkeh`) grades a sample twice, blind both to tool identity and to the first pass, and runs
`judge_stability.py pass1.json pass2.json`. It reports exact agreement, Cohen's kappa on the 6-way
verdict, kappa on the `real`/`not-real` collapse that precision actually depends on, agreement
restricted to the `valid-other`/`trivia` boundary, and every disagreement by cluster.

The **pre-registered** threshold — fixed before the first pass ran, so it cannot be drawn around the
result — is `real_vs_not.kappa >= 0.60` and `exact_agreement >= 0.70`. Pass 2 must run in a separate
process; a continuation of the session that produced pass 1 measures memory, not stability.

## Four axes, never merged

- **pooled** — precision (plain and severity-weighted), trivia ratio, unique real findings, noise per
  cell. Bounded by the union of tool output, so it cannot see what everything missed.
- **threads** — recall against admitted **human** review threads. The miss detector, and the only
  axis not derived from tool output — a property that holds *by construction*, not by assumption:
  every admitted thread carries `origin: human|bot` (stamped by `annotate_thread_origin.py` from the
  committed `bot-authors.json`, derived per corpus by `derive_bot_authors.py`), and the scorer
  refuses to run without it. Agreement with expert review is related to, but not the same as,
  finding real bugs — OSS reviewers skew toward API design and convention over correctness.
- **incumbent** — `incumbent_agreement`: recall against admitted **bot** threads, i.e. agreement
  with incumbent automated review (Copilot, Greptile, CodeRabbit, Codex, Graphite, CodeQL — several
  are peers or competitors of the tools under test). A legitimate measurement, but not a miss
  detector, and never pooled with the human axis: on the first corpus 28% of admitted threads were
  bot-authored, unevenly spread from 0% to 80% per subject (`analysis/THREAD-AXIS.md`).
- **anchor** — recall against an answer key, for anchor subjects only.

**Thin human cells:** `threads.human_axis_thin` is true when the subject holds 1–2 human threads
(four of the seven citable subjects do). A recall there is 0/0.5/1.0 quantization, not a
measurement — report it per subject with n shown; never pool it, never headline it.

## Reported vs found

A tool can find a defect, verify it, and then suppress it below its own reporting bar. Every
recall-style metric is therefore computed twice, and neither figure is allowed to stand alone:

| Metric | Meaning |
|---|---|
| `thread_recall` / `anchor_recall` | what a user would actually have been shown |
| `thread_recall_found` / `anchor_recall_found` | what the tool is capable of finding |
| `demotion_gap` | the difference — a publishable tool property, not an artifact |

Precision-style metrics count **reported findings only**, because a demoted finding costs the reader
no attention. `clusters_reported` and `clusters_found` are both emitted.

The corpus-level miss detector splits the same way. `threads.missed_by_every_tool` is what nobody
*showed*; `missed_by_every_tool_found` is what nobody *found*; the difference,
`demoted_by_every_tool_that_found_it`, is a threshold problem rather than a blind spot — a distinction
that decides whether the fix is a better model or a changed reporting bar.

Verified against the real cell that motivated this: an anthropic run headlined "Verdict: No blocking
issues found" while its sub-threshold section described the key defect exactly, verified empirically.
It scores **anchor_recall 0.0 / anchor_recall_found 1.0**. A tool that finds everything and reports
nothing is not the same product as one that finds nothing — and the fix for the first is a threshold
change, not a better model.

## Verdicts

`matches-key` · `matches-thread` · `valid-other` · `valid-minor` · `trivia` · `false-positive`

v1's `TP-primary`/`TP-human` are renamed so nothing presupposes a key — pooled subjects have none.
The old names are rejected rather than silently accepted, so a stale grader fails loudly.

Severity weighting is applied to precision because v1's was unweighted, which let four minor findings
outscore one revert-forcing defect.

## Guards that exit 3 rather than emit a number

Each one corresponds to a defect that already produced a wrong published figure, or to a requirement
of the scoring-model decision:

- a tool whose findings carry **no severity at all**, or on under 20% of them — a stray sub-agent
  `critical` once handed a tool a free 1.00 on n=1 carrying a full one-ninth of its published figure.
  That is the *tool-reported* severity, which `/bench-synthesize` reads for its calibration axis
- a cluster with **no `judged_severity`**, or one outside the weight table. This is the field
  `precision_severity_weighted` actually divides by, and an absent one used to default silently to
  weight 1.0 — the same weight as `low`, so an ungraded cluster was indistinguishable from a
  low-severity one
- a **cell contributing zero clusters** — nearly always an extraction failure, since the tool still
  wrote a report. **The null arm is the exception** and must pass `--allow-silent-cells`: there, a
  tool that reported nothing is the headline result, not a defect
- a **real verdict without a `code_citation`** — the judge shares a model family with the reviewers,
  so an unciteable verdict is not evidence
- `matches-thread` **without a thread index**, or an index out of range — and the same for
  `matches-key`, which was previously unguarded, so a key match with no index was silently dropped
  from anchor recall and read as a miss
- a **v1 verdict name**, so a stale grader cannot pass silently
- **missing `judge_model`** — results must be attributable to a grader
- an **admitted thread without `origin: human|bot`** — thread recall is defined over the human
  population only, and a thread whose population is unknown makes every thread-recall figure
  unprovable as human-only. Annotate the corpus rather than let 28% competing-tool output back into
  the miss detector
- artifacts describing **different finding sets** (`check_artifacts.py`): 20 findings in one layer, 33
  in another, 1 in common, and the clustering run on the stale set

Run `python3 test_score_pooled.py` after any change. A guard without a passing test is a guard that
has not been shown to fire.
