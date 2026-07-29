---
# dcc-xewu
version: 1
title: Score findings before consolidating, not after
status: todo
type: feature
priority: normal
estimate: l
tags:
    - code-review
created_at: 2026-07-28T20:41:05Z
updated_at: 2026-07-29T17:47:33Z
parent: dcc-hyxw
order: "n"
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
- [ ] [manual] The three broken premises in the Assessment are corrected wherever cited (this nib,
      #dcc-05uw) before any design rests on them
- [x] [manual] Clustering experiment run against the archived findings across all three model
      tiers, clusters compared to the committed ones, and an explicit verdict on whether
      `cluster-then-screen` is viable — **PASSED 2026-07-29**: sonnet F1 0.90 (best of the three,
      beating opus), and the corroboration signal is preserved. Put clustering on the mid tier
- [ ] [manual] Re-run the clustering experiment on a **large** subject before committing — no large
      run had joinable ground truth, and dedup is hardest where the orchestrator's thinking share is
      77%. Fixing subject 6's `cluster-assign.json` id scheme is the cheapest route
- [ ] [run] the prototype asserts every input finding lands in exactly one cluster — the cheap model
      silently dropped ids until told to count them
- [ ] [run] `rg -n "Step 5" -A15 decaf-quality/skills/code-review/SKILL.md` — expect: the
      scoring pass documented ahead of consolidation, with its model tier stated
- [ ] [manual] Downstream contract re-verified: `auto-code-review` Step 3c and
      `resolve-code-review` Step 2 still receive severity, anchor and validation state for every
      finding they triage
- [ ] [manual] Re-measured on benchmark subjects: calibration against the 0.70 baseline (21/30), cost
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

## Gating experiment — RUN 2026-07-29, PASSED. Move clustering to the MID tier, not the cheap one

Replayed archived `ours` sub-agent findings through a clustering pass and scored against the
committed reference clustering. 8 runs, 227 findings, 83 reference clusters (subjects 1/4/5/7 — the
ones whose `findings.json` carries an inline `cluster_id`). Run three times, once per model tier,
with an identical prompt and identical inputs. Reproduce with
`analysis/scripts/cluster_replay.py build|score <workdir>`.

### Agreement with the reference clustering

| model | precision | recall | F1 | pairs wrongly merged | wrongly split |
|---|---|---|---|---|---|
| haiku | 0.83 | 0.81 | 0.82 | 62 | 70 |
| **sonnet** | **0.97** | 0.83 | **0.90** | **9** | 61 |
| opus | 0.89 | 0.85 | 0.87 | 39 | 55 |

**Sonnet beats Opus** — and not marginally: Opus wrongly merges 39 pairs to Sonnet's 9. On the small
inputs Opus and Haiku both over-merge (3 groups where the reference has 4); Sonnet is exact. So
clustering is not a task where the top tier earns its price, and moving it off Opus is a quality
*improvement* as well as a saving.

### Corroboration survival

| model | substantive finders | 2+ | trivia finders | 2+ | substantive:trivia gap |
|---|---|---|---|---|---|
| *reference* | 3.96 | 78% | 2.00 | 40% | 1.95x |
| haiku | 3.56 | 74% | 1.64 | 36% | 2.06x |
| sonnet | 3.70 | 78% | 1.64 | 40% | 1.95x |
| opus | 3.70 | 78% | 1.68 | 40% | 1.95x |

All three approximately preserve the signal a screen would rank on. Sonnet and Opus reproduce the
reference distribution almost exactly; Haiku shaves a little off both sides.

### Correction to the first run of this experiment

An earlier pass reported that clustering **sharpened** the signal — the substantive-to-trivia gap
widening from 1.95x to 3.08x. **That was an artifact and is withdrawn.** That run used two different
prompts across its two batches, and the weaker one caused the model to silently drop findings, which
shrank trivia clusters and inflated the apparent separation. Under one prompt with no dropped ids
the gap is preserved, not sharpened. The conclusion survives; the dramatic version of it does not.

### Verdict

**The gate passes**, with a sharper recommendation than "a cheap model can do it": put clustering on
the **mid tier**. It is the most accurate of the three *and* cheaper than the status quo. Haiku is
usable — F1 0.82, signal roughly intact — but the worse trade when mid-tier is available.

Four limits carry forward:

1. **Large runs are untested.** Subject 6's `cluster-assign.json` uses positional ids
   (`ours__r1__N`) that do not join to its `findings.json` (`f00NN`), so no large run had usable
   ground truth. Dedup is hardest exactly where the orchestrator's thinking share is 77%. **Test a
   large run before committing.**
2. **The reference is itself an LLM product.** F1 0.90 means "agrees with the bench-analyze
   clustering", not "correct". Both could be wrong together.
3. **Findings get silently dropped without a hard check.** Fixed here by instruction, but a screen
   that never sees a finding cannot tier it — the prototype needs an assertion, not a prompt line.
   Haiku also mis-named its output files, following the example loosely.
4. **Only dedup was tested.** Severity normalization, confidence promotion and validator selection
   are untouched by this result.

`subject-05-r2` scored poorly for all three models (0.53 / 0.55 / 0.58), so per-run variance is a
property of the changeset rather than of the model — mild evidence the metric measures something
real.

### What this does not change

The sequencing in the Assessment above stands. The gate makes this nib *buildable*, not *next* —
#dcc-2a8i (the `roster` axis) is still the larger and better-evidenced lever, and this nib's target
remains 14-18% of output.

Screen thresholds must be calibrated against post-clustering finder counts (substantive 3.96 ->
3.70 on the mid tier), not against today's distribution.
