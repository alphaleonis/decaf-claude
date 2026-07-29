---
# dcc-gcob
version: 1
title: Give reviewer personas disjoint briefs to cut the 77% restatement rate
status: scrapped
type: feature
priority: normal
estimate: l
tags:
    - code-review
created_at: 2026-07-28T20:41:05Z
updated_at: 2026-07-29T13:26:49Z
parent: dcc-hyxw
order: aw
---

# Why

**~77% of sub-agent findings restate a sibling's**, and ours emits ~19.5k output tokens per agent
against anthropic's 9.6k — a **2.0× gap**, and the field's outlier low. Ours runs only 23% more
reviewer count (9.4 vs 5), so the redundancy is paid nine times over.

Anthropic's five agents have genuinely **disjoint** jobs: CLAUDE.md compliance, a shallow bug
scan, git history, prior PR comments, and code comments. Ours has `broad`, `quick`, `knowledge`,
`consistency` and `adversarial` all sweeping overlapping general ground — the personas differ in
emphasis, not in territory.

This is the only lever that could plausibly close the per-agent output gap, because it attacks
the cause rather than trimming the symptom.

# What to change

Narrow each persona's brief so agents cannot restate each other. The generalist cluster is where
the overlap is: `broad` (15.4% of sub-agent output, 45 substantive clusters) and `quick` (11.3%,
29) are the always-on floor and overlap most with `knowledge` and `consistency`.

Anthropic's model is worth copying literally: each agent gets **one channel of evidence**
(the diff alone, git history, prior review threads, code comments, project conventions) rather
than one *concern* (bugs, design, knowledge) applied to all evidence.

# The risk — read before starting

**Redundancy is also what produces corroboration, and corroboration drives the anchors.**
Consolidation promotes confidence on agreement (Step 5 rule 4), which is what carries a finding
over the confidence gate and up the ranking. Ours' calibration is already the weak metric
(0.70 vs 0.90, restated per #dcc-hmp6); stripping overlap could make it worse even while output
drops.

This exact error has been made once already in #dcc-e0wj: `performance-reviewer` looked
droppable because it never *uniquely* found anything, when it was in fact among the finders on 7
of 9 perf clusters including an escaped bug. Disjoint briefs risk reproducing that at roster
scale — the difference being that here it would be designed in, not measured after.

Treat a drop in multi-finder agreement as a **cost**, not a success, and measure it explicitly.

# Acceptance

- [ ] [manual] Each reviewer persona's brief states its evidence channel, and no two personas
      share one. `[manual]` because "these briefs do not overlap" is a reading of prose, not a
      mechanical check.
- [ ] [run] `python3 competition/benchmark/analysis/scripts/roster_yield.py` — expect: exit 0,
      per-persona output recorded post-change against the 19.5k/agent baseline
- [ ] [manual] Re-measured on benchmark subjects: restatement rate against the 77% baseline,
      **and** the multi-finder agreement rate and severity calibration against theirs, with an
      explicit judgement that calibration did not regress

# Notes

Reasoning and measured basis: #dcc-e0wj → `# Candidate interventions` → item 3. Larger design
change; needs its own re-run rather than sharing one.

# Constraint: keep every evidence channel scoped to the changed files

Adopting anthropic's evidence-channel model is the point of this nib, but three of the five
channels named above — git history, prior review threads, project conventions — are **repo- and
history-scaled unless explicitly bounded**. Lifting the idea without the bound would flip ours'
cost from diff-driven to repo-driven.

Measured residual repo-sensitivity, after controlling for diff size (n=9 subjects):

| tool | partial r(cost, repo files \| diff) |
|---|---|
| **ours** | **0.403** |
| anthropic | 0.572 |
| pr-review-toolkit | 0.595 |
| tag1 | 0.770 |
| superpowers | 0.831 |

**Corrected on the repaired data (#dcc-9kkz).** An earlier version of this table had anthropic at
0.119 and cited it as the exemplar — that figure came from the contaminated cells and is wrong.
On clean data **ours has the lowest repo sensitivity in the field**, and anthropic sits mid-pack
at 0.572 despite scoping every repo-touching channel to the modified files:

- "Read the git blame and history of the code **modified**"
- "Read previous pull requests that touched **these files**"
- "CLAUDE.md files in the directories **whose files the pull request modified**"

So the scoping discipline is still the right design rule — it is what keeps a history channel
bounded — but it is no longer demonstrated by anthropic being exemplary. The evidence now rests
on the counterexamples: superpowers at 0.831 (one agent, a diff range, free rein) and tag1 at
0.770, both of which explore unbounded.

**Rule: scoped retrieval stays diff-scaled; unscoped exploration becomes repo-scaled.** Every
brief written under this nib must name its scope in terms of the changed files. Ours currently
scales with the change under review (r = +0.80 on diff LOC, +0.31 on repo files) — and that is
now the **best** such property in the field, so this nib is defending a lead rather than chasing
one.

Treat a rise in partial r(cost, repo | diff) above the 0.403 baseline as a **regression**, and
measure it in the same re-run as the restatement rate.

## Reasons for Scrapping
## Reasons for Scrapping

Measured before building. **The premise does not hold: the redundancy this nib set out to remove is
the signal consolidation depends on.**

### 1. The 77% baseline does not measure sibling restatement

It is `1 − distinct_clusters / all reported_by rows`, macro-averaged across subjects
(`compute_metrics.py::subagent_distinctness`). That denominator counts three things that are not a
reviewer restating a sibling:

- **consolidated-report rows** — not a sub-agent at all;
- **validator rows** — whose *job* is to re-examine an already-raised finding (98% co-occurrence,
  by construction);
- **the same agent finding the same thing in both repeats** — that is determinism, a property worth
  having, counted here as waste (the metric is repeat-agnostic when counting distinct clusters but
  not when counting instances).

Reviewer-to-reviewer restatement *within a single run* is **44%** (270 distinct findings over 485
discovery reports), not 77%. On the corrected metric `ours` is **not an outlier** — anthropic 38%,
pr-review-toolkit 39%, ours 44%, tag1 45% — where the published 77% had made it look uniquely
redundant. (An earlier hand calculation in this nib said 47%; the committed metric resolves
sub-agent personas through the per-run cache and so excludes validators the hand version missed.)

### 2. Corroboration is the strongest quality signal in the roster

| tier | mean finders | 2+ finders | 3+ finders |
|---|---|---|---|
| substantive | **2.80** | **72%** | 46% |
| valid-minor | 1.64 | 38% | 15% |
| trivia / FP | 1.32 | 16% | 7% |

### 3. The redundancy sits on real findings, not noise

Of 240 restated reviewer findings, **62% land on substantive clusters** and only **12%** on
trivia/FP. Disjoint briefs delete those 240 findings, and what goes is mostly agreement about things
that turned out to be real. 72% of substantive findings would fall to a single finder — which is
exactly where 84% of trivia already sits. Consolidation would lose its discriminator, and Step 5
rule 4 (promote confidence on agreement) would have nothing to act on.

The `# The risk` section above anticipated this. The measurement says it is not a risk to be managed
by careful brief-writing — it is the dominant effect, and it is what the intervention removes.

**One nuance worth keeping:** narrowing any *single* persona is cheap — each costs 0–4 substantive
clusters and demotes ~2 to single-finder. The damage is collective. That asymmetry is why disjoint
briefs read as safe when reasoned about one agent at a time, and are not in aggregate.

### The cost problem is real, and report format is NOT the lever

The 19.5k vs 9.6k per-agent output gap stands, and territorial overlap is not its cause.

A quarter of reviewer *report text* is non-finding prose — Considered But Not Flagged 20.1%, probe
requests 3.6%, positive observations 1.4% — and #dcc-3fl5 measured CBNF as yielding 7 promotions
across 18 runs, none substantive. That looks like an obvious replacement lever. **It is not, and the
arithmetic has to be done in output tokens rather than report text to see why:**

| | per ours run |
|---|---|
| written sub-agent report text | ~23,600 tokens |
| total run output | 260,800 tokens |
| report text as a share of output | **9.1%** |
| all non-finding prose | ~5,900 tokens = **2.3% of output** |
| saving if every dismissed-item list, probe request and positive note were deleted | **~$0.48 of $21.33** |

So trimming report format cannot close a 2× per-agent gap — it is worth about fifty cents a run.

**What this implies is more useful than the lever it kills.** Reviewers do not *write* twice as much
as anthropic's agents; 91% of their output never reaches the report at all. The per-agent gap is a
**reasoning** gap — thinking and tool use before the write-up — not a verbosity gap. No nib in
#dcc-hyxw currently targets that, and no measured lever for it exists.

Recorded here rather than opened as a follow-up (operator's call, 2026-07-29).

### The metric itself — fixed 2026-07-29

`compute_metrics.py::subagent_distinctness` now computes what `METHODOLOGY.md` describes: distinct
findings over *discovery* sub-agent reports, counted **within a single run**, excluding the
consolidated report's own rows and verification agents (validators, anthropic's `scorer`). Reports
publish `k/n` and mark with `*` any tool whose personas could not all be resolved, since the
verifier exclusion is then incomplete and the figure reads high — resolution is 100% for `ours`
and 77–83% elsewhere. METHODOLOGY and the per-subject glossary now also state that redundancy is
not straightforwardly waste, so the next reader meets the corroboration finding alongside the
number. All 9 subjects regenerated; the synthesis page never carried this metric and is unchanged.
