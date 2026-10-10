---
# dcc-fa60
version: 1
title: Port bibbla's pending comment rules into conventions/comments.md
status: completed
type: task
created_at: 2026-10-10T15:47:54Z
updated_at: 2026-10-10T15:50:33Z
order: zzzzzzy
---

Port the general comment rules that bibbla settled (`bibl-wgmg`, "Pending in the plugin" in `../bibbla/.decaf/conventions/comments.md`) into `conventions/comments.md`. General rules are worded for any language; C#-specific rules go in a C# subsection.

`comment-lint.py` stays in bibbla: it reads only C#, holds bibbla-specific checks (nib ids, glossary exemptions), and the write-comments rewrite mode reads every comment anyway.

- [x] Port What-a-comment-is-for rules (sources for vendor facts and figures, guarding reasons, one home for a rule)
- [x] Port Doc comments rules, C# subsection for the C#-only ones
- [x] Port Tests rules
- [x] Port Wording additions (colon lists, imperative for instructions, passive exception, technical phrasal verbs, idioms with two readings, qualified glossary rows)
- [x] Remove the section from the bibbla overlay and the sentence in bibbla CLAUDE.md

## Summary

**Completed 2026-10-10** — Moved the general comment rules that bibbla settled (`bibl-wgmg`) into `conventions/comments.md`: sources for vendor facts and figures, one home for a rule, more doc-comment rules with a C# subsection, a new Tests section, and wording additions. Generalized bibbla's wording for any language and work tracker. The C# cref rule says the compiler warns, which a scratch build confirmed (CS0419, CS1574). Bibbla's own build fails on it because of TreatWarningsAsErrors.

Did not port comment-lint.py: it reads only C#, has bibbla-specific checks, and the rewrite mode of write-comments reads every comment anyway.
