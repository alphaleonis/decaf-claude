---
# dcc-ly77
version: 1
title: 'benchmark: valid-minor/trivia suggestion-tier split + severity calibration, regrade subjects 2/3/9/10'
status: completed
type: task
created_at: 2026-07-22T16:25:22Z
updated_at: 2026-07-22T16:40:13Z
order: zzs
---

The findings-quality methodology treats every nitpick as pure noise, which structurally punishes
improvement-suggestion output (conventions, naming, doc fixes, coverage gaps) and flatters terse tools.
Approved design (operator, this session):

- Split the `nitpick` verdict into `valid-minor` (true; specific one-shot fix; anchored in an in-repo
  convention/standard or objective doc/spelling correctness; maintainers would take it as a patch
  without debate — the class converges under the fix-and-rerun test) vs `trivia` (taste-only,
  speculative, out-of-scope/pre-existing, duplicative, or an unbounded suggestion class). Borderline → trivia.
- Substantive precision stays (TP+valid-other ÷ reported); new columns: suggestions/run (valid-minor),
  trivia/run (replaces noise/run).
- New severity-calibration metric: P(judged substantive | tool flagged critical/high).

## Todo
- [x] METHODOLOGY.md: rubric + new metrics documented
- [x] compute_metrics.py: valid_minor_per_cell, trivia_per_cell (legacy nitpick folded), severity_calibration
- [x] render_report.py: leaderboard columns + glossary entries
- [x] Blind regrade of the 107 nitpick clusters across subjects 02/03/09/10 (diff-anchored, identity-stripped) — 26 valid-minor / 81 trivia
- [x] Merge regrades into analysis.json (audit field regraded_from), recompute metrics, re-render HTML
- [x] report.md addendum per subject + spot-check queue for low-confidence regrades (8 items <60)

## Summary

Implemented the suggestion-tier split (valid-minor vs trivia) and severity-calibration metric, and
blind-regraded all 107 nitpick clusters across subjects 02/03/09/10 → 26 valid-minor / 81 trivia.
Cross-subject: suggestion yield prt 4.5/run > ours 3.6 > tag1 3.5 > anthropic 3.2 > superpowers 0.9;
severity calibration anthropic 90% > tag1 82% > ours 71% ≈ prt 70% > superpowers 66% (n/a subject-10,
pilot data lacks per-report severities). 8 regrades at confidence 55 flagged for human spot-check.
Rubric anchored on: verifiable truth, one-shot fix, finite in-repo anchor, maintainer-would-take-it,
fix-and-rerun convergence; borderline → trivia (default-down).
