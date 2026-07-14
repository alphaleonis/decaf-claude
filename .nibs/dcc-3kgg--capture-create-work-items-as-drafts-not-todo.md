---
# dcc-3kgg
version: 1
title: 'capture: create work items as drafts, not todo'
status: completed
type: feature
created_at: 2026-07-14T14:26:02Z
updated_at: 2026-07-14T14:31:08Z
order: zs
---

`/decaf-plan:capture` creates work items with `-s todo`, but captured items are by
nature unrefined — the user gives a short note and the skill infers the rest. The
state should reflect that, so unrefined work isn't picked up for execution.

The docs already claim this behavior (`README.md:62`, `CLAUDE.md:74` both say
"work-item draft"); the implementation doesn't do it.

## Scope

Decided with the user: do it in one pass, across the tracker contract.

- [x] `conventions/work-items.md`: add `draft` to the normalized status model
- [x] `conventions/work-items.md`: teach ADO `next-ready` to exclude draft-tagged items
- [x] `decaf-plan/skills/capture/SKILL.md`: detect tracker, use the contract's `create` op
- [x] `decaf-plan/skills/capture/SKILL.md`: create as draft
- [x] `decaf-plan/skills/capture/SKILL.md`: fix stale nibs commands (see below)
- [x] `README.md:257`: correct the claim about how captured nibs get built

## Draft mapping

| Backend | Draft representation | Native? |
|---------|---------------------|---------|
| nibs | `-s draft` | yes — `--ready` excludes it |
| ado | `State=New` + tag | no — tag only |
| github | open + `status:draft` label | no — label only |
| markdown | `[?]` | no — convention |

Tag name: detect an existing draft-ish label/tag (draft / refine / triage), fall back
to a fixed default (`Draft` on ado, `status:draft` on github).

## Why ADO needs the next-ready change

ADO `next-ready` selects "children of the plan with `System.State` in (`New`,`To Do`)
and no open Predecessor" (`work-items.md:87`). A captured item parented to an epic sits
at `State=New`, so next-ready would select it — the tag alone does nothing. It must be
excluded explicitly, or `auto-deliver` executes unrefined work.

GitHub is safe by accident: its `next-ready` only considers issues carrying a
`phase:<n>` label, which captured items don't have. nibs is safe natively.

## Stale commands (found while reading; fixed in the same pass)

`nibs new --help` states `-d/--body` accepts only `-` (stdin) or `@FILE`, "no inline
text". `SKILL.md:71,77` pass inline `-d "<description>"` — rejected as written, so the
skill appears broken today, independent of the state change. Also `nibs create` and
`nibs show` are working aliases, but `new`/`get` are the documented grammar.

## Consequence to document

`draft` is excluded from `--ready`, so captured items will NOT be picked up by
`batch-dev --ready` (`batch-dev/SKILL.md:37`) or `auto-deliver`. That is the intent —
refine to `todo` first — but `README.md:257` currently promises the opposite.

## Summary

Done in one pass, across the tracker contract.

`conventions/work-items.md` — added `draft` to the normalized status model with a
per-backend mapping, and a section explaining why `next-ready` must never return one.
Taught each backend's `next-ready` to exclude drafts: ADO via a `System.Tags NOT CONTAINS`
WIQL clause (the only real enforcement point there), GitHub via the label check, Markdown
via the `## Drafts` section. nibs needed nothing — `--ready` excludes `draft` natively.
Added `capture` to the list of contract callers.

`decaf-plan/skills/capture/SKILL.md` — rewritten to detect the tracker and call the
contract's `create` op with `status: draft`. Dropped the nibs-only prerequisite and the
`allowed-tools` restriction (it blocked the ADO MCP tools the contract prefers; siblings
declare none). Kept the minimal-interruption goal by not confirming a single detected
tracker, while honoring the contract's confirm-before-create rule for GitHub/ADO. Told it
not to invent `## Acceptance` on a draft.

Tag naming: detect an existing `draft`/`refine`/`needs-refinement`/`triage` label first,
fall back to `Draft` (ado) / `status:draft` (github).

## Verified against the real CLI

- `nibs new ... -s draft -d -` works, creates `status: draft`
- `nibs list --ready` excludes it; `nibs list -s draft` returns it — the exclusion is real
- `nibs new ... -d "inline"` → `Error: inline text is not allowed here`

That last one means **capture was broken before this change**, not merely creating the
wrong status.

## Stale commands fixed

Four in `work-items.md`'s nibs adapter (inline `--body`, `--full` instead of `--view full`,
inline `close --summary`, `create`/`show` aliases) and one in `close-out/SKILL.md:109`
(inline `close --summary`). The close ones were breaking `close-out` and `auto-deliver`,
not just capture — same bug class, found while reading, fixed here rather than left behind.

## Docs

`README.md:257` promised the opposite of the new behavior ("Captured nibs get built later
— e.g. via batch-dev or auto-deliver"); corrected to say drafts are excluded until refined,
and that you can still name a draft id explicitly. `CLAUDE.md` and `decaf-plan/README.md`
dropped the now-wrong "(nib)" parenthetical.

## Not done

The ADO/GitHub paths are written to the contract but not executed — no repo here to try
them against. The ADO draft-tag mapping assumes an out-of-box process; a custom process
with a real draft/triage state should use that state instead, which the contract now says.
