---
# dcc-ixyy
version: 1
title: 'Build the pooled-adjudication corpus: size x application type, reputable repos'
status: todo
type: task
priority: high
created_at: 2026-08-10T18:26:35Z
updated_at: 2026-08-10T19:19:51Z
parent: dcc-ho2w
blocked_by:
    - dcc-f2nf
order: F
---

Superseded by the instrument decision in [[dcc-595v]]. This is no longer "replace 5 rejected
subjects" — pooled adjudication needs **no revert, no regression issue, and no answer key**, so the
selection criteria change completely and the corpus gets much cheaper to build.

## Selection criteria

1. **A repository with genuine review discipline.** This is now the primary criterion, and it is a
   deliberate choice against using our own PRs: the review quality there is not trusted and the
   codebases are legacy. Reputable OSS repos give substantive human review threads, which serve as a
   **non-scoring validity check on the judge** — an adjudicator that systematically rejects what
   expert reviewers flagged is visibly miscalibrated.
2. **Merged after the roster's Jan-2026 training cutoff.** Trivial to satisfy now that no revert is
   required, and it removes the memorization exposure that most of the current corpus carries.
3. **A substantive change** — real logic, not a rename or a lockfile bump.
4. No fixing/reverting PR needed, so the cross-reference leak surface is largely absent by
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

Two or three surviving audited subjects can fill library/internals cells, since that is what they are.
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
- [ ] Human review threads captured per subject as the judge's validity check — stored, not scored
- [ ] Step 8 airtightness check passes per fixture
