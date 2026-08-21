---
# dcc-p2th
version: 1
title: Curated merge of the skill surface to main (no competition/, reports/, bench commands, dev script, nibs)
status: in-progress
type: task
created_at: 2026-08-21T08:17:21Z
updated_at: 2026-08-21T08:17:31Z
order: zzzzy
---

Port the preset/axes skill work from `tuning` to `main` without any tuning-specific content.

- [ ] Reword the two competition/ path citations in code-review/SKILL.md to name the tuning branch (they would dangle on main)
- [ ] Drop the stale "Not yet merged to `main`" sentence from CLAUDE.md (stale on both branches)
- [ ] Branch off main; checkout the skill surface from tuning (decaf-quality agents+skills+README, decaf-build skills+README, 3 conventions files, root README.md)
- [ ] CLAUDE.md: tuning's version minus the benchmark section
- [ ] Verify the merge set contains no competition/reports/bench references; merge --no-ff into main
- [ ] Merge main back into tuning to record the merge point

Excluded by operator decision: competition/, reports/, .claude/commands/bench-*.md, scripts/install-dev-plugin.sh, the 88 benchmark nibs (tuning remains the tuning workspace).
