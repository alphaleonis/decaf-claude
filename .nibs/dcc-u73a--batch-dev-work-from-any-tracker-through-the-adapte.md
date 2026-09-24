---
# dcc-u73a
version: 1
title: 'batch-dev: work from any tracker through the adapter contract, not only nibs'
status: completed
type: bug
priority: high
estimate: l
created_at: 2026-09-24T17:25:49Z
updated_at: 2026-09-24T17:53:17Z
parent: dcc-fq6j
order: aF
---

## Steps to Reproduce

Run `/decaf-build:auto-deliver <plan>` on a project whose tracker is Azure DevOps, GitHub or a Markdown plan. auto-deliver talks to the tracker only through the adapter contract in `conventions/work-items.md`, but its EXECUTE step hands the phase's items to batch-dev, which speaks nibs directly. Found by reading the skills; not yet observed in a run.

## Expected vs Actual

Expected: batch-dev accepts work items from any tracker the adapter contract supports, as auto-deliver and the planning skills do. In batch-dev, "nib" is the word for a work item, whatever tracker holds it.

Actual: batch-dev assumes nibs in its prerequisites, its `--filter`/`--ready` queue sources, Phase 1's status names, Phase 2's `nibs show`/`nibs links` reads, Phase 6's status and commit rules (including 6b's `.nibs/*.md` exclusion), its failure note, and Phase 8's follow-ups. Phase 6a's review spec is already tracker-agnostic (#dcc-bb1s).

The review's deferrals also lose track of the tracker. auto-code-review detects where to file deferred findings from the project CLAUDE.md, while auto-deliver already knows its tracker from `state.json`. When CLAUDE.md names no tracker, an unattended review lists its deferrals as unfiled (#dcc-qdxo), and nothing up the chain files them.

## Root Cause

batch-dev was written against nibs directly, and the contract's six operations cannot express what it needs: `next-ready` returns one item where `--ready` needs all of them, `read` does not return children (auto-deliver needs a phase's children to resume at EXECUTE without mirroring the tracker), and there is no way to append a note to an item. close-out already works around the last gap with its own per-tracker table.

## Plan

Decided in refine on 2026-09-24:

1. **Extend the contract** in `conventions/work-items.md`: `list-ready` (the `next-ready` rule, every match in plan order) and `append-note` (a headed note on an item), each with a form in all four adapter sections, and `read` also returns the item's children. Update every "six operations" wording (work-items.md, auto-deliver).
2. **Port batch-dev onto the contract.** Define "nib" once as a work item in whatever tracker the project uses. Add `--tracker nibs|ado|github|markdown`; without it, detect per the contract (use a single detected tracker silently; ask when several or none, except under `--unattended`, which requires `--tracker` or a single detected tracker). `--ready` uses `list-ready`. `--filter` becomes a tracker-native query (nibs filter, WIQL, `gh issue` search); Markdown has no search, so `--filter` is refused there. Phase 1 drops `done` items and flags `in-progress` and `draft` ones (unattended runs skip drafts and log it). Phase 2 reads bodies, blockers and children with `read` and orders by blockers. Status goes through `set-status`/`close`. Commits carry the code plus any tracker files the status changes touched in the working tree (nibs, Markdown only). The failure note uses `append-note`; Phase 8 follow-ups use `create-followup`.
3. **Pass the tracker down.** auto-deliver's EXECUTE passes `--tracker` and the phase's open children's ids (from `read`) instead of "a phase-scoped filter". batch-dev passes `--tracker` to auto-code-review, which uses it as `deferSystem` and skips CLAUDE.md detection. The unfiled listing stays as the fallback for callers that pass no tracker.

## Acceptance

- [x] [run] `grep -c -E '^\| \`(list-ready|append-note)\` \|' conventions/work-items.md` — expect: `2` (both ops in the contract table)
- [x] [run] `for name in list-ready append-note; do grep -c -- "^- \*\*$name\*\*" conventions/work-items.md; done` — expect: `4` then `4` (a form in each adapter section)
- [x] [run] `grep -rn -i -E 'six (op|operation)' conventions decaf-build decaf-plan decaf-quality` — expect: no output
- [x] [run] `grep -n -E 'nibs (show|links|list|query|rel|get)|\.nibs/' decaf-build/skills/batch-dev/SKILL.md` — expect: only the nibs row of the `--filter` mapping
- [x] [run] `grep -n -- '--tracker' decaf-build/skills/batch-dev/SKILL.md` — expect: the argument-hint, the argument list, and the Phase 6a forward to auto-code-review
- [x] [run] `grep -n -- '--tracker' decaf-quality/skills/auto-code-review/SKILL.md` — expect: the argument-hint, the argument list, and Step 1's `deferSystem` detection
- [x] [run] `grep -c 'phase-scoped filter' decaf-build/skills/auto-deliver/SKILL.md` — expect: `0`, and the EXECUTE step passes `--tracker`
- [x] [manual] A fresh agent walking batch-dev on an Azure DevOps scenario and a Markdown scenario uses only contract operations and the tracker-native `--filter`, and under auto-deliver files deferred review findings in auto-deliver's tracker when CLAUDE.md names none. Reason: the skills are prose an agent executes; no command can run them, so the check is an agent walkthrough.

## Notes
- The acceptance loop variable is `name`, not `op`: the decaf-protection hook matches `op in` in command text as a 1Password call and blocks the command, which would also stop auto-deliver's VERIFY from running this check.
- Walkthroughs by fresh agents, one per scenario. Old text on Azure DevOps: only nibs commands, no way to read an item's relations or append a note, no tracker flag, and "commit the nib file" undefined. New text: the Azure DevOps and Markdown agents both drove the whole run through contract operations; auto-deliver passed `--tracker` and child ids from `read`; commits carried code only on Azure DevOps and code plus the plan file on Markdown; the failure note went through `append-note`; deferrals landed in the passed-down tracker; Markdown refused `--filter`.
- All three agents noticed the contract never said how each backend's `read` finds blockers, which batch-dev now orders by. Added per backend: nibs `blocked_by`, Azure DevOps Predecessor relations, GitHub `Blocked by #<m>` lines plus lower phases, Markdown prose. Azure DevOps `set-status` now names `az boards work-item update`; its flags were not added because the Azure CLI is not installed to check them.
- Left as is: auto-code-review files deferrals through its own per-tracker logic rather than the contract's `create-followup`, so decaf-quality keeps no dependency on the tracker-adapter convention. The walkthrough agent read `create-followup` as the natural route; nothing required it.

## Summary

**Completed 2026-09-24** — batch-dev now works from any tracker the adapter contract supports. The contract gains `list-ready` and `append-note` in all four backends, and `read` returns children and, per backend, blockers. batch-dev takes `--tracker` (else detects per the contract), reads, orders, sets status, closes, notes failures and files follow-ups through contract operations, treats `--filter` as a tracker-native query (refused on Markdown), and commits only the tracker files that live in the repo. auto-deliver passes `--tracker` and the phase's open child ids from `read`; batch-dev passes `--tracker` to auto-code-review, which uses it as `deferSystem`. Verified by the seven acceptance greps and fresh-agent walkthroughs on Azure DevOps and Markdown against an Azure DevOps baseline.
