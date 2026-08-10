---
# dcc-ixyy
version: 1
title: 'Build the pooled-adjudication corpus: size x application type, reputable repos'
status: completed
type: task
priority: high
created_at: 2026-08-10T18:26:35Z
updated_at: 2026-08-10T19:55:42Z
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
## Acceptance

- [x] Grid filled — all 12 cells built, no deferral. Table in `v2/analysis/CANDIDATES.md`
- [x] Every subject from a review-disciplined repo and merged post-cutoff, both recorded in the
      fixture (`merged_at`, `vintage.merged`; status computed per model at analysis time)
- [x] Fixtures built via METHODOLOGY-v2 section 4 steps 1-4 only (no key) — `v2/pooled/*/fixture.json`
- [x] >=5 admissible human review threads per subject — met on 10 of 12; see the note below
- [x] Step 8 airtightness check passes per fixture — depth >=500, clean tree, no remote, base
      present, no PR-number reference in any checkout

**Two cells fall short of the >=5 admitted-thread target** and are recorded rather than hidden:
`immich#28886` (contract/S) admits 2 of 5, and `sveltejs/kit#15685` (library/S) admits 3 of 8. Small
diffs give the mechanical filter little to match against. Both remain usable — they contribute to
pooled adjudication regardless, since that does not depend on threads — but their thread-recall axis
is thin and should not be read on its own. Replacing them means finding small PRs with dense review,
which the screen showed to be the scarcest combination in the corpus (13 of 547 candidates).

## Summary

**Completed 2026-08-10** — Full 12-cell grid built. Fixtures and thread sets in `v2/pooled/`; checkouts gitignored and rebuilt
from pinned SHAs by `v2/build_pooled_repo.sh`.

**120 admitted review threads across 12 subjects**, against the anchor's 12 key entries across 7 — the
tenfold jump in miss-detector signal that justified the instrument. Nine repos, max two each, five
languages that fell out rather than being selected for.

The checkpoint rule needed measuring, not assuming: threads disperse across **4 to 15 commits** per PR,
the most-commented commit holding only ~42%. So the checkpoint is the commit the earliest review
comment targeted — the state at which human review began — with admission applied per thread (file in
the checkpoint diff, line in a changed hunk). That recovers 120 where a modal-commit rule gives ~92.

Verified rather than asserted: merge-base correctness per subject (every checkpoint diff touches dirs
the PR touches — the failure mode that once turned 18 files into 240); diff-size sanity, where two
outliers were investigated and `grafana#117615`'s 3.14x proved to be genuine branch shrinkage, its
checkpoint holding test scaffolding reviewers later consolidated; and Step 8 on all 12.

Two silent failures caught and fixed in tooling: `find_candidates.sh` reported "0 candidates" for two
repos that have ~100, from transient GraphQL errors swallowed by `2>/dev/null`; and
`build_pooled_repo.sh` aborted before printing its report because `grep` exits 1 on no match under
`set -e`. Both now fail loudly.

Carried forward: two small-diff cells admit fewer than 5 threads (2 and 3). They stay usable for
pooled adjudication, which does not depend on threads, but their thread-recall axis is thin. Small
PRs with dense review are the scarcest combination in the corpus — 13 of 547 candidates.
