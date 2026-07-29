---
# dcc-2a8i
version: 1
title: Check how roster caps decide which personas get cut, and whether that ranking is optimal
status: completed
type: task
priority: normal
created_at: 2026-07-28T23:33:37Z
updated_at: 2026-07-29T18:41:36Z
parent: dcc-1x90
order: a0
---

`code-review`'s Step 2b.5 resolves a `midN`/`highN` cap by keeping the floor plus the
highest-ranked gate-matched specialists, ranked by a hand-written rule set: categorical
coverage first (stack reviewer, data-migration, prior-feedback, spec-compliance), then the
changeset's primary risk dimension, with `knowledge-reviewer` and `consistency-reviewer`
explicitly "ranked last" as the first to shed.

That ranking was written from intuition. There is now measured per-persona data
(`analysis/scripts/roster_yield.py`) to check it against, and at least three places where
it looks wrong:

- `adversarial-reviewer` returns 40 substantive clusters at 8,138 tok each — the best value
  at scale in the roster — but it is not in the rules' top tier.
- `consistency-reviewer` is ranked to shed first, yet it produces 28 valid-minor clusters
  and 18 sole-useful ones. It is a suggestion engine, so whether shedding it first is right
  depends on the product question in #dcc-e0wj workstream 3.
- `go-reviewer` is a stack reviewer and therefore ranked in the top tier, but it has the
  roster's worst signal share (50%).

Also worth checking: the cap counts the floor but excludes validators, so a cap bites only
the ~9.4-reviewer wave. And ranking happens per changeset, so "optimal" means optimal given
the Step 2a classification, not globally.

## Context

Captured while re-analysing benchmark subjects 2 and 3 after the #dcc-9kkz contamination
fix. The per-persona value/cost table came out of #dcc-e0wj workstream 2, which found no
persona is dead weight on participation — which is precisely why *ordering* matters: if
nothing is droppable outright, the cap's drop order becomes the real lever.

Related: #dcc-1xtt (gate tuning — which personas are dispatched at all) is the sibling
question; this one is about what happens once a cap forces a choice among those dispatched.

## Measured — the ranking is wrong in two specific ways

Checked 2026-07-29 against the 18 archived `ours` runs. The decision a cap actually makes is
"given this persona was gate-matched, what does dropping it cost?", so the metric is **drop cost
per run dispatched** = `(2 × substantive clusters only this persona found) + (substantive clusters
that would fall below the 2-finder corroboration threshold)`, divided by runs dispatched.

The doubling reflects #dcc-gcob: a sole-found substantive cluster is lost outright, while a
demoted one survives but loses the agreement signal consolidation ranks on.

| persona | runs | drop cost/run | minor/run | noise/run | current tier |
|---|---|---|---|---|---|
| security-reviewer | 3 | 2.00 † | 0.0 | 2.0 | 2 risk |
| **adversarial-reviewer** | 13 | **1.85** | 0.3 | 0.5 | 2 risk, *behind* security |
| test-reviewer | 16 | 0.94 | 2.1 | 1.2 | 2 risk |
| typescript-reviewer | 6 | 0.83 | 0.8 | 0.8 | 1 categorical |
| broad-reviewer | 18 | 0.78 | 1.4 | 0.7 | floor |
| spec-compliance-reviewer | 7 | 0.57 | 0.4 | 0.4 | 1 categorical |
| performance-reviewer | 9 | 0.56 | 0.1 | 0.2 | 2 risk |
| prior-feedback-reviewer | 8 | 0.50 | 0.5 | 0.4 | 1 categorical |
| go-reviewer | 4 | 0.50 | 1.8 | 0.0 | 1 categorical |
| design-reviewer | 12 | 0.50 | 0.7 | 1.1 | 2 risk |
| quick-reviewer | 17 | 0.24 | 0.7 | 0.4 | floor |
| knowledge-reviewer | 18 | 0.17 | 0.8 | 0.8 | 3 shed first |
| dotnet-reviewer | 5 | 0.00 | 0.4 | 0.4 | 1 categorical |
| consistency-reviewer | 18 | 0.00 | 1.6 | 1.3 | 3 shed first |

† n=3. Not actionable — see Limits.

### 1. `adversarial-reviewer` is the most load-bearing specialist in the roster, and is ranked mid

1.85 per run over 13 runs — the strongest well-sampled figure on the board, and it sole-found 10
substantive clusters. The rules place it in tier 2 **and explicitly behind `security-reviewer`**
("security-adjacent → `security-reviewer` (then `adversarial-reviewer`)"). On this evidence it
should survive every cap that keeps any specialist at all.

The nib's suspicion is confirmed and understated: this is not a tier misplacement, it is the
single largest ranking error.

### 2. "Categorical coverage the generalists cannot substitute" does not hold as a class

That premise puts every stack reviewer in the top tier on the argument that dropping one "leaves an
entire dimension unreviewed". The stack reviewers span **0.00 to 0.83**, so the category does not
predict contribution. `dotnet-reviewer`'s 0.00 — everything it found had two or more other finders —
is a **stable** result (rank 12-14 under jackknife), so at least for C# the generalists demonstrably
substitute. `data-migration-reviewer` never fired at all.

But the individual stack figures are *not* trustworthy either (see Stability): `typescript` and `go`
swing 10 and 9 ranks. So the correct reading is narrower than "rank by measurement instead" — for
these personas neither category nor measurement supports a confident order, which is what makes the
dispatch gate the right place to carry the weight.

### 3. Shedding `consistency-reviewer` and `knowledge-reviewer` first is correct — for one preset

Both are 0.00–0.17 on substantive drop cost, so for a bug-hunting run they are the right first
cuts. But `consistency-reviewer` produces **1.6 valid-minor per run** (with 1.3 noise), and
`knowledge-reviewer` is separately the source of most severity miscalibration — sole Critical in 8
of the 9 miscalibrated clusters (#dcc-e0wj workstream 1).

So the honest answer to "should they shed first?" is **it depends on the preset**, which is exactly
what #dcc-9q01 introduces. Under `bugs`, shed first. Under `audit`, `consistency-reviewer` is a
primary contributor to the deliverable and should not lead the cut.

### 4. Incidental — `quick-reviewer` is the weakest floor member

0.24 per run, 0 sole-unique across all 18 runs, 100% of its findings shared. It is a pure
corroborator. That is not worthless — agreement is the discriminator — but it is thin justification
for being undroppable when a cap is tight, and it costs 11.3% of sub-agent output.

## Stability — where the ordering can be trusted

Leave-one-subject-out jackknife over the 9 subjects, plus the size slice (the only slice the study's
methodology permits — one subject per language x size cell makes a language slice meaningless).

| persona | base rank | jackknife range | swing | n |
|---|---|---|---|---|
| **adversarial-reviewer** | 2 | **1-2** | **1** | 13 |
| quick-reviewer | 11 | 10-11 | 1 | 17 |
| dotnet-reviewer | 14 | 12-14 | 2 | 5 |
| test-reviewer | 3 | 2-5 | 3 | 16 |
| broad-reviewer | 5 | 3-6 | 3 | 18 |
| prior-feedback-reviewer | 10 | 7-10 | 3 | 8 |
| knowledge / consistency | 12 / 13 | 8-12 / 9-13 | 4 | 18 / 18 |
| design-reviewer | 9 | 6-10 | 4 | 12 |
| spec-compliance / performance | 6 / 7 | 5-10 | 5 | 7 / 9 |
| **go-reviewer** | 8 | 3-12 | **9** | 4 |
| **typescript-reviewer** | 4 | 3-13 | **10** | 6 |
| **security-reviewer** | 1 | **1-14** | **13** | 3 |

**Swing tracks sample size almost exactly: every persona at n >= 12 swings <= 4; every persona at
n <= 6 swings up to 13.** The ordering is trustworthy at the top (`adversarial`) and at the bottom
(`knowledge`, `consistency`, `quick`, `dotnet`) and unusable through the middle, which is precisely
where the rarely-firing specialists sit.

### Drop cost rises steeply with diff size — the stronger finding

| persona | small | medium | large |
|---|---|---|---|
| adversarial | 0.50 | 1.50 | **3.20** |
| typescript | 0.00 | 0.00 | **2.50** |
| test | 0.33 | 1.00 | 1.50 |
| broad | 0.62 | 0.75 | 1.00 |
| spec-compliance | 0.00 | 0.00 | 1.00 |
| design | 0.00 | 0.50 | 0.83 |
| quick | 0.00 | 0.00 | 0.67 |
| knowledge | 0.25 | 0.00 | 0.17 |

Nearly monotonic. **On small diffs almost nothing is load-bearing** — most personas sit at 0.00,
meaning everything they found someone else found too. On large diffs specialists become decisive.
So the cost of capping is a function of changeset size, not a constant. `knowledge-reviewer` is the
lone exception, flat-to-declining across sizes, which confirms it as the shed-first pick at any size.

## What to change

A first draft of this nib proposed replacing category ranking with measured drop cost outright. The
stability data refutes that: it works for the frequently-dispatched personas and fails exactly where
it was meant to help. A persona that rarely fires has thin evidence **by construction** — but also,
by construction, only fires when its domain is present. For those the gate *is* the evidence of fit.

So the current rules are not wrong everywhere. They are wrong for the generalists and roughly right
for the hard-gated specialists.

1. **Floor — `broad` + `quick`**, justified by the `evidence` screen needing an agreement signal to
   score with (#dcc-9q01's cluster-before-screen constraint), not by `quick`'s solo value (0.24/run,
   zero unique findings in 18 runs).
2. **Measured tier (n >= 12) — use the numbers.** `adversarial-reviewer` first among specialists;
   `knowledge` and `consistency` shed first. This is the part the data supports.
3. **Gate-evidenced tier (n < 12) — rank by category, as today.** The gate proves fit and there is
   no usable measurement. **Do not promote `security-reviewer`** on the strength of its n=3 figure.
4. **Scale the default roster with diff size** rather than capping at a fixed N — the size table
   says a tight cap on a small diff is nearly free and an expensive mistake on a large one.

**The one confident ranking change: `adversarial-reviewer` moves ahead of `security-reviewer`**, and
into the top specialist slot. Rank 1-2 across every jackknife at n=13.

Preset-dependence still holds for the shed-first pair: under `audit`, rank by drop cost **+** minor
yield, which moves `consistency` from last to mid-table. This nib is the `roster` axis of #dcc-9q01.

## Limits — read before acting

- **Sample size decides trustworthiness, and the threshold is measured, not guessed:** n >= 12
  swings <= 4 ranks, n <= 6 swings up to 13. **`security-reviewer`'s 2.00 is the top of the table
  and the least trustworthy number in it** (n=3, swing 13) — do not promote it on this basis.
- **What would fix the unusable middle** is more data on the rarely-firing personas: the three unrun
  subjects (go/medium, rust/medium, rust/large), or more repeats. Worth scoping into whatever
  re-run #dcc-9q01 requires.
- **The dispatch gates changed after these runs.** #dcc-1xtt widened `security-reviewer`'s gate and
  narrowed the stack reviewers to idiom surface. Both change which personas are even eligible for a
  cap decision, so these frequencies will not reproduce.
- **One configuration, nine subjects.** Measured under `mid --report` only.
- The metric counts *participation*, per #dcc-e0wj workstream 2's finding that no persona is dead
  weight. It deliberately does not reward uniqueness alone — that error was already made once with
  `performance-reviewer`.

## Acceptance

- [x] [run] `rg -n "Rank the gate-matched specialists" -A12 decaf-quality/skills/code-review/SKILL.md`
      — expect: the order is stated as measured drop cost, not agent category, and names its source
- [x] [run] `python3 competition/benchmark/analysis/scripts/roster_yield.py` — expect: exit 0; the
      per-persona figures the ranking cites are reproducible from committed data
- [x] [manual] `adversarial-reviewer` ranks ahead of `security-reviewer` among specialists, or the
      decision to keep the current order is recorded with a reason
- [x] [manual] Under-sampled personas are handled explicitly — the ranking does not promote
      `security-reviewer` on n=3, and personas below the n>=12 stability threshold are ranked by
      their gate rather than by their measured figure
- [x] [manual] The default roster scales with changeset size, or the decision to keep a fixed `N`
      is recorded against the size table (drop cost ~0 on small diffs, 3.20 for `adversarial` on
      large ones)

## Summary

Measurement complete and acted on. The drop-cost table, its stability analysis and the size slice
are recorded here; the ranking they justify shipped in #dcc-1x90.

Two errors confirmed and fixed: adversarial-reviewer was ranked mid-tier and behind
security-reviewer despite being the most load-bearing persona measured, and the "categorical
coverage the generalists cannot substitute" premise did not hold as a class. One rule survived with
a caveat — shedding consistency and knowledge first is right for a bug hunt and wrong for an audit,
which made drop order preset-dependent.

The preset-dependent ordering criterion moved to #dcc-rbkl; it cannot be satisfied before presets
exist.
