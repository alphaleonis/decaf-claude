---
# dcc-1ix0
version: 1
title: ours-bugs is strictly dominated by superpowers at half the cost — find out why
status: in-progress
type: task
priority: high
created_at: 2026-08-16T10:18:32Z
updated_at: 2026-08-16T13:15:06Z
parent: dcc-hyxw
order: aq
---

Measured in the v2 pilot ([[dcc-vkeh]]) — two subjects (`prometheus/prometheus#18081` library/L,
`dotnet/efcore#34127` library/M), two repeats each, blind-adjudicated twice, all cells clean. Full
data in `v2/analysis/TUNING-SIGNALS.md` and `v2/analysis/PILOT-RESULTS.md`.

## The finding

`superpowers` reports a **strict superset** of what `ours-bugs` reports, at **half the cost and half
the wall time**.

| | `ours-bugs` | `superpowers` |
|---|---|---|
| avg cost / cell | $8.56 | **$4.12** |
| avg wall / cell | ~22 min | **~12 min** |
| reported clusters (both subjects) | 7 | 45 |
| substantive share | 71% | 69% |
| real defects reported (of 16 in pool) | 5 | **9** |
| real defects *found* | 8 | 9 |
| unique real findings | 0 | 4 |

Cluster overlap, both pooled subjects:

| class | both | only `superpowers` | **only `ours-bugs`** |
|---|---|---|---|
| defect | 6 | 7 | **0** |
| risk | 0 | 2 | **0** |
| test-gap | 0 | 12 | **0** |
| docs | 0 | 8 | **0** |
| design | 1 | 7 | **0** |
| style | 0 | 2 | **0** |

**`ours-bugs` reported nothing `superpowers` did not.** And the 38 clusters `superpowers` reported
alone are **68% substantive** against 71% for the shared set — it is not buying volume by lowering
its bar. It finds six times as much, at the same quality, for half the money.

## What `superpowers` actually is

One `general-purpose` subagent on the session model, handed a prompt template
(`superpowers/skills/requesting-code-review/code-reviewer.md`) and a diff range. **No roster, no
screening step, no validation wave, no clustering, no demotion tiering.** It writes one report.

## Where decaf's money goes — the leading hypothesis

Token breakdown, same subject and repeat (efcore r2):

| | `ours-bugs` | `superpowers` |
|---|---|---|
| Opus 5 output | 86,843 tok — **$7.66** | 38,234 tok — **$3.46** |
| Haiku output | 74,960 tok — **$0.90** | — |
| turns | **44** | **6** |

**The cheap-tier reviewers cost 90 cents.** The spend is the orchestrator: 44 Opus turns against
`superpowers`' 6. The pipeline — dispatch, per-cluster screening (Step 4.95), the validation wave
(Step 5), consolidation, report assembly — is where 2.2x the Opus tokens go, and it produced 2
reported clusters on that cell against `superpowers`' 17.

So the working hypothesis is **not** that the reviewers are weak or too few. It is that decaf's
orchestration overhead exceeds what it adds at this preset's scale.

## What NOT to do

An earlier draft of this analysis recommended **raising** the `bugs` roster cap to fix detection.
That is the wrong direction: it buys recall with money, and the pilot shows the target result is
achievable for half of what the preset already spends. Any intervention here has to come out at or
below $4/cell to be interesting.

Two other rejected candidates, recorded so they are not re-proposed: lowering the `evidence` bar
(it accounts for **one** lost finding, and `ours-bugs`' precision is real — 7 reported, only 2
non-substantive, both `low`); and making the corroboration clause roster-relative (conceptually
wrong — two agents independently converging is evidence whether 4 ran or 12; one agent alone is not).

## What to investigate

1. **Where do the 44 turns go?** The cell transcripts are committed under
   `v2/runs/*__ours-bugs__shim-on__r*/`, with `cell-report.md` and the full `.decaf` report in
   `tool-artifacts/`. Attribute Opus output tokens to pipeline stage: dispatch, screen, validate,
   consolidate, assemble.
2. **Read the two implementations side by side.** `superpowers`'
   `requesting-code-review/code-reviewer.md` template against decaf's `code-review` SKILL.md steps
   2–6. What does the single-agent prompt elicit that four gated reviewers plus machinery do not?
3. **Is the machinery load-bearing at this scale?** The screen, the validator wave and consolidation
   exist to raise precision. `ours-bugs` and `superpowers` have the *same* substantive share (71% vs
   69%) — so on this evidence the machinery is not buying precision here, only cost. Check whether
   that holds for `review` and `audit`, where roster is larger and the machinery may pay for itself.
4. **Detection is nearly competitive** — 8 real defects found against 9, and `ours-bugs` found one
   (`Coalesce`, high) that `superpowers` missed entirely. The reviewers work. Confirm the loss is
   downstream of them.

## Acceptance

- [ ] Turn-level cost attribution for one `ours-bugs` cell — which stage consumes the Opus tokens
- [x] Written comparison of the two implementations, naming what the single-agent path does better —
      `v2/analysis/OURS-BUGS-VS-SUPERPOWERS.md`
- [x] A concrete proposal that lands at or below $4/cell, with the mechanism it changes —
      `v2/analysis/PROPOSAL-BUGS-SP.md` (implementation: [[dcc-1sbc]]; companion tiering change: [[dcc-dduy]])
- [ ] Re-measured on both pilot subjects against the known counterfactual: 16 real defects, of which
      this preset currently reports 5 and finds 8


---

## CORRECTION (2026-08-16): the orchestration hypothesis above is WRONG

The section "Where decaf's money goes" attributed the spend to the orchestrator, reading `meter.json`
`modelUsage` as "Opus = orchestrator, Haiku = reviewers". **That inference is invalid.** Under
`models=low` the *judgment* reviewers also inherit the session model, so the Opus total contains
reviewer subagents as well as the orchestrator. `modelUsage` aggregates the whole session and does
not separate the lanes; the transcript cannot separate them either (its per-message `usage` blocks do
not sum to the session total, so any split derived from them is unsound).

Measured properly — reviewer count taken from each cell's own report header, against that cell's cost:

| preset | reviewers | mean cost | $/reviewer |
|---|---|---|---|
| `ours-bugs` | 4 | $8.57 | ~$2.14 |
| `ours-review` | 6–9 | $16.73 | ~$2.54 |
| `ours-audit` | 9–10 | $28.23 | ~$2.80 |

Least squares over **14 cells** spanning 4–10 reviewers, three presets and three subjects:

```
cost  =  -4.19  +  3.17 × reviewers          R² = 0.948
```

**The fixed component is negative.** There is no orchestrator overhead worth naming; cost is
essentially linear in reviewer count at ~$3.17 marginal per reviewer. Cost per reviewer is flat
across the range (1.99–3.08) — if a fixed orchestration cost dominated, it would fall sharply as the
roster grows, and it does not.

### The reframed question

decaf pays **~$3.17 per reviewer**. `superpowers` pays **$4.12 for one** generalist agent — about 1.3
decaf reviewers — and that single agent reports a strict superset of what `ours-bugs`' four produce.

So this is not an orchestration-overhead problem. It is a **breadth-per-dollar** problem:

> Four narrow, individually cheaper reviewers produce strictly less than one deeper generalist
> costing about a third more than any one of them.

That points the investigation at agent design rather than pipeline mechanics:

- Does the narrow brief each decaf reviewer receives *prevent* the cross-concern connections a
  generalist makes? `superpowers`' single agent produced findings across all six classes; `ours-bugs`'
  four produced defects and one design item and nothing else.
- How much do the four duplicate each other's reading of the same diff? Four agents each paying to
  read and build the same code is four times the setup cost for one changeset.
- Is one deep pass simply better than four shallow ones at this budget — and if so, does the same
  hold at `audit`'s scale, where 10 reviewers produce the roster's best detection?

The cheapest experiment implied: run `bugs` at `roster=1` or `2` with `models=high`, landing near
$3–6/cell, and measure against the known counterfactual.
