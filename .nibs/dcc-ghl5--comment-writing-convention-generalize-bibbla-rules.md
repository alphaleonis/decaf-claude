---
# dcc-ghl5
version: 1
title: 'Comment-writing convention: generalize bibbla rules, write-comments skill, pointer hooks'
status: in-progress
type: feature
created_at: 2026-10-09T21:03:07Z
updated_at: 2026-10-09T21:10:27Z
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

- [ ] After push + plugin reinstall: verify the skill's overlay injection runs without a permission abort, and that a general-purpose subagent receives the SubagentStart pointer
