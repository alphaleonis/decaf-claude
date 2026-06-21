---
# dcc-d6d1
version: 1
title: Drop csharp-developer and go-developer agents from decaf-build
status: completed
type: task
priority: normal
created_at: 2026-06-21T12:59:19Z
updated_at: 2026-06-21T13:01:44Z
order: aw
---

Remove the two language-specific implementer agents (`csharp-developer`, `go-developer`) from decaf-build/agents/, plus all doc references.

Reverses the KEEP decision recorded in #dcc-ts2r (parent #dcc-f5dj), which kept them on the grounds they're independently invocable via the Agent/Task tool even though no skill dispatches them.

## Rationale
- **Never auto-invoked by any skill** — `tdd`/`auto-tdd`/`auto-dev` explicitly launch a *general-purpose* subagent (auto-dev SKILL.md:88, auto-tdd SKILL.md:91); zero SKILL.md references the two agents.
- **Persona conflicts with TDD** — the agents are spec-executor personas that prohibit writing tests / running the suite (RULE 1), which collides with red-green-refactor.
- **Only 2 of 5 languages** — can't replace the universal general-purpose fallback; would need new language-gated dispatch logic to matter.
- **The asset is the idiom knowledge, not the persona** — recoverable from git history; for mainstream languages a convention-reading generic subagent performs comparably (and mirrors local style more faithfully).

## Keep
- `technical-writer` stays — referenced by decaf-quality:coherence-audit (SKILL.md:26) and a distinct value prop (post-feature docs).

## Future
If a language ever underdelivers, deliver idioms as a language-gated convention file (e.g. `conventions/csharp-idioms.md`) loaded by the generic implementer — not as a re-added competing persona.

## Verification
- [x] decaf-build/agents/csharp-developer.md removed
- [x] decaf-build/agents/go-developer.md removed
- [x] decaf-build/agents/technical-writer.md retained
- [x] CLAUDE.md updated (build-agents line, dissolved-core note, dir-structure comment)
- [x] README.md build-agents line updated
- [x] decaf-build/README.md agent table updated
- [x] committed (code + nib) and pushed to main

## Summary of Changes

- Removed `decaf-build/agents/csharp-developer.md` and `decaf-build/agents/go-developer.md` (git rm). Idiom content remains recoverable from git history.
- Updated docs to drop the two from the build-agents surface:
  - `CLAUDE.md`: build-agents line, dissolved-core note (moved the two to **Dropped** with reason), directory-structure comment.
  - `README.md`: build-agents summary line.
  - `decaf-build/README.md`: agent-table intro + removed the two table rows.
- `technical-writer` retained throughout (referenced by `decaf-quality:coherence-audit`).
- Historical nibs #dcc-ts2r / #dcc-f5dj left intact as records; this nib supersedes their KEEP decision for the two developers.
- Future direction (deferred): if a language underdelivers, deliver idioms as a language-gated convention file loaded by the generic implementer — not a re-added persona.
