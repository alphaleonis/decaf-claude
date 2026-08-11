---
# dcc-3cm6
version: 1
title: Comprehensive review of the v2 harness before spending on the pilot
status: completed
type: task
priority: high
created_at: 2026-08-10T20:14:04Z
updated_at: 2026-08-11T08:30:55Z
parent: dcc-ho2w
order: 8c
---

The v2 harness was built quickly across several sessions, and the decisions underneath it changed
twice in that time — the instrument moved from a retrospective key to pooled adjudication
([[dcc-595v]]), and human review threads went from decoration to a scored target. Scripts, docs and
fixtures were written against all three states. **Review before [[dcc-vkeh]] spends real money**, not
after.

Motivating pattern: the *same* silent-failure bug has appeared three times — a `nibs mv` loop that
no-opped because zsh does not word-split, `find_candidates.sh` reporting "0 candidates" for two repos
that have ~100, and `build_pooled_repo.sh` aborting before its report because `grep` exits 1 under
`set -u -e`. Each looked like a legitimate empty result. There are almost certainly more.

## Seeded findings (already confirmed, fix or justify each)

1. **Stale answer key for a rejected subject.** `v2/analysis/subject-11/answer-key.json` still exists,
   though the ground-truth audit ruled subject 11 unscorable (the indicted ordering bug was fixed
   during review; the hang was never root-caused). This is precisely the stale-artifact class
   [[dcc-8tjr]] existed to remove, reappearing inside v2.
2. **`run_cell_v2.sh` instructs the tool to "Fetch the PR with gh."** That was v1-faithful, but under
   pooled adjudication threads are a *scored target* — so the prompt now actively invites the leak the
   shim has to block. Reconcile the prompt with the scoring model, or state why the instruction stays.
3. **`run_cell_v2.sh` resolves subjects to `v2/repos/<id>`**, while the 12 pooled subjects live at
   `v2/pooled/<owner>-<repo>-<pr>/repo`. It cannot currently run the corpus at all.
4. **`2>/dev/null` on data-producing commands** in six v2 scripts. Each is a place an error can
   masquerade as an empty result.
5. **Two fixture shapes coexist** — `v2/subjects/*.json` (anchor, 3 files) and `v2/pooled/*/fixture.json`
   (pooled, 12 dirs) — with different schemas and no shared loader.
6. **Repeated figures across four documents** (120 admitted threads, 98 clusters from 800 findings,
   5 of 12 subjects rejected, 12 scoreable entries, 218 raw threads). Any of these can drift.

## Review scope

- **Methodology**: `METHODOLOGY-v2.md` — three sections were rewritten in place; check it reads as one
  document and that no passage still assumes the key is the metric. Note [[dcc-envo]] covers
  *restructuring*; this is about correctness and internal contradiction.
- **Docs**: `v2/README.md`, `v1-archive/README.md`, `README.md` banner, `CLAUDE.md` benchmark section,
  and `v2/analysis/{GROUND-TRUTH-AUDIT,STEP0-FEASIBILITY,CANDIDATES}.md`.
- **v2 scripts**: `run_cell_v2.sh`, `build_pooled_fixture.py`, `build_pooled_repo.sh`,
  `audit_subject.sh`, `find_candidates.sh`, `classify_candidate.sh`, `screen_step0.sh`.
- **Shims**: `shim/gh`, `shim/docs-at`, `shim-log/gh`. The deny list is now load-bearing for *scoring*,
  not just hygiene — re-derive it against the pooled corpus rather than assuming v1 coverage holds.
  Confirm `docs-at` still resolves.
- **Scoring**: `scoring/score_pooled.py`, `check_artifacts.py`, `test_score_pooled.py` — including
  whether the three-axis separation is genuinely unexpressible-if-merged, and whether any guard lacks
  a test.
- **v1 machinery still live**: `scripts/lib.sh`, `bench_next.sh` (guarded), `bench_status.sh`,
  `rebuild_metrics.sh`, `analysis/scripts/*` — repointed at `v1-archive/`, but verify nothing writes
  where v2 reads.
- **Commands**: the five bannered v1 `bench-*` plus `bench-analyze-v2`.
- **Fixtures**: all 12 `fixture.json` + `threads.json`, and the 3 anchor keys.

## Checks worth running, not just reading

- **Reproducibility**: delete a pooled checkout and rebuild it from the committed `fixture.json`
  alone. If it does not come back byte-identical at HEAD, the fixture is under-specified.
- **Silent-failure sweep**: every `2>/dev/null`, every `|| true`, every unguarded `grep`/`jq` whose
  emptiness is indistinguishable from failure.
- **Cross-document number audit**: pick each repeated figure, trace it to the artifact that produced
  it, and correct or delete the copies that disagree.
- **Leak re-derivation**: for one pooled subject, actually attempt to reach its review threads through
  the shim and confirm refusal — the threads are the answer now.

## Acceptance

- [x] Every seeded finding fixed, or explicitly justified in writing
- [x] Silent-failure sweep complete; each surviving suppression justified in a comment
- [x] One pooled checkout destroyed and rebuilt from its committed fixture, verified identical
- [x] Shim refusal to reach review threads demonstrated on a pooled subject, not assumed
- [x] Repeated figures reconciled across all documents, or reduced to a single source
- [x] Findings recorded, with anything not worth fixing written down as accepted risk

## Summary

**Completed 2026-08-11** — **Completed 2026-08-11** — Full review in `competition/benchmark/v2/analysis/HARNESS-REVIEW.md`.
**Verdict: the pilot must not spend yet**, and the two reasons are filed as [[dcc-suz4]] and
[[dcc-vvf0]], both now blocking [[dcc-vkeh]].

Five defects would have corrupted or voided the pilot, four of them silently:

1. **The answers are reachable from a cell.** Cells run `cd .../pooled/<subject>/repo` under
   `--dangerously-skip-permissions`; `../threads.json` is the thread axis's answer key, `../../*/`
   is every other subject, and `../../../runs/` is every prior cell. `reset_repo()` cleans only
   inside the checkout. This is [[dcc-2cxq]] with a worse payload. Relocation does not help — the
   flag removes path gating entirely. Detection shipped (`verify_cell_isolation.sh`, wired into the
   runner, all four existing cells CLEAN); prevention is [[dcc-suz4]].
2. **`run_cell_v2.sh` could not address the pooled corpus at all** — it resolved only
   `v2/subjects/NN-*.json` + `v2/repos/<id>`. Fixed via a new `v2/fixture_lib.sh` that resolves all
   three fixture shapes (there were three, not two: anchor, pooled, null).
3. **The `gh` shim's `--json` filter was a case-sensitive substring blocklist over a 46-field API.**
   `latestReviews` leaked `CHANGES_REQUESTED` (2026-05-18) and `APPROVED` (2026-07-01) against a
   2026-04-09 checkpoint; `commits` returned all 8 post-checkpoint commits; `reviewDecision`,
   `files` and the merge-state family were open. Now an allowlist — 0 of 30 probed fields reachable.
4. **A URL target skipped the date check entirely.** `gh pr view <url> --json title,body` on any
   post-checkpoint PR was ALLOW. URLs are now parsed and date-checked; an unresolvable target denies.
5. **Every cell recorded `build-capability.json = {"error":"detection failed"}`** — `detect_build.sh`
   was passed `dirname "$REPO"`, and `2>/dev/null || echo` then destroyed its real diagnostic. So
   [[dcc-fhp1]]'s "identifiable rather than quietly weaker" guarantee was void.

Two findings changed facts rather than code:

- **`docs-at` reported Wayback outages as "no snapshot".** Measured 3 of 12 identical requests
  failing at connection level — a 25% false-MISS rate logged as MISS either way. Its
  `filter=statuscode:200` also dropped sites that redirect: SvelteKit's docs were *unreachable* for
  every `sveltejs/kit#15685` cell. Both fixed; the page now resolves.
- **The null arm's file probe silently covered 12 of 33 files** on the large subject. Full coverage
  surfaces 8 hits where 1 was adjudicated, one of them in `global-exception.filter.ts` — the
  production file central to a PR titled "structured validation error responses". Filed [[dcc-nvrt]].

**Seeded finding 1 was a false positive and nothing was deleted.** `subject-11/answer-key.json` and
`v2/subjects/11-rust-medium.json` pin the *same* as-opened checkpoint, and METHODOLOGY-v2 documents
that head as the one place subject 11 is scorable — it is the single case where the checkpoint
machinery changed the answer. The audit's "replace / 0 entries" is a verdict on the *merged* head.
The real defect was that the two documents disagreed where a reader could not resolve it; both now
say so, and the key carries a `scope` field.

Cross-document figure audit found **no disagreements**: 218/120/98 threads, 5 of 12 rejected, and the
fixture↔threads.json agreement all trace exactly. One *framing* was wrong — "12 scoreable entries
across 7 subjects" is a projection; 2 of 7 keys are built (3 entries). Corrected in place.

Also fixed: case-sensitive GitHub host denial in the curl/wget shims (`https://GITHUB.com/...` was
allowed); `score_pooled.py` guarding `severity` (which no metric reads) while
`precision_severity_weighted` divided by an unguarded `judged_severity`; no `matches_key` guard; the
null arm being unscoreable by its own scorer; and the corpus-level miss detector silently reporting
the "found" reading. 21 scoring tests pass, up from 15.

`git` and the local filesystem are now named as unmeasured channels in the Tier 3 table and in
`leak_audit.sh`, per the methodology's own commitment to name what it does not measure.
