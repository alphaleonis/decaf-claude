# Proposal: `bugs-sp` — a single-agent experimental preset

Investigation `dcc-1ix0`, acceptance item 3: a concrete proposal at or below $4/cell, with the
mechanism it changes. The mechanism was identified in `OURS-BUGS-VS-SUPERPOWERS.md`; measured basis
in `PILOT-RESULTS.md` and `TUNING-SIGNALS.md`. The deliverable is unchanged from `bugs` —
high-confidence defects introduced by the changed lines — produced by a different mechanism: one
deep reviewer instead of a wave and a funnel.

## Decisions this encodes (operator, 2026-08-16)

1. **A new experimental preset `bugs-sp`** ("single pass"), not a modification of `bugs`. Both stay
   in the matrix so the comparison is direct; the benchmark gains a new tool arm, `ours-bugs-sp`.
2. **Haiku exits the reasoning lanes** (companion change, own nib): under `models=low`, volume and
   verification agents move to Sonnet. Accepted consequence: `low` may become identical to `norm`;
   the axis gets rearranged later if so. Supporting discovery: `anthropic-code-review` runs its
   *review agents* on Sonnet and uses Haiku only for helpers (METHODOLOGY-v2, model-cutoff table) —
   the premise behind `dcc-c2uc`'s cheap-validator tier ("anthropic does the identical job on
   Haiku") was wrong.
3. **Scoring lens**: the per-class reported-findings table is the primary comparison, not
   precision. Precision is secondary and in any case unpublishable below 10 reported clusters
   (PILOT-RESULTS). Detection/reporting against the known real-defect pool remains the recall
   measure.

## The mechanism it changes

`ours-bugs` spends ~$8.6/cell to field four reviewers (three of them until now on Haiku) plus a
cluster → screen → consolidate → validate funnel, and reported 7 clusters across both pilot
subjects — processing ~40 clusters to do so, and wrongly demoting 3 of the 8 real defects its
reviewers found. `superpowers` spends $4.12 on one session-model agent with a whole-surface
checklist and no post-processing, and reported a strict superset. The comparison doc traces the
advantage to five properties, all of which `bugs-sp` adopts:

| property | how `bugs-sp` gets it |
|---|---|
| budget concentration | one session-model seat; no co-readers, no verification wave |
| whole-surface license | one brief spanning every concern class, scoped only by `reach` |
| self-calibration | confidence anchors self-assigned at generation; no post-hoc screen |
| inline empirical verification | sole tree ownership → execution license, no probe indirection |
| no corroboration dependency | findings stand on evidence; nothing requires a second finder |

The filtering happens **at generation, in the prompt** (`reach` block + calibration lines), not
after generation in machinery — which is where the pilot showed the money and the lost defects go.

## Preset definition

| axis | value at `bugs-sp` | notes |
|---|---|---|
| `roster` | **1**, fixed | the seat is `solo-reviewer` (new agent brief) |
| `models` | seat inherits the session model | judgment-class seat; axis effectively inert |
| `evidence` | inert | replaced by self-assigned anchors + calibration prompt |
| `reach` | `narrow` (default, overridable) | same in-prompt scoping text the wave uses |

**Pipeline at `roster=1`** — the orchestrator keeps Step 1 (context), Step 1.5 (spec discovery),
dispatch, and Step 6 (report file). It skips: Step 3.0 shared pre-flight (the solo agent runs its
own gates — it is the only actor), Step 4.5 probe protocol, Step 4.9 clustering, Step 4.95 screen,
Step 5 consolidation (nothing to merge), Step 5.5 CBNF re-review, Step 5.6 validation. Each skipped
stage's function is either absorbed into the brief (screen → calibration; CBNF → the agent's own
Considered But Not Flagged section) or exists only for multi-agent output (clustering,
consolidation, corroboration promotion).

## The `solo-reviewer` brief (outline)

Adapted from `superpowers/skills/requesting-code-review/code-reviewer.md`, made decaf-native:

- **Persona + full responsibility**: senior reviewer; the report goes straight to the developer;
  no downstream validator — "your verdict is the verdict."
- **Intent slot**: description of the change plus the Step 1.5 spec when one was discovered — the
  plan-alignment lane nobody in an `ours-bugs` wave covers today.
- **Whole-surface checklist**: correctness, error handling, edge cases, security, concurrency,
  API/design, tests-verify-real-behavior, production readiness — phrased as decaf finding
  categories so class attribution is natural.
- **`reach` block verbatim** from the SKILL's base context — the get-go scoping.
- **Confidence anchors self-assigned** (100/75/50 with the existing definitions; report ≥50, park
  25/0 in Considered But Not Flagged). No "plausibility, not proof" delegation — the opposite.
- **Calibration lines carried over from superpowers** (measured to replace the funnel at equal
  substantive share): "Categorize by actual severity — not everything is Critical"; "Never give
  feedback on code you didn't actually read"; "Don't say 'looks good' without checking."
- **Execution license**: read-only on *this checkout* (never move HEAD, never reset/checkout/
  restore tracked files — the diff under review is uncommitted); temp `git worktree` for other
  revisions; targeted builds/tests/repro probes encouraged and run inline.
- **Output: decaf report format** — header, severity icons, anchors, Minor buckets, verdict logic,
  numbered findings — so `.decaf/code-reviews/` files from `bugs-sp` are drop-in consumable by
  `resolve-code-review` and `auto-code-review` with no changes.

## What it knowingly gives up

Corroboration entirely; conditional dispatch (one seat costs the same on every diff); any
independent check on the seat's claims; and it is a single point of stochastic failure. The last
is the live risk: PILOT-RESULTS made two repeats the variance detector because single-repeat
results lied three times during the pilot. The experiment measures repeat stability explicitly.

## The experiment

**Arm**: `ours-bugs-sp`, both pilot subjects (`prometheus/prometheus#18081`,
`dotnet/efcore#34127`) × 2 repeats = 4 cells. Operator-gated spend, expected ~$4/cell against the
`superpowers` datum ($4.12; the cost regression cannot extrapolate to one seat — it predicts a
negative price — so the datum is the anchor). Judge re-adjudication: adding an arm means the two
subjects' pooled clusters must be re-clustered and re-graded blind with the new findings included,
per the bench-analyze pipeline; grading stays blind to tool identity as before.

**Harness changes**: `run_cell_v2.sh` INVOKE case (`ours-bugs-sp` →
`/decaf-quality-dev:code-review bugs-sp --report`), `tools.json` entry with `model_policy`, and
the preset + agent brief implemented in `decaf-quality` and synced to the dev copy the harness
invokes (`~/.claude/skills/decaf-quality-dev/` — confirm the sync mechanism before editing; the
dev copy is what cells actually run).

**Primary readout — the class table**, `bugs-sp` as a new row against the seven existing tools
(reported clusters by judge-assigned class, both pooled subjects):

| tool | defect | risk | test-gap | docs | design | style | total |
|---|---|---|---|---|---|---|---|
| `ours-bugs` (baseline) | 6 | 0 | 0 | 0 | 1 | 0 | 7 |
| `superpowers` (target mechanism) | 13 | 2 | 12 | 8 | 8 | 2 | 45 |
| `ours-bugs-sp` | ? | ? | ? | ? | ? | ? | ? |

This table is also the test of the in-prompt-scoping hypothesis: if `reach=narrow` in a solo brief
does the filtering the funnel was doing, the `bugs-sp` row stays defect-dominant (like
`ours-bugs`' 6-of-7) while its defect count approaches `superpowers`' 13 — breadth of *detection*
without breadth of *report*.

**Secondary readouts**: real defects found and reported against the 16-defect pool (baselines:
`ours-bugs` 8 found / 5 reported; `superpowers` 9/9); cost and wall time per cell; repeat-to-repeat
cluster overlap (stability); precision only if ≥10 reported clusters.

## Success criteria

1. **Recall**: reports ≥ 8 of the 16 pool defects (i.e., at least what `ours-bugs`' reviewers
   already found and the funnel then binned), on the pooled two subjects.
2. **Cost**: ≤ $4.30/cell mean (superpowers ± ~5%).
3. **Composition**: defect-class share of reported findings ≥ 2/3 — in-prompt scoping holds
   without machinery.
4. **Stability**: no repeat pair where the two runs' reported real defects diverge by more than
   the wave arms' observed repeat variance on the same subjects.

Failing 3 with 1–2 passing means the scoping needs prompt work, not machinery. Failing 1 while
`superpowers` passes it on the same cells means the adaptation lost something the template had —
diff the briefs, not the pipeline.

## Standing rules that bind this experiment

Two subjects do not generalize — this promotes `bugs-sp` from experiment to default for nothing
until replicated on a wider slice; no precision figure below 10 reported clusters; never cite v1;
all cells through the shim with clean leak audits.
