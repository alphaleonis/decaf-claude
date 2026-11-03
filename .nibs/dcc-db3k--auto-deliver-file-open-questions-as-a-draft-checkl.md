---
# dcc-db3k
version: 1
title: 'auto-deliver: file open questions as a draft checklist nib, walked by resolve-open-questions'
status: in-progress
type: feature
created_at: 2026-11-03T08:41:12Z
updated_at: 2026-11-03T08:43:59Z
order: zzzzzzzw
---

After a long auto-deliver run, the decisions left for the human are scattered across the final report's sections and recorded only in closed nibs and `phases/<id>/reflection.md`. None of them becomes an open item, and the report states each in a line too short to act on.

Seen in lotsen (session 2855a60a, 2026-11-03): a 30-feature run ended with ~12 open decisions spread over six report headings. The operator had to ask whether any were left, then prompt twice more ("walk me through…", "one at a time") before getting a usable per-item format: what happened → options → recommendation → choice. The good explanations also needed a fresh look at the code at walk time.

## Design

- **Capture** during the run: each phase's `reflection.md` gets a structured `## Open questions` section. Each entry has a kind (decision / confirm / manual check), the originating item, files, what happened, options, recommendation. The format lives in one shared convention (`conventions/open-questions.md`), symlinked into decaf-build and decaf-plan.
- **File** at STOP: gather every unfiled section into one `draft` work item (a checklist grouped by kind) under the plan, then mark the sections filed so a later STOP does not file them again. `draft` keeps the item out of `next-ready`.
- **Report**: the final report names the item and the count per kind, and ends with a bold line naming the command. It no longer lists the items in detail.
- **Resolve**: new `/decaf-plan:resolve-open-questions <id>` walks the checklist one item at a time. It re-checks each against the current code, then presents what happened / options / recommendation. Each item ends as: change now, decision recorded on the originating item, new item filed (manual checks as `draft`), or accepted as is. It ticks items off and closes the work item when none remain.

## Todo

- [x] `conventions/open-questions.md` + symlinks in decaf-build and decaf-plan
- [x] auto-deliver: capture in VERIFY/RECONCILE/REPLAN, file at STOP, slim final report
- [x] artifact-layout.md: reflection `## Open questions` section
- [x] `decaf-plan/skills/resolve-open-questions/SKILL.md`
- [x] README + CLAUDE.md skill tables
- [x] `scripts/check-skill-references.sh` passes

## Acceptance

- [run] `scripts/check-skill-references.sh` — expect: exit 0
- [run] `test -L decaf-build/conventions/open-questions.md && test -L decaf-plan/conventions/open-questions.md` — expect: exit 0
- [run] `grep -c "resolve-open-questions" README.md CLAUDE.md` — expect: each count ≥ 1
- [manual] The next auto-deliver run ends with one draft open-questions item and a bold line naming the resolve command — needs a real plan run to observe.
