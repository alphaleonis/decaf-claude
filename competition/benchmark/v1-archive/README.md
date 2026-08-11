# v1 archive — invalid data, kept as evidence

**Every number produced from anything in this directory is void. Do not cite one — not in a
comparison, not hedged, not "roughly."** Archived 2026-08-10 under nib `dcc-8tjr`.

This is the complete v1 dataset: 88 review cells, the graded analyses for 9 subjects, the metrics
CSV, the run ledger, and two earlier quarantines. It is kept because it is the evidence base for the
failures that ended v1 — not because any part of it is salvageable as a measurement.

## Why it is void

Four independent failures, any one of which is disqualifying:

| # | Failure | Effect | Nib |
|---|---|---|---|
| 1 | Cross-cell `.decaf/` contamination | `repos/<sid>` was one checkout shared by all 16 cells of a subject, and `ensure_repo()` skipped the reset whenever the commit was already present. Decaf's recurring-findings cross-check reads `.decaf/code-reviews/`, so a decaf cell could harvest every earlier decaf cell's report. | `dcc-2cxq` |
| 2 | GitHub cross-reference leak | 11 of 12 subjects have the fixing/reverting PR auto-linked on the original's timeline. `anthropic-code-review`'s finders cited the revert PR in both subject-9 repeats — lookup, not review. | `dcc-ho2w` |
| 3 | Unreliable ground truth | 2 of the first 3 subjects audited had invalid answer keys. The base rate of bad ground truth in the corpus is unknown. | `dcc-5xad` |
| 4 | Unpinned reasoning effort | Effort was ambient and unrecorded until `BENCH_EFFORT` was pinned in `config.env`. Cells are not known to be comparable to each other. | — |

**The two leaks push in opposite directions.** Contamination flattered the decaf presets; the GitHub
leak flattered `anthropic-code-review`. So the *direction* of any headline gap is unknown, not merely
imprecise — "approximately right" is not available as a fallback reading.

## What it may still legitimately be cited for

- **The existence and mechanism of the leaks** — the contaminated bundles under `quarantine/` are the
  primary evidence for `dcc-2cxq`.
- **Cost and wall-clock telemetry**, with care. Token spend was not affected by the leaks, though a
  contaminated cell may have terminated earlier than a clean one would.
- **Qualitative observations about tool behavior** that do not depend on the answer key — e.g. that a
  tool dispatches N subagents, or that its findings cite a URL.

Anything of the form "tool A caught more than tool B" is not on that list.

## Contents

| Path | What |
|---|---|
| `runs/` | 88 v1 cells: `final-output.md`, per-subagent `findings/`, `meta.json`, `meter.json` |
| `runs-invalid/` | 10 cells that did not run the tool they were recorded as (`dcc-9kkz`) — see its README |
| `quarantine/2026-08-06-decaf-leak/` | the contaminated runs + analyses isolated when the leak was found — see its README |
| `analysis/subject-NN/` | v1 answer keys, clusters, graded verdicts, `metrics.json`, reports. **The keys here are the unreliable ones.** |
| `analysis/cluster-replay/`, `cbnf-adjudication.json` | clustering-stability replay and one adjudication record |
| `results/metrics.csv` | the v1 leaderboard |
| `manifest.jsonl` | the v1 run ledger |

## What deliberately stayed outside this directory

`scripts/`, `analysis/scripts/`, `analysis/METHODOLOGY.md`, `subjects/`, `tools.json`, `config.env`
and `subjects.annotations.json` are **machinery and corpus definition**, not results. v2 adapts them
(`dcc-y2e6`) rather than starting over.

One caveat worth knowing: `subjects/NN-*.json` still carries a `ground_truth` block, and that is the
ground truth failure #3 is about. `dcc-5xad` audits all 12. Until it lands, treat any
`subjects/*.json` ground truth as a claim, not a fact — v2 reads its own `v2/subjects/` and
`v2/analysis/subject-NN/answer-key.json`, and must never fall back to these.

## Path safety

No v2 code path can reach anything in here. v2 reads `v2/subjects/`, `v2/analysis/`, `v2/runs/`;
this tree is `v1-archive/`. The specific collision that motivated the move was
`analysis/scripts/gather_inputs.sh` writing to `analysis/subject-NN/` — the same directory shape v2
uses — which would have let a v2 grader pick up a v1 key by path convention alone. `analysis/` now
holds only `scripts/` and `METHODOLOGY.md`; no `subject-NN/` remains, and `gather_inputs.sh` writes
to `v1-archive/analysis/`.

Re-verified 2026-08-11 (`dcc-3cm6`): no surviving v1 script writes anywhere v2 reads. One consequence
worth knowing — `analysis/scripts/cluster_replay.py` still globs `analysis/subject-*/findings.json`
and therefore now matches nothing and returns silently. It is v1-only and reads nothing v2 writes, so
it is left as archived evidence rather than repaired.

The v1 driver (`scripts/bench_next.sh`) refuses to run without `BENCH_V1_ALLOW=1`, so a stray
`/bench-run` cannot append new cells to a dataset that is already void.
