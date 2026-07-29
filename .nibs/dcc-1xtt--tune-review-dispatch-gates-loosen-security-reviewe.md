---
# dcc-1xtt
version: 1
title: 'Tune review dispatch gates: loosen security-reviewer, gate stack reviewers on idiom surface'
status: todo
type: feature
priority: normal
estimate: m
tags:
    - code-review
created_at: 2026-07-28T20:41:05Z
updated_at: 2026-07-29T11:24:12Z
parent: dcc-hyxw
order: as
---

# Why

The per-persona analysis (`analysis/scripts/roster_yield.py`) points in two directions at once,
and both are gate problems rather than persona problems:

- **`security-reviewer` is starved.** Best ratio in the roster — 5,416 tokens per substantive
  cluster, against a roster median around 20k — yet dispatched in only **3 of 18 runs**. Its
  gate is filtering out the cheapest good findings available.
- **`go-reviewer` is noisy.** 50% signal — over half its reports are trivia or false positives,
  worst in the roster by 20 points. Stack reviewers hard-gate on **file presence**, so they fire
  on any diff containing their language whether or not there is idiom risk to review.

Neither warrants removal: #dcc-e0wj's corrected analysis found no dead weight, and `go-reviewer`
still participates in 6 substantive clusters.

# What to change

In `decaf-quality/skills/code-review/SKILL.md` Step 2b:

1. **Widen `security-reviewer`'s gate.** It already says to lean toward spawning when unsure;
   the measured 3/18 dispatch rate says that is not happening. Make the trigger conditions
   concrete enough to fire reliably.
2. **Re-gate the stack reviewers on idiom surface, not file presence.** `go-reviewer` should
   fire on goroutines, channels, `defer`, `context`, or slice aliasing in the diff — not on the
   mere presence of `.go` files. Same shape for `dotnet` (async/disposal/EF/LINQ), `typescript`
   (promises/type escapes/coercion), `cpp`, `rust`. This is a **hard gate becoming a judgement
   gate**, so update the Step 2b table and the agents' own `## Dispatch Gate` sections together —
   they are required to stay in sync.

# Risk

Low, and independently testable per gate. Widening security costs more, not less — the case is
yield per token, not saving.

Watch the `mid`/`max` interaction: `max` opens judgement gates but not hard ones, so converting
a stack reviewer's hard gate to a judgement gate changes what `max` dispatches. Confirm that is
intended before landing.

# Acceptance

- [ ] [run] `rg -n "Dispatch Gate" -A8 decaf-quality/agents/go-reviewer.md` — expect: the gate
      names idiom surface rather than file presence
- [ ] [run] `rg -n "go-reviewer|security-reviewer" decaf-quality/skills/code-review/SKILL.md` —
      expect: the Step 2b table matches the agents' own gate text
- [ ] [manual] Re-measured dispatch rates on the benchmark subjects: `security-reviewer` above
      3/18, `go-reviewer` firing only where its idioms appear, with the signal share recorded
      against the 50% baseline. `[manual]` because "fires in the right places" is a judgement
      against each diff, not a threshold.

# Notes

Reasoning and measured basis: #dcc-e0wj → `# Candidate interventions` → item 4. Can share a
benchmark re-run with #dcc-c2uc.
