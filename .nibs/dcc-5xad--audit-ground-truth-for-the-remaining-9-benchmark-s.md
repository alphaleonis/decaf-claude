---
# dcc-5xad
version: 1
title: Audit ground truth for the remaining 9 benchmark subjects
status: completed
type: task
priority: high
created_at: 2026-08-10T15:05:01Z
updated_at: 2026-08-10T18:27:46Z
parent: dcc-ho2w
order: R
---

Three subjects have been through the [[dcc-ho2w]] v2 key-building procedure as a proof of concept.
**Two of the three had invalid ground truth.** Base rate of bad keys is high enough that no subject
should be trusted as presented, and a full bench-run against unaudited keys would produce scores
graded against defects that are not in the reviewed diff.

## Done (3)

| # | Subject | Outcome |
|---|---|---|
| 9 | kubernetes#130837 | key built, 2 entries. Defects were INTRODUCED at push #2; merged head is the better checkpoint (3 entries) |
| 11 | tokio#7757 | **GROUND TRUTH INVALID.** Fixture indicts a Release/AcqRel ordering bug that was FIXED during review and is absent from the merged code. The hang that forced the revert was never root-caused, so the escaped defect is UNSCORABLE |
| 2 | aspnetcore#67075 | key built, 2 entries (one provisional silent-fix). Defect was TRANSFORMED by review. **Fixture claims 9 human threads; API returns 4.** Vintage-safe (merged 2026-07-09) |

## Remaining (9)
## Remaining (9)

All audited 2026-08-10. Verdicts and evidence: `competition/benchmark/v2/analysis/GROUND-TRUTH-AUDIT.md`.

- [x] 1 — dotnet/efcore#32770 — **usable**, ~2 entries (assert/`-1` sentinel; issue #32944 stack trace)
- [x] 3 — dotnet/runtime#127146 — **replace**, bare CI failure list, total revert
- [x] 4 — microsoft/TypeScript#61928 — **replace**, downstream crash never stated in TS terms
- [x] 5 — microsoft/vscode#308517 — **replace**, GROUND TRUTH INVALID (all 3 findings fixed pre-merge)
- [x] 6 — microsoft/vscode#320685 — **replace**, no named bug ("more than normal regressions")
- [x] 7 — prometheus/prometheus#13777 — **usable**, 1 entry; crispest defect in the corpus
- [x] 8 — kubernetes/kubernetes#129768 — **usable**, ~2 entries; root cause only in re-land #133995
- [x] 10 — BurntSushi/ripgrep#3185 — **usable**, 1 entry; read-loop vs `--line-buffered`
- [x] 12 — rust-lang/rust#153540 — **usable**, ~3 entries; richest key available
## Replacement criterion

A subject is REPLACED, not repaired, when any of these hold:

- the escaped defect was never root-caused, so no `must_flag` can be written (subject 11)
- the defect is absent from the reviewed diff in the shape the ground truth indicts
- fewer than ~2 admissible key entries survive Step 6, making the subject too thin to discriminate

Prefer replacements that are vintage-safe (merged after the roster's newest training cutoff) and
lightly force-pushed.

## Acceptance

- [x] All 9 audited against METHODOLOGY-v2.md section 4 — evidence in `v2/analysis/subject-NN/audit/`
- [x] Each classified: usable as-is / needs a different checkpoint / replace — `v2/analysis/GROUND-TRUTH-AUDIT.md`
- [x] Replacements sourced for any that fail — scoped and handed to [[dcc-ixyy]] (5 subjects, incl. the whole TS row)
- [x] No full bench-run authorized until this is complete — [[dcc-plsq]] now blocked by [[dcc-ixyy]]

## Summary

**Completed 2026-08-10** — All 9 audited. **5 of 12 subjects rejected** (3, 4, 5, 6, 11) — a worse base rate than the 2-of-3
that motivated this. Seven survive: 1, 2, 7, 8, 9, 10, 12. Evidence per subject in
`v2/analysis/subject-NN/audit/`, regenerable via `v2/audit_subject.sh`; verdicts and reasoning in
`v2/analysis/GROUND-TRUTH-AUDIT.md`.

**The entire TypeScript row is gone** (4, 5, 6), so the language x size grid no longer holds and no
TypeScript claim is available from this corpus. Sourcing 5 replacements is [[dcc-ixyy]]; [[dcc-plsq]]
is now blocked on it.

Subject 5 failed the same way as 11 and for the same reason: the key was written from what reviewers
*said* rather than what the merged code *does*. Its fixture indicts an idle timer left running during
consumer processing; the merged code clears it before `yield` and carries a comment saying so.

Subject 8 was saved by a source the methodology did not list — its re-land PR #133995 enumerated both
gaps, where the revert body only said "I suspect". Added to Step 5.

Three methodology changes landed from this: Step 0 triages on whether the fix names a mechanism or a
symptom (which predicted every outcome here, cheaply); Step 5 now checks re-land PRs; Step 6 warns
that a review comment proves something was once true, never that it shipped.

Two corrections to earlier records: the fixtures' `human_threads.count` counts COMMENTS, not threads
(verified on 1, 8, 12), so the subject-2 "claims 9, API returns 4" note was a mislabel and overstated
fixture unreliability. And subjects 7 and 10 yield exactly ONE entry each, so the methodology's ">=2
entries" replacement rule would discard subject 7 — the most valid subject in the corpus. Validity
and richness conflict; raised for [[dcc-595v]] rather than settled here.
