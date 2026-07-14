---
name: capture
description: Capture a follow-up idea or task as a work-item draft without interrupting current work. Use to quickly jot down something you think of mid-task so it gets tracked. Works with nibs, GitHub, Azure DevOps, or a Markdown fallback.
argument-hint: "[parent:<id>] <description>"
---

# Capture a follow-up task

You have been invoked as the `capture` skill. The user's arguments are: $ARGUMENTS

The user wants to quickly capture a thought, idea, or follow-up task without interrupting
their current work. **Keep the interaction minimal** — every question you ask is an
interruption to something else they were doing. Prefer a sensible default over a prompt.

## Captured items are drafts

A captured item is a short note with **everything else inferred by you**. Nobody has
confirmed its scope, its acceptance criteria, or that it should be built at all. So it is
created with contract status **`draft`**, never `todo`.

This is load-bearing, not cosmetic: `draft` is what keeps unrefined work out of
`next-ready`, and therefore out of `/decaf-build:auto-deliver` and
`/decaf-build:batch-dev --ready`. An item you guessed the details of must not get built
from those guesses. Promoting a draft to `todo` is a deliberate human step.

Create the item through the **`create` operation** in @../../conventions/work-items.md —
never a backend directly. That file defines `draft` for each backend and how the tag name
is chosen; read it before creating anything.

## Detect the tracker

Follow the detection order in `work-items.md` (GitHub → Azure DevOps → nibs → Markdown).

Two deviations from the contract's default gating, because this skill is
minimal-interruption by design:

- **Do not confirm the tracker when exactly one is detected.** Use it silently. (The
  contract's "confirm before proceeding" exists for skills that create many items at once;
  capture creates exactly one, and the confirmation line names the tracker anyway.)
- **If several are detected, or none, ask** — a one-line pick. This is the only case where
  guessing is worse than asking, since a note filed into the wrong tracker is lost.

The contract's rule for **collaborative systems still applies**: on GitHub and Azure
DevOps, show the drafted title + body and get an OK before creating, because those are
visible to other people. On nibs and Markdown, create directly and show the result.

## Parse arguments

Check if the arguments start with an explicit parent reference:

- `parent:<id>` — explicit parent work item (e.g., `parent:proj-a1b2`, `parent:#42`)

Strip any parent reference from the remaining text — the rest is the note description.

## Find the parent

### If an explicit parent was given

Verify it exists via the contract's `read` op. If it doesn't, tell the user and stop.

### If no explicit parent was given

Determine the best parent from context:

1. **Check for in-progress items** — these represent active work streams. Use the
   backend's `in-progress` mapping from the contract's status table (nibs:
   `nibs list --json -s in-progress`; GitHub: `status:in-progress` label; ado: `Active`).
2. **Select the parent using your judgment**:
   - If exactly one in-progress item exists, use it
   - If several, pick the one most relevant to the note's topic from conversation context
   - If none, look for a `todo` feature or epic matching the note's topic
   - If nothing suitable, create without a parent — an unparented draft is fine, and
     better than interrupting to ask

## Create the item

Formulate a concise, descriptive title from the user's note text. The body should include:

- The idea or follow-up described by the user, expanded slightly if terse
- A `## Context` section noting what was being discussed (branch, active work, topic from
  conversation) to preserve the *why* behind the note — this is the part that decays
  fastest, and the whole reason to capture rather than remember

Do **not** invent an `## Acceptance` section. Acceptance criteria on a draft would be
guesses wearing the costume of a decision; they get written when the draft is refined.

Then call the contract's `create` op with `type` = task (or bug/feature if clearly one),
`status` = `draft`, and the parent if found.

### nibs specifics

`-d`/`--body` accepts **only** `-` (stdin) or `@FILE` — inline text is rejected. Pipe the
body in:

```bash
nibs new "<title>" -t task -s draft [--parent <parent-id>] -d - <<'BODY'
<body text>
BODY
```

If a hook or quoting issue blocks the heredoc, write the body to a scratch file and pass
`-d @<path>` instead.

## Confirm

Keep the confirmation brief — the user does not want to be interrupted:

**With parent:** `Captured <id> (draft): <title> — under <parent-id>`

**Without parent:** `Captured <id> (draft): <title>`

If this is the first draft in a project that had no draft label/tag convention and you
created one (e.g. `status:draft` on GitHub), add: `Created the <name> label.`

Do not explain the draft status every time — it's the documented default and the
confirmation already says `(draft)`. Add `Refine it to todo before it gets picked up.`
**only** when the user's note implies they expect it built soon, or they ask why it wasn't.
