---
# dcc-ce0m
version: 1
title: 'bugs-sp brief v3: closed-set parking reasons — stop filtering defects on intentionality'
status: in-progress
type: feature
priority: high
created_at: 2026-08-17T11:03:57Z
updated_at: 2026-08-17T11:08:40Z
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
- [ ] Run (operator-gated): **3 repeats** on the two pilot subjects — the effect targeted (2–3
      defects/run) is the size of the seat variance at 2 repeats — and fold in; readout against
      the pool: expected ceiling ≈9/16 reported at ≥60% defect share

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
