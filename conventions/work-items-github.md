# Work Items — Adapter: GitHub (weakest backend — `next-ready` by convention)

The operations of the tracker adapter contract in [work-items.md](work-items.md), on GitHub Issues.
Read the contract first; this file only says how each operation runs here.

GitHub Issues has **no native dependency ordering**, so the contract is satisfied by
convention. The loop must behave identically, so these conventions are mandatory when the
backend is GitHub:

- **Plan = an epic issue.** Phases are **sub-issues** of it (`gh issue create --parent <epic#>` where supported), else linked by a `Tracked by #<epic>` line + a checklist in the epic body.
- **Order label** `phase:<n>` (e.g. `phase:1`) on each phase issue establishes plan order.
- **Cross-phase dependencies** beyond the linear `phase:<n>` order: a `Blocked by #<m>` line in the issue body (machine-readable).
- **Status labels** `status:todo` / `status:in-progress` / `status:blocked` / `status:draft`; **done = the issue is closed.**
- **Draft label.** Without an existing project convention (see the contract's *Picking the tag name*), the draft label is **`status:draft`**. It may not exist yet; creating it is a repo-visible mutation, so confirm with the user before `gh label create` (under `--unattended`, create it and record the fact).

Operations:

- **create** — `gh issue create --title "<title>" --body "<body>" [--parent <epic#>] [--label phase:<n>] [--label status:todo]`. Record dependencies as `Blocked by #<m>` lines in the body. For `draft` status, apply the draft label and **omit `phase:<n>`** — a draft has no place in plan order yet.
- **next-ready** — among open phase issues of the plan, pick the **lowest `phase:<n>`** whose predecessors are all satisfied: every lower-`n` phase is **closed**, and every `Blocked by #<m>` referenced issue is **closed**. Skip any issue carrying the **draft label**. That issue is next-ready. None open ⇒ plan complete. (`gh issue list --label "phase" --state open --json number,labels,body` then apply the rule.)
- **list-ready** — apply the `next-ready` rule and keep every qualifying issue, lowest `phase:<n>` first. None ⇒ nothing ready.
- **read** — `gh issue view <n> --json title,body,labels,state`. Body holds spec + `## Acceptance`. Blockers are the issues named in its `Blocked by #<m>` lines, plus, for a phase issue, every open lower-`phase:<n>` issue. Children are its sub-issues, or, where sub-issues are unavailable, the issues whose body carries `Tracked by #<n>`; order them by `phase:<n>`.
- **set-status** — swap the `status:*` label (`gh issue edit <n> --add-label status:in-progress --remove-label status:todo`). Refining a draft = swap `status:draft` → `status:todo` and assign a `phase:<n>`.
- **close** — `gh issue close <n> --comment "<summary>"`.
- **append-note** — `gh issue comment <n> --body-file -`, with the note on stdin starting with its `## <heading>` line.
- **create-followup** — `gh issue create` linked to the epic (`--parent`/`Tracked by`), with an appropriate `phase:<n>` or a `followup` label and any `Blocked by #<m>` lines.

> **Draft is doubly safe here, but state it anyway.** A draft carries no `phase:<n>`, and
> `next-ready` only considers `phase`-labelled issues — so drafts fall out of selection
> even without the label check. The label check is still required: it keeps the rule true
> under the contract rather than true by accident, and it survives someone later
> phase-labelling a draft.
