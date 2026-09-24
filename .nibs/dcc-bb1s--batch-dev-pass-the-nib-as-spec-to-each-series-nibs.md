---
# dcc-bb1s
version: 1
title: 'batch-dev: pass the nib as --spec to each series nib''s review'
status: in-progress
type: task
priority: normal
estimate: s
created_at: 2026-09-24T17:02:59Z
updated_at: 2026-09-24T17:22:33Z
parent: dcc-fq6j
order: a0
---

## Description

batch-dev Phase 6a runs `/decaf-quality:auto-code-review {reviewSpec} --max-iterations … {--report}` for each series nib but never passes the nib as `--spec`. The review runs inside a subagent (auto-code-review Step 2), so code-review's Step 1.5 spec discovery cannot find the nib from session context either, and there is no PR to link one. Result: the `spec-compliance-reviewer` most likely never runs during batch-dev or auto-deliver work, and a task is only checked against its intent later, by the phase's `## Acceptance` checks in auto-deliver VERIFY.

superpowers gates every task on spec compliance against an extracted brief. decaf can get the same effect cheaply: code-review's `--spec` already accepts a document path, and a nib is a file (`.nibs/<id>--<slug>.md`). An explicit spec is reviewed at full strength, unlike an inferred one, which is capped at Medium.

## Acceptance

- [x] [run] `grep -n 'auto-code-review' decaf-build/skills/batch-dev/SKILL.md | grep -c -- '--spec'` — expect: at least 1 (the Phase 6a review invocation passes the nib as `--spec`)
- [ ] [manual] In a real batch-dev run, each series item's consolidated review header names its spec with source `explicit`: the item ID on Azure DevOps, `.decaf/batch-dev/specs/<item-id>.md` on any other tracker. The roster includes `spec-compliance-reviewer`

## Notes
- The review gets the adapter's `read` output written to `.decaf/batch-dev/specs/<item-id>.md`, not the nib file path. Items can come from any tracker in `conventions/work-items.md`: a Markdown item is one section of a shared plan file, and a GitHub issue has no local file. Azure DevOps items pass their ID, because code-review fetches those natively, including the Acceptance Criteria field.
- `.decaf/batch-dev/.gitignore` containing `*` keeps spec files out of the conductor's commit. Checked in a scratch repo: `git add -A` staged only the code file, and the spec file did not appear in `git status`.
- code-review's local mode diffs tracked changes only, so the untracked spec file stays out of the reviewed changeset. The `bugs` preset also runs spec discovery, so the spec reaches the reviewer under every preset.
- Tested with fresh agents reading the skill. Old text: the review invocation carried no `--spec`. New text: Azure DevOps passed `--spec 48213` with no file; nibs, GitHub and Markdown each wrote a spec file holding only their item, created the ignore guard first, and passed the file path.
