---
# dcc-9q01
version: 1
title: Parameterize code-review on four axes (roster / models / evidence / reach) with named presets
status: todo
type: epic
priority: high
estimate: l
tags:
    - code-review
    - design
created_at: 2026-07-29T16:29:22Z
updated_at: 2026-07-29T18:29:03Z
order: zzzs
---

# Why

The epic asked a product question — *"a short trustworthy list, or exhaustive coverage with
tiers?"* (#dcc-e0wj workstream 3) — as if it needed one permanent answer. It does not. Both are
wanted, at different times, by the same operator.

Three things say so:

1. **The tiering machinery already exists.** The report separates Findings / Minor Findings /
   Pre-existing Issues / Testing Gaps / Residual Risks, and `auto-code-review` already refuses to
   triage the last three. What is missing is control over whether reviewers *generate* them.
2. **Autonomous loops want the opposite of interactive review.** In `auto-deliver` / `batch-dev`
   runs, pre-existing defects are worth surfacing precisely because nothing else will find them —
   while the fixer must not drown in speculation. That combination is inexpressible today.
3. **The tool we benchmarked against does not separate these either, and that is its weakness,
   not its strength.** See "What anthropic actually does" below.

# The four axes

| axis | values | controls | today |
|---|---|---|---|
| `roster` | integer | how many personas review | exists — the `N` in `mid4` (Step 2b.5) |
| `models` | low / norm / high | model policy **per role**; mechanical work stays cheap at every level | exists — Step 2d, but welded to the mode keyword |
| `evidence` | strong / norm / any | how well-evidenced a finding must be to survive the pre-consolidation screen | **new** |
| `reach` | narrow / norm / wide | what counts as reportable — changed lines only → surrounding code → pre-existing, coverage gaps, docs | **new** |

All four point the same way: **less output ← `small`/`low`/`strong`/`narrow` … `large`/`high`/`any`/`wide` → more output.**

## `evidence` and `reach` are the substantive split

`evidence` asks *"is this real?"*. `reach` asks *"does this count?"*. They are independent, and
conflating them is the single clearest defect in the design we were copying.

The case that proves they must be separate: an autonomous fix loop wants `reach=wide` (pre-existing
bugs count — nothing else will find them) with `evidence=strong` (do not hand the fixer hunches).
No single dial expresses that.

# The three presets

| preset | roster | models | evidence | reach | the product |
|---|---|---|---|---|---|
| **`bugs`** | small | low | strong | narrow | high-confidence defects in changed lines only |
| **`review`** *(default)* | gate-matched | norm | norm | norm | the above plus actionable minor findings |
| **`audit`** | all matched | high | any | wide | everything, tiered |

The names state the deliverable, which is what actually differs — and that quietly answers
workstream 3 by making the product selectable per run rather than fixed forever.

**The axis values in this table are a first guess.** Nobody knows what `roster: small` should be.
Presets are measured; the cross-product is not (see Measurement).

Presets set all four axes; any axis stays individually overridable for tuning.

# Architectural constraint: cluster BEFORE you screen

A pre-consolidation screen runs before consolidation — which is where corroboration is computed.
That matters because agreement is our best discriminator (#dcc-gcob, measured):

| tier | mean finders | 2+ finders |
|---|---|---|
| substantive | **2.80** | **72%** |
| valid-minor | 1.64 | 38% |
| trivia / FP | 1.32 | 16% |

Score raw findings one at a time and that signal is not available yet. Anthropic can afford
per-issue scoring because its five agents are deliberately disjoint and rarely corroborate — it has
no agreement signal to lose. We do.

**Therefore: dedupe/cluster first, then screen clusters, with finder-count as an input to the
screen.** Clustering is matching, not reasoning — it does not need a frontier model. This keeps the
discriminator, still spares the orchestrator from deep reasoning over findings that die at the
screen, and is what lets the screen absorb the validation wave (the prize #dcc-xewu was after).

# What anthropic actually does — read before designing the screen

From `~/.claude/plugins/cache/claude-plugins-official/code-review/unknown/commands/code-review.md`
(read 2026-07-29). Two claims repeated in #dcc-xewu and #dcc-05uw are **wrong** and should not be
built on:

- **It is not a discrete anchor ladder.** The skill says *"score each issue on a scale from 0-100"*
  and supplies five anchor **descriptions** (0/25/50/75/100) as a rubric — not five permitted
  values. The 80 cutoff is therefore an ordinary threshold, not "only 100 survives". Observed
  output confirms scorers interpolate: across its runs, scores of **80 (×1), 85 (×2), 100 (×4)** —
  3 of 7 off-ladder. Ours *is* a strict ladder ("never intermediate values"), and that design was
  projected onto theirs.
- **Its precision is partly scope, not judgment.** The skill instructs reviewers to treat as false
  positives: *"General code quality issues (eg. lack of test coverage, general security issues,
  poor documentation)"*, *"Real issues, but on lines that the user did not modify"*, pre-existing
  issues, and anything a linter or typechecker would catch. It is a bug-and-convention checker
  scoped to changed lines. Its 56% substantive share against ours' 30% is partly a narrower
  denominator — it never emits the categories that dilute ours.

Shape, for reference: Haiku eligibility check → Haiku CLAUDE.md-path finder → Haiku summarizer →
**5 parallel Sonnet reviewers with disjoint evidence channels** (CLAUDE.md compliance; deliberately
shallow bug scan; git blame/history; prior PRs touching these files; code comments) → **one Haiku
scorer per issue** → filter <80.

# What this supersedes or changes

- **#dcc-e0wj workstream 3** — the product question is answered by making the product a preset.
- **#dcc-xewu** — becomes the implementation of `evidence`, not a permanent commitment to a short
  list. Its hard-filter framing and its "only 100 survives" basis are both superseded. Its blocker
  ("resolve workstream 3 first") is discharged by this nib.
- **#dcc-2a8i** — gains its actual purpose: how `roster` chooses *which* personas to cut. That is
  now one axis of four rather than a loose end.
- **`low`/`mid`/`high`/`max`** — presets should replace this ladder (see Open questions). The
  existing ladder conflates `roster` with `models`, which is the confusion the axes remove.
- **#dcc-c2uc and #dcc-1xtt** — already landed and unverified. Both get re-measured under whatever
  the new default is, so the sweep reserved for them is superseded by this work.

# Open questions — decide before building

- [ ] Do presets **replace** `low`/`mid`/`high`/`max`, or coexist? (Recommend replace. `max` has no
      natural home among the three — it becomes `audit` with everything on the session model.)
- [ ] Does `reach=wide` mean reviewers **generate** more, or that the report stops suppressing what
      they already generate? Cost differs enormously between those.
- [ ] Does the `evidence` screen **merge with** the existing post-consolidation confidence gate
      (Step 5.6), or sit in front of it? Two separately-named gates at different pipeline stages is
      a bug factory — see Naming.
- [ ] What are the actual `roster` sizes per preset?
- [ ] Should a git-history channel be added (scoped to changed files)? Subject 4 is the only subject
      ours missed in **both** repeats and anthropic caught it from the revert commit — the one
      measured recall gap. Constraints in #dcc-e0wj workstream 4: scope it to the modified files or
      ours loses the best repo-sensitivity in the field (partial r 0.403), and verify retrieved
      claims against merged code — that same channel produced anthropic's worst false positive.

# Naming — decided, with what was rejected

Recording the rejects so they are not re-proposed.

| chosen | rejected | why |
|---|---|---|
| `evidence` | `bar` | unintuitive as a noun |
| | `severity` | collides with finding severity (Critical/High/…). Every agent file states *"Severity describes impact only. Rate certainty separately"* — this axis is the certainty one |
| | `strictness`, `level` | direction inversion: `low` would mean *more* work, opposite to the other three axes |
| | `gate` | fourth meaning of an already-overloaded word — `## Dispatch Gate`, hard/judgment gates, confidence gate |
| | `filter` | workable; `lax` reads pejorative for a mode you legitimately want in autonomous loops |
| `reach` | `scope` | taken — the existing `[path]` argument means *which files* |
| `models` | `tier` | implies one model; the value is a **policy** across roles, and mechanical work stays cheap even at `high` |

# Acceptance

- [ ] [manual] Terminology recorded and used consistently — the four axis names and three preset
      names appear in `code-review/SKILL.md`, `decaf-quality/README.md`, and any nib that references
      a mode. `[manual]` because consistency of prose is a reading, not a check
- [ ] [run] `rg -n "roster|models|evidence|reach" decaf-quality/skills/code-review/SKILL.md` —
      expect: all four axes defined in one place with their values and defaults
- [ ] [run] `rg -n "bugs|review|audit" decaf-quality/skills/code-review/SKILL.md` — expect: the
      three presets defined as axis settings, each stating its deliverable
- [ ] [run] `rg -n "cluster" decaf-quality/skills/code-review/SKILL.md` — expect: the screen runs
      after clustering and receives finder-count, per the architectural constraint above
- [ ] [manual] The open questions above are answered in this nib before implementation starts
- [ ] [manual] Measured: each preset run on the benchmark subjects, with bug-catch, substantive
      share, calibration and cost recorded per preset. Cross-product combinations explicitly NOT
      measured — and that limit stated wherever the results are published

# Measurement

**This invalidates every committed `ours` figure.** The benchmark's `ours` column is one
configuration (`mid --report`); after this it is a configuration *space*. Re-runs are per preset,
`ours`-only (other tools are unaffected), so ~9-18 cells per preset.

Measure the presets. Do **not** attempt the cross-product — four axes at three-ish values each is
unmeasurable at ~$160-320 per configuration, and the epic already has one metric
(`subagent_distinctness`) that was misread for want of anyone checking what it counted. Feel for the
off-preset combinations comes from real use, not from the benchmark.

# Notes

Terminology settled with the operator 2026-07-29. Supersedes the sweep ordering recorded in
#dcc-hyxw `# Sequencing`, which reserved the next benchmark spend for #dcc-c2uc + #dcc-1xtt.
