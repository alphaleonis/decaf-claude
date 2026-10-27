# Work Items — Adapter: Azure DevOps

The operations of the tracker adapter contract in [work-items.md](work-items.md), on Azure DevOps.
Read the contract first; this file only says how each operation runs here.

Prefer the Azure DevOps MCP tools; fall back to `az boards`. Dependencies use
Predecessor/Successor links; hierarchy uses Parent/Child.

**Draft tag.** Without an existing project convention (see the contract's *Picking the tag
name*), the draft tag is **`Draft`**, in `System.Tags`.

- **create** — MCP `wit_create_work_item`, or `az boards work-item create --type "<type>" --title "<title>" --description "<body>"`. Link to parent: `az boards work-item relation add --id <child> --relation-type "System.LinkTypes.Hierarchy-Reverse" --target-id <parent>`. Dependencies: relation type `System.LinkTypes.Dependency-Reverse` (predecessor). Hierarchy by scope: large = Feature → User Stories, small = User Story → Tasks. For `draft` status, create in the normal initial state (`New`/`Proposed`) **and** add the draft tag (`System.Tags`) — see below.
- **next-ready** — WIQL: children of the plan (`System.Parent` = plan, or the target work-item-type tier) with `System.State` in (`New`,`To Do`), **no draft tag** (`AND System.Tags NOT CONTAINS '<draft-tag>'`), **and** no open Predecessor (no incomplete `Dependency-Reverse` link target); order by `Microsoft.VSTS.Common.StackRank` (backlog order). First result = next ready. None ⇒ plan complete.
- **list-ready** — the `next-ready` WIQL, keeping every result in `StackRank` order instead of the first. None ⇒ nothing ready.
- **read** — MCP `wit_get_work_item` (or `az boards work-item show --id <id>`); `System.Description` carries spec + `## Acceptance`. Fetch with relations expanded: blockers are its `System.LinkTypes.Dependency-Reverse` (Predecessor) relations, children its `System.LinkTypes.Hierarchy-Forward` relations; read each child's state.
- **set-status** — update `System.State` to the mapped native state (`az boards work-item update`, as for `close`). `draft` → `todo` is a **tag removal**, not a state change: both map to `New`/`To Do`, so refining a draft means dropping the draft tag.
- **close** — set `System.State` = `Closed`/`Done` and add the summary as a comment (`wit_add_work_item_comment` / `az boards work-item update`).
- **append-note** — add the note as a comment whose first line is the heading (`wit_add_work_item_comment` / `az boards work-item update`). A comment leaves `System.Description`, and so the spec `read` returns, untouched.
- **create-followup** — `create` + link to the plan (Hierarchy) and/or the originating item.

> **Why the tag is load-bearing here.** Out-of-box ADO processes have no draft tier —
> Agile is New/Active/Resolved/Closed, Scrum is New/Approved/Committed/Done, CMMI is
> Proposed/Active/Resolved/Closed. The initial state is already what `todo` maps to, so a
> drafted item is indistinguishable from a ready one *by state alone*, and the `next-ready`
> WIQL above would select it. The tag is the only thing separating them — which is why
> `next-ready` must filter on it. If a project runs a **custom process with a real draft /
> triage state**, prefer that state over the tag and filter `next-ready` on the state instead.
