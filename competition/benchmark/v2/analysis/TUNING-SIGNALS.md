# What the pilot says about tuning decaf's review presets

Derived from the v2 pilot ([`PILOT-RESULTS.md`](PILOT-RESULTS.md)) — two subjects, both `library`,
seven tools × two repeats, blind-adjudicated twice. Every figure carries the pilot's caveats: two
subjects, one application type, and no precision ratio where a tool reported under ten clusters.

These are signals, not verdicts. What makes them worth acting on is that three of the five are
*compositional* — they say where a preset's output sits, not just how much of it there is — and
composition is stable in a way a ranking is not.

---

## 1. `ours-bugs`'s reporting bar is miscalibrated, not conservative

This is the strongest single result for tuning, and it is not a precision/noise trade-off.

Across both subjects `ours-bugs` **found 40 clusters and reported 7**. Of the 33 it suppressed,
**7 were graded real — a 21% demotion loss.** It binned as many real findings as it published.

| Tool | reported | demoted | demoted **and real** | loss |
|---|---|---|---|---|
| `anthropic-code-review` | 11 | 10 | 3 | 30% |
| **`ours-bugs`** | **7** | **33** | **7** | **21%** |
| `ours-audit` | 78 | 50 | 4 | 8% |
| `ours-review` | 39 | 46 | 3 | 7% |
| `comprehensive-review` | 41 | 11 | 0 | 0% |
| `pr-review-toolkit` | 54 | 7 | 0 | 0% |
| `superpowers` | 45 | 0 | 0 | — |

The seven it discarded were not marginal judgment calls. **Every one was reported by four to six
other tools, and three were high severity:**

- the when-clause result already simplified under the assumption the rewrite deletes *(high, 4 tools)*
- `Coalesce` admitted by the unfiltered operator recursion *(high, 4 tools)*
- all five new tests positive, none covering the shape the optimization breaks *(high, 6 tools)*
- subquery per-step attribution folding out-of-window steps onto step 0 *(medium, 4 tools)*
- `MergeSamplesReadFromSubquery` merging positionally on an unstated precondition *(medium, 4 tools)*
- the null-forgiving `func.Instance!` on an unenforced invariant *(low, 4 tools)*
- the vacuous `GreaterOrEqual(SamplesRead, 0)` API assertion *(low, 6 tools)*

**The gate is rejecting consensus defects.** Its cost is the roster's worst — $34.60 for 5 real
findings, $6.92 each — and its thread recall is the roster's lowest at 0.05.

**Intervention:** the `bugs` preset's evidence/confidence gate, not the shared demotion mechanism —
see signal 2. A finding corroborated by multiple reviewers should not be reachable by that gate.

---

## 2. The shared demotion machinery works; only `bugs` misuses it

`ours-audit` and `ours-review` demote heavily — 50 and 46 clusters — and lose only 8% and 7% to it.
That is a working reporting bar: it suppresses a lot and it suppresses correctly.

So the fault in signal 1 is not "decaf demotes too much." Two of three presets demote more in absolute
terms than `bugs` does and lose a third as much proportionally. The defect is specific to the `bugs`
preset's threshold, which is the narrow, actionable conclusion.

---

## 3. decaf's precision cost is *entirely* low-severity volume

Of `ours-audit`'s 41 reported-but-not-substantive clusters, **every single one is judged low, nit or
info**. Not one is medium or above. `ours-review` is the same shape: 18 non-substantive, 17 of them
low or nit.

| Preset | non-real reported | judged severity of that output |
|---|---|---|
| `ours-audit` | 41 | low 22 · nit 13 · info 6 — **zero medium+** |
| `ours-review` | 18 | low 13 · nit 4 · info 1 |
| `ours-bugs` | 2 | low 2 |

The severity-weighted precision confirms it from the other direction. Weighting rewards catching the
consequential ones, and decaf's presets gain far more from it than the field does:

| Tool | prometheus plain → weighted | efcore plain → weighted |
|---|---|---|
| `ours-audit` | 0.46 → 0.66 (+0.20) | 0.50 → 0.75 (+0.25) |
| `ours-review` | 0.50 → 0.68 (+0.18) | 0.60 → 0.84 (+0.24) |
| `comprehensive-review` | 0.74 → 0.85 (+0.12) | 0.89 → 0.96 (+0.07) |

**The noise is not wrong — it is small.** decaf's presets are accurate about minor things at volume.

**Intervention:** this is the cheapest available precision gain, because it touches no real finding.
Collapsing the Minor/nit tier into a counted summary line rather than enumerating each item as a
finding would move plain precision substantially while leaving every substantive finding, and every
unique one, exactly where it is. It is a presentation change, not a detection change.

---

## 4. `ours-audit` is the roster's best detector, and that is worth protecting

37 real findings — the most of any tool — and **6 unique real findings, also the most.** The uncapped
roster earns its cost on detection. Any intervention that trims it must be checked against
`unique_real`, not against precision, or it will trade away the thing the preset is actually good at.

## 5. `ours-review` and `ours-bugs` contributed **zero** unique real findings

Everything they surfaced, at least one other tool also surfaced. Against a roster this is redundancy;
against a single-tool deployment it is not, since a user runs one tool and not seven. But it does mean
neither preset is currently reaching anything the field misses, and `ours-review` costs $71.69 to do
it.

---

## 6. Cost per real finding is decaf's weakest axis

| Tool | real | cost | $/real |
|---|---|---|---|
| `superpowers` | 31 | $17.16 | **$0.55** |
| `comprehensive-review` | 33 | $82.40 | $2.50 |
| `pr-review-toolkit` | 29 | $89.85 | $3.10 |
| `ours-audit` | 37 | $117.60 | $3.18 |
| `ours-review` | 21 | $71.69 | $3.41 |
| `ours-bugs` | 5 | $34.60 | $6.92 |

`superpowers` reaches 31 real findings — within striking distance of `ours-audit`'s 37 — for **a
seventh of the spend**, with zero demotion machinery and no roster at all. That is the number
`dcc-hyxw` has to beat, and it is a far more demanding target than the v1 comparison that epic was
founded on.

---

## The tuning epic's premise needs restating

`dcc-hyxw` opens with "`ours` costs $21.33/run against anthropic's $7.61 while losing on severity
calibration (0.70 vs 0.90)". **Those are v1 numbers and v1 is void** — contamination, GitHub leak,
unaudited ground truth, unpinned effort, with the two leaks pushing in opposite directions. The epic's
motivating comparison cannot be cited, including in its own justification.

The v2 replacement premise, from this pilot: decaf's presets are **accurate but expensive and
verbose**, their non-substantive output is **entirely low-severity**, `ours-audit` is the roster's
**best detector** and should be protected rather than trimmed, and `ours-bugs`'s gate is **discarding
consensus defects** and is the one outright defect the data shows.

---

## Caveats that bound all of this

- Two subjects, both `library`. No `backend`, `contract` or `app-ui` evidence.
- `ours-bugs` has no precision figure at all — it never cleared the ten-cluster floor. Signal 1 rests
  on demotion counts, which need no ratio.
- Signals 3 and 5 are compositional and hold on both subjects independently. Signal 6 is a ratio over
  two subjects and should be re-checked when the corpus widens.
- Every "real" here is the blind judge's call, stable across two passes at κ 0.74–0.78 on the
  load-bearing boundary — but the judge shares a model family with the reviewers, which is a bounded
  and stated limitation, not a resolved one.

---

## The class axis changes the `ours-bugs` diagnosis (2026-08-13, [[dcc-opdr]])

All 267 clusters were backfilled with a judge-assigned `finding_class` from a closed set, graded
blind to tool identity **and blind to the verdict** — class and substance are meant to be orthogonal,
and showing the grader "this was trivia" would pull the classification style-ward.

### `ours-bugs` is doing its job in composition, and failing it in reach

What each tool **reports**, by class, both pooled subjects, counts:

| tool | defect | risk | test-gap | docs | design | style | total |
|---|---|---|---|---|---|---|---|
| `ours-audit` | 20 | 8 | 21 | 8 | 14 | 7 | 78 |
| `pr-review-toolkit` | 14 | 2 | 13 | 11 | 10 | 4 | 54 |
| `superpowers` | 13 | 2 | 12 | 8 | 8 | 2 | 45 |
| `ours-review` | 12 | 2 | 9 | 5 | 9 | 2 | 39 |
| `comprehensive-review` | 11 | 4 | 6 | 7 | 12 | 1 | 41 |
| **`ours-bugs`** | **6** | 0 | 0 | 0 | 1 | 0 | **7** |
| `anthropic-code-review` | 5 | 0 | 2 | 2 | 2 | 0 | 11 |

**`ours-bugs` has by far the purest defect focus in the roster** — 6 of its 7 reported findings are
defect-class. Every other tool sits between 26% and 45%. The preset is not confused about what it is
for, and its low volume is a design choice rather than a malfunction.

### But it is the worst defect-finder among decaf's presets

Against the 16 real defect-class clusters the whole roster found:

| tool | defects found | reported | **suppressed** | defect recall |
|---|---|---|---|---|
| `ours-audit` | 13 | 13 | **0** | 81% |
| `pr-review-toolkit` | 12 | 12 | 0 | 75% |
| `comprehensive-review` | 10 | 10 | 0 | 62% |
| `ours-review` | 10 | 9 | 1 | 56% |
| `superpowers` | 9 | 9 | 0 | 56% |
| **`ours-bugs`** | **8** | **5** | **3** | **31%** |
| `anthropic-code-review` | 6 | 5 | 1 | 31% |

`ours-bugs` **found eight real defects and reported five.** Its defect recall is the lowest of any
decaf preset — 31% against `ours-audit`'s 81% — and a third of that shortfall is self-inflicted: it
detected three more and binned them.

`ours-audit` is the counter-example that localizes the fault precisely: it suppressed 4 real findings
and **not one was a defect** (2 risk, 2 design). Its gate is correctly calibrated for correctness. So
decaf's demotion machinery *can* protect defects; the `bugs` preset's threshold does not.

### The restated conclusion

The earlier framing — "21% demotion loss" — understated it and pointed at the wrong lever. The
sharper statement is:

> The preset whose sole purpose is finding correctness flaws has the lowest defect recall of decaf's
> three presets, and it discards three of the eight real defects it manages to find.

Purity is not the problem. Reach is, and the gate is making reach worse.

---

## Mechanism, traced (2026-08-16) — and two corrections to the claim above

The earlier statement — "`ours-audit` suppressed 4 real findings and not one was a defect, so the
machinery can protect correctness findings and the `bugs` threshold does not" — reaches the right
conclusion by wrong reasoning, twice.

### Correction 1: `ours-audit`'s gate does not *spare* defects, it *judges* them correctly

Both presets fire the screen on defect-class claims at **exactly the same rate**:

| tool | demoted | of which defect-class | defect demoted **and real** |
|---|---|---|---|
| `ours-audit` | 50 | **16** | **0** |
| `ours-bugs` | 33 | **16** | **3** |
| `ours-review` | 46 | 17 | 1 |

`ours-audit` rejected 16 defect claims and was right about all 16. `ours-bugs` rejected 16 and was
wrong about 3. The gate is not being avoided on one side and over-applied on the other — it engages
identically and differs in accuracy.

### Correction 2: it is not the bar, it is the bar interacting with the roster cap

`evidence=strong` admits a cluster as primary at **screen score ≥ 80, or ≥ 60 with two or more
independent finders** (`code-review` SKILL.md, "What `evidence` admits"). The presets differ on four
axes at once, and two of them compound here:

| preset | `roster` | `evidence` |
|---|---|---|
| `bugs` | **capped at 4** | **`strong`** |
| `audit` | all gate-matched (10–12) | `any` |

At an uncapped roster almost any real defect attracts a second finder and takes the ≥60 path. At
`roster≤4` it frequently cannot, and must clear **≥80 on a single reviewer's say-so**.

The three real defects `ours-bugs` binned show exactly this:

| judged severity | finders | found by |
|---|---|---|
| medium | 2 | `adversarial-reviewer`, `quick-reviewer` |
| **high** | **1** | `adversarial-reviewer` |
| **high** | **1** | `adversarial-reviewer` |

Two high-severity real defects with a single finder each, each requiring ≥80 alone, each rejected —
and each independently confirmed afterwards by four other tools.

### Why this is a design fault and not a tuning miss

All three came from `adversarial-reviewer`, whose brief is to construct failure scenarios *"in the
space between pattern-matching reviewers"*. **Its findings are uncorroborated by construction.** The
corroboration escape hatch in the `strong` bar is therefore systematically unavailable to the one
agent whose output most depends on it — and `bugs`, the preset that most wants adversarial findings,
is also the preset that caps the roster hardest.

The skill already documents this interaction one step down the ladder:

> **`low` overrides `evidence` back to `norm` deliberately.** With two reviewers corroboration is
> scarce, and `strong` would demand a lone reviewer score ≥80 on its own — which would empty the
> report on the one mode whose whole purpose is fast feedback.

That correction stops at `roster=2`. It was never extended to `bugs` at `roster≤4`, where the same
argument holds with slightly less force — and the pilot shows it holding hard enough to lose two
high-severity defects across two subjects.

### What this changes about the intervention

"Lower the `strong` bar" is the wrong fix and would cost precision the preset currently earns —
`ours-bugs` reported 7 clusters and only 2 were non-substantive, both `low`. Candidates that target
the actual mechanism:

1. **Extend `low`'s override upward** — `bugs` uses `evidence=norm` at any roster below some floor.
   Smallest change, matches reasoning already in the skill.
2. **Make the corroboration clause roster-relative** — "two or more finders" becomes a share of the
   dispatched roster, so 1-of-4 counts as 3-of-12 does.
3. **Exempt the adversarial lane** — a finding from an agent whose brief is non-overlapping is
   scored on its own merits at the ≥60 line without the finder-count requirement.

Option 2 is the most principled and the most invasive; option 1 is the cheapest and is already
justified in the skill's own words. Neither should ship without re-measuring on both pilot subjects,
where the counterfactual is known exactly: three real defects, two of them high.

---

## Correction (2026-08-16): the roster-cap recommendation is withdrawn

Signal 1 above proposed raising the `bugs` roster cap to fix detection. **That is the wrong
direction.** It buys recall with money, and the pilot shows the target result is achievable at half
what the preset already spends: `superpowers` reports a strict superset of `ours-bugs`' output —
zero clusters unique to `ours-bugs` across both subjects — at $4.12/cell against $8.56 and ~12 min
against ~22.

The cost is **linear in reviewer count**: least squares over 14 decaf cells spanning 4–10 reviewers,
three presets and three subjects gives `cost = -4.19 + 3.17 × reviewers`, R² = 0.948, with a
*negative* fixed component — there is no orchestrator overhead worth naming. decaf pays ~$3.17 per
reviewer; `superpowers` pays $4.12 for one generalist agent that reports a strict superset of what
`ours-bugs`' four produce. (An earlier draft blamed orchestration overhead, reading Opus tokens as
the orchestrator's; under `models=low` the judgment reviewers inherit the session model too, so that
split was unfounded.)

Any intervention on `bugs` has to come out at or below $4/cell. Tracked in [[dcc-1ix0]].
