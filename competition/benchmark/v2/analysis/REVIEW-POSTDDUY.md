# `review` post-dduy — results (2026-08-18, nib dcc-u10u)

> ⚠️ **Thread-axis figures in this document predate the 2026-08-20 correction** ([[dcc-hw48]],
> [[dcc-qfr5]]). Every `thread_recall` / `incumbent_agreement` number below was computed over a
> denominator that included threads no tool could match at the checkpoint, and — on subjects with
> duplicate threads — with credit assigned to the wrong origin axis. The direction of the error is
> known (recall understated, incumbent agreement overstated) but its size varies by subject, from 10%
> to 100% of the human axis. **Re-derive from the current `metrics.json` before citing any thread
> figure here.** The pooled and defect axes in this document are unaffected. See
> `analysis/THREAD-AXIS.md`, "The counting was wrong too".


`ours-review` re-measured after [[dcc-dduy]] moved volume and verification agents off the cheap tier
(under `models=low`/`norm` they now run Sonnet). `review` is `models=norm`, so dduy applies to it.
Ten cells: prometheus-18081 r4/r5, dotnet-efcore-34127 r3/r4, and mattermost-36824 / immich-28886 /
grafana-117615 r1/r2 — the five subjects that already carry complete adjudications. All ten CLEAN,
`is_error=false`, artifacts captured. Judge `claude-opus-5`; all five subjects **out-of-window**
(merged 2026-06-10 … 2026-07-17, past the 2026-06-01 provably-clean line), so they may be pooled.

**The arm id is `ours-review-postdduy`, not `ours-review`.** `foldin.py` refuses a tool already
present in a subject, and on prom/efcore `ours-review` already holds pre-dduy r1/r2; folding under
one id would also have pooled two configurations behind one label — the thing `tools.json` forbids
for `ours-bugs`. Run directories keep their true `ours-review` names; the scoring layer sees the new
id through a symlink alias (`foldin.py --runs`). Cells were invoked as `ours-review`.

## Calibration — report it every time

75 already-graded clusters (15 per subject, stratified across the six verdicts, relabelled and mixed
with the new ones so the judge could not tell which was which; seeded draw, reproducible).

| subject | vs pilot p1 | vs pilot p2 | today p1 vs p2 | κ real/not | exact | pre-registered threshold |
|---|---|---|---|---|---|---|
| prometheus-18081 | 10/15 | 8/15 | 24/24 | 1.000 | 1.000 | PASS |
| dotnet-efcore-34127 | 12/15 | 12/15 | 14/17 | 0.717 | 0.824 | PASS |
| mattermost-36824 | 10/15 | 10/15 | 20/24 | 0.731 | 0.833 | PASS |
| immich-28886 | 11/15 | 11/15 | 27/30 | 0.737 | 0.900 | PASS |
| grafana-117615 | 10/15 | 10/15 | 23/27 | 0.833 | 0.852 | PASS |

**53/75 (71%) against pilot pass 1, 51/75 (68%) against pass 2.** No subject near efcore's 3/12 of
2026-08-17. All five clear `real_vs_not.kappa ≥ 0.60` and `exact_agreement ≥ 0.70`.

**prometheus is the row worth keeping.** Today's judge is perfectly self-consistent there (24/24,
κ=1.0) while agreeing with the pilot on only 10/15 and 8/15. `judge_stability.py` cannot see drift
from the baseline because it never looks at the baseline — only the calibration sample does. That is
[[dcc-n4nf]]'s case in one row.

## Post-dduy `review`, five subjects

Precision is publishable on all five (every subject reports ≥ 14 clusters, over the n≥10 floor).

| subject | reported | found | real | precision | trivia | defect recall (rep / found) | thread recall (rep / found) | n human | $/cell | $/real |
|---|---|---|---|---|---|---|---|---|---|---|
| prometheus-18081 | 27 | 45 | 14 | 0.519 | 0.000 | 0.455 / 0.455 | 0.60 / 0.80 | 10 | $26.25 | $3.75 |
| dotnet-efcore-34127 | 15 | 32 | 7 | 0.467 | 0.067 | 0.400 / 0.600 | 0.30 / 0.50 | 10 | $14.47 | $4.13 |
| mattermost-36824 | 17 | 31 | 7 | 0.412 | 0.118 | 0.833 / 1.000 | 0.75 / 0.75 | 4 | $16.86 | $4.82 |
| immich-28886 | 15 | 35 | 5 | 0.333 | 0.267 | 0.800 / 1.000 | 0.50 / 0.50 | **2 — thin** | $16.51 | $6.60 |
| grafana-117615 | 14 | 27 | 6 | 0.429 | 0.214 | 0.833 / 0.833 | 0.00 / 0.00 | **2 — thin** | $17.21 | $5.74 |

immich and grafana are `human_axis_thin`: their thread recall is per-subject disclosure only, never
poolable. grafana's 0.00 is over **two** threads — it is not a rate.

`judge_dismissed_reported_threads` is empty on all five: no cluster that matched a human thread was
called trivia or wrong. `missed_by_every_tool` = 2 / 3 / 1 / 1 / 2.

**Demotion gap** is 0.2 on both library subjects and 0.0 on the three small ones — `review` moves
some real findings below the fold on large diffs, and none on small ones. 112 of its 245 raw findings
(46%) were Considered-But-Not-Flagged.

## Pre- vs post-dduy, same subject, same pool

The only clean comparison, because these two subjects carry both eras against one adjudication.

| | prometheus pre → post | efcore pre → post |
|---|---|---|
| reported | 24 → **27** | 15 → **15** |
| found | 48 → **45** | 37 → **32** |
| real | 12 → **14** | 9 → **7** |
| precision | 0.500 → **0.519** | 0.600 → **0.467** |
| defect recall, reported | 0.455 → **0.455** | 0.800 → **0.400** |
| defect recall, found | 0.455 → **0.455** | 1.000 → **0.600** |
| thread recall, rep / found | 0.6/0.6 → **0.6/0.8** | 0.2/0.3 → **0.3/0.5** |
| defect share of reported | 33% → **22%** | 27% → **27%** |
| cost / cell | $19.04 → **$26.25** | $16.80 → **$14.47** |

**The two subjects move in opposite directions on every axis that matters.** prometheus gains real
findings and as-found thread recall while shedding defect share to docs; efcore halves its defect
recall and loses precision while getting cheaper. Neither direction replicates.

**No dduy effect can be claimed from this.** The within-subject spread between the two post-dduy
repeats is as large as the pre/post gap it would have to explain: prometheus $21.70 vs $30.81 (1.42×),
efcore $12.33 vs $16.60 (1.35×), and on findings efcore returned 15 vs 25 raw items across its two
repeats. At two repeats the policy change and run-to-run variance are not separable — PILOT-RESULTS'
warning, now measured on `review`.

## The rubber-stamp question (dcc-c2uc), first measurement

Whether the verification wave confirms whatever it is handed. Read from the eight `review` cells'
filed reports.

| era | cells with ≥1 refutation | total refutations |
|---|---|---|
| pre-dduy (Haiku validators) | 1 of 4 | 1 |
| post-dduy (Sonnet validators) | 3 of 4 | 5 |

Post-dduy verification refutes its own findings materially more often — including two cells where a
reported Critical was withdrawn. On the evidence available it is **not** rubber-stamping.

**This is directional, not a rate.** The reports' validation headers are free-form prose, not a
fixed field, and several cells in *both* eras waived the validator wave in favour of orchestrator
probes (probe verdicts and validator verdicts are mixed in the same sentence). A real rate needs a
machine-readable validation block; that is worth adding to the skill before this is measured again.

## Fold-in integrity — and one criterion that did not hold

245 findings, 198 (81%) merged into clusters the pilot had already graded twice; 47 new clusters
graded blind today. `check_artifacts.py` and `score_pooled.py` exit 0 on all five subjects.

dcc-u10u's acceptance line "existing per-tool figures asserted unchanged" **did not hold**, in two
distinct ways:

1. **`unique_real` fell in three places** (efcore `pr-review-toolkit` 2→1, mattermost `superpowers`
   1→0, grafana `superpowers` 3→2). Benign and correct: "unique" means only that tool reported it,
   and now another arm did too. Same case the `bugs-sp` fold-in produced once.
2. **The real-defect pool GREW** — immich 4→5, grafana 4→6 — because three clusters only this arm
   found (`im36`, `gf27`, `gf28`) graded `valid-other` and classed `defect`. That deflated **every**
   pre-existing tool's recall without those tools changing: `ours-bugs` and `ours-bugs-sp3` fell
   1.000 → 0.800 on immich and 1.000 → 0.667 on grafana; `superpowers` 0.750 → 0.500 on grafana.

The second is inherent to pooled adjudication, not a defect: METHODOLOGY-v2 states the pooled axis is
"bounded by the union of tool output". Any arm contributing genuinely new real defects enlarges the
pool and retroactively deflates everyone. The `bugs-sp` fold-in never hit it because its three new
clusters were demoted-only trivia.

Consequences, stated plainly:

- **The generalization-slice defect-recall figures for immich-28886 and grafana-117615 in
  `BUGS-SP-RESULTS.md` are superseded.** `ours-bugs` at 1.00 on immich is 0.80 against today's pool.
- **Defect recall is not comparable across fold-ins** unless the pool is held constant. Cite it with
  the pool size attached, always.
- **The acceptance wording is wrong as a gate.** "Figures unchanged" is only achievable by an arm
  that finds nothing new, so as a pass/fail it rewards weakness. It should require that every
  movement be *explained*, not that none occur. Filed as [[dcc-dirp]].

## Recommendation — is `review` post-dduy fit to ship?

**Yes, with the reservation that the change was not shown to help.** Nothing regressed structurally:
no cell approved a change with real defects found; `judge_dismissed_reported_threads` is empty
everywhere; verification refutes rather than rubber-stamps; precision is publishable on all five
subjects and sits in a narrow 0.33–0.52 band. Cost is unchanged within noise.

But dduy's *benefit* to `review` is unmeasured and unmeasurable at this scale: two subjects moving in
opposite directions on every axis, with repeat variance larger than the effect. The honest statement
for a `tuning → main` merge is that `review` post-dduy was checked for regression and none was found
— not that the model-policy change improved it.

**Does `review` need the treatment `bugs` got** (the wave replaced by a single seat)? This run does
not answer it, and it is the more interesting question. Two observations point at it:

- `review`'s defect share of reported findings is **22–27%** on the library subjects, against
  `bugs`' 77% and `bugs-sp3`'s 66%. It buys its extra volume in docs and test-gap, not defects.
- Its cost per real finding is **$3.75–6.60**, against `bugs-sp3`'s $1.33–2.48 on the same subjects.

A single-seat `review` is worth exploring on the same evidence that motivated `bugs` — but on a
wider slice than two library subjects, and not before [[dcc-n5h2]] settles what actually drives
per-cell detection.
