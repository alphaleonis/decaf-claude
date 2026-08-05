---
# dcc-xewu
version: 1
title: Score findings before consolidating, not after
status: in-progress
type: feature
priority: normal
estimate: l
tags:
    - code-review
created_at: 2026-07-28T20:41:05Z
updated_at: 2026-08-05T22:37:11Z
parent: dcc-9q01
blocked_by:
    - dcc-evph
order: as
---

# Why

Ours consolidates **everything** (Step 5), validates afterwards (Step 5.6), then suppresses via
the confidence gate. So the orchestrator spends frontier-model thinking on findings it is about
to discard — and orchestrator thinking is 60% of orchestrator output on a small subject, 77% on
a large one.

Anthropic inverts the order: a **Haiku** agent scores every issue against a 0–100 rubric and
everything below 80 is discarded **before** its orchestrator does any real reasoning. On a
discrete 0/25/50/75/100 ladder that means only findings scored exactly 100 survive. It posts the
study's best calibration (0.90, 9/10, vs ours' 0.70, 21/30) at half the cost.

Same insight, opposite order — and the order is where the cost difference lives.

# What to change

Move a cheap scoring pass ahead of consolidation. The prize is not only the thinking saved: a
pre-consolidation pass could **absorb** the validation wave (17.3% of sub-agent output) rather
than adding to it — one cheap pass over raw findings instead of an expensive pass over
consolidated ones.

This is simultaneously #dcc-e0wj workstream 1's calibration lever: an early cheap filter is what
makes a trustworthy top-of-list possible. The two workstreams converge here.

# Blocked on a product decision

A hard pre-filter is a **commitment to the "short trustworthy list" product**. If the intended
product is exhaustive coverage with explicit tiers, aggressive early filtering is the wrong
change — the valid-minor findings it would discard are precisely what a fix-and-rerun loop
consumes, and ours currently produces 4.8 of them per run against anthropic's 2.1.

~~Resolve #dcc-e0wj workstream 3's first item before starting.~~ **Discharged 2026-07-29 by
#dcc-9q01**, which answers the product question by making the product a per-run preset rather than a
permanent commitment. This nib becomes the implementation of that design's `evidence` axis.

Two premises here are superseded and must not be built on: the hard-filter framing (the screen
selects a tier, it does not permanently discard), and the claim that anthropic's 0/25/50/75/100
ladder means only findings scored 100 survive — the skill specifies a continuous 0-100 scale with
five anchor *descriptions*, and its scorers demonstrably emit 80 and 85. See #dcc-9q01.

# Risk

High. This changes the skill's spine: dispatch → consolidate → validate → gate is the structure
every downstream skill's expectations are built on, including `auto-code-review`'s triage table,
which keys on severity × anchor × validated-flag. A finding that never reaches consolidation has
no anchor, so the whole downstream contract has to be re-checked.

# Acceptance

- [x] [manual] Product decision recorded first (#dcc-e0wj workstream 3) — discharged by #dcc-9q01,
      which makes the product a per-run preset; this nib becomes its `evidence` axis
- [x] [manual] The three broken premises in the Assessment are corrected wherever cited (this nib,
      #dcc-05uw) before any design rests on them
- [x] [manual] Clustering experiment run against the archived findings across all three model
      tiers, clusters compared to the committed ones, and an explicit verdict on whether
      `cluster-then-screen` is viable — **PASSED 2026-07-29**: sonnet F1 0.87 matches opus 0.86 at a
      fraction of the cost, haiku trails at 0.80, corroboration preserved. Clustering runs mid-tier
- [ ] [manual] Re-run the clustering experiment on a **large** subject before committing — no large
      run had joinable ground truth, and dedup is hardest where the orchestrator's thinking share is
      77%. Fixing subject 6's `cluster-assign.json` id scheme is the cheapest route
- [x] [run] the prototype asserts every input finding lands in exactly one cluster — the cheap model
      silently dropped ids until told to count them
- [x] [run] `rg -n "Step 5" -A15 decaf-quality/skills/code-review/SKILL.md` — expect: the
      scoring pass documented ahead of consolidation, with its model tier stated
- [x] [manual] Downstream contract re-verified: `auto-code-review` Step 3c and
      `resolve-code-review` Step 2 still receive severity, anchor and validation state for every
      finding they triage
- [x] [manual] Re-measured on benchmark subjects: calibration against the 0.70 baseline (21/30), cost
      against $21.33/run, escaped-bug recall against 16/18, **and the multi-finder agreement rate** —
      with an explicit judgement that neither recall nor corroboration regressed

# Notes

Reasoning and measured basis: #dcc-e0wj → `# Candidate interventions` → item 2.

## Assessment 2026-07-29 — do not build next, and fix the basis first
## Assessment 2026-07-29 — do not build next, and fix the basis first

**The prize is real but roughly half what this nib implies, and three of its premises are wrong.**

### What the target is actually worth

On corrected token figures (the published `ws_output` undercounted every tool by 35–49%; fixed
2026-07-29):

| | ours, per run |
|---|---|
| session output | 367,084 |
| orchestrator output | 84,533 — **23%** |
| orchestrator *thinking* (60–77% of that, per #dcc-e0wj) | 50.7k–65.1k — **14–18% of output** |
| validation wave this nib would absorb | ~13% of output |

So the absolute ceiling is under a third of output, before subtracting the dedup that must happen
regardless and the validation that must survive. Real saving is materially less.

### Three premises that do not hold

1. **"Only findings scored exactly 100 survive" is false.** The skill
   (`~/.claude/plugins/cache/claude-plugins-official/code-review/unknown/commands/code-review.md`,
   step 5) says *"score each issue on a scale from 0-100"* and supplies five anchor **descriptions**
   — not five permitted values. Observed output: 80 (×1), 85 (×2), 100 (×4). The filter is moderate,
   not brutal. Our own strict ladder ("never intermediate values") was projected onto theirs.
2. **"Early filtering produces the best calibration" is unsupported.** Anthropic's precision is
   substantially *scope*: its skill instructs reviewers to discard test coverage, docs, general
   security, pre-existing issues and anything on unmodified lines. It never emits the categories
   that dilute ours, so they cannot count against it. The filter is not shown to be the cause.
3. **Screening raw findings destroys our best discriminator.** Corroboration separates signal from
   noise here — substantive clusters average 2.80 finders against trivia's 1.32 (#dcc-gcob) — and a
   pre-consolidation screen runs *before* agreement exists. Anthropic can score per-issue because
   its five agents are deliberately disjoint and rarely corroborate; it has no agreement signal to
   lose. We do.

### The strongest argument against this nib is in the nib it cites as its basis

#dcc-e0wj, decomposing orchestrator output: *"That residual is Steps 5 / 5.5 / 5.6 … It is the one
job no sub-agent can take: the orchestrator is the only component holding all 16–20 reports at once,
and **you cannot dedupe findings you cannot see together**."*

If the thinking is mostly dedup, a pre-filter saves little — you must still see everything to know
what to filter. The fix is `cluster-then-screen` (#dcc-9q01): dedupe cheaply, then screen clusters
with finder-count as an input. But that rests on an assumption nobody has tested — **that a cheap
model can cluster as well as the orchestrator does.**

### There is a bigger, better-evidenced lever

Sub-agent output is **77%** of session output — over three times the orchestrator. #dcc-e0wj
measured r = 0.694 between sub-agent count and orchestrator output, so cutting roster cuts both
sides. #dcc-2a8i then measured that drop cost is ≈0 on small diffs: most personas contribute
nothing another persona did not also find. **Roster is a larger target than orchestrator thinking,
and on small changesets it is nearly free.**

Also relevant, and it reframes the whole "ours is verbose" premise: per-sub-agent output is
**ours 19.5k, tag1 19.6k, pr-review-toolkit 21.0k, superpowers 26.3k, anthropic 9.6k**. Ours is
mid-pack. Anthropic is the outlier. "Close the per-agent gap" means "become as terse as the single
outlier", not "fix our excess".

## Recommendation

**Keep, rewrite, do not build next.** Specifically:

- Recast as the implementation of #dcc-9q01's `evidence` axis — a screen that *routes findings into
  tiers*, not one that permanently discards. The hard-filter framing is what would have broken
  `auto-code-review`, which consumes the Minor tier.
- Correct the three premises above before any design work rests on them.
- **Gate it on one cheap experiment that needs no benchmark re-runs:** replay the archived findings
  through a cheap-model clustering pass and compare the resulting clusters against the committed
  ones. If a cheap model clusters as well, `cluster-then-screen` works and the prize is reachable.
  If it does not, #dcc-e0wj is right that the thinking is irreducible, and this nib should be
  scrapped on measurement like #dcc-gcob was.
- Sequence #dcc-2a8i (the `roster` axis) ahead of it — bigger target, better evidence, measured.

## Gating experiment — RUN 2026-07-29, PASSED. Clustering belongs on the mid tier

Replayed archived `ours` reviewer findings through a clustering pass and scored against the
committed reference clustering. 8 runs, 190 findings, 83 reference clusters (subjects 1/4/5/7 — the
ones whose `findings.json` carries an inline `cluster_id`). Run once per model tier under an
identical prompt and identical inputs. Reproduce with
`analysis/scripts/cluster_replay.py build|score <workdir>`.

| model | precision | recall | F1 | substantive finders kept | 2+ preserved |
|---|---|---|---|---|---|
| haiku | 0.88 | 0.73 | 0.80 | 2.81 of 3.30 | 67% of 67% |
| **sonnet** | 0.96 | 0.79 | **0.87** | 2.93 | 63% |
| opus | 0.88 | 0.85 | 0.86 | 2.96 | 67% |

**Sonnet matches Opus at a fraction of the cost** — 0.87 against 0.86 is inside the noise of an
8-run sample, and the corroboration signal survives about equally. **Haiku is measurably behind**
at 0.80, mostly on recall: it splits apart a quarter more of what belongs together.

So clustering is a task the top tier does not win, which is what makes moving it off the session
model a saving rather than a trade. **Decision: mid tier** (operator, 2026-07-29).

### Two corrections to earlier runs of this experiment

Both overstated the result, in different directions. Recorded so the numbers above are not
re-litigated from the older ones.

1. **"Clustering sharpens the signal (1.95x -> 3.08x)" — withdrawn.** That pass used two prompts
   across its batches; the weaker one caused silent dropping of findings, which shrank trivia
   clusters and manufactured the separation.
2. **"Sonnet beats Opus, and not marginally" — withdrawn.** That pass fed the models validator
   output as if it were reviewer output. Validators restate the finding they are checking, so they
   are trivially mergeable, and 16% of the input was validator findings. Opus merged them (correctly)
   and was scored wrong for it; Sonnet's apparent precision advantage was largely this artifact.
   With validators excluded the two are tied.

### A bias that remains, and cuts toward Opus

The reference clustering is itself an LLM product and it **under-merges**. Reading Opus's disputed
merges from the contaminated run: several were the same file:line describing the same defect in
different words, and in one case a validator confirming the very finding it was split from. The
metric rewards agreeing with the reference, so a model that merges correctly where the reference did
not is penalized.

This does not change the decision. If the bias were corrected Opus would gain, not Sonnet — and Opus
is already only a hair ahead at many times the price. But it does mean **F1 0.87 understates how good
mid-tier clustering actually is**, and that the reference should not be treated as truth in any
follow-up.

### Limits carried forward

1. ~~**Large runs are untested.**~~ **Cleared 2026-08-06.** Subject 6 ran at the mid tier against
   an 8-run same-prompt control: per-run F1 0.78/0.76 against a small/medium spread of 0.51-0.95,
   so large diffs are not a clustering risk. The live question moved to how the `evidence` bar is
   expressed — see the control-run section.
2. **The prototype needs a hard count assertion.** Models silently dropped findings until told to
   count, and Haiku mis-reported its own counts even when told. A screen that never sees a finding
   cannot tier it.
3. **Only dedup was tested** — not severity normalization, confidence promotion or validator
   selection, which are the rest of the orchestrator's residual.
4. `subject-05-r2` scored poorly for every model (0.53-0.82), so per-run variance is a property of
   the changeset rather than the model.

### What this does not change

The gate makes this nib *buildable*, not *next* — #dcc-2a8i (the `roster` axis) is still the larger
and better-evidenced lever, and this nib's target remains 14-18% of output.

Screen thresholds must be calibrated against post-clustering finder counts (substantive 3.30 ->
2.93 on the mid tier), not against today's distribution.

## Implemented 2026-07-29

The screen is a **tiering** step, not a filter. That is the correction to this nib's original
framing: a cluster below the bar moves to Minor Findings or Considered But Not Flagged, where the
fix loops and the reader can still reach it. Nothing is discarded for want of evidence.

### Pipeline

- **Step 4.9 — Cluster** (new). One agent groups every reviewer finding before the orchestrator
  reasons about any of them. Dedup is the largest single line item in orchestrator thinking and does
  not need the session model. Validator output is excluded from the input, because it restates what
  it verifies. A hard count assertion, one retry, then orchestrator fallback — a finding that never
  reaches a cluster is invisible to every later step.
- **Step 4.95 — Screen** (new). One cheap agent per cluster scores it 0–100 against a rubric with
  five described reference points, receiving the cluster's **finder count** as an input. The
  `evidence` bar decides primary vs tiered-down.
- **Step 5** now *verifies* the clustering instead of performing it, and its confidence gate applies
  only to clusters the screen skipped — the two must not both demote the same cluster.
- **Step 5.6** shrinks to what a score cannot settle: Criticals, clusters within 15 points of the
  bar, and dissenting severities. **Single-finder alone no longer selects a validator**, because
  corroboration is now an input to the screen.

### Two design decisions worth knowing

**The clustering agent is not tiered by the `models` axis — it always runs mid.** Measured: mid F1
0.87, top 0.86, cheap 0.80. The top tier buys nothing, the cheap tier loses real accuracy, and an
under-merged cluster destroys the corroboration signal every later step ranks on. That is a
measurement, not a policy preference, so `models` does not move it.

**The screen rubric is continuous, not a five-rung ladder.** Reviewers use discrete anchors; this
does not, and the skill says why: a threshold on a five-rung ladder is really "the top rung", which
is far harsher than the numbers suggest. This is the mistake this nib itself made about the
reference implementation.

### Unverified

The `evidence` cut points (80/60/40/25) are a **first calibration**, set against post-clustering
finder counts. The skill says so. Whether the screen preserves recall, and whether shrinking the
validation wave costs verdict quality, is unmeasured until #dcc-gxuk.

The large-subject clustering test is still owed — dedup is hardest exactly where the orchestrator's
thinking share is 77%. Subject 6 no longer blocks it (2026-08-06); the tasks are built, not run.

## Subject 6 unblocked 2026-08-06 — the large-run clustering test can now be built

`findings.json` now carries an inline `cluster_id` for 661 of its 694 findings, so
`cluster_replay.py build` picks the subject up and emits two large tasks:

| task | findings | reference clusters |
|---|---|---|
| subject-06-r1 | 49 | 33 |
| subject-06-r2 | 61 | 40 |

Against 190 findings across the existing 8 tasks. **Do not silently pool them** — 110 new findings
from one large TypeScript diff would be 37% of the sample and would restate the published F1 0.87
into a differently-weighted number. Report subject 6 as its own row; the question is whether the
mid-tier decision survives scale, not what the new global F1 is.

### It was a re-key, not a re-cluster

The reference clustering was never lost. `cluster-assign.json`'s values map onto `analysis.json`'s
95 `cluster_id`s at 95/95. Only the finding-side key was unjoinable: the assign map uses the
composite ids the per-run extracts carry (`ours__r1__N`), while `findings.json` had been rebuilt
with positional `f00NN` ids. `extract/<tool>__r<N>.json` bridges the two — it carries the composite
id and sits in the same order as `findings.json`.

That order is the whole basis of the re-key, so `analysis/scripts/backfill_cluster_ids.py` verifies
it position by position on file+line and skips any run that disagrees anywhere. For the `ours` runs
— the only ones the replay consumes — it matched 183/183. Each backfilled finding records
`cluster_id_source` for audit.

### The check caught a real problem: subject 6's `anthropic-code-review` r2 is two different datasets

`extract/anthropic-code-review__r2.json` holds 20 findings, none with a subagent.
`findings.json` holds 33 for that run, 23 of them with a subagent. They agree on **1** file+line
pair out of 20 — so this is not a reordering, it is a re-extraction that `extract/` and
`cluster-assign.json` never caught up with. Those 33 findings are the only ones left without a
`cluster_id`.

Harmless here — the replay filters `tool == "ours"` — but subject 6's `analysis.json` clusters
still cite the stale anthropic r2 findings in `reported_by`, so any published anthropic number for
subject 6 rests on a finding set that `findings.json` no longer contains. Filed separately; it is a
data-integrity question about the benchmark, not about clustering.

### Still owed

The two tasks are built but **not run**. Run them at the mid tier (the tier decision is already
made; the open question is whether it holds at scale), then `cluster_replay.py score`. The build is
deterministic under a fixed seed, so the workdir need not be committed — but the resulting numbers
should land here.

## Large-run result 2026-08-06 — F1 0.77, and the corroboration signal survives

Subject 6 ran at the mid tier. Both runs passed the count assertion under independent check
(nothing dropped, duplicated or invented), so the `dropped` column is 0 and no finding went
missing.

| run | n | ref clusters | predicted | precision | recall | F1 |
|---|---|---|---|---|---|---|
| subject-06-r1 | 49 | 33 | 34 | 0.73 | 0.83 | 0.78 |
| subject-06-r2 | 61 | 40 | 38 | 0.76 | 0.76 | 0.76 |
| **pooled** | 110 | 73 | 72 | 0.75 | 0.78 | **0.77** |

| tier | clusters | finders before | after | 2+ before | 2+ after |
|---|---|---|---|---|---|
| substantive | 26 | 2.31 | 2.15 | 65% | 62% |
| valid-minor | 18 | 1.11 | 1.06 | 11% | 6% |
| trivia/FP | 29 | 1.03 | 1.00 | 3% | 0% |

**The experiment's own criterion passes.** What decides this is not F1, it is whether the
corroboration gap survives clustering — and it does: substantive clusters keep 2.15 finders and 62%
at 2+, while trivia collapses to exactly 1.00 and 0%. Retention is 93% of the substantive
corroboration that was there to keep. A screen ranking on finder count still has something to rank
on at large-diff scale.

### F1 0.77 against 0.87 is NOT yet evidence that large runs cluster worse

Two variables moved at once. The 2026-07-29 prompt was never recorded — only `cluster_replay.py`
and the results survive — so this run used a prompt derived from the skill's Step 4.9 brief, now
committed at `analysis/cluster-replay/PROMPT.md` so it cannot happen twice. The 10-point drop is
therefore attributable to subject size, to prompt wording, or to both, and nothing here separates
them.

**The control that would separate them is cheap:** re-run the 8 existing small/medium tasks under
`PROMPT.md`. If they reproduce ~0.87, the drop is real and belongs to scale. If they land near
0.77, the drop is the prompt and large runs are fine. Until that runs, do not publish 0.77 as a
size effect, and do not pool it with 0.87 — they are different measurements.

### A calibration consequence that holds either way

Subject 6's substantive clusters carry **2.31 finders before clustering, against 3.30 on the
small/medium subjects**. Large diffs spread reviewers apart: they overlap less, so corroboration is
a structurally weaker signal there regardless of how well the clusterer performs.

The `evidence` cut points (80/60/40/25) were calibrated against post-clustering counts from the
small subjects (2.93 substantive). The large-subject figure is **2.15**. A screen weighting finder
count against a bar tuned at 2.93 will tier down more substantive clusters as the diff grows —
precisely the wrong direction, since a large diff is where the reader most needs the primary list
to be complete. #dcc-gxuk should read the cut points against subject size, not against a single
pooled distribution.

### Artifacts

`analysis/cluster-replay/` — the two result files and the prompt. Inputs regenerate deterministically
from `cluster_replay.py build` under its fixed seed; agent outputs do not, so they are committed.

## Control run 2026-08-06 — there is no demonstrated size effect

All 8 small/medium tasks re-run under the same committed `PROMPT.md` and the same mid tier as
subject 6, so prompt and model are now held fixed across the size comparison. All 10 runs passed
the count assertion under independent verification; `dropped` is 0 everywhere.

| group | runs | pooled F1 | precision | recall |
|---|---|---|---|---|
| small/medium (subjects 1/4/5/7) | 8 | 0.84 | 0.87 | 0.81 |
| large (subject 6) | 2 | 0.77 | 0.75 | 0.78 |
| *published 2026-07-29, unknown prompt* | *8* | *0.87* | | |

### The 0.77-vs-0.87 gap decomposes into prompt plus noise, not size

- **~3 points is prompt.** Same 8 tasks, same tier: 0.87 under the lost prompt, 0.84 under this
  one. [Inference] — the two runs differ in prompt AND in sampling, and nothing separates those.
- **The rest is inside run-to-run variance.** Per-run F1 across the 8 small/medium tasks spans
  **0.51 to 0.95** (mean 0.797, sd 0.161). Subject 6's runs are 0.78 and 0.76 — both inside that
  range, and the difference of means is **0.027, or 0.17 sd**. Three small/medium runs
  (04-r2 0.74, 07-r2 0.62, 05-r2 0.51) score *below* subject 6's mean.

So the earlier "large runs might cluster worse" framing does not survive the control. Pooled F1
weights by pair count, which is why the group figures separate (0.84 vs 0.77) while the runs
themselves do not. With n=2 large runs this cannot establish a size effect in either direction —
what it does establish is that **nothing here justifies treating large diffs as a clustering risk**,
which is what the limit carried forward was asking.

### The real large-diff finding is corroboration, and it points the other way

Post-clustering share of clusters with 2+ finders:

| tier | small/medium | large |
|---|---|---|
| substantive | 67% | 62% |
| valid-minor | 48% | 6% |
| trivia/FP | 16% | 0% |

On the small subjects, finder count barely separates substantive from valid-minor — 67% against
48%. On the large subject the same signal is nearly clean: 62% / 6% / 0%, with trivia corroborated
exactly never. **Corroboration is a much sharper discriminator on large diffs than on small ones**,
even though the absolute counts are lower there (substantive 2.15 finders against 2.96).

That sharpens, and partly reverses, the calibration note recorded earlier today. The risk is not
that large diffs degrade the signal — it is that an `evidence` bar expressed as an **absolute**
finder count reads two different distributions as if they were one. Tuned at the small subjects'
2.96 it will tier down real findings on a large diff; tuned at 2.15 it will admit corroborated
trivia on a small one. #dcc-gxuk should calibrate the cut points against corroboration relative to
the run's own distribution, not against a pooled absolute.

### Artifacts

All 10 result files and the prompt are in `analysis/cluster-replay/`. Score them split, not pooled:
copy each group's tasks into its own workdir with a filtered `manifest.json` — `score` pools
whatever the manifest lists, and one blended number across both sizes answers nothing.
