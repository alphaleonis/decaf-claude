---
# dcc-u73a
version: 1
title: 'batch-dev: work from any tracker through the adapter contract, not only nibs'
status: draft
type: bug
priority: high
estimate: l
created_at: 2026-09-24T17:25:49Z
updated_at: 2026-09-24T17:40:20Z
parent: dcc-fq6j
order: aF
---

## Steps to Reproduce

Run `/decaf-build:auto-deliver <plan>` on a project whose tracker is Azure DevOps, GitHub or a Markdown plan. auto-deliver talks to the tracker only through the adapter contract in `conventions/work-items.md`, but its EXECUTE step hands the phase's items to batch-dev, which speaks nibs directly. Found by reading the skills; not yet observed in a run.

## Expected vs Actual

Expected: batch-dev accepts work items from any tracker the adapter contract supports, as auto-deliver and the planning skills do. In batch-dev, "nib" is the word for a work item, whatever tracker holds it.

Actual: batch-dev assumes nibs throughout.

- **Prerequisites** require nibs and `nibs prime --full`.
- **Argument parsing:** `--filter` is a nibs expression (`nibs list` / `nibs query`), and `--ready` is `nibs list --json --ready`.
- **Phase 1** drops items by nibs status names (`completed` / `scrapped`).
- **Phase 2** reads bodies with `nibs show --json` and relationships with `nibs links … --rel blocked-by,blocking,children`, including `--order topo`.
- **Phase 6** sets status with nibs values, commits "code and the nib file together", and Phase 6b excludes `.nibs/*.md` from lane commits.
- **Failure handling** appends a `## Batch failure note` to the item's body.
- **Phase 8** offers "follow-up nibs".

Phase 6a's review spec is already tracker-agnostic (#dcc-bb1s).

The review's deferrals also lose track of the tracker. auto-code-review detects where to file deferred findings from the project CLAUDE.md, while auto-deliver already knows its tracker from `state.json`. When CLAUDE.md names no tracker, an unattended review lists its deferrals as unfiled for the caller (#dcc-qdxo), and nothing up the chain is told to file them: batch-dev only offers follow-ups, and close-out picks up deferred work from conversation context only implicitly.

## Root Cause

batch-dev was written against nibs directly, and the adapter contract does not yet cover everything it needs. The contract's six operations have no way to:

- list every ready item in a scope (`next-ready` returns one),
- list an item's children in dependency order,
- append a note to an item (the failure note),
- resolve a filter expression.

## Open questions

- Extend the contract with the missing operations, or have batch-dev compose the existing six? The contract is designed to the weakest backend, so any new operation needs a GitHub and a Markdown form.
- What does the conductor commit alongside code? Only nibs and Markdown plans live in the repo; on Azure DevOps and GitHub a status change is an API call with nothing to commit.
- What does `--filter` mean per backend: WIQL, a `gh` search, a Markdown section match?
- Keep "nib" as batch-dev's generic word for a work item and say so once, or rename it to "work item" throughout?

## Acceptance
- [ ] [manual] Under auto-deliver, deferred review findings are filed in auto-deliver's tracker even when the project CLAUDE.md names none: batch-dev receives the tracker and passes it to auto-code-review, which uses it as `deferSystem`. The unfiled listing remains only as a fallback for callers that know no tracker.
