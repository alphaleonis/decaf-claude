# Work Items — Tracker Adapter Contract

Shared contract for detecting a work-item tracker and operating on work items through a
small, **tracker-agnostic** interface. Planning skills (`draft-plan`, `breakdown-phase`,
`close-out`) and the autonomous `auto-deliver` loop call **only the six operations
defined here** — never a backend directly. Each backend below implements the same six
operations, so loop logic never assumes a specific tracker.

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
| `todo` | not started | `todo` | New / To Do | open, label `status:todo` (or no status label) | `[ ]` |
| `in-progress` | being worked | `in-progress` | Active / In Progress | open, label `status:in-progress` | `[~]` |
| `blocked` | waiting on a blocker | open with an unmet `blocked-by` | Active + open Predecessor link | open, label `status:blocked` | `[ ]` + listed unmet dep |
| `done` | completed | `completed` (via `close`) | Resolved / Closed / Done | closed | `[x]` |

`blocked` is derived, not stored, where a backend tracks dependencies natively (nibs, ado):
an item is blocked iff it has an open blocker. GitHub/Markdown express it by convention.

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

- **create** — `nibs create "<title>" --type <type> --status todo [--body <body> | --body-file <path>] [--parent <id>] [--blocked-by <id> ...] [--priority <p>] [--tag <t> ...]`. Hierarchy by scope: large = `milestone → epic → phase(epic)/task`, small = `epic → task`.
- **next-ready** — native: `nibs list --ready --parent <plan-id> [--type epic] -q` → take the **first** id (default sort is the sibling order key = plan order). `--ready` already excludes blocked / in-progress / completed / draft. Empty output ⇒ no ready phase ⇒ plan complete.
- **read** — `nibs show <id>` (human) or `nibs list --parent <id> --full --json` for structured. Body holds the spec + `## Acceptance`.
- **set-status** — `nibs update <id> --status <todo|in-progress|completed>`.
- **close** — `nibs close <id> --summary "<summary>"` (marks completed, merges Key Decisions / Current Focus into the parent).
- **create-followup** — `nibs create "<title>" --type <task|feature> --parent <plan-or-epic-id> --body <body> [--blocked-by <id>]`.

## Adapter: Azure DevOps

Prefer the Azure DevOps MCP tools; fall back to `az boards`. Dependencies use
Predecessor/Successor links; hierarchy uses Parent/Child.

- **create** — MCP `wit_create_work_item`, or `az boards work-item create --type "<type>" --title "<title>" --description "<body>"`. Link to parent: `az boards work-item relation add --id <child> --relation-type "System.LinkTypes.Hierarchy-Reverse" --target-id <parent>`. Dependencies: relation type `System.LinkTypes.Dependency-Reverse` (predecessor). Hierarchy by scope: large = Feature → User Stories, small = User Story → Tasks.
- **next-ready** — WIQL: children of the plan (`System.Parent` = plan, or the target work-item-type tier) with `System.State` in (`New`,`To Do`) **and** no open Predecessor (no incomplete `Dependency-Reverse` link target); order by `Microsoft.VSTS.Common.StackRank` (backlog order). First result = next ready. None ⇒ plan complete.
- **read** — MCP `wit_get_work_item` (or `az boards work-item show --id <id>`); `System.Description` carries spec + `## Acceptance`.
- **set-status** — update `System.State` to the mapped native state.
- **close** — set `System.State` = `Closed`/`Done` and add the summary as a comment (`wit_add_work_item_comment` / `az boards work-item update`).
- **create-followup** — `create` + link to the plan (Hierarchy) and/or the originating item.

## Adapter: GitHub (weakest backend — `next-ready` by convention)

GitHub Issues has **no native dependency ordering**, so the contract is satisfied by
convention. The loop must behave identically, so these conventions are mandatory when the
backend is GitHub:

- **Plan = an epic issue.** Phases are **sub-issues** of it (`gh issue create --parent <epic#>` where supported), else linked by a `Tracked by #<epic>` line + a checklist in the epic body.
- **Order label** `phase:<n>` (e.g. `phase:1`) on each phase issue establishes plan order.
- **Cross-phase dependencies** beyond the linear `phase:<n>` order: a `Blocked by #<m>` line in the issue body (machine-readable).
- **Status labels** `status:todo` / `status:in-progress` / `status:blocked`; **done = the issue is closed.**

Operations:

- **create** — `gh issue create --title "<title>" --body "<body>" [--parent <epic#>] [--label phase:<n>] [--label status:todo]`. Record dependencies as `Blocked by #<m>` lines in the body.
- **next-ready** — among open phase issues of the plan, pick the **lowest `phase:<n>`** whose predecessors are all satisfied: every lower-`n` phase is **closed**, and every `Blocked by #<m>` referenced issue is **closed**. That issue is next-ready. None open ⇒ plan complete. (`gh issue list --label "phase" --state open --json number,labels,body` then apply the rule.)
- **read** — `gh issue view <n> --json title,body,labels,state`. Body holds spec + `## Acceptance`.
- **set-status** — swap the `status:*` label (`gh issue edit <n> --add-label status:in-progress --remove-label status:todo`).
- **close** — `gh issue close <n> --comment "<summary>"`.
- **create-followup** — `gh issue create` linked to the epic (`--parent`/`Tracked by`), with an appropriate `phase:<n>` or a `followup` label and any `Blocked by #<m>` lines.

## Adapter: Markdown (fallback)

A single plan file at `./plans/<plan-name>.md`. Phases are `##` sections in plan order;
features are checklist items; dependencies are stated in prose; status is the checkbox plus
an optional marker. Everything is by convention; the loop reads/writes the file.

- **create** — append a `## Phase N — <title>` section (or a `- [ ]` feature line) with the body and `## Acceptance` beneath it. Create `./plans/` if missing.
- **next-ready** — the **first** phase section not marked done (`[ ]`/`[~]`) whose listed dependency phases are all `[x]`. None ⇒ plan complete.
- **read** — read the phase section (spec + `## Acceptance`).
- **set-status** — change the section's checkbox marker (`[ ]` → `[~]` → `[x]`).
- **close** — mark `[x]` and append a `> Closed: <summary>` line under the section.
- **create-followup** — append a new `- [ ]` item under a `## Follow-ups` section (or a new phase), with any dependency noted in prose.

---

## next-ready: the portable rule

Whatever the backend, `next-ready` returns the single item that is **(a)** in scope under
the plan, **(b)** not yet done, **(c)** not in-progress, and **(d)** has every dependency
satisfied (all blockers / predecessors / lower-order phases done) — taking the **first**
such item in plan order. nibs and ado answer this natively; GitHub and Markdown answer it
from the conventions above. When no item qualifies, the plan is complete and the loop stops.
