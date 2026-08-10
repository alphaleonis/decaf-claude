# v2 scoring (nib dcc-y2e6)

Deterministic half of the v2 pipeline. The LLM stages (extract → cluster → blind grade) are driven by
`/bench-analyze-v2`; everything numeric lives here, so no metric is ever produced by a model.

| File | Role |
|---|---|
| `score_pooled.py` | validate `analysis.json`, then compute the three axes → `metrics.json` |
| `check_artifacts.py` | assert `extract/`, `findings.json` and `analysis.json` describe one finding set |
| `test_score_pooled.py` | 12 self-tests; every guard below has one |

## Three axes, never merged

- **pooled** — precision (plain and severity-weighted), trivia ratio, unique real findings, noise per
  cell. Bounded by the union of tool output, so it cannot see what everything missed.
- **threads** — recall against *admitted* human review threads. The miss detector, and the only axis
  not derived from tool output. Agreement with expert review is related to, but not the same as,
  finding real bugs — OSS reviewers skew toward API design and convention over correctness.
- **anchor** — recall against an answer key, for anchor subjects only.

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
  `critical` once handed a tool a free 1.00 on n=1 carrying a full one-ninth of its published figure
- a **cell contributing zero clusters** — nearly always an extraction failure, since the tool still
  wrote a report
- a **real verdict without a `code_citation`** — the judge shares a model family with the reviewers,
  so an unciteable verdict is not evidence
- `matches-thread` **without a thread index**, or an index out of range
- a **v1 verdict name**, so a stale grader cannot pass silently
- **missing `judge_model`** — results must be attributable to a grader
- artifacts describing **different finding sets** (`check_artifacts.py`): 20 findings in one layer, 33
  in another, 1 in common, and the clustering run on the stale set

Run `python3 test_score_pooled.py` after any change. A guard without a passing test is a guard that
has not been shown to fire.
