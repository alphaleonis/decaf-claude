# `bugs-sp` experiment — results (2026-08-17)

The `ours-bugs-sp` arm (`PROPOSAL-BUGS-SP.md`, nib `dcc-1sbc`) run on the two pilot subjects
(`prometheus/prometheus#18081` library/L, `dotnet/efcore#34127` library/M), 2 repeats each, shim on,
all four cells CLEAN, and folded into the existing pooled adjudication. Every figure below is read
from `pooled/<subject>/metrics.json`; nothing here is hand-computed except the pooled sums of
per-subject fields, shown with their per-subject parts. Judge: `claude-opus-5` (cutoff 2026-05);
**both subjects are `out-of-window`** (merged after the cutoff), so their numbers may be pooled.

## How the arm was folded in — and why the baseline is untouched

Adding an arm to an already-graded subject was done **incrementally**: the 51 new findings were
extracted (both layers, `disposition` mandatory), then clustered against the existing clusters by an
agent that saw cluster summaries only. Result: **48 of 51 merged into clusters the pilot had already
graded twice; 3 new clusters, all on prometheus, all `demoted`-only** (two pre-existing notes, one
considered-and-cleared check). Every *reported* `bugs-sp` finding on both subjects landed in a
cluster whose verdict and class the pilot had already fixed — so the arm's reported-side figures rest
entirely on pilot verdicts, and no existing tool's figure moved (asserted field-by-field on both
subjects before and after).

The 3 new clusters were graded blind in two independent passes, inside a stratified sample of 15
pilot-graded clusters relabelled so the judge could not tell new from old. Calibration on that
sample: today's pass 1 agreed with the pilot's pass 1 on 11/14, with the pilot's pass 2 on 9/14; the
two passes today agreed with each other 14/14; class assignments agreed with the pilot on 11/14 (the
misses on the risk/design/defect edges dcc-opdr already noted). Judge stability over the full 132
prometheus clusters after the fold-in: exact agreement 0.894, κ 0.843 (was 0.899 / 0.852 over 129).

`score_pooled.py` gained two per-tool fields for this: `class_distribution` (reported and found)
and `defect_recall` against the pool of real defect-class clusters — the two tables TUNING-SIGNALS
had computed by hand. Verified to reproduce those hand counts exactly on both subjects.

## Primary readout — reported clusters by judge-assigned class (pooled; prom+efcore)

| tool | defect | risk | test-gap | docs | design | style | **total** |
|---|---|---|---|---|---|---|---|
| `ours-audit` | 20 (15+5) | 8 | 21 | 8 | 14 | 7 | **78** |
| `pr-review-toolkit` | 14 (8+6) | 2 | 13 | 11 | 10 | 4 | **54** |
| `superpowers` | 13 (8+5) | 2 | 12 | 8 | 8 | 2 | **45** |
| `ours-review` | 12 (8+4) | 2 | 9 | 5 | 9 | 2 | **39** |
| `comprehensive-review` | 11 (6+5) | 4 | 6 | 7 | 12 | 1 | **41** |
| **`ours-bugs-sp`** | **8 (5+3)** | 1 | 3 | 2 | 4 | 0 | **18** |
| `ours-bugs` | 6 (4+2) | 0 | 0 | 0 | 1 | 0 | **7** |
| `anthropic-code-review` | 5 (4+1) | 0 | 2 | 2 | 2 | 0 | **11** |

`bugs-sp` reports 2.6× what `bugs` reports and 8 defect-class clusters against 6 — but its
defect share is **44%**, not `bugs`' 86%. Split by decaf's own report tiers: the **primary**
findings (verdict-driving) are 10 clusters at **70% defect** (7 defect + 3 test-gap, and those three
are tautological/snapshot tests the seat's brief classes as defects); the **Minor bucket**
contributed the other 8 (4 design, 2 docs, 1 risk, 1 defect). The composition drift is almost
entirely the Minor bucket — items the `bugs` funnel would have routed to Considered But Not
Flagged, which the single seat reports as one-liners.

## Defect recall against the real-defect pool (11 prom + 5 efcore = 16)

| tool | found | reported | suppressed | recall (reported) | recall (found) |
|---|---|---|---|---|---|
| `ours-audit` | 13 | 13 | 0 | 0.81 | 0.81 |
| `pr-review-toolkit` | 12 | 12 | 0 | 0.75 | 0.75 |
| `superpowers` | 9 | 9 | 0 | 0.56 | 0.56 |
| `ours-review` | 10 | 9 | 1 | 0.56 | 0.62 |
| `comprehensive-review` | 10 | 10 | 0 | 0.62 | 0.62 |
| **`ours-bugs-sp`** | **10** | **6** | **4** | **0.38** | **0.62** |
| `ours-bugs` | 8 | 5 | 3 | 0.31 | 0.50 |
| `anthropic-code-review` | 6 | 5 | 1 | 0.31 | 0.38 |

The single seat **found 10 of 16 — more than `superpowers`' 9 and `ours-bugs`' 8** — and reported
6. Its four "suppressed" defects are not funnel losses; there is no funnel. Each is an item the seat
examined and parked under Considered But Not Flagged with a stated reason:

| cluster | judged | what the seat said |
|---|---|---|
| prom c05 (matches-thread, medium) | subquery step attribution clamps trailing steps | "deliberate and documented in the code comment" |
| prom c07 (valid-other, medium) | `samplesRead` over-counts under lookback | "documented as intended at feature_flags.md:48 — design choice" |
| efcore e04 (valid-other, medium) | `RestoreNullValueColumnsList` wrong counter | "pre-existing, out of reach" — **`reach=narrow` working as designed** |
| efcore e13 (matches-thread, high) | `Coalesce` is a legal binary operator that does not propagate NULL | traced reachability, "never constructed in the relational stack today" |

Three are judgment calls where the seat traced the mechanism and disagreed with the human reviewer
and the judge (on e13, `superpowers`' agent reached the same "unreachable" conclusion and listed it
as a *strength*); one is the reach rule doing exactly what `bugs` asks. Contrast `ours-bugs`' three:
`adversarial-reviewer` **reported** them (one at Critical) and the funnel binned them.

## The other axes, per subject

| | subject | reported | found | real (reported) | real (found) | unique real | precision | thread recall (found) | cost / cell | $ per real |
|---|---|---|---|---|---|---|---|---|---|---|
| **`bugs-sp`** | prom | 11 | 22 | 8 | 10 | 0 | **0.73** | 0.3 (0.4) | $5.31 | $1.33 |
| | efcore | 7 | 17 | 4 | 7 | 0 | n=7 — not publishable | 0.1 (0.1) | $4.96 | $2.48 |
| `bugs` | prom | 5 | 20 | 3 | 6 | 0 | n=5 — not publishable | 0.1 (0.4) | $9.01 | $6.00 |
| | efcore | 2 | 20 | 2 | 6 | 0 | n=2 — not publishable | 0.0 (0.0) | $8.29 | $8.29 |
| `superpowers` | prom | 28 | 28 | 22 | 22 | 3 | 0.79 | 0.7 (0.7) | $4.59 | $0.42 |
| | efcore | 17 | 17 | 9 | 9 | 1 | 0.53 | 0.2 (0.2) | $3.99 | $0.89 |

Thread recall is over 10 admitted human threads per subject (not thin). `missed_by_every_tool` is
unchanged by the new arm (prom threads 1, 2, 7; efcore 7, 8, 9); `judge_dismissed_reported_threads`
is empty on both. `bugs-sp` has **zero unique real findings**, like `bugs`.

## Repeat stability

Reported-cluster Jaccard across the two repeats: `bugs-sp` 0.36 (prom) / 0.43 (efcore);
`superpowers` 0.36 / 0.41; `bugs` 0.60 / 0.50. Real defects reported per repeat: `bugs-sp` prom
{c01,c02,c04} vs {c01,c02,c03}, efcore {e01,e02} both; `superpowers` prom 4 vs 6, efcore 3 vs 1. The
single seat's variance is superpowers-like — and larger than `bugs`', whose overlap is high because
it reports so little. Cost spread on prometheus $6.30 vs $4.31 is the same variance seen in money.

## Against the pre-registered success criteria

| criterion | target | measured | |
|---|---|---|---|
| recall — real defects **reported** | ≥ 8 / 16 | **6** (found 10) | ✗ |
| cost | ≤ $4.30 / cell mean | **$5.13** | ✗ |
| composition — defect share of reported | ≥ 2/3 | **44%** all reported; 70% primary-only | ✗ (all) / ✓ (primary) |
| repeat stability | within wave arms' variance | superpowers-like, above `bugs`' | ~ |

**None of the four passes cleanly.** But read against the failure guidance the proposal wrote in
advance: recall failed *while superpowers passed on the same cells* — the proposal says diff the
briefs, not the pipeline. The seat found more real defects than superpowers; the difference is
entirely disposition. And composition failed through the Minor bucket, not through primary findings.

## What this does and does not establish

- **`bugs-sp` dominates `bugs` on every reported axis at ~40% less cost**: 18 vs 7 reported, 12 vs 5
  real, 8 vs 6 defect-class, 10 vs 8 found, prometheus precision 0.73 (publishable) where `bugs` never
  reaches n=10, thread recall 0.3 vs 0.1 on prometheus, $1.33–2.48 vs $6.00–8.29 per real finding.
  Zero unique findings for both.
- **It does not reproduce `superpowers`**: 18 vs 45 reported, 12 vs 31 real, 0 vs 4 unique, and 20%
  dearer. The seat *finds* as much or more (10 vs 9 pool defects) but reports less and costs more —
  the two mechanisms are the brief's dispositions (three defects it argued away) and something in the
  path that produces ~40% more Opus output for fewer reported findings; the latter is unattributed
  and is the concrete follow-up.
- **The in-prompt-scoping hypothesis is half-confirmed**: `reach=narrow` held on primary findings
  (70% defect, one absence hunt correctly declined) but the Minor bucket leaks design/docs one-liners
  the funnel would have hidden.
- **Two subjects; the pilot's rules bind.** Nothing here promotes `bugs-sp` beyond experimental,
  and no cross-tool ranking from this run is publishable on its own.

---

## Cost attribution (2026-08-17, dcc-pulk item 1)

Where the $0.84/cell gap to superpowers goes, from the eight cell transcripts (four per tool, same
two subjects). Method: dedupe per-request `usage` by `requestId` — after which **cache-read tokens
reconcile to `meter.json` exactly in all eight cells**, so turn structure and the input side are
attributable per lane. Per-request `output_tokens` in transcripts is *not* usable (it sums to 19–35%
of the meter, non-uniformly — the earlier correction's warning stands), so output is taken from the
meter as a whole-cell total. Prices are fitted from the meters themselves (least squares over 50 Opus
rows: $26/M out, $0.52/M cache-read, $6.6/M cache-write; median error 2%), not from memory.

| per cell (mean of 4) | `bugs-sp` | `superpowers` | Δ |
|---|---|---|---|
| orchestrator, input side — **exact** | $0.89 | $0.40 | **+$0.49** |
| seat, input side — **exact** | $2.51 | $2.68 | −$0.17 |
| output, all lanes (meter) | $1.71 | $1.22 | +$0.49 |
| meter | $5.13 | $4.29 | +$0.84 |
| orchestrator turns (with thinking) | 10.2 (6.2) | 4.8 (1.2) | |
| seat turns (with thinking) | 36.2 (28.0) | 41.8 (29.2) | |

**The seat is not the gap.** Its input side is slightly *cheaper* than superpowers' agent, and its
visible emissions match on every axis that can be measured: 22–38k vs 25–30k chars emitted, 35–45 vs
37–51 shell calls, 6–14 vs 11–12 build/test runs, 2–3 vs 2–3 temporary worktrees, 28 vs 29 thinking
turns. [Inference] The output-side Δ is therefore orchestrator too — the seat lanes are equal, and
the orchestrator emits the seat's 15–18k-char report a second time as a 15–24k-char file plus
thinking on 6 turns against 1.

**What the orchestrator's extra ~$0.85 is**, read off its turns:

1. **The 69 KB `code-review` SKILL.md is ~35k tokens of context** — cache-read jumps from 16k to
   51k on the turn after the skill loads — and every one of the ~10 orchestrator turns re-reads it.
   Superpowers' skill is 95 lines. This is most of the exact $0.49: `bugs-sp` needs ~2.5 KB of that
   file (its own section) and loads all of it.
2. **~10 turns instead of ~5**: four context-gathering shell turns (diff stat, log, a per-file diff,
   spec-discovery globs), then after the seat returns: read the `--report` convention file, `git
   status`, `mkdir`/`date`, **Write the report**, `git status` again, closing text.
3. **The report is emitted twice**: the seat returns it as text (its return value), then the
   orchestrator re-emits it — reformatted with header, rationale and agent-summary ceremony, 1.3–1.6×
   longer — through the Write tool. There is no "pipe tool result to file" primitive, so this costs
   the whole report in output tokens a second time (~$0.15–0.20/cell at fitted prices), plus a turn.

**Levers, in order of size** [Inference from the above; unmeasured until re-run]: (a) stop loading
the whole SKILL.md on the `bugs-sp` path — a thin skill or a split file, saving ~30k tokens × ~10
turns of cache reads (~$0.15–0.20) and shrinking every orchestrator turn; (b) let the seat write the
report file itself and return a one-line summary — sound on this path because there is no shared
tree, and it removes the re-emission and one turn (~$0.20–0.25); (c) fold the context-gathering and
housekeeping into two shell turns instead of eight. Together these plausibly land `bugs-sp` at
≈$4.3–4.5/cell — the superpowers anchor — without touching the seat.

**Note on the earlier correction.** dcc-1ix0's CORRECTION dismissed "orchestrator overhead" for the
`bugs` wave on a regression that its own caveat later called confounded. On the one preset where the
lanes are separable — one seat, so the residual is the orchestrator — the overhead is real and
measured: ~$0.85 of $5.13, and 100% of the gap to a tool with the same seat.
