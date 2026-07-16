---
# dcc-orxl
version: 1
title: 'Competitive analysis: Claude Code code-review plugins/skills'
status: completed
type: task
created_at: 2026-07-16T11:05:19Z
updated_at: 2026-07-16T11:15:21Z
order: zzV
---

Research prominent, widely-used, well-regarded Claude Code code-review plugins/skills. Clone each into ./competition/<name>/ and write ./competition/README.md summarizing each (popularity, usage examples, provenance).

- [ ] Identify candidates via web research
- [ ] Clone/download sources into ./competition
- [ ] Capture provenance (source URL + SHA + retrieval date)
- [ ] Write ./competition/README.md

## Summary

Surveyed and cloned 10 prominent Claude Code code-review plugins/skills into ./competition, each with PROVENANCE.md (source URL + commit SHA + retrieval date), plus a competitive-analysis README.md.

Entries: (1) Anthropic code-review, (2) Anthropic pr-review-toolkit, (3) Anthropic security-guidance, (4) awesome-skills/code-review-skill, (5) CodeRabbit claude-plugin, (6) Tag1 comprehensive-review, (7) alirezarezvani code-reviewer, (8) Trail of Bits skills, (9) agamm OWASP security, (10) obra/superpowers review skills. Honorable mentions: getsentry/skills, VibeSec, mhattingpete, jeremylongshore, travisvn awesome list, aidankinzett, Composio list.

README includes a popularity/metadata table (GitHub stars/forks/dates as of 2026-07-16), per-tool write-ups (mechanism, popularity, usage examples), a head-to-head comparison of general reviewers, and grouping into general reviewers / security specialists / methodology.
