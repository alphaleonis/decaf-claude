---
# dcc-ghl5
version: 1
title: 'Comment-writing convention: generalize bibbla rules, write-comments skill, pointer hooks'
status: completed
type: feature
created_at: 2026-10-09T21:03:07Z
updated_at: 2026-11-24T13:38:38Z
order: zzzzzzs
---

Generalize the comment-writing rules from bibbla's `.claude/conventions/comments.md` into a plugin convention that every agent writes and reviews against, with a per-project overlay for glossary and local rules.

## Design

- Canonical `conventions/comments.md`: what a comment is for, doc-comment shape (generalized from C# XML doc to each language's doc format; the language's own idiom wins, e.g. Go's "starts with the identifier", PEP 257 imperative), wording rules (ASD-STE100 subset), neutral examples in more than one language.
- Project overlay `.decaf/conventions/comments.md` in the target repo: glossary, line width, language scope, project examples. Overlay wins on conflict.
- Skill `decaf-quality:write-comments`: `@`-includes the convention, injects the overlay via `` !`cat …` ``.
- `SessionStart` + `SubagentStart` hooks in `decaf-quality` inject a one-line pointer: invoke the skill before editing source files. (Probe on 2026-10-09: SessionStart context does not reach subagents; subagents do see plugin skills.)
- Reviewers (`knowledge-reviewer`, `consistency-reviewer`, `solo-reviewer`, `broad-reviewer`, `quick-reviewer`, `pr-thread-resolver`) and `technical-writer` `@`-load the convention and read the overlay.
- `conventions/artifacts.md`: `.decaf/conventions/` is committed config; projects ignore artifact subfolders, not `.decaf/` wholesale.

## Todo

- [x] Write `conventions/comments.md` (+ symlinks in quality/build/plan)
- [x] Decide fate of `conventions/temporal.md`
- [x] Skill `decaf-quality/skills/write-comments`
- [x] SessionStart + SubagentStart pointer hooks in `decaf-quality`
- [x] Wire reviewers and technical-writer
- [x] Amend `conventions/artifacts.md` and `conventions/CLAUDE.md`
- [x] Reduce bibbla's file to an overlay at `.decaf/conventions/comments.md`
- [x] README / CLAUDE.md entries

- [x] After push + plugin reinstall: verify the skill's overlay injection runs without a permission abort, and that a general-purpose subagent receives the SubagentStart pointer

## Summary

**Completed 2026-11-24** — Final check passed on 2026-11-24. The write-comments overlay injection ran with no permission prompt; in a project with no overlay it printed "This project has no overlay.". A general-purpose subagent dispatched as a probe received the pointer verbatim as SubagentStart hook context and listed decaf-quality:write-comments among its skills. The backstop draft dcc-642p was scrapped as unneeded.
