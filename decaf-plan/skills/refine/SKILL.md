---
name: refine
description: Take an under-specified work item and make it actionable — resolve its open questions through a short interview grounded in the code, and give it acceptance criteria. Use on a captured draft, or any item too vague to start on.
argument-hint: "[work item id] [--scrap-ok]"
---

# Refine a work item

You have been invoked as the `refine` skill. The user's arguments are: $ARGUMENTS

Take one under-specified work item and leave it specified well enough to act on. Refine
**decides and documents**; it does not implement. Its output is a better work item.

This is the exit for the `draft` status: `capture` files an item from a one-line note with
everything inferred, and refine is where a human confirms what it should actually be. But
it is **not draft-only** — any open item too vague to start on is fair game.

## What refine is for

| Situation | Refine? |
|---|---|
| A captured `draft` — a note with the rest inferred | **Yes** — the main case |
| A `todo` someone hand-wrote that nobody can start on | **Yes** |
| An `in-progress` item that turned out to be vaguer than it looked | **Yes** |
| A `completed` item | **No** — ask whether to reopen or file a follow-up (below) |
| A phase from a plan that needs splitting into features | **No** — that's `/decaf-plan:breakdown-phase` |
| A decision that needs stress-testing | **No** — that's `/decaf-plan:grill-me` |

The line against `breakdown-phase`: **breakdown-phase decomposes a decision a human already
made** — it has a spec behind it and the question is only how to slice it. **Refine has to
establish whether there is a decision at all.** If you find yourself splitting a
well-specified item into parts, you're in the wrong skill.

## The rule that governs everything below

> **Ask nothing the code could have answered.**

Read first. Arrive at the interview with a **proposed** work item and ask the user to
correct it — never interview from a blank page. That is the whole ergonomic difference
between refine and `draft-spec`/`grill-me`, and it is what makes refine proportionate for
a small task: one question, not twenty.

Every question you ask is a question the user has to context-switch to answer. Spend your
own effort first so theirs is cheap.

## Process

### 1. Identify the item

The user may give a work item ID, or refer to something in conversation context. If it's
ambiguous, ask — but only if you genuinely cannot tell.

Read it via the `read` op in @../../conventions/work-items.md.

**If the item is `completed`/closed:** stop and ask whether they want to reopen it or file
a follow-up. Do not silently reopen — a closed item may have shipped, and re-specifying it
under the same id rewrites history someone else may be relying on.

### 2. Gather evidence

This is most of the work, and it happens **before** you ask anything. Establish from the
code, not from the user:

- **Is this already done?** The note may predate work that landed since.
- **Where does it land?** The files, module, or boundary this touches.
- **What pattern already exists?** Sibling code doing the same kind of thing, the
  established convention, the helper that already exists. Most "how should this work?"
  questions are answered by "the same way as the five places next to it."
- **What would "done" look like, observably?** An existing test suite, a command, an
  endpoint, a check — the raw material for `[run]` acceptance.
- **Does it conflict with anything?** A decision, an RFC, an in-flight change.
- **How big is it, really?** Against actual code, not the sentence.

Also read the item's `## Context` if `capture` wrote one — it records what was being
discussed when the note was jotted, which is usually the fastest route to intent.

### 3. Triage

What you found decides which of these you're in. **Act on it — don't just report it.**

| You found | Do this | Item ends up |
|---|---|---|
| **Just under-specified** — the common case | Continue to step 4 | `todo`, with `## Acceptance` |
| **Too large for one item** — it's several features, or needs phasing | Say so, and offer to hand to `/decaf-plan:draft-spec` (then `draft-plan`) | Epic/milestone, or scrapped in favor of the plan it spawns |
| **Real design tension** — not missing detail but a genuine fork with consequences | Say so, and offer to hand to `/decaf-plan:grill-me` | Stays `draft` until the design settles |
| **Obsolete / already done / contradicted by the code** | Show the evidence, propose scrapping | `scrap` (only with the user's OK, or if `--scrap-ok`) |

Be honest about which one you're in. Forcing a too-large item through step 4 produces a
work item that looks actionable and isn't — the worst outcome this skill can produce,
because it launders a guess into something `auto-deliver` will pick up.

### 4. Draft the refined item

Write the item you think it should be. Against the code you just read:

- **Title** — concrete and specific.
- **Description** — what to build and why, in terms of end-to-end behavior. Reference the
  patterns and files you found. Preserve the original `## Context`.
- **`## Acceptance`** — the done-check, per @../../conventions/acceptance-criteria.md.
- **Open questions** — the ones the code genuinely could not answer. These become your
  interview, and there should be **few**.

### 5. Interview from the proposal

Show the drafted item, then ask **only** the open questions from step 4. Prefer a concrete
proposal the user can confirm or correct over an open question they have to compose an
answer to:

> Good: "`RetryPolicy` is used in five sibling paths — three attempts, exponential backoff.
> Same here? And done = `dotnet test --filter Category=Upload.Retry` passes."
>
> Bad: "How should retry behave on the upload path?"

Iterate until the user is satisfied. If an answer invalidates your evidence, go back to
step 2 rather than patching the draft — a proposal built on a wrong assumption doesn't get
better by amendment.

### 6. Write it back

Update the item **in place** via the contract's ops (`work-items.md`) — refine improves an
existing item, it does not create a replacement and it does not spawn children (that's
`breakdown-phase`). Set the status to `todo` via `set-status` unless triage sent you
elsewhere.

If refine surfaced follow-up work that is genuinely separate, file it with
`create-followup` — as a `draft`, since it's a new note with the rest inferred.

### 7. Report

State what changed, the verdict from triage, and — plainly — **whether this can be built
autonomously**:

- If `## Acceptance` is all or mostly `[run]`: it can. `/decaf-build:auto-deliver` or
  `/decaf-build:batch-dev` can take it from here.
- If it's substantially `[manual]`: it can't be *verified* autonomously. Say so in one
  line. This is not a failure — see below — but the user should know before handing it to
  a loop that will build it and then be unable to check its own work.

## Acceptance criteria: the standard

Read @../../conventions/acceptance-criteria.md — the `[run]`/`[manual]` format, and rules
1 (prefer `[run]`) and 2 (tag honestly) are the standard refine is held to.

**`[manual]` is allowed.** Some work genuinely cannot be machine-checked — visual and UX
work, external services, judgement calls. That is the nature of the task, not a defect in
the refinement. An item whose acceptance is honest prose is **finished** as far as refine
is concerned: it is ready for a human to act on, and refusing to promote it would trap
legitimate work in `draft` forever. Do not gate promotion on runnable acceptance.

**`[manual]` needs a reason.** State *why* there is no runnable form — "visual match
against the agreed mock", "depends on the vendor's sandbox" — not a bare assertion.

The reason is required because **the failure mode here is asymmetric and invisible**.
Writing `[manual] the retry logic works correctly` is cheap; working out that the runnable
form is `dotnet test --filter Category=Upload.Retry — expect: exit 0` is work. So the drift
is always toward `[manual]`, for reasons of effort rather than truth — and the item looks
well-specified either way. Nobody notices until a loop builds it and can't check anything.
Making the reason explicit is what keeps "prefer `[run]`" honest.

If you cannot state a reason, you have not tried hard enough to find the runnable form.

## Flags

- `--scrap-ok` — if triage concludes the item is obsolete or already done, scrap it with
  the evidence rather than asking. Everything else still asks.

## There is no `--unattended` mode, deliberately

Sibling planning skills (`breakdown-phase`, `close-out`) take `--unattended` so
`auto-deliver` can drive them. **Refine must not.** Do not add one.

The reason is the point of the skill. `capture` infers a work item from a one-line note.
If refine then *inferred* its acceptance criteria too, `auto-deliver` would verify a guess
against itself: acceptance criteria are the ground truth an autonomous run checks against
(`acceptance-criteria.md`), so they have to enter from outside the inference chain. The
human answering step 5 **is** that entry point — it is the mechanism, not a gate in front
of it. Remove the human and refine doesn't become automatic; it becomes a machine that
writes its own exam.

`auto-deliver` never needs this anyway: `next-ready` never returns a `draft`
(`work-items.md`), so the loop never encounters an unrefined item. Refinement happens
before the loop, on purpose. Autonomous implementation happens *after* refine, never
during it.
