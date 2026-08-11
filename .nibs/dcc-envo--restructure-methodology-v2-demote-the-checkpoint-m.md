---
# dcc-envo
version: 1
title: 'Restructure METHODOLOGY-v2: demote the checkpoint machinery'
status: completed
type: task
priority: normal
created_at: 2026-08-10T17:43:28Z
updated_at: 2026-08-11T09:41:16Z
parent: dcc-ho2w
order: 8s
---

The document still presents the review checkpoint as v2's organizing idea. Three subjects built end
to end say otherwise: **the checkpoint choice changed the answer in 1 of 3**, and in that one only
because the merged head turned out unscorable.

| | Subject 9 | Subject 11 | Subject 2 |
|---|---|---|---|
| What review did to the defect | introduced it | removed it | transformed it |
| Better checkpoint | merged head | as-opened | final head (= merged) |

What actually earned its keep is the leak-proofing and the key-building discipline, which caught
three invalid ground truths before any of them cost a review cell.

## Changes

- Lead with the leak controls and the key-building procedure; the checkpoint becomes a tool used when
  the defect's location demands it, not the frame
- Fold in the scoring-model decision, replacing the key-only framing
- Correct the stale example: the claim that mechanical filters drop the `topology.go` and
  `hollow_proxy.go` threads is true of the as-opened checkpoint and FALSE at push #2, where the file
  filter rejected 0 of 46
- Record the four procedure bugs found by execution as standing warnings (re-shallowing fetch, weak
  mechanical filters, force-pushes not enumerating heads, full-revert giving no localization)

## Acceptance

- [x] Checkpoint section reframed as conditional, with the 1-of-3 evidence stated
- [x] No stale examples or superseded framing remain

## Summary

**Completed 2026-08-11** — **Completed 2026-08-11.** The document is restructured; the checkpoint is now a step inside subject
construction rather than a section of its own, and the two construction procedures are one section.

New shape (section numbers changed — a translation note is in the header and in `HARNESS-REVIEW.md`):

| Was | Is |
|---|---|
| §2 "What v2 reviews: the review checkpoint" | dissolved into §4a |
| §3 instruments | **§2** |
| §5 access controls | **§3** |
| §4 anchor + §4A pooled | **§4** — 4a checkpoint, 4b shared spine, 4c pooled, 4d anchor |
| §6 what v2 cannot fix | **§5** |
| §7 open questions | **§6** |

§1 now closes by naming what earned its keep, in measured order: the access controls, then the
construction discipline. The checkpoint is introduced in §4a as one of two selection rules, with the
1-of-3 evidence and the sobering count stated where the choice is made.

**The §4/§4A merge (`dcc-3cm6` M2) is done.** The shared spine — merge base, fixture build, the
presence-at-T admission rule, airtightness — is stated once in §4b; §4c (pooled) and §4d (anchor) are
deltas on it. Anchor Steps 0–8 became A1–A6, pooled P1–P6 became P1–P3.

Four stale or false passages corrected:

1. **The `topology.go` / `hollow_proxy.go` exclusion example was false at the checkpoint actually
   used.** Verified against the API: the as-opened diff is 11 files and contains neither; push #2 —
   subject 9's checkpoint — contains both, and the file filter rejected 0 of 46 threads there. The
   passage now says which checkpoint each claim belongs to.
2. **Step 7's example `rejected` entry was fabricated and false** — it claimed `topology.go` was
   rejected as "file absent from the checkpoint diff". Replaced with a real entry from the built key
   (the 5-minute poll timeout, rejected on presence-at-T). Added `must_not_require`, which the real
   key carries and the documented schema omitted.
3. **"~31 candidate key entries against 2 at the merged head" was a pre-execution projection stated
   as a result.** Building the key returned **2** admitted entries against **3** in the v1
   merged-head key. Now recorded as a falsified projection with the warning that candidate count is
   not entry count.
4. **Subject 11's early-checkpoint entry count was "≥1"**; the built key has 2.

The four execution-found procedure bugs are indexed as a standing-warnings table at the head of §4
and kept inline at the step each one breaks. Also folded in: the §3 Tier 1 `--json` allowlist and URL
date-check holes, the `docs-at` outage-as-absence bug, and the void `build-capability.json` — all
from `dcc-3cm6`, none of which had reached the methodology.

Cross-references updated in 20 places across scripts, scoring, commands, `CLAUDE.md`, `v2/README.md`,
`CANDIDATES.md`, `GROUND-TRUTH-AUDIT.md`, `STEP0-FEASIBILITY.md` and 15 fixtures. 25 scoring tests
still pass; every edited script parses.
