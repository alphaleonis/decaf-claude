---
# dcc-f2nf
version: 1
title: Subject vintage and corpus refresh policy
status: completed
type: task
priority: normal
created_at: 2026-08-10T17:43:02Z
updated_at: 2026-08-10T19:30:14Z
parent: dcc-ho2w
blocked_by:
    - dcc-595v
order: D
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
## Acceptance

- [x] Policy written into METHODOLOGY-v2.md section 6
- [x] Each subject tagged with its vintage status against the current roster — per-model table in
      section 6; status is computed from (merge date, model cutoff), never stored as a boolean
- [x] Replacement sources identified for subjects that fail — no subject is dropped for vintage.
      Out-of-window subjects change role to memorization probes; new subjects come from [[dcc-ixyy]]
      under the post-2026-05 admission rule

## Summary

**Completed 2026-08-10** — Policy written into METHODOLOGY-v2 section 6.

**Vintage is a property of a (subject, model) pair, never of a subject alone.** Fixtures store the
merge date; status is computed at analysis time. A "vintage-safe" boolean baked into a fixture is
wrong the day a model ships.

The corpus table exposed something that would have silently biased the headline result: **weaker
models have older cutoffs, so more of the corpus is clean for them.** Haiku 4.5 (cutoff 2025-07) has
five usable subjects where Opus 4.8 has two and the judge, Opus 5, has one. Since
`anthropic-code-review` pins Sonnet and Haiku regardless of `BENCH_MODEL`, a pooled cross-model
comparison is confounded in the direction of flattering the weaker model. Per-cell results must now
carry the reviewer's cutoff and the subject's merge date, and no headline may pool in-window with
out-of-window cells without showing the split.

New subjects must be out of window for the newest roster model AND the judge — currently merged after
2026-05, not merely after `BENCH_MODEL`'s 2026-01. Cheap to satisfy because pooled adjudication needs
no revert. Hard admission rule on [[dcc-ixyy]].

Pre-cutoff subjects are **retained as probes rather than deleted**, which is what stops this policy
from destroying 5 of 7 survivors. Memorization is unfalsifiable in the abstract, but its effect size
is measurable via **matched vintage pairs** — same repo, same size, same application type, one either
side of the cutoff. Unmatched pre/post comparisons confound vintage with difficulty and prove nothing.
Until pairs exist, memorization is disclosed, not measured.

Retirement is a change of role, not a deletion: when a cutoff advances past a subject, it stops being
scored for that model and becomes probe material.

The judge is the worst-exposed party — one of seven subjects out of window — and under pooled
adjudication its foreknowledge biases toward rating the *famous* defect valid while judging equally
valid unfamous findings more harshly. Mitigated by the already-decided code-citation requirement and
adversarial re-judging; disclosed alongside results.
