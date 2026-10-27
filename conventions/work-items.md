# Work Items — Tracker Adapter Contract

Shared contract for detecting a work-item tracker and operating on work items through a
small, **tracker-agnostic** interface. Planning skills (`draft-plan`, `breakdown-phase`,
`capture`, `close-out`), the `batch-dev` executor and the autonomous `auto-deliver` loop
call **only the operations defined here** — never a backend directly. Each backend
implements every operation, so loop logic never assumes a specific tracker.

Backends: **nibs**, **Azure DevOps** (ado), **GitHub** (github), **Markdown** (fallback).
The contract is **designed to the weakest backend** — where a tracker lacks a native
capability (notably GitHub dependency ordering), the operation is satisfied **by
convention** so the loop behaves identically everywhere.

Each backend's operations live in its own adapter file beside this one. Once the tracker is
known (see [System detection](#system-detection)), read **only** its adapter, before the
first operation:

| Backend | Adapter |
|---------|---------|
| nibs | [work-items-nibs.md](work-items-nibs.md) |
| Azure DevOps | [work-items-ado.md](work-items-ado.md) |
| GitHub | [work-items-github.md](work-items-github.md) |
| Markdown | [work-items-markdown.md](work-items-markdown.md) |

## The contract

| Op | Purpose | Inputs | Returns |
|----|---------|--------|---------|
| `create` | Create a work item (epic / phase / feature / task) | type, title, body, parent?, blocked-by?, status? | item id |
| `next-ready` | The next item ready to start, in dependency + plan order | scope (plan/epic id), type? | one item id, or *none* (→ plan complete) |
| `list-ready` | Every item ready to start, in dependency + plan order | scope (plan/epic id), type? | item ids, possibly none |
| `read` | Read an item's full content — spec **and** `## Acceptance` | item id | type, title, body, status, parent, blockers, children |
| `set-status` | Move an item between states | item id, status | — |
| `close` | Mark an item done and record a closing summary | item id, summary | — |
| `append-note` | Add a headed note to an item without replacing its body | item id, heading, text | — |
| `create-followup` | File newly discovered / deferred work as a tracked item | title, body, parent?/link, blocked-by? | item id |

`read` returns the **whole body**, which carries the spec and a structured `## Acceptance`
section (format in [acceptance-criteria.md](acceptance-criteria.md)). The loop's verify
step parses `## Acceptance` from what `read` returns, so acceptance travels with the item
across every backend. `read` also returns the item's children (id and status, in plan
order), so a caller can walk a phase without keeping its own copy of the tracker.

### Normalized status model

The contract uses one small status vocabulary; each backend maps it to native states.

| Contract status | Meaning | nibs | Azure DevOps | GitHub | Markdown |
|-----------------|---------|------|--------------|--------|----------|
| `draft` | captured, not yet refined | `draft` | New / Proposed **+ draft tag** | open, **draft label** | `[?]` |
| `todo` | not started, ready to be picked up | `todo` | New / To Do | open, label `status:todo` (or no status label) | `[ ]` |
| `in-progress` | being worked | `in-progress` | Active / In Progress | open, label `status:in-progress` | `[~]` |
| `blocked` | waiting on a blocker | open with an unmet `blocked-by` | Active + open Predecessor link | open, label `status:blocked` | `[ ]` + listed unmet dep |
| `done` | completed | `completed` (via `close`) | Resolved / Closed / Done | closed | `[x]` |

`blocked` is derived, not stored, where a backend tracks dependencies natively (nibs, ado):
an item is blocked iff it has an open blocker. GitHub/Markdown express it by convention.

#### `draft` — captured but not ready to build

`draft` means the item was jotted down (typically by `capture`) from a short note, with
the rest inferred. It is **not refined enough to execute**: nobody has confirmed the
scope, the acceptance criteria, or that it should be built at all.

**`next-ready` MUST never return a `draft` item, on any backend.** This is the whole
point of the status — an unrefined item that reaches `auto-deliver` gets built from
guesses. Refining a draft to `todo` is a deliberate human step: `/decaf-plan:refine` is
the skill that does it (read the code, resolve the open questions with the user, add
`## Acceptance`, then `set-status` to `todo`).

Only nibs enforces this natively (`--ready` excludes `draft`). The other three backends
have no draft state, so `draft` is expressed with a **tag/label/marker** and each
backend's `next-ready` must filter it out explicitly — see its adapter.

**Picking the tag name.** Projects name this differently. Detect an existing convention
before inventing one: look for a label/tag matching `draft`, `refine`, `needs-refinement`,
or `triage` (case-insensitive) and reuse it. Only if none exists, fall back to the
adapter's default.

## System detection

If the user named a target system, use it. Otherwise detect and, if ambiguous, confirm.
Check in order:

1. **GitHub** — `gh repo view --json name 2>/dev/null` succeeds → GitHub Issues available.
2. **Azure DevOps** — an Azure DevOps MCP server is connected (tools containing
   `azure-devops` / `azuredevops`), or `az devops project show 2>/dev/null` works.
3. **nibs** — `command -v nibs 2>/dev/null` and a `.nibs.yml` exists (project initialized).

If multiple are available, or none, ask which to use. If exactly one is detected, confirm
before proceeding (except under `--unattended`, where the loop uses the detected/configured
tracker without prompting). Markdown is the always-available fallback.

### User confirmation

**Show draft content before creating items in collaborative systems** (GitHub, Azure
DevOps) — these are visible to others. For local targets (nibs, Markdown), create directly;
the user can edit after. Under an unattended loop run these gates are suppressed (see each
skill's `--unattended` behavior); the loop still records what it created in
`.decaf/auto-deliver/`.

## next-ready: the portable rule

Whatever the backend, `next-ready` returns the single item that is **(a)** in scope under
the plan, **(b)** not yet done, **(c)** not in-progress, **(d)** **not a draft**, and
**(e)** has every dependency satisfied (all blockers / predecessors / lower-order phases
done) — taking the **first** such item in plan order. When no item qualifies, the plan is
complete and the loop stops. `list-ready` applies the same rule and returns every
qualifying item, in the same order.

Only **(d)** is enforced natively everywhere it can be: nibs excludes `draft` from
`--ready` for free. On ado it is the tag filter in the WIQL, on GitHub the label check,
on Markdown the `## Drafts` section — get any of those wrong and the loop silently starts
building work nobody has refined.
