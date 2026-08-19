# What every number means (nib dcc-t83x)

Written because on 2026-08-19 five conclusions about one 12-cell dataset reversed inside a session,
and four of the five were caused by reading the wrong quantity rather than by bad data. Definitions
now live here and are printed by `compare_arms.py` on every run, so a caveat cannot get separated
from the number it applies to.

## The two orthogonal axes

Every cluster carries both. Conflating them caused the first reversal.

| axis | question | values |
|---|---|---|
| **`verdict`** | is the claim **right**? | `matches-thread` · `matches-key` · `valid-other` · `valid-minor` · `trivia` · `false-positive` |
| **`finding_class`** | what is it **about**? | `defect` · `risk` · `test-gap` · `docs` · `design` · `style` |

A "considered whether X could crash — it cannot" note is **`defect`-class and `trivia`-verdict**. It
is *about* a potential defect, and it is *not* a finding. Counting defect-class clusters as defects
found is wrong, and it is the specific mistake that made `reach=norm` look like it had discovered
three new efcore defects when the judge had called all three trivia.

## Disposition: found vs reported

| term | meaning |
|---|---|
| **reported** / **shown** | the tool put it in front of the developer |
| **demoted** | the tool examined it and decided not to show it (decaf's "Considered But Not Flagged") |
| **found** | reported ∪ demoted — everything the tool formed a claim about |
| **demotion gap** | `(found − reported) / found` |

Detection and disposition are different capabilities. An arm can find a defect and hide it; the fix
for that is a threshold change, not a detection change. superpowers has no demotion channel at all,
so its `found` always equals its `reported` — which flatters it on `reported` metrics and must be
stated when comparing.

## `real`, and what `precision` actually counts

```
REAL  = {matches-thread, matches-key, valid-other}     ← counts toward precision
MINOR = {valid-minor}                                  ← CORRECT AND ACTIONABLE, but NOT in `real`
NOISE = {trivia}
WRONG = {false-positive}
```

**`precision` = `real / reported`, and it treats `valid-minor` as a miss.**

`valid-minor` is defined by the grader rubric as "correct and actionable but small (a nit that is
nonetheless right)". So an arm reporting 24 clusters of which 12 are `real`, 10 are `valid-minor`,
1 `trivia` and 1 `false-positive` scores **precision 0.50** while **22 of its 24 items are correct**.
Reading 0.50 as "half of this is wrong" is a factual error — that was reversal 4.

When the question is *how much of this is worth reading*, use:

```
noise% = (trivia + false-positive) / reported
```

`noise%` is **not** `1 − precision`. Report both, or report `noise%` and the verdict bands.

## Pools and denominators

- **real-defect pool** — clusters that are `real` **and** `defect`-class. The denominator for
  defect recall.
- **The pool is dynamic.** It is the union of what tools found, so adding an arm that finds
  something genuinely new *enlarges it* and retroactively lowers every other arm's recall. On
  2026-08-18 folding in one arm moved immich 4 → 5 and grafana 4 → 6, dropping `ours-bugs` from
  1.000 to 0.800 and 0.667 without that arm changing. **Always publish the pool size and the arm set
  beside a recall figure**, and never compare a recall across fold-ins (nib dcc-dirp).
- **Coverage groups.** An arm run on 2 subjects is scored against a different pool than one run on
  5 — on 2026-08-19 that was 53 clusters versus 77. `compare_arms.py` refuses to rank across groups.

## Ratios that are withheld

No ratio is emitted below **10 reported clusters**. During the pilot a precision moved 1.00 → 0.60
when a second repeat took its denominator from 3 to 5. A withheld figure prints the raw counts and
the reason; it is never silently omitted.

This bites decaf hardest and it is not a flaw in the rule: `bugs` at `reach=narrow` reports 2
clusters on efcore. Its "perfect precision" was never a measurement.

## What is NOT a detection measure

**`new_clusters`** — the clusterer's count of claims not already present in the pool. A defect that
eleven earlier arms already recorded produces **no new cluster** when a twelfth arm finds it. Three
of the 2026-08-19 reversals came from reading this as a detection record. It answers "what did this
arm add to the corpus", never "what did this arm find".

## Judge-dependent figures

Every verdict-derived number depends on the grading day. Report the judge model, and the
calibration against the pilot verdicts, beside any of them (nib dcc-n4nf). On 2026-08-19 the judge
was internally perfect on prometheus (κ 1.0) while agreeing with the pilot on 9/15 and 6/15, and it
was systematically harsher: 11 disagreements on the calibration sample, all 11 in the harsher
direction. Comparative claims within one grading wave survive that; absolute trivia counts do not.

Thread recall is the least stable axis — two blind passes over identical clusters moved it by up to
0.20 — and should be reported as a band with `n` attached (nib dcc-di47).

## A limitation of the fact tables, found by testing them

**"This cluster was new in fold-in X" is not derivable from the facts.** `clusters.jsonl` records
what a cluster *is*, not when it entered the pool, and set arithmetic over `observations.jsonl`
cannot recover it: `reported(armB) − reported(armA)` also picks up long-standing clusters that armA
simply did not report. Those are different sets, and confusing them is exactly the substitution that
caused three of the 2026-08-19 reversals.

If you need novelty, read the committed grading artifact for that fold-in
(`pooled/<subject>/grading/foldin-<date>-<arm>/cluster-assignments-*.json`), which lists
`new_clusters` explicitly. `scoring/test_reversals.py` names the ids for that reason.

This is a deliberate omission rather than an oversight: novelty is a property of a *fold-in event*,
not of a cluster, and putting it on the cluster row would make it wrong as soon as another arm is
added. Anything that wants it should read the event.
