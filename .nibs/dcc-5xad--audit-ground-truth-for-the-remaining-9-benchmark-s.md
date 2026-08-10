---
# dcc-5xad
version: 1
title: Audit ground truth for the remaining 9 benchmark subjects
status: todo
type: task
priority: high
created_at: 2026-08-10T15:05:01Z
updated_at: 2026-08-10T15:05:01Z
order: zzzzk
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

Audit each: locate the defect, verify it is present in the reviewed diff, confirm the stated ground
truth matches it, and count admissible key entries.

- [ ] 1 — dotnet/efcore#32770 (csharp/small) — reverted next day; 100 cross-refs (worst leak surface)
- [ ] 3 — dotnet/runtime#127146 (csharp/large) — JIT casting; 3 human + 5 Copilot threads
- [ ] 4 — microsoft/TypeScript#61928 (typescript/small) — bug manifests downstream, not in TS's own tests
- [ ] 5 — microsoft/vscode#308517 (typescript/medium) — 0 human threads, bot-only; the ONLY subject with 0 cross-refs
- [ ] 6 — microsoft/vscode#320685 (typescript/large) — reverted twice, **no single named bug** (fuzzy key expected)
- [ ] 7 — prometheus/prometheus#13777 (go/small) — 0 threads; fixture calls this the crispest ground truth
- [ ] 8 — kubernetes/kubernetes#129768 (go/medium) — merged then reverted in a day
- [ ] 10 — BurntSushi/ripgrep#3185 (rust/small) — solo maintainer, 0 threads; bug isolated to 1 of 2 commits
- [ ] 12 — rust-lang/rust#153540 (rust/large) — PARTIAL revert of one commit; ~270 diff lines are .stderr fixtures

## Replacement criterion

A subject is REPLACED, not repaired, when any of these hold:

- the escaped defect was never root-caused, so no `must_flag` can be written (subject 11)
- the defect is absent from the reviewed diff in the shape the ground truth indicts
- fewer than ~2 admissible key entries survive Step 6, making the subject too thin to discriminate

Prefer replacements that are vintage-safe (merged after the roster's newest training cutoff) and
lightly force-pushed.

## Acceptance

- [ ] All 9 audited against METHODOLOGY-v2.md section 4
- [ ] Each classified: usable as-is / needs a different checkpoint / replace
- [ ] Replacements sourced for any that fail
- [ ] No full bench-run authorized until this is complete
