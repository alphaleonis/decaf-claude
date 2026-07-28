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
updated_at: 2026-07-28T20:42:40Z
parent: dcc-hyxw
order: as
---

# Why

**~77% of sub-agent findings restate a sibling's**, and ours emits ~19.5k output tokens per agent
against anthropic's 13.7k — the field's outlier low. Ours runs roughly **twice** anthropic's
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
