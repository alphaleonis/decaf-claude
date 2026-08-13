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
