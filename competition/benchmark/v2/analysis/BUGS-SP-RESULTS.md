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

---

## Brief v2 (`ours-bugs-sp2`, 2026-08-17) — Minor bucket omitted under `narrow`, fail closed

Same two subjects × 2 repeats, all CLEAN, folded in the same way (extract → cluster against the
pools → blind-grade only new clusters inside relabelled calibration samples, two passes + class).
Every *reported* v2 finding again landed on a pilot-graded cluster; 3 new clusters, all
demoted-only. Pilot tools' figures unchanged except `ours-audit`'s prometheus `unique_real` (−1:
v2 *found* c15, which only audit had reported — correct semantics, not drift). Calibration: 10/14
(prom), **3/12 (efcore)** — see `scoring/prompts/README.md`; efcore's one new cluster is
demoted-only trivia in both passes so no reported figure rests on today's judge.

| per cell (mean of 4) | v1 `bugs-sp` | **v2 `bugs-sp2`** | superpowers |
|---|---|---|---|
| reported clusters (pooled) | 18 | **8** | 45 |
| defect share of reported | 44% (70% primary-only) | **62%** | 29% |
| real defects reported / found (of 16) | 6 / 10 | **5 / 9** | 9 / 9 |
| real clusters reported (pooled) | 12 | **7** | 31 |
| repeat Jaccard, prom / efcore | 0.36 / 0.43 | **0.50 / 0.50** | 0.36 / 0.41 |
| cost / cell | $5.13 | **$6.36** | $4.29 |
| seat input side (exact) | $2.51 | **$3.71** | $2.68 |
| orchestrator input side (exact) | $0.89 | $0.88 | $0.40 |
| seat turns / shell calls | 36 / 40 | **55 / 51** | 42 / 44 |

**Against the restated criteria**: recall reported 5/16 ✗ (target ≥8; v1 6); composition 62% ✗
(target ≥2/3; v1 44%); seat cost at superpowers parity ✗ ($3.71 vs $2.68; v1 met it);
orchestrator ≤ $1 ✓; stability no worse than v1 ✓ (better: 0.50/0.50).

**What each decision did, cluster by cluster:**

- *Fail closed* fired once — efcore **e13** (`Coalesce`, high, human thread): demoted twice in v1,
  **reported** in v2 r1 as a Medium with the counter-argument. It **under-fired** on prometheus
  **c07** (`samplesRead` lookback over-count, valid-other medium): parked in both v2 repeats with
  the exact reasoning the rule names — "the docs explicitly scope the delta optimization … cannot
  be distinguished from the stated design". The rule needs a sharper trigger than a paragraph.
- *Minor bucket omitted* raised composition 44% → 62% and cut reported volume 18 → 8, but the new
  `minor, out of reach` label became an **off-ramp for a Low**: prometheus **c03** (judged medium,
  valid-other) was a Low primary finding in v1 r2 and was parked as minor in v2 r2.
- *Seat variance dominated the rest*: efcore **e02** (Critical, reported in both v1 repeats) was
  not found in either v2 repeat; prometheus c05 vanished; c04 was gained (both v2 repeats vs one
  in v1). None of these track the brief edits.
- *Cost*: the whole +$1.23/cell is the seat — 55 turns against 36, 51 shell calls against 40 —
  under a brief that asks it not to dismiss what it traced. It investigated more and reported
  less. Orchestrator unchanged.

**Reading.** Brief v2 is not an improvement on recall and is a small one on composition and
stability, at a seat cost that lost superpowers parity. Two of the four movements that decide the
recall figure (e02, c05) are unrelated to the edits; at 2 repeats the brief effect and single-seat
variance are not separable for changes of this size — which is PILOT-RESULTS' warning again, now
measured on our own preset. Concretely for the brief: (a) the fail-closed rule needs an operational
trigger — e.g. "if your Considered-But-Not-Flagged reason cites a doc, comment, or test as the
authority, that item is a finding" — rather than prose; (b) `minor, out of reach` should be barred
for anything the seat itself rated Low or above (a Low is a finding; "minor" is for nits). Neither
should be re-run alone at 2 repeats expecting a legible signal; the honest next step for the
recall question is more repeats or a wider subject slice, not another prompt tweak.

---

## Brief v3 (`ours-bugs-sp3`, 2026-08-17) — closed-set parking reasons, 3 repeats

Same two subjects, **3 repeats each** (the targeted effect, 2–3 defects/run, is the size of the
seat variance at 2), all six cells CLEAN, folded in as before. Every reported v3 finding landed on
a pilot-graded cluster; 3 new demoted-only clusters (trivia/false-positive in both passes).
Calibration 9/14 (prom), 8/12 (efcore). Judge stability over the full pools: κ 0.835 / 0.848.

Because v3 has an extra repeat, union figures over-credit it; the per-cell figures are the fair
comparison.

| | v1 (2 reps) | v2 (2 reps) | **v3 (3 reps)** | superpowers (2 reps) |
|---|---|---|---|---|
| reported clusters, pooled union | 18 | 8 | **9** | 45 |
| defect share of reported | 44% | 62% | **67%** | 29% |
| real defects reported, union / found, union (of 16) | 6 / 10 | 5 / 9 | **6 / 8** | 9 / 9 |
| **real defects reported per cell** — prom / efcore | 3.0 / 2.0 | 3.0 / 1.5 | **3.0 / 1.33** | 5.0 / 2.0 |
| real defects found per cell — prom / efcore | 4.0 / 4.0 | 5.0 / 2.0 | **3.7 / 2.0** | 5.0 / 2.0 |
| repeat Jaccard — prom / efcore | 0.36 / 0.43 | 0.50 / 0.50 | **0.59 / 0.67** | 0.36 / 0.41 |
| cost / cell · seat input side | $5.13 · $2.51 | $6.36 · $3.71 | **$5.69 · $2.91** | $4.29 · $2.68 |
| seat turns / shell calls | 36 / 40 | 55 / 51 | **38 / 40** | 42 / 44 |

**Against the restated criteria:** composition ✓ (67%, target ≥2/3); stability ✓ (best of the
three); seat cost ≈ superpowers' agent ✓ ($2.91 vs $2.68), orchestrator ≤ $1 ✓; **recall ✗** —
6/16 union (target ≥8), and per cell the number the deliverable is about did not move on
prometheus across three briefs (3.0 / 3.0 / 3.0) and fell on efcore (2.0 → 1.5 → 1.33).

**What the closed set did, cluster by cluster:**

- efcore **e13** (`Coalesce`, high, human thread): parked ×2 under v1; reported 1/2 under v2 and
  1/3 under v3. The mechanism moves it — some of the time.
- prometheus **c05** (matches-thread, medium): parked twice under v3 with a *legal* tag,
  `[unverified]`, and the old rationale in the reason ("stays a documented approximation"). The
  closed set constrains the label, not the reasoning; the seat wore the tag as a costume. The
  format-pass count cannot see this — it checks tags, not reasons.
- prometheus **c107** (subquery-offset attribution, valid-other medium): reported once under v3
  — the first time any `bugs-sp` brief reported it; superpowers never did.
- prometheus **c03**, **c07** and efcore **e02**: not found in any v3 repeat. Not disposition
  losses — the seat never reached them.

**The detection finding.** efcore **e02** (Critical: SQL Server's search-condition conversion
turns UNKNOWN into `false` once the CASE guard is dropped) was found in **both** v1 repeats and
in **none of five** v2/v3 repeats. The seat transcripts show why: the v1 seats generated SQL
Server SQL and saw the `CAST(… AS bit)` shape (42 and 68 mentions each); the v2/v3 seats mostly
did not (2–9 mentions; three of five never called `ToQueryString`). Nothing in the v2/v3 edits
addressed probing — [Speculation] the tighter "defect list, nits parked" framing may narrow the
seat's exploration once its first Critical is confirmed — but the loss is in *what the seat
chose to look at*, not in what it did with what it found. Same for c03/c07.

**Reading.** Three briefs, one per-cell yield: on prometheus the seat reports 3.0 real defects
per cell whatever the parking rules say. The intentionality fix is real but worth about one
defect per run at best, and the seat found a way around it on c05. What actually decides the
number is which paths the seat probes — and that varies between repeats of the same brief more
than between briefs. Per cell on prometheus, superpowers' agent *finds* ~5 real defects and
`bugs-sp`'s finds ~3.7; the remaining parking loss is ~0.7/cell. So the gap that is left is
mostly detection breadth, and no parking rule reaches it.

`bugs-sp` v3 is the version to keep: highest composition, best stability, seat at superpowers
parity, and the format-pass count is a free signal. It should not be iterated further on
disposition. The next lever, if there is one, is exploration — and the honest next measurement
is a wider subject slice, not another prompt on these two.
