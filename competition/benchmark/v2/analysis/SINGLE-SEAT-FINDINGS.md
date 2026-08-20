# The single seat: what reach does, and where the gap actually is

Closes `dcc-tmz2` (does `reach=narrow` shorten exploration?) and the measurable half of `dcc-n5h2`
(why superpowers' seat finds more per cell). Both were opened after the five-subject slice showed
`bugs` reporting less than superpowers while finding comparably.

**Read `ARM-RENAMES.md` first if any figure here looks misfiled.** These cells ran as
`ours-bugs-narrow` / `ours-bugs-reachnorm`; both arms are now retired.

## The experiment

12 cells: `bugs reach=narrow` vs `bugs reach=norm`, prometheus-18081 and dotnet-efcore-34127, 3
repeats each. The arms differ by **exactly one token** — the control states `reach=narrow`
explicitly rather than inheriting it, so the presence of an argument is not itself a difference.
Arms alternated pair by pair so drift over a multi-hour run could not be confounded with the arm.

Probed first: the override is not a no-op. The `narrow` report omits Pre-existing Issues and Minor
Findings and says so; the `norm` report carries both and states it is overriding the default.

## Result: reach moves disposition, not exploration

| | `reach=narrow` | `reach=norm` |
|---|---|---|
| real-defect pool hit / cell | 0.375 | **0.458** |
| reported / cell | 0.271 | **0.375** |
| demotion gap | 0.72 | **0.41** |
| files touched per cell (mean) | 20 | 20 |
| findings found per repeat | 13,14,15 · 8,7,7 | 17,16,18 · 15,15,14 |
| cost / cell | $4.92 | $5.53 |

**Exploration breadth is identical — 20 files per cell in both arms**, measured from the seat's own
shell calls, entirely independently of the judge. Within-arm variance is 4.7x (9 to 42 files) and
dwarfs the between-arm difference of zero.

So `norm` does not make the seat look at more code. It makes it *report* more of what it already
examined, and that is worth +22% on defects found and +38% on defects reported, because much of what
`narrow` parks is real.

**Not adopted.** `reach=norm` doubles correct output (prometheus 10 → 22 correct of 24 shown) and
zeroes the demotion gap, at 8% noise and 12% cost. But it is two subjects, and `narrow`'s apparent
1.000 precision was never a measurement — it reports 2 clusters on efcore, far below the n≥10 floor.
Revisit with a third subject.

## Where the gap to superpowers actually is

**Not the brief.** decaf's `solo-reviewer` brief is 1,916 words against superpowers' 552, and roughly
2:1 against searching — 923 words on how to classify and format versus 478 on what to look for. But
decaf's checklist *names the exact defect class it missed* ("three-valued logic, coercions, and
operator semantics where the language has traps" — which is efcore `e02`), while superpowers' brief
never mentions null semantics and its agent found it. Coverage is not the gap.

**Not the model.** Measured from every cell's `modelUsage`: `bugs` and `superpowers` are both
**claude-opus-5 at 100% of cost**, one agent each. No tier advantage in either direction.

**Not reach.** See above.

**Detection is stochastic.** efcore `e02` (Critical) is found by roughly one cell in three in *every*
arm — narrow 1/3, norm 1/3, superpowers 1/2, `bugs` 0/3. It is not a blind spot; it is a coin flip.
The three-brief-revision history reads as variance, not regression. Repeats recover 0.05–0.19 of the
pool per arm, so **repeats are a lever with a known exchange rate where brief edits have produced
3.0/3.0/3.0 across three revisions.**

## Agent contribution inside the wave (14 cells)

| agent | clusters/cell | real % | sole real / cell |
|---|---|---|---|
| `adversarial-reviewer` | 6.4 | 33% | **1.07** |
| `quick-reviewer` | 3.1 | **45%** | **0.79** |
| `broad-reviewer` | 4.8 | 32% | 0.50 |
| `test-reviewer` | 3.3 | 26% | 0.50 |

`quick-reviewer` is the quietest always-on agent and the most accurate, and it out-contributes its
own floor partner `broad-reviewer` on sole-real findings while costing less (it runs mid-tier under
both `norm` and `high`). Of the 16 clusters it alone found, 12 are defect-class. If a floor slot were
ever reconsidered, the data points at `broad`, not `quick`.

**Do not act on this yet.** 14% of wave findings (49 of 351) carry no agent attribution, and
"sole finder within a cell" bounds contribution above rather than measuring true drop cost — another
agent might have found it in that agent's absence.

## What follows

- A third subject before either `reach=norm` or any roster change is decided. `PostHog-posthog-55149`
  has **20 human threads** against the corpus's current maximum of 10, and would fix the thread axis
  as well as supplying the third subject.
- `dcc-wuid` (machine-readable validation block) would let the rubber-stamp question be answered as a
  rate rather than directionally.
- Agent attribution needs fixing before any roster conclusion: 14% unattributed is too much.
