---
# dcc-f2nf
version: 1
title: Subject vintage and corpus refresh policy
status: todo
type: task
priority: normal
created_at: 2026-08-10T17:43:02Z
updated_at: 2026-08-10T17:43:41Z
parent: dcc-ho2w
order: Zs
---

Six of ten dated subjects predate the benchmark model's Jan 2026 training cutoff, including subject
9. The judge (`claude-opus-5[1m]`, cutoff May 2026) may also know the defects. Memorization is
unfalsifiable — you can prove a tool did not call `gh`, never that it did not recall.

Only vintage bounds it, and vintage decays: every model release moves the cutoff forward and retires
more of the corpus. This is a maintenance property, not a one-time fix.

Cutoffs on record (training data, not reliable-knowledge — see the milestone body for both columns):
Opus 5 May 2026 · Sonnet 5 / Fable 5 / Opus 4.8 / Opus 4.7 Jan 2026 · Sonnet 4.6 Jan 2026 ·
Opus 4.6 Aug 2025 · Haiku 4.5 Jul 2025.

Note the per-model complication: `anthropic-code-review` hard-pins Sonnet and Haiku regardless of
`BENCH_MODEL`, so the same subject can sit on opposite sides of the cutoff for different reviewers in
one comparison.

## Decide

- Minimum vintage for admission, and whether pre-cutoff subjects are excluded or reported separately
- Retirement trigger as roster cutoffs advance
- Refresh cadence and where replacements are sourced (candidates: recent merged PRs with a confirmed
  follow-up fix, harvested on a date window rather than a nightly watch)
- Whether a "possibly memorized" tag on results is sufficient disclosure when a subject cannot be
  replaced

Currently vintage-safe: subjects 2, 3, 5, 6. Only subject 2 has a v2 key.

## Acceptance

- [ ] Policy written into METHODOLOGY-v2.md
- [ ] Each subject tagged with its vintage status against the current roster
- [ ] Replacement sources identified for subjects that fail
