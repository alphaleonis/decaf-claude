---
# dcc-1xtt
version: 1
title: 'Tune review dispatch gates: loosen security-reviewer, gate stack reviewers on idiom surface'
status: in-progress
type: feature
priority: normal
estimate: m
tags:
    - code-review
created_at: 2026-07-28T20:41:05Z
updated_at: 2026-07-29T12:20:08Z
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

- [x] [run] `rg -n "Dispatch Gate" -A8 decaf-quality/agents/go-reviewer.md` — expect: the gate
      names idiom surface rather than file presence
- [x] [run] `rg -n "go-reviewer|security-reviewer" decaf-quality/skills/code-review/SKILL.md` —
      expect: the Step 2b table matches the agents' own gate text
- [ ] [manual] Re-measured dispatch rates on the benchmark subjects: `security-reviewer` above
      3/18, `go-reviewer` firing only where its idioms appear, with the signal share recorded
      against the 50% baseline. `[manual]` because "fires in the right places" is a judgement
      against each diff, not a threshold.

# Notes

Reasoning and measured basis: #dcc-e0wj → `# Candidate interventions` → item 4. Can share a
benchmark re-run with #dcc-c2uc.

## Implementation (done) — dispatch rates still unmeasured
## Implementation (done) — dispatch rates still unmeasured

### The `max` interaction the Risk section flagged — resolved by not converting the gate

A plain hard→judgment conversion would let `max` spawn `go-reviewer` on a Rust project, which
Step 2b explicitly forbids. So the stack reviewers now carry **two gates in order**, rather than
one converted gate:

1. **Hard gate (all modes, `max` included)** — does the changeset contain this language? Absolute,
   unchanged. `max` still cannot spawn a Go persona on a Rust diff.
2. **Judgment gate (`mid`/`high`; `max` opens it)** — does a diff *in that language* have idiom
   surface worth a specialist?

**`max` behavior is therefore unchanged**: any diff containing the language still gets its stack
reviewer. Only `mid`/`high` narrow, which is where the 50%-signal problem was measured. Step 2b
carries a paragraph explaining why the two halves must not be collapsed in either direction.

Idiom surface per language, each matched to that agent's own In-Scope categories:

| agent | fires on |
|---|---|
| `go` | goroutines, channels/`select`, `defer`, `context`, slice/map aliasing, typed-nil interfaces, shared state |
| `dotnet` | async/`Task`, disposal, EF Core, deferred LINQ, nullable annotations, threading |
| `typescript` | promises, type escape hatches, coercion, unvalidated boundary data, event-loop blocking, shared mutable state |
| `cpp` | lifetime/ownership, RAII, UB constructs, exception safety, concurrency |
| `rust` | `unsafe`, panic paths, async hazards, lock discipline, ownership changes, error-context erasure |

### `security-reviewer` — made concrete, and made deterministic

The gate is now nine observable diff facts (handler/route/middleware; parsing across a
process/user/network boundary; an identity or permission check *or its absence on a new path*;
crypto/randomness; secrets/config; path building from non-constant input; privilege or subprocess
boundaries; network client behavior; dependency manifests), with an explicit instruction to spawn
on the first one you can point at.

Two additions beyond "make it concrete", both from what the archived runs actually show:

- **Determinism.** It fired on subject 5 repeat 1 but *not* repeat 2 — same diff, opposite answer.
  The gate now says to decide the same way twice and work the list rather than classify the change.
- **Don't require the change to look adversarial.** A refactor that moves parsing, or a timeout
  added to a network client, is in scope. The old phrasing invited "is this security work?", which
  is the wrong question and is the likeliest cause of 3/18.

### Sanity check on the narrowing (proxy, not a measurement)

Grepping the nine committed subject diffs for the idiom triggers: **both Go subjects retain them** —
subject 7 has `defer` (3 hits) and `context.` (3), subject 9 has all of them (43 `context.`, 13
`defer`, 6 `chan`, 3 `go func`). Subject 7's primary bug *is* a `defer` misuse, so the narrower gate
would not have cost either Go bug-catch.

A keyword grep for the security triggers hits 5 of 9 subjects against today's 2. **Do not read that
as a predicted dispatch rate** — the same grep flags subject 4 on the word "token", which there is a
*lexer* token stream, not auth. That misfire is precisely why the gate text describes behavior
rather than listing keywords, and why this stays a proxy.

### What is NOT verified

The `[manual]` criterion needs re-measured dispatch rates on a re-run — operator-gated spend, not
started. Unknown until then: whether `security-reviewer` actually clears 3/18 under the new text,
whether `go-reviewer`'s 50% signal share improves, and whether the stack narrowing costs any
finding on a diff whose idiom surface is subtler than the trigger list.

Shares a re-run sweep with **#dcc-c2uc** — both should be measured in one pass.

### Incidental

The six reworded agent `description:` frontmatter lines initially contained a `": "` sequence, which
is invalid in a YAML plain scalar and broke the frontmatter in all six files. Caught and fixed by
parsing every agent's frontmatter; all 23 now load. Worth a guard if agent descriptions keep
growing — none exists today.
