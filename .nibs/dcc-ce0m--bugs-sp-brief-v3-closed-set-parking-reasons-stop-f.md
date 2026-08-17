---
# dcc-ce0m
version: 1
title: 'bugs-sp brief v3: closed-set parking reasons — stop filtering defects on intentionality'
status: completed
type: feature
priority: high
created_at: 2026-08-17T11:03:57Z
updated_at: 2026-08-17T13:08:40Z
parent: dcc-hyxw
order: ark
---

Follow-up from [[dcc-pulk]] / `v2/analysis/BUGS-SP-RESULTS.md`. Diagnosis (operator-confirmed
2026-08-17): `bugs-sp` finds 9–10 of the 16 pool defects per run and parks ~4, of which 2–3 are wrong
— medium/high defects the seat verified as real and then set aside on **intentionality** grounds
("the comment/doc/test says it's intended", "unreachable today") or by mis-routing a Low to
`minor, out of reach`. The brief filters on class and confidence as designed, and additionally on
intentionality, which is not the reviewer's call to make silently. Fail-closed prose (brief v2)
under-fired: c07 was parked again in both repeats with the exact wording the rule named.

## The change (brief v3)

- Considered But Not Flagged takes a **closed set of parking reasons** and nothing else:
  `[unverified]` (anchor 25), `[false]` (anchor 0), `[pre-existing]` (`narrow` only),
  `[minor]` (`narrow` only; nit-level items only — anything the seat would rate Low or above is a
  finding). "Intended by design", "documented", "commented", "tested as such", "unreachable today"
  are not parking reasons: an item whose only reason is one of those is a finding at anchor 50
  with that reason in its Evidence field.
- Orchestrator format pass (`bugs-sp` path): count CBNF entries lacking a valid tag and record it
  in the report header; never re-tier.
- Benchmark arm `ours-bugs-sp3`; v1/v2 cells stay frozen.

## Acceptance

- [x] Brief edited (closed-set reasons; `[minor]` barred for Low+; fail-closed prose replaced by
      the rule); SKILL format-pass check added; dev copy synced
- [x] Arm `ours-bugs-sp3` in `run_cell_v2.sh` + `tools.json`
- [x] Smoke test on a scratch repo with a planted "documented as intended" defect: the seat
      reports it (tagged reason in Evidence), does not park it — passed (see below)
- [x] Run: 3 repeats on the two pilot subjects, all CLEAN, folded in — `BUGS-SP-RESULTS.md` § Brief
      v3. Composition 67% ✓, stability best ✓, seat cost at parity ✓; recall 6/16 ✗ — per-cell
      real defects reported flat on prom (3.0 across all three briefs), down on efcore. e13 moved
      (1/3); c05 re-parked under `[unverified]` with the intent rationale (tag as costume); c107
      newly reported once; e02 lost 2/2 → 0/5 because v2/v3 seats did not probe SQL Server SQL
      generation — a detection change, not disposition

## Smoke test (2026-08-17, brief v3)

Scratch repo; the change replaces a `ValueError` on `page < 1` with `page = max(page, 1)`, and a
comment, the docstring, a new `docs/pagination.md`, and a new passing test all declare the clamp
intentional — the exact "documented as intended" trap that parked prom c05/c07 and efcore e13.

Two seats run on it in parallel: the registered agent type (which turned out to be running the
cached **v2** brief — it wrote "reported under the fail-closed rule" and untagged CBNF entries) and
the **v3** body inlined through a general-purpose agent. Both **reported** the trap as #1 Medium /
anchor 50 / `executed`, with the doc cited in Evidence as the counter-argument and the doc's own
rationale turned against the code ("off-by-one covers page 0, the code admits every negative"). Both
also caught the comment/code mismatch as a Low. The v3 run's Considered But Not Flagged carries the
closed-set tags exactly (`[pre-existing]` ×2, `[unverified]`, `[false]`, plus one untagged process
note); no `minor` off-ramp was used. Tree clean afterwards in both.

Caveat for future in-session smoke tests: the registered agent type is cached from an earlier load
and does not pick up brief edits within a session — inline the body via general-purpose, as here.
Fresh harness sessions read the file from disk.

## Summary

**Completed 2026-08-17** — Implemented, smoke-tested (the seat reports a comment/doc/test-backed "intended" behavior change
as a Medium with the doc as counter-argument), run at 3 repeats and scored. v3 meets composition
(67% defect), stability (Jaccard 0.59/0.67) and seat-cost parity; recall stays at 6/16 union and
3.0 real defects per cell on prometheus across all three briefs. The closed set moved e13 (1/3)
but c05 was re-parked under a legal tag with the intent rationale, and the larger movements
(e02 2/2 → 0/5, c03, c07) are detection changes — the v2/v3 seats did not probe SQL Server SQL
generation — not disposition. Verdict: keep v3 as the bugs-sp brief; stop iterating on parking
rules; the remaining gap to superpowers on prometheus (~1.3 real defects/cell) is exploration
breadth. Full write-up in `v2/analysis/BUGS-SP-RESULTS.md` § Brief v3.
