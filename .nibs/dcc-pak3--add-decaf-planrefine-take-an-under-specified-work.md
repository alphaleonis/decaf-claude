---
# dcc-pak3
version: 1
title: Add /decaf-plan:refine — take an under-specified work item to actionable
status: completed
type: feature
created_at: 2026-07-14T14:47:21Z
updated_at: 2026-07-14T14:50:56Z
order: zw
---

Add a `/decaf-plan:refine` skill that takes an under-specified work item and, through a
short interview grounded in code evidence, leaves it specified well enough to act on.

This is the missing exit for the `draft` state added in dcc-3kgg: nothing currently
promotes `draft` to `todo`, and the README says "refine it to todo" without saying how.

## Context

Designed in conversation on 2026-07-14, immediately after dcc-3kgg shipped the `draft`
status. Two design corrections happened during that discussion and both are load-bearing:

1. **Refine is interactive.** An early proposal had it promoting drafts autonomously.
   Rejected: `capture` infers the item from a one-line note, so autonomously inferring its
   acceptance criteria too would mean `auto-deliver` verifies a guess against itself —
   acceptance criteria are the ground truth (`acceptance-criteria.md:5`) and must enter
   from outside the inference chain. The human confirming IS the mechanism. Autonomous
   implementation happens *after* refine, not during it.

2. **Do not gate promotion on `[run]` acceptance.** An early proposal blocked `draft →
   todo` unless acceptance was machine-checkable. Rejected: some work is genuinely not
   auto-verifiable (visual, external service, judgement), and gating would trap it in
   `draft` forever. "Specified as well as it can be" is a finished outcome even when it
   isn't auto-deliverable. `[run]`/`[manual]` already carries that signal.

## Shape

Not draft-only — applies to any **open** work item that is under-specified. Refining a
`completed` item should ask whether to reopen or file a follow-up, not silently reopen.

Triage, acting on what it finds:

| Discovers | Hand to | Item becomes |
|---|---|---|
| Scope too large for one item | `draft-spec` then `draft-plan` | epic/milestone, or scrapped for the plan |
| Real design tension, not missing detail | `grill-me` | stays `draft` until design settles |
| Just under-specified (common case) | nobody — refine handles it | `todo` + `## Acceptance` |
| Obsolete / already done / contradicted | — | `scrap`, with evidence |

## The rule that matters most

**Ask nothing the code could have answered.** Refine reads first and arrives at the
interview with a *proposed* work item, then asks the user to correct it. This is what
separates it from `grill-me` and `draft-spec`, which interview from near-blank. For a
simple task it should be one question ("RetryPolicy in five sibling paths, three retries,
exponential; same here, done = this test passes. Right?"), not twenty.

This is also the rule most likely to erode, because interviewing from blank is easier to
write than interviewing from a proposal.

## Burden of proof on `[manual]`

Not a gate — a reason. `[manual]` must state *why* there is no runnable form ("visual match
against a mock"), not merely assert it. The failure mode is asymmetric and invisible:
writing `[manual] the retry logic works correctly` is cheap, working out
`dotnet test --filter Category=Upload.Retry — expect: exit 0` is work, so an LLM drifts
toward `[manual]` for reasons of effort rather than truth — and the item looks
well-specified either way. `acceptance-criteria.md` rule 1 (prefer `[run]`) and rule 2
(tag honestly) are the standard; the stated reason is what makes rule 2 auditable.

## Open questions

- Overlap with `breakdown-phase` is real. The distinction: breakdown-phase decomposes a
  decision a human already made (it has a spec behind it); refine has to establish whether
  there is a decision at all. If that distinction does not survive implementation, refine
  is breakdown-phase with a different entry point and should not be a twelfth plan skill.
- Where does refine sit relative to `resolve-*` skills? It is analyze+act on one item,
  which is closer to the resolve convention than to the analyze convention.
- Should it accept several ids / a filter, or strictly one item at a time?

## Done means

- [x] `decaf-plan/skills/refine/SKILL.md` exists and follows the contract in `work-items.md`
- [x] Reads `@../../conventions/acceptance-criteria.md` for the `## Acceptance` format
- [x] Documented in root README.md, decaf-plan/README.md, CLAUDE.md
- [x] The `draft` exit is documented where dcc-3kgg left it dangling (README "refine it to todo")

## Summary

Implemented as designed in conversation. `decaf-plan/skills/refine/SKILL.md` created;
wired into root README, decaf-plan/README, CLAUDE.md, and the two dangling
"refine it to todo" pointers (work-items.md, capture/SKILL.md).

Both design corrections from the discussion are recorded IN the skill with their
reasoning, not just applied — they are the kind of thing that erodes silently:
the interview-from-a-proposal rule, and the refusal to gate promotion on `[run]`
acceptance. Added a third: an explicit "no --unattended mode" section, because
every sibling planning skill has one and its absence here would otherwise read as
an oversight rather than the whole point.

Verified: both `@../../conventions/*` refs are plugin-local (resolve inside
decaf-plan/, matching breakdown-phase), so they survive the install-time copy.

Open questions from the draft, still open and worth revisiting once it has been
used a few times: whether the breakdown-phase distinction survives contact with
real use, and whether refine should accept several ids rather than one.
