# Pooled-adjudication corpus: candidate pool (nib dcc-ixyy)

Gathered 2026-08-10. Regenerate with `v2/find_candidates.sh <repo>` then
`v2/classify_candidate.sh <repo> <pr>`. Raw classified rows: `candidate-pool.tsv`.

Every candidate satisfies the hard admission rules: **merged after 2026-05** (out of window for both
`BENCH_MODEL` and the judge, per METHODOLOGY-v2 section 6), **carries real human review threads**
(now a scored target, not decoration), non-bot author, and >=20 changed lines.

Pool: 547 candidates found across 10 repos; 69 classified by application type.

## Coverage — every cell is populated

| Type | S | M | L |
|---|---|---|---|
| app-ui | 10 | 20 | 3 |
| contract-crossing | 3 | 3 | 3 |
| backend | 5 | 5 | 1 |
| library internals | 2 | 4 | 2 |

Contract-crossing — the row the corpus has never had — is thinnest but real at every size. It is also
the only row that exercises multi-specialist dispatch (`typescript-reviewer` + `dotnet-reviewer`
together), because the defect lives in the mismatch between two files in two languages.

## BUILT — the full 12-cell grid (2026-08-10)

All twelve cells built, no deferral. Fixtures and thread sets in `v2/pooled/<owner>-<repo>-<pr>/`;
checkouts are gitignored and rebuilt by `v2/build_pooled_repo.sh`.

| Type | S | M | L |
|---|---|---|---|
| contract | immich#28886 | mattermost#36824 | PostHog#55149 |
| app-ui | grafana#117615 | immich#24627 | element-web#32964 |
| backend | jellyfin#12834 | grafana#124181 | PostHog#52408 |
| library | sveltejs/kit#15685 | efcore#34127 | prometheus#18081 |

**120 admitted review threads across the 12 subjects** (of 218 raw), against the anchor's 12 key
entries across 7 subjects — a tenfold increase in miss-detector signal, which was the whole argument
for this instrument.

Nine distinct repos, maximum two per repo. Five languages — TS, Svelte, Go, Python, C# — none of
which was selected for. Svelte appears twice and EF Core once, so the operator's stack is represented
without having been targeted, which is what dropping language as an axis is meant to produce.

### The checkpoint rule for pooled subjects

**Checkpoint = the commit the earliest review comment was written against** — the state at which
human review began, so tools and humans review the same starting point and thread recall is
meaningful.

This needed deciding because threads are *not* concentrated on one commit: measured across the 12
subjects, they disperse over **4 to 15 commits**, with the single most-commented commit holding only
about 42% of them. So admission is applied per thread rather than by assuming one commit carries the
set: a thread is admitted if its flagged file is in the checkpoint diff and its line falls inside a
changed hunk. That recovers 120 threads where a modal-commit rule would have yielded ~92.

### Verification performed

- **Merge-base correctness**, per subject: every checkpoint diff touches directories the PR itself
  touches (≥50% overlap, mostly 100%). This is the real test — the failure mode is a stale base
  dragging in unrelated target-branch changes, which turned 18 files into 240 on an earlier subject.
- **Diff-size sanity**: two subjects exceeded their final PR size and were investigated rather than
  waved through. `grafana#117615` (3.14×) is legitimate — its checkpoint carries test scaffolding
  (`sqlCompletionProvider.test.ts` +48, `metaSqlExpr.test.ts` +67) that reviewers consolidated away
  before merge. Real branch shrinkage, not a bad base.
- **Step 8 airtightness**, all 12: history depth ≥500 (the one-fetch rule held — no re-shallowing),
  clean working tree, no remote, merge base present, and no reference to the PR number anywhere in
  the checkout.

