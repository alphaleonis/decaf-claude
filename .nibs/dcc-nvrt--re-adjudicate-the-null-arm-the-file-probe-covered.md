---
# dcc-nvrt
version: 1
title: 'Re-adjudicate the null arm: the file probe covered 12 of 33 files'
status: completed
type: task
priority: high
created_at: 2026-08-11T08:20:56Z
updated_at: 2026-08-11T10:02:41Z
parent: dcc-ho2w
order: w
---

`verify_null.sh` capped its file probe at the first 12 files and said nothing about the rest, so the
nullness adjudication recorded in [[dcc-mjj5]] covered a subset of two subjects:

| Null subject | files | probed then | never queried |
|---|---|---|---|
| `jellyfin#16695` (S) | 3 | 3 | 0 |
| `grafana#122269` (M) | 17 | 12 | 5 |
| `immich#28204` (L) | 33 | 12 | **21** |

The cap is now reported (`dcc-3cm6`). Re-running with it lifted surfaces **eight** files on
`immich#28204` carrying later fix-shaped commits, where the recorded adjudication addressed one
("a different endpoint in a shared e2e spec"). Seven are new, and one is not an e2e spec:

    server/src/middleware/global-exception.filter.ts
      fix: error log on aborted uploads (#28806)

`immich#28204` is *"refactor(server)!: structured validation error responses"* — the global exception
filter is the production file most central to what the PR changes, and a later fix touching it is
exactly the shape the line-level test exists to adjudicate.

This matters because `immich#28204` is the **large** null subject. If it is not null, the noise floor
for large changes is measured on a change that had something to find, which biases every large-subject
precision figure read against it.

Not a defect in the arm's design — the methodology already says file overlap is "a screen, not a
verdict". It is adjudication that was never done because the probe never reported the gap.

## Acceptance

- [x] All eight `immich#28204` hits adjudicated at line level, `global-exception.filter.ts` first
- [x] The five unqueried `grafana#122269` files probed and adjudicated
- [x] Verdicts recorded per subject where a later reader will find them, not only in a nib summary
- [x] If `immich#28204` fails, source a replacement large null subject before [[dcc-vkeh]] reads a
      noise floor from it

## Summary

**Completed 2026-08-11** — **Completed 2026-08-11. All three null subjects hold — no replacement needed.**

Re-ran `verify_null.sh` with the cap lifted and adjudicated every hit at line level. The method
compares the PR's **added** line texts against each later fix's **removed** line texts, which is
immune to the line drift between the two commits: a fix that repairs something this PR wrote has to
delete or rewrite a line this PR added.

| Subject | Files | Probed | Files with later fixes | Verdict |
|---|---|---|---|---|
| `jellyfin#16695` (S) | 3 | 3 | 0 | **NULL** |
| `grafana#122269` (M) | 17 | 12 (+5 excluded) | 2 — both disjoint | **NULL** |
| `immich#28204` (L) | 33 | 33 | 8 — all disjoint | **NULL** |

**The decisive one clears.** `server/src/middleware/global-exception.filter.ts` was changed by
`#28806 fix: error log on aborted uploads`, which rewrites lines 1-10 and 17-36 — it threads
`Request` through `catch`/`handleError` and moves error logging out of `fromError`
(`logGlobalError` → `onRequestError`). PR 28204 changed the `ZodValidationException` branch at lines
~40-55 and never touched logging. Zero of the 4 non-trivial lines it added appear among the 5 the
fix deletes: different region, different concern.

Worth knowing about the subject: of 33 files only **three** are production —
`global-exception.filter.ts` (+5/-5), `fetch-errors.ts` (+7/-0) and `handle-error.ts` (+12/-0) — and
the latter two have no later fix-shaped commit at all. The remaining 30 are specs and helpers, and
every fix touching those is a new test in an unrelated domain (map privacy, heatmap permissions,
non-UTC offsets, OIDC logout, search visibility).

On grafana the cap really was hiding something: `pkg/setting/setting.go` is one of the five files it
never reached, and it carries a later fix (`#128543`, annotation-service TLS). Adjudicated disjoint.
The five files excluded as shared/generated are `defaults.ini`, one docs page and the three
`toggles_gen.*` — all append-only in this PR, so there is no PR-written line for a later fix to
rewrite. Recorded rather than assumed.

Changes:

- `v2/analysis/NULL-ARM.md` — the record the arm was missing. Per-subject verdicts, the full hit
  table with adjudication, what the cap was hiding, and how to re-run.
- Each null `fixture.json` gains a `nullness` block: verdict, adjudication date, probe coverage,
  method, and an explicit `recheck` note. **Nullness is a claim with a date, not a property** — the
  same reasoning that keeps vintage out of fixtures as a boolean.
- `verify_null.sh` default cap 12 → 100. A cap below the corpus's own file counts is a coverage gap
  dressed as a result; the cap now exists only to bound a pathological diff, and anything unreached
  is still reported.
- METHODOLOGY-v2 §2 records the full-coverage requirement and the drift-immune line test, and states
  that nullness is re-checked before a noise floor is cited.
- `v2/README.md` moves the null arm from "Not done" to built, and points at the record.

[[dcc-vkeh]] can read a noise floor from all three.
