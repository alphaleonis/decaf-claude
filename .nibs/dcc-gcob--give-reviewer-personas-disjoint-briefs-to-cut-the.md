---
# dcc-gcob
version: 1
title: Give reviewer personas disjoint briefs to cut the 77% restatement rate
status: todo
type: feature
priority: normal
estimate: l
tags:
    - code-review
created_at: 2026-07-28T20:41:05Z
updated_at: 2026-07-29T11:04:12Z
parent: dcc-hyxw
order: as
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
(0.62 vs 0.88); stripping overlap could make it worse even while output drops.

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
