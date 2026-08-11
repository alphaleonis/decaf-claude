---
# dcc-mjj5
version: 1
title: 'Add the null arm: absolute noise floor on a defect-free change'
status: completed
type: task
priority: high
created_at: 2026-08-10T19:20:06Z
updated_at: 2026-08-11T06:41:46Z
parent: dcc-ho2w
blocked_by:
    - dcc-595v
order: 8V
---

The third instrument from [[dcc-595v]]. Pooled adjudication measures precision **relative to the
pool**, not to truth — every tool is scored against what the tools collectively found. That gives no
absolute scale, and no way to answer "how much of this output is noise in the first place?"

The null arm supplies it: run the roster on a **substantive change with no known defect**, where
approximately every finding is a false positive by construction. It needs no answer key and no
ground truth of any kind.

This matters because of what the v1 verdict distribution showed — of 98 distinct clusters on one
subject, only 6 were *wrong* while 58 were *trivial*. Tools fail by immateriality, not error, and
that is exactly what a null arm quantifies: given nothing to find, how much does each tool still say?

## Selecting a null subject

The hard part is establishing "no known defect" without it being a claim we cannot support:

- A substantive merged PR from a review-disciplined repo, old enough that a regression would have
  surfaced, with **no revert, no linked regression issue, and no follow-up fix** touching the same
  lines. Verify the last of these against the file's later history rather than assuming it.
- "No *known* defect" is the honest framing — findings are only *approximately* false positives.
  Where the judge rates a null-arm finding as genuinely valid, that is a real result worth keeping,
  not an error to suppress: it means the tool found something the project missed.
- Match size and application type to a scored subject so the noise floor is comparable rather than
  measured on a trivially different change.

## Acceptance
## Acceptance

- [x] **Null-subject selection criteria written into METHODOLOGY-v2 section 3** — including the two
      corrections that only surfaced by building it: a null subject is checkpointed at the MERGE
      commit (a pre-review checkpoint would still contain the thread-flagged issues, making it
      non-null), and its diff is `merge^1..merge`.
- [x] **At least one null subject per size bucket** — three built, all `backend`, matched to scored
      subjects and verified by `v2/verify_null.sh`:
      | Size | Subject | Diff | Soak | Verdict |
      |---|---|---|---|---|
      | S | `jellyfin/jellyfin#16695` | 3f +24/-6 | 99d | NULL-OK |
      | M | `grafana/grafana#122269` | 17f +223/-14 | 98d | adjudicated clean |
      | L | `immich-app/immich#28204` | 33f +456/-185 | 99d | adjudicated clean |
      Both REVIEW verdicts were adjudicated at line level, not waved through: grafana's hit is an
      append-only feature-toggle registry (different lines by construction) and immich's is a
      different endpoint in a shared e2e spec.
- [ ] **Roster run against it and findings-per-cell reported per tool** — deferred to [[dcc-vkeh]],
      which is where cells are actually spent. Fixtures, checkouts and build capability are ready;
      all three subjects are buildable.
- [x] **Genuinely-valid null findings reported separately** — specified in section 3 and in
      `/bench-analyze-v2`: a valid finding on a null subject is a real result (the tool found
      something the project has not noticed), not an error to fold into the noise count.

## Summary

**Completed 2026-08-11** — Three null subjects built and verified, one per size bucket, all `backend` and matched to scored
subjects so the noise floor is comparable: `jellyfin#16695` (S), `grafana#122269` (M),
`immich#28204` (L), each with ~100 days of soak.

Two design corrections surfaced only by building it:

- **A null subject must be checkpointed at the MERGE commit.** Scored subjects are checkpointed
  pre-review precisely so thread-flagged issues remain findable — which is exactly what makes them
  non-null. The null arm needs the post-review state that shipped.
- **Its diff is `merge^1..merge`.** Comparing the base branch to the merge commit yields an EMPTY
  diff, because the merge is already on that branch. All three fixtures first built as 0 files, which
  would have had cells reviewing nothing.

`v2/verify_null.sh` had two bugs worth recording, both caught by running it rather than reading it.
`since=<mergedAt>` is inclusive, so every subject flagged its OWN merge commit as a later fix. And
file-level overlap is far too coarse: shared and generated files (dependency manifests, translation
bundles, CI config, append-only registries) are touched by every subsequent fix, so it reports
REVIEW for adjudication instead of rejecting. Both REVIEW verdicts here were then adjudicated at line
level and cleared.

Operator input on vintage (2026-08-11): we are probably over-weighting the training cutoff — a
routine PR is a tiny fraction of the corpus and recalling that a specific diff shipped a defect is a
much higher bar than having seen the repo. For null subjects the constraint actively conflicts with
soak time, so soak wins and vintage is recorded rather than binding. A memorized null subject would
if anything *deflate* the noise floor, which is the conservative direction for a noise measurement.
The broader question is settled empirically by the matched-pair probe, not by argument — worth
revisiting in [[dcc-3cm6]] whether the hard post-2026-05 rule on scored subjects should also relax.

The roster run itself is [[dcc-vkeh]]; all three are buildable and ready.
