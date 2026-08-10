---
# dcc-3cm6
version: 1
title: Comprehensive review of the v2 harness before spending on the pilot
status: todo
type: task
priority: high
created_at: 2026-08-10T20:14:04Z
updated_at: 2026-08-10T20:15:00Z
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

- [ ] Every seeded finding fixed, or explicitly justified in writing
- [ ] Silent-failure sweep complete; each surviving suppression justified in a comment
- [ ] One pooled checkout destroyed and rebuilt from its committed fixture, verified identical
- [ ] Shim refusal to reach review threads demonstrated on a pooled subject, not assumed
- [ ] Repeated figures reconciled across all documents, or reduced to a single source
- [ ] Findings recorded, with anything not worth fixing written down as accepted risk
