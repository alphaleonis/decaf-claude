# Pooled-adjudication corpus: candidate pool (nib dcc-ixyy)

> ⚠️ **The pool below is superseded by the human-thread re-screen** (`dcc-2gu2`, next section). It
> was gathered under the RAW thread-count criterion, which the census (`dcc-qwt3`) showed measures
> comment volume — substantially a property of which review bots a repo has installed. The same
> supersession applies to `dcc-vvf0`'s replacement-feasibility counts (grafana 98, mattermost 67,
> immich 20, element-web 19, jellyfin 6 candidates after 2026-06-01): those counted raw threads and
> are replaced by the per-cell numbers in the re-screen section. Kept for provenance; select from
> the re-screen.

Gathered 2026-08-10. Regenerate with `v2/find_candidates.sh <repo>` then
`v2/classify_candidate.sh <repo> <pr>`. Raw classified rows: `candidate-pool.tsv`.

Every candidate satisfies the hard admission rules: **merged after 2026-05** (out of window for both
`BENCH_MODEL` and the judge, per METHODOLOGY-v2 section 5), **carries real human review threads**
(now a scored target, not decoration), non-bot author, and >=20 changed lines.

> ⚠️ **The screen ran at 2026-05-01; the defensible bound is 2026-06-01** (`dcc-vvf0`). Anthropic
> publishes no day-level training cutoff, so Opus 5's "2026-05" must be read as end-of-May. Five of
> the twelve built subjects merged inside May 2026 and are therefore **in-window and not poolable** —
> the whole `backend` row, plus contract L and app-ui M. They are kept and flagged rather than
> replaced; `v2/find_candidates.sh` now defaults to 2026-06-01 so the flagged set cannot grow.
> METHODOLOGY-v2 section 5 has the table and the reasoning.

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
- **Airtightness** (METHODOLOGY-v2 §4b), all 12: history depth ≥500 (the one-fetch rule held — no re-shallowing),
  clean working tree, no remote, merge base present, and no reference to the PR number anywhere in
  the checkout.


---

## Re-screen under the human-thread criterion (nib dcc-2gu2, 2026-08-11)

The density criterion is now **≥5 HUMAN review threads** (raw count superseded — `dcc-qwt3` showed
raw counts admit subjects on bot volume: element-web#32964 passed the old bar with 4 of 5 admitted
threads bot-written). Screen: `v2/find_candidates.sh` two-phase — top-100-by-comments search, then
per-candidate thread authors typed by GraphQL actor `__typename` ∪ the committed
`v2/pooled/bot-authors.json`. Raw rows: `candidate-pool-human.tsv` (type · repo#pr · merged · band ·
size · files · raw thr · human thr · bot share · distinct human reviewers · title).

**Pool: 298 candidates at ≥5 human threads, merged ≥2026-06-01**, across the same ten repos:
grafana 65, PostHog 65, aspnetcore 38, mattermost 37, sveltejs/kit 34, immich 19, element-web 13,
prometheus 12, efcore 9, jellyfin 6. 132 were classified by application type (every S/M row in the
app repos plus every L row with ≥2 distinct human reviewers); docs-only PRs excluded by hand
(grafana#126814, grafana#127829, immich#29911, grafana#129154 — all "unclear"/misclassified,
all documentation).

Two caveats that bound every number below:

- **The screen counts RAW human threads; a cell is fixed only by ADMITTED human threads.** Admission
  (§4b: in the checkpoint diff, inside a changed hunk) filters hard — element-web#32964 has 13 raw
  human threads but 1 admitted; immich#28886 has 5 raw and 2 admitted. Every replacement must
  re-verify ≥5 human threads *at admission* when the fixture is built.
- **The sampling cap (top 100 by comments) disadvantages small PRs**, so S-band zeros are the least
  trustworthy. Merged-PR totals since 2026-06-01 vs the 100-PR window: PostHog 11286, grafana 2745,
  mattermost 734, immich 603, aspnetcore 591, element-web 515, sveltejs/kit 503, efcore 307,
  prometheus 283, **jellyfin 212**. Only jellyfin is close to covered, and it was then swept
  **completely** in three <100-PR windows (range form of `merged_after`) for the backend-S question.

### Per-cell results and recommendations

**The vintage five** (in-window, feeding `dcc-ryo4` — same-repo replacements double as the matched
vintage pairs §5 calls for):

| Cell | Current | Recommendation | Basis |
|---|---|---|---|
| backend S | jellyfin#12834 | **no viable candidate** — see below | complete jellyfin sweep + all screens |
| backend M | grafana#124181 | **replace → grafana#125982** (matched pair) | 21 human/21 raw, 4 reviewers, 0% bot, 2026-06-18, "Folder scope apiextensions" |
| backend L | PostHog#52408 | **replace → PostHog#59630** (matched pair) | 59 human/65 raw, 2 reviewers, 9% bot, 2026-06-04, "AI report pipeline primitive" |
| contract L | PostHog#55149 | **replace → PostHog#67924** (matched pair) | 79 human/86 raw, 2 reviewers, 8% bot, 2026-07-16, "product skeleton + on-demand brief pipeline" |
| app-ui M | immich#24627 | **replace → immich#29965** (matched pair) | 19 human/19 raw, 2 reviewers, 0% bot, 2026-08-10, "decode remote thumbnails at display size" |

Alternates, if a primary fails admission at build: backend M grafana#124578 (13 hum, 4 rev, 0% bot);
backend L immich#28686 (42 hum, 4 rev, 0% bot — takes immich to its 2-subject cap only if app-ui M
goes elsewhere); contract L immich#24205 (44 hum, 2 rev, 2% bot — same cap interplay) or
mattermost#36338 (72 hum, 4 rev, 17% bot — but +20924/−1486, a review-cost outlier); app-ui M
element-web#33692 (16 hum, 2 rev, 11% bot).

Under the primary set, active-subject repo counts stay legal: PostHog 2 (59630, 67924), grafana 2
(125982 + kept 117615), immich 2 (29965 + kept 28886).

**The thin four** (citable but ≤2 admitted human threads, feeding `dcc-scc3`):

| Cell | Current (adm. human) | Recommendation | Basis |
|---|---|---|---|
| app-ui L | element-web#32964 (1) | **replace → element-web#33184** | 20 human/21 raw, 4 reviewers, 4% bot, 2026-06-04, "Sign in with QR" — same repo; alternate mattermost#36575 (28 hum, 2 rev, 6% bot) |
| library S | sveltejs#15685 (1) | **replace → sveltejs/kit#16507** | 9 human/11 raw, 2 reviewers, 18% bot, 2026-08-10, "prerender errors during development" — same repo, keeps 9-repo diversity; alternate prometheus#18289 (10 hum, 2 rev, 0% bot — puts prometheus at 2 and drops sveltejs) |
| app-ui S | grafana#117615 (2) | **keep-thin** | only candidates are immich#28164 and immich#29820: 5 human each but a single reviewer (fails the ≥2 preference) and either would be a third immich subject |
| contract S | immich#28886 (2) | **keep as-is** | the screen's sole contract-S candidate IS the incumbent (5 raw human, 3 reviewers, 0% bot); its thinness comes from checkpoint admission, not authorship — no better subject exists at this size |

### backend S: none found — the record

Query: `find_candidates.sh <repo> 2026-06-01 5` over all ten repos (search
`repo:<r> is:pr is:merged merged:>=2026-06-01 sort:comments-desc`, first 100, then per-candidate
thread-author typing). Zero S-band rows classified `backend` anywhere: the six app-repo S rows are
2× app-ui (immich), 1× contract (the immich#28886 incumbent), 3× docs. jellyfin — the natural
backend-S repo, 0% bot on every row — was then swept **completely** (212 merged PRs in three
windows, threshold lowered to 3): its best S-band PRs are jellyfin#15954 and #14935 at **4 human
threads, 1 reviewer** each. Small backend PRs with ≥5 human threads post-cutoff do not currently
exist in this pool; the nearest misses are recorded here in case `dcc-ryo4` prefers a relaxed bar to
a permanently unreportable cell. Re-screen before deciding — the window shifts (the same PostHog
query returned 0 rows on 2026-08-10 and 65 on 2026-08-11).
