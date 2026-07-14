# Work Items — Tracker Adapter Contract

Shared contract for detecting a work-item tracker and operating on work items through a
small, **tracker-agnostic** interface. Planning skills (`draft-plan`, `breakdown-phase`,
`capture`, `close-out`) and the autonomous `auto-deliver` loop call **only the six
operations defined here** — never a backend directly. Each backend below implements the
same six operations, so loop logic never assumes a specific tracker.

Backends, in detection order: **nibs**, **Azure DevOps** (ado), **GitHub** (github),
**Markdown** (fallback). The contract is **designed to the weakest backend** — where a
tracker lacks a native capability (notably GitHub dependency ordering), the operation is
satisfied **by convention** so the loop behaves identically everywhere.

## The contract

| Op | Purpose | Inputs | Returns |
|----|---------|--------|---------|
| `create` | Create a work item (epic / phase / feature / task) | type, title, body, parent?, blocked-by?, status? | item id |
| `next-ready` | The next item ready to start, in dependency + plan order | scope (plan/epic id), type? | one item id, or *none* (→ plan complete) |
| `read` | Read an item's full content — spec **and** `## Acceptance` | item id | type, title, body, status, parent, blockers |
| `set-status` | Move an item between states | item id, status | — |
| `close` | Mark an item done and record a closing summary | item id, summary | — |
| `create-followup` | File newly discovered / deferred work as a tracked item | title, body, parent?/link, blocked-by? | item id |

`read` returns the **whole body**, which carries the spec and a structured `## Acceptance`
section (format in [acceptance-criteria.md](acceptance-criteria.md)). The loop's verify
step parses `## Acceptance` from what `read` returns, so acceptance travels with the item
across every backend.

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
guesses. Refining a draft to `todo` is a deliberate human step.

Only nibs enforces this natively (`--ready` excludes `draft`). The other three backends
have no draft state, so `draft` is expressed with a **tag/label/marker** and each
backend's `next-ready` must filter it out explicitly — see the per-adapter rules below.

**Picking the tag name.** Projects name this differently. Detect an existing convention
before inventing one: look for a label/tag matching `draft`, `refine`, `needs-refinement`,
or `triage` (case-insensitive) and reuse it. Only if none exists, fall back to the
default: **`Draft`** (Azure DevOps tag) / **`status:draft`** (GitHub label, consistent
with the other `status:*` labels here). On GitHub the fallback label may not exist yet;
creating it is a repo-visible mutation, so confirm with the user before `gh label create`
(under `--unattended`, create it and record the fact).

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

---

## Adapter: nibs

Local markdown tracker with native types, hierarchy, dependencies, and a ready filter. Run
`nibs prime` once per project first — it emits project-specific agent instructions; honor
them. Types: `milestone`, `epic`, `bug`, `feature`, `task`, `research`.

> **Prose is never inline.** `-d`/`--body` and `close --summary` accept **only** `-`
> (stdin) or `@FILE` — passing inline text is rejected. Either pipe the body in
> (`... -d - <<'EOF'`) or write it to a file first and pass `@<path>` / `--body-file`.

- **create** — `nibs new "<title>" --type <type> --status <draft|todo> [--body-file <path> | -d @<path> | -d -] [--parent <id>] [--blocked-by <id> ...] [--priority <p>] [--tag <t> ...]`. Hierarchy by scope: large = `milestone → epic → phase(epic)/task`, small = `epic → task`.
- **next-ready** — native: `nibs list --ready --parent <plan-id> [--type epic] -q` → take the **first** id (default sort is the sibling order key = plan order). `--ready` already excludes blocked / in-progress / completed / **draft** / deferred, so drafts are filtered natively — no extra work on this backend. Empty output ⇒ no ready phase ⇒ plan complete.
- **read** — `nibs get <id>` (document) or `nibs list --parent <id> --view full --json` for structured. Body holds the spec + `## Acceptance`.
- **set-status** — `nibs set <id> --status <draft|todo|in-progress|completed>`.
- **close** — `nibs close <id> --summary -` (summary on stdin; marks completed, merges Key Decisions / Current Focus into the parent).
- **create-followup** — `nibs new "<title>" --type <task|feature> --parent <plan-or-epic-id> --body-file <path> [--blocked-by <id>]`.

## Adapter: Azure DevOps

Prefer the Azure DevOps MCP tools; fall back to `az boards`. Dependencies use
Predecessor/Successor links; hierarchy uses Parent/Child.

- **create** — MCP `wit_create_work_item`, or `az boards work-item create --type "<type>" --title "<title>" --description "<body>"`. Link to parent: `az boards work-item relation add --id <child> --relation-type "System.LinkTypes.Hierarchy-Reverse" --target-id <parent>`. Dependencies: relation type `System.LinkTypes.Dependency-Reverse` (predecessor). Hierarchy by scope: large = Feature → User Stories, small = User Story → Tasks. For `draft` status, create in the normal initial state (`New`/`Proposed`) **and** add the draft tag (`System.Tags`) — see below.
- **next-ready** — WIQL: children of the plan (`System.Parent` = plan, or the target work-item-type tier) with `System.State` in (`New`,`To Do`), **no draft tag** (`AND System.Tags NOT CONTAINS '<draft-tag>'`), **and** no open Predecessor (no incomplete `Dependency-Reverse` link target); order by `Microsoft.VSTS.Common.StackRank` (backlog order). First result = next ready. None ⇒ plan complete.
- **read** — MCP `wit_get_work_item` (or `az boards work-item show --id <id>`); `System.Description` carries spec + `## Acceptance`.
- **set-status** — update `System.State` to the mapped native state. `draft` → `todo` is a **tag removal**, not a state change: both map to `New`/`To Do`, so refining a draft means dropping the draft tag.
- **close** — set `System.State` = `Closed`/`Done` and add the summary as a comment (`wit_add_work_item_comment` / `az boards work-item update`).
- **create-followup** — `create` + link to the plan (Hierarchy) and/or the originating item.

> **Why the tag is load-bearing here.** Out-of-box ADO processes have no draft tier —
> Agile is New/Active/Resolved/Closed, Scrum is New/Approved/Committed/Done, CMMI is
> Proposed/Active/Resolved/Closed. The initial state is already what `todo` maps to, so a
> drafted item is indistinguishable from a ready one *by state alone*, and the `next-ready`
> WIQL above would select it. The tag is the only thing separating them — which is why
> `next-ready` must filter on it. If a project runs a **custom process with a real draft /
> triage state**, prefer that state over the tag and filter `next-ready` on the state instead.

## Adapter: GitHub (weakest backend — `next-ready` by convention)

GitHub Issues has **no native dependency ordering**, so the contract is satisfied by
convention. The loop must behave identically, so these conventions are mandatory when the
backend is GitHub:

- **Plan = an epic issue.** Phases are **sub-issues** of it (`gh issue create --parent <epic#>` where supported), else linked by a `Tracked by #<epic>` line + a checklist in the epic body.
- **Order label** `phase:<n>` (e.g. `phase:1`) on each phase issue establishes plan order.
- **Cross-phase dependencies** beyond the linear `phase:<n>` order: a `Blocked by #<m>` line in the issue body (machine-readable).
- **Status labels** `status:todo` / `status:in-progress` / `status:blocked` / `status:draft`; **done = the issue is closed.**

Operations:

- **create** — `gh issue create --title "<title>" --body "<body>" [--parent <epic#>] [--label phase:<n>] [--label status:todo]`. Record dependencies as `Blocked by #<m>` lines in the body. For `draft` status, apply the draft label and **omit `phase:<n>`** — a draft has no place in plan order yet.
- **next-ready** — among open phase issues of the plan, pick the **lowest `phase:<n>`** whose predecessors are all satisfied: every lower-`n` phase is **closed**, and every `Blocked by #<m>` referenced issue is **closed**. Skip any issue carrying the **draft label**. That issue is next-ready. None open ⇒ plan complete. (`gh issue list --label "phase" --state open --json number,labels,body` then apply the rule.)
- **read** — `gh issue view <n> --json title,body,labels,state`. Body holds spec + `## Acceptance`.
- **set-status** — swap the `status:*` label (`gh issue edit <n> --add-label status:in-progress --remove-label status:todo`). Refining a draft = swap `status:draft` → `status:todo` and assign a `phase:<n>`.
- **close** — `gh issue close <n> --comment "<summary>"`.
- **create-followup** — `gh issue create` linked to the epic (`--parent`/`Tracked by`), with an appropriate `phase:<n>` or a `followup` label and any `Blocked by #<m>` lines.

> **Draft is doubly safe here, but state it anyway.** A draft carries no `phase:<n>`, and
> `next-ready` only considers `phase`-labelled issues — so drafts fall out of selection
> even without the label check. The label check is still required: it keeps the rule true
> under the contract rather than true by accident, and it survives someone later
> phase-labelling a draft.

## Adapter: Markdown (fallback)

A single plan file at `./plans/<plan-name>.md`. Phases are `##` sections in plan order;
features are checklist items; dependencies are stated in prose; status is the checkbox plus
an optional marker. Everything is by convention; the loop reads/writes the file.

- **create** — append a `## Phase N — <title>` section (or a `- [ ]` feature line) with the body and `## Acceptance` beneath it. Create `./plans/` if missing. For `draft` status, append a `- [?]` item under a `## Drafts` section instead — outside plan order.
- **next-ready** — the **first** phase section not marked done (`[ ]`/`[~]`) whose listed dependency phases are all `[x]`. Skip `[?]` items and anything under `## Drafts`. None ⇒ plan complete.
- **read** — read the phase section (spec + `## Acceptance`).
- **set-status** — change the section's checkbox marker (`[ ]` → `[~]` → `[x]`).
- **close** — mark `[x]` and append a `> Closed: <summary>` line under the section.
- **create-followup** — append a new `- [ ]` item under a `## Follow-ups` section (or a new phase), with any dependency noted in prose.

---

## next-ready: the portable rule

Whatever the backend, `next-ready` returns the single item that is **(a)** in scope under
the plan, **(b)** not yet done, **(c)** not in-progress, **(d)** **not a draft**, and
**(e)** has every dependency satisfied (all blockers / predecessors / lower-order phases
done) — taking the **first** such item in plan order. When no item qualifies, the plan is
complete and the loop stops.

Only **(d)** is enforced natively everywhere it can be: nibs excludes `draft` from
`--ready` for free. On ado it is the tag filter in the WIQL, on GitHub the label check,
on Markdown the `## Drafts` section — get any of those wrong and the loop silently starts
building work nobody has refined.
