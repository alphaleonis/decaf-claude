---
# dcc-p2th
version: 1
title: Curated merge of the skill surface to main (no competition/, reports/, bench commands, dev script, nibs)
status: completed
type: task
created_at: 2026-08-21T08:17:21Z
updated_at: 2026-08-21T08:21:32Z
order: zzzzy
---

Port the preset/axes skill work from `tuning` to `main` without any tuning-specific content.

- [x] Reword the two competition/ path citations in code-review/SKILL.md to name the tuning branch (they would dangle on main)
- [x] Drop the stale "Not yet merged to `main`" sentence from CLAUDE.md (stale on both branches)
- [x] Branch off main; checkout the skill surface from tuning (decaf-quality agents+skills+README, decaf-build skills+README, 3 conventions files, root README.md)
- [x] CLAUDE.md: tuning's version minus the benchmark section
- [x] Verify the merge set contains no competition/reports/bench references; merge --no-ff into main
- [x] Merge main back into tuning to record the merge point

Excluded by operator decision: competition/, reports/, .claude/commands/bench-*.md, scripts/install-dev-plugin.sh, the 88 benchmark nibs (tuning remains the tuning workspace).

## Summary

**Completed 2026-08-21** — Merged as main f544560 (curated port 03d0e96, 30 files: decaf-quality agents+skills+README, decaf-build skills+README, 3 conventions files, root README.md, CLAUDE.md minus the benchmark section). Excluded per operator decision: competition/, reports/, bench-* commands, install-dev-plugin.sh, benchmark nibs. Merge point recorded on tuning (d546194); merge branch deleted.

One regression caught and fixed during verification: the checkout-based port silently reverted main-only commit 40602ca (no-`name` dispatch rule + spawn-ack tripwire, dcc-8yio) because checkout replaces wholesale instead of merging. Re-applied to the preset-era text on tuning (9cc75d1) and cherry-picked to main (7491d3c), extended to the bugs path's single-seat dispatch. Lesson: before a checkout-based port, diff BOTH directions — target-only commits in the ported paths get clobbered.
