---
# dcc-ixyy
version: 1
title: 'Build the pooled-adjudication corpus: size x application type, reputable repos'
status: in-progress
type: task
priority: high
created_at: 2026-08-10T18:26:35Z
updated_at: 2026-08-10T19:36:27Z
parent: dcc-ho2w
blocked_by:
    - dcc-f2nf
order: F
---

Superseded by the instrument decision in [[dcc-595v]]. This is no longer "replace 5 rejected
subjects" — pooled adjudication needs **no revert, no regression issue, and no answer key**, so the
selection criteria change completely and the corpus gets much cheaper to build.

## Selection criteria

1. **A repository with genuine review discipline, and a PR carrying substantive human review
   threads.** Primary criterion, and a deliberate choice against our own PRs: the review quality
   there is not trusted and the codebases are legacy.

   The threads are **scored, not decorative**. They are an independent list of things an expert
   thought worth raising, not derived from tool output, so "reviewers flagged X and no tool flagged
   X" is a detectable miss — precisely what pooled adjudication is structurally blind to. They also
   double as a calibration check on the judge.

   Target **>=5 admissible threads** per subject after the in-diff and `must_flag` filters. Screen
   for this before committing to a subject: the v1 corpus averaged 3 threads per subject with one
   subject holding 12 and two holding zero, because it was selected for reverts rather than for
   review.
2. **Merged after 2026-05** — out of window for the newest roster model AND the judge (Opus 5,
   cutoff 2026-05), not merely for `BENCH_MODEL`. Hard admission rule ([[dcc-f2nf]]). Trivial now
   that no revert is required.
3. **Build matched vintage pairs where cheap** — same repo, same size bucket, same application type,
   one subject either side of the cutoff. This is the only way to measure the memorization effect
   size rather than merely disclose it: unmatched pre/post comparisons confound vintage with
   difficulty. A handful of pairs is enough; it does not need to cover the grid.
4. **A substantive change** — real logic, not a rename or a lockfile bump.
5. No fixing/reverting PR needed, so the cross-reference leak surface is largely absent by
   construction. The `gh` shim still applies: review threads leak human findings a tool could parrot.

## Grid: size x application type

Language is deliberately **not** an axis ([[dcc-595v]]). Size is kept — it drives cost, wall-clock and
decaf's own roster sizing (the roster N is derived from executable lines), so it is a real independent
variable for tool behavior.

| | Small (<~100 lines) | Medium (~100-500) | Large (>~500) |
|---|---|---|---|
| **Application / UI** | | | |
| **Contract-crossing (client+server)** | | | |
| **Backend service** | | | |
| **Library / framework internals** | | | |

The audited survivors **cannot** fill pooled cells: only subject 2 (2026-07) clears the 2026-05 rule,
the rest are pre-cutoff. They serve as the anchor ([[dcc-9ncz]]) and as matched-pair vintage probes.
So library/internals cells need fresh post-cutoff subjects like every other row.
The grid is affordable now only because pooled adjudication yields ~50-100 clusters per subject rather
than 1-3 key entries — a 12-cell grid was decorative under key-based scoring and is well powered here.

Contract-crossing is the highest-value row and the current corpus has none of it: the defect lives in
the *mismatch* between two files, and it is the only shape that exercises multi-specialist dispatch
(`typescript-reviewer` + `dotnet-reviewer` together).

## Candidates already found

From the Step 0 screen (`v2/analysis/STEP0-FEASIBILITY.md`) — these were screened for a *named
mechanism*, which is no longer required, so treat them as evidence the repos have discipline rather
than as a shortlist:

- **mattermost** (Go + React) and **PostHog** (Django + React + ClickHouse) scored at or above
  kubernetes and prometheus on revert discipline
- **grafana** (Go + React), **immich** (TS + Dart), **jellyfin** (.NET + web UI) all viable
- `outline` and `twentyhq` scored near zero — younger and smaller, avoid

## Acceptance

- [ ] Grid filled: a subject per cell, or an explicit note where a cell is deliberately empty
- [ ] Every subject from a review-disciplined repo and merged post-cutoff, both recorded in the fixture
- [ ] Fixtures built via METHODOLOGY-v2 section 4 **steps 1-4 only** (no key)
- [ ] >=5 admissible human review threads per subject, triaged with the in-diff + `must_flag` filters and committed as a scored target
- [ ] Step 8 airtightness check passes per fixture
