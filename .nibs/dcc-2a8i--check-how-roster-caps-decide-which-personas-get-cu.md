---
# dcc-2a8i
version: 1
title: Check how roster caps decide which personas get cut, and whether that ranking is optimal
status: todo
type: task
priority: normal
created_at: 2026-07-28T23:33:37Z
updated_at: 2026-07-29T16:33:26Z
parent: dcc-hyxw
order: az
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

### 2. "Categorical coverage the generalists cannot substitute" is not supported

That premise puts every stack reviewer in the top tier on the argument that dropping one "leaves an
entire dimension unreviewed". The stack reviewers span **0.00 to 0.83**, and `dotnet-reviewer`'s
0.00 means literally everything it found was also found by two or more siblings. The generalists
do substitute, at least on these subjects. `data-migration-reviewer` never fired at all.

Ranking by *category* is the error; category is a poor predictor of contribution.

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

## What to change

Replace the hand-written category ranking in Step 2b.5 with a **measured, preset-aware drop-cost
order**, refreshable from `roster_yield.py` rather than re-derived by intuition:

- **`bugs`** — rank by substantive drop cost. `adversarial` first among specialists; `consistency`
  and `knowledge` shed first (unchanged); stack reviewers ranked on their own numbers, not as a
  class.
- **`audit`** — rank by drop cost **+ minor yield**, which promotes `consistency` and `test`.
- **`review`** — between the two.

This nib is now the `roster` axis of #dcc-9q01 rather than a standalone question.

## Limits — read before acting

- **Sample sizes differ wildly.** Only `broad`, `quick`, `knowledge`, `consistency` (18 runs),
  `test` (16) and `adversarial` (13) are well sampled. `security` (3), `go` (4), `dotnet` (5),
  `typescript` (6), `rust` (2) are not. **`security-reviewer`'s 2.00 is the top of the table and
  the least trustworthy number in it** — do not promote it on this basis.
- **The dispatch gates changed after these runs.** #dcc-1xtt widened `security-reviewer`'s gate and
  narrowed the stack reviewers to idiom surface. Both change which personas are even eligible for a
  cap decision, so these frequencies will not reproduce.
- **One configuration, nine subjects.** Measured under `mid --report` only.
- The metric counts *participation*, per #dcc-e0wj workstream 2's finding that no persona is dead
  weight. It deliberately does not reward uniqueness alone — that error was already made once with
  `performance-reviewer`.

## Acceptance
## Acceptance

- [ ] [run] `rg -n "Rank the gate-matched specialists" -A12 decaf-quality/skills/code-review/SKILL.md`
      — expect: the order is stated as measured drop cost, not agent category, and names its source
- [ ] [run] `python3 competition/benchmark/analysis/scripts/roster_yield.py` — expect: exit 0; the
      per-persona figures the ranking cites are reproducible from committed data
- [ ] [manual] `adversarial-reviewer` ranks ahead of `security-reviewer` among specialists, or the
      decision to keep the current order is recorded with a reason
- [ ] [manual] The order differs by preset (`bugs` / `review` / `audit`) per #dcc-9q01, with
      `consistency-reviewer` not leading the cut under `audit`
- [ ] [manual] Under-sampled personas are handled explicitly — the ranking does not promote
      `security-reviewer` on n=3
