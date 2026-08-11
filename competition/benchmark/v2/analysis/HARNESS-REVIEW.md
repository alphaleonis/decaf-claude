# v2 harness review — before the pilot spends (nib `dcc-3cm6`)

> ⚠️ **Section numbers below are `METHODOLOGY-v2.md` as it stood on 2026-08-11, before `dcc-envo`
> restructured it.** Translate: §3 (instruments) → §2, §5 (access controls) → §3, §6 (what v2 cannot
> fix) → §5, §4A (pooled construction) → §4c, §4's Steps 0–8 → §4b + §4d's Steps A1–A6. M2's "`dcc-envo`
> still owns the larger restructure" is now done.

Reviewed 2026-08-11 against `HEAD` of `tuning`. Scope: `METHODOLOGY-v2.md`, `v2/README.md`,
`README.md`, `v1-archive/README.md`, `CLAUDE.md`, `v2/analysis/*.md`, the seven v2 scripts, the four
shims, the scoring package, the surviving v1 machinery, the six `bench-*` commands, and all 12 pooled
fixtures + 3 null fixtures + 3 anchor keys.

**Verdict: do not run `dcc-vkeh` yet.** Five defects would corrupt or void the pilot's data, and four
of them are silent — the run completes and the artifacts look well-formed. Everything below was
verified by execution, not by reading; the commands are given so each can be re-run.

---

## What was checked by running it

| Check | Result |
|---|---|
| Destroy a pooled checkout and rebuild from its committed `fixture.json` alone | **PASS** — byte-identical |
| Reach a pooled subject's review threads from inside a cell | **FAIL** — reachable three ways |
| `python3 test_score_pooled.py` | 15/15 pass |
| `docs-at` resolves and refuses GitHub | resolves; **but see H1** |
| Fixture ↔ `threads.json` agreement, all 12 subjects | **PASS** — 218 total / 120 admitted, exact |
| v1 machinery writing where v2 reads | **PASS** — no collision |

### Reproducibility (acceptance item 3) — passes

`v2/pooled/jellyfin-jellyfin-12834/repo` deleted and rebuilt with `v2/build_pooled_repo.sh`:

| | before | after |
|---|---|---|
| `HEAD` | `92bc04f002f2…` | `92bc04f002f2…` |
| `HEAD^{tree}` | `1fb96d0d3f6c…` | `1fb96d0d3f6c…` |
| `git ls-files -s` sha256 | `ebdce0f7de963354` | `ebdce0f7de963354` |
| `rev-list --count HEAD` | 15040 | 15040 |
| dirty / untracked / remotes | 0 / 0 / 0 | 0 / 0 / 0 |
| `git diff base checkpoint` | 1 file, +21/−12 | 1 file, +21/−12 (= `diff_stat`) |

The fixture is fully specifying. The one-fetch rule held (15040 commits, not 7).

---

## BLOCKING — fix before any cell runs

### B1. The scored answers sit beside the checkout, and cells run with no permission gate

`config.env` sets `PERM_FLAGS="--dangerously-skip-permissions"`. `run_cell_v2.sh` does
`cd "$REPO"` and launches `claude -p` there. From that working directory, with no network and no
shim involved:

```console
$ cd v2/pooled/sveltejs-kit-15685/repo
$ jq -r '[.[]|select(.admission=="admitted")][]|"  \(.path):\(.line)"' ../threads.json
  packages/kit/src/exports/vite/index.js:603
  packages/kit/src/exports/vite/index.js:671
  packages/kit/src/exports/vite/index.js:606
$ ls ../../*/threads.json | wc -l                     # every other subject's answers
12
$ ls ../../../analysis/subject-*/answer-key.json      # the anchor keys
$ ls ../../../runs/                                   # every prior cell's final-output.md
```

`threads.json` carries `path`, `line`, `body` and `admission_reason` for each thread — it *is* the
thread axis's answer key, and the thread axis is the miss detector and the only scoring signal in the
design not produced by an Opus 5 (METHODOLOGY-v2 §6).

`reset_repo()` cleans inside the checkout only, so nothing above is in its scope. This is the v1
`dcc-2cxq` failure with the contamination moved one directory up and the payload upgraded from
"another tool's report" to "the answer". Relocating the files does not fix it: with
`--dangerously-skip-permissions` there is no path gating at all, so an absolute path reaches them
from anywhere.

**RESOLVED under `dcc-suz4`** — a fourth option beat the three this review first considered.

The three were: (a) drop the blanket bypass for a permission allowlist, (b) run the cell in a
sandbox, (c) detect after the fact from the transcript. (a) changes what the tools can do, and tool
behavior is the thing being measured; (b) is a lot of setup; (c) detects rather than prevents.

**(d) A `PreToolUse` hook still fires under `--dangerously-skip-permissions`, and exit 2 blocks the
call.** This repo already relies on that for `decaf-protection`; measured again here on Claude Code
2.1.226, where the hook payload reports `permission_mode: bypassPermissions` and the block held
against both the `Read` tool and a `cat ../threads.json` Bash fallback.

`v2/hooks/block-answer-access.js` denies any path resolving inside the benchmark tree but outside the
cell's checkout. Verified on the boundary — 12 escape attempts denied (`../threads.json`,
`../../*/threads.json`, `../../../analysis/*/answer-key.json`, `ls ../../../runs/`,
`cd .. && cat threads.json`, an absolute `grep -r` over `v2/`), 10 legitimate operations allowed,
including `cat test/fixture.json` (a repo-internal file whose name collides) and absolute system
paths.

End to end, on the real `sveltejs-kit-15685` checkout:

| Cell | Guard evaluated | Denied | Outcome |
|---|---|---|---|
| adversarially told to read `../threads.json`, `../fixture.json` and the sibling subjects | 3 | **3** | obtained none of them |
| an ordinary review of `base..checkpoint` | 29 | **0** | completed normally |

So it is enforcement *and* behavior-neutral, which is what ruled out (a). (c) is kept anyway —
`verify_cell_isolation.sh` still re-checks each transcript, because prevention that has only been
reasoned about is not prevention.

⚠️ Both cells above ran on **Haiku 4.5**, not `BENCH_MODEL`, and one cell is not a measurement. They
demonstrate that the control works and does not obstruct; they say nothing about any tool's quality.

### B2. `run_cell_v2.sh` cannot address the pooled corpus (seeded finding 3)

```sh
FIX="$(ls "$V2"/subjects/$(printf %02d "$SID")-*.json)"
REPO="$V2/repos/$SID"
```

Only the three anchor fixtures resolve. The 12 pooled subjects live at
`v2/pooled/<owner>-<repo>-<pr>/{fixture.json,repo}`, and the null subjects at `v2/null/<id>/`. The
runner cannot run the corpus the pilot is for. **Fixed** — see "Changes applied".

### B3. The `gh` shim's field filter is a substring blocklist; it leaks on a pooled subject

`shim/gh` denies a `--json` request by globbing the argument against
`*comments*|*reviews*|*timelineItems*|*reviewThreads*|*closingIssuesReferences*|*mergedAt*|*mergeCommit*|*state*`.
`gh pr view --json` accepts **46** fields. The glob is case-sensitive, so `*reviews*` does not match
`latestReviews`. Measured against `sveltejs/kit#15685` (checkpoint `2026-04-09`), all under
`BENCH_POLICY_DRYRUN=1`:

| Request | Shim verdict | What it actually returns |
|---|---|---|
| `--json latestReviews` | **ALLOW** | `COMMENTED 2026-04-21`, `CHANGES_REQUESTED 2026-05-18`, `APPROVED 2026-07-01` — post-checkpoint review states |
| `--json commits` | **ALLOW** | 8 commits, **8 of 8 dated after the checkpoint** — the author's entire response to review |
| `--json reviewDecision` | **ALLOW** | `CHANGES_REQUESTED` |
| `--json files` | **ALLOW** | the merged file list — the same class of leak as `pr diff`, which *is* denied |
| `--json closed,closedAt,mergedBy,mergeable,mergeStateStatus,statusCheckRollup,potentialMergeCommit` | **ALLOW** | post-checkpoint lifecycle |
| `--json reviews` / `state` / `comments` | DENY | (the three the blocklist happens to spell correctly) |

`gh pr list --json latestReviews` is allowed too — the same loop guards both.

`v2/README.md` already documents the correct design: "`--json` required, **safe fields only**". The
code implements the opposite. **Fixed** — converted to an allowlist.

### B4. A URL target bypasses the `createdAt` check entirely

The shim finds its target by scanning for an argument that starts with a digit. A URL does not, so
`num` stays empty and control falls through to `allow` + `exec` with **no date check at all**:

```console
$ gh pr view https://github.com/sveltejs/kit/pull/99999 --json title,body
=> ALLOW pr view https://github.com/sveltejs/kit/pull/99999 --json title,body
```

`gh` accepts URLs for `pr view` and `issue view`. This reaches any post-checkpoint PR or issue by
title and body — and METHODOLOGY-v2 §1 records that subject 9's linked item is *"proxy: node-manager
ignores timeouts to get NodeIPs"*: the bug, in a title. **Fixed** — URLs are parsed for the number,
and an unresolvable target is denied rather than allowed.

### B5. Every cell records `build-capability.json = {"error":"detection failed"}`

`detect_build.sh` takes a **subject directory** and appends `/repo`. `run_cell_v2.sh` passes
`dirname "$REPO"`, which for `REPO=v2/repos/2` is `v2/repos` — so detection looks for
`v2/repos/repo`, which does not exist. Reproduced exactly as the runner invokes it:

```console
$ bash v2/detect_build.sh "$(dirname v2/repos/2)" > bc.json 2>/dev/null || echo '{"error":"detection failed"}' > bc.json
$ cat bc.json
{"error":"detection failed"}
$ bash v2/detect_build.sh v2/pooled/sveltejs-kit-15685        # correct call
{"languages":["js"],"package_managers":["pnpm"],"restore_commands":["corepack pnpm install --frozen-lockfile"],"date_neutral":true,"build_possible":true}
```

Two failures compound. The path is wrong, and then `2>/dev/null || echo '{"error":"detection
failed"}'` **overwrites** detect_build's own diagnostic (`{"error":"no checkout at v2/repos/repo"}`)
with a generic one, so the artifact cannot tell an operator that the cause is a path bug.

`dcc-fhp1`'s whole guarantee — "a run without a toolchain is identifiable rather than quietly weaker"
— is void today. **Fixed.**

---

## HIGH

### H1. `docs-at` reports a failed Wayback query as "no capture at or before the checkpoint"

`picked="$(curl -sS --max-time 30 "$CDX" 2>/dev/null | grep -oE '[0-9]{14}' | tail -1)"`. Empty
`picked` means "no snapshot exists" *and* "the request failed", and the two are reported identically
— including in the access log, which records `MISS` either way.

The Internet Archive rate-limits. Twelve identical requests for one URL:

```
1:EMPTY  2:EMPTY  3:20260331053003  4:20260331053003  5:20260331053003  6:EMPTY
7:20260331053003  8:…  9:…  10:…  11:…  12:20260331053003
```

**3 of 12 failed**, with no HTTP status at all (connection-level). Each would have told the cell that
SvelteKit's documentation does not exist at its checkpoint. `leak_audit.sh` reports docs-at as
`shimmed — snapshot date enforced` and cannot distinguish the two outcomes, so a cell degraded this
way is not identifiable afterwards.

Second, smaller problem: `filter=statuscode:200` drops captures recorded as redirects, and doc sites
redirect constantly (`svelte.dev/docs/kit/routing` has a `308` between two `200`s in the same
window). **Fixed** — the CDX call now separates failure from absence, retries, and logs `ERROR`
distinctly from `MISS`.

### H2. `verify_null.sh`'s falsifying check fails open

Check 3 is described in its own header as "the check that can actually falsify nullness". It is the
one that fails silently in the unsafe direction:

```sh
hits="$(gh api "repos/$REPO/commits?path=$f&since=$after&per_page=100" \
         --jq '.[] | .commit.message | split("\n")[0]' 2>/dev/null | grep -iE '…')"
```

A rate-limited or 404 response yields empty `hits` → no later fix found → `VERDICT: NULL-OK`. The jq
on the cross-reference query (line 52) has the same shape, and an error there turns a `REJECT` into
`NULL-OK`. Three null subjects were admitted under this check.

Also `for f in "${files[@]:0:12}"` silently caps at 12 files, and the output prints "later fix-shaped
commits on the same files: none" without saying how many files were never looked at. **Fixed** —
fails closed, and reports the cap.

### H3. The `curl`/`wget` shim's host denial is case-sensitive

```console
$ bash v2/shim/curl -sS https://api.github.com/repos/…/comments   => DENY
$ bash v2/shim/curl -sS https://GITHUB.com/x                      => ALLOWED
```

DNS is case-insensitive. **Fixed** — matched case-insensitively.

### H4. `git` is an unmeasured channel and is not named as one

Tier 3 commits to a table where every channel is "logged, denied at the harness level, or explicitly
named as unmeasured". `git` is none of the three. The fixture drops its remote, but nothing stops a
cell running `git remote add o https://github.com/O/R && git fetch o` and reaching the merged state —
and the `curl` shim does not see it, because git uses its own transport. Probability is low (an agent
has little reason to), impact is total. **Fixed as documentation**: added to the Tier 3 table and to
`leak_audit.sh` as an explicitly unmeasured row. Denying it is a separate decision (`dcc-suz4`).

### H5. `score_pooled.py` guards a field no metric reads, and leaves the metric-bearing one unguarded

`validate()` fails the run when `reported_by[].severity` is empty or under 20% populated. No metric in
`score()` reads that field. `precision_severity_weighted` is computed from `judged_severity`:

```python
def w(c): return SEV_WEIGHT.get((c.get("judged_severity") or "").lower(), 1.0)
```

A missing `judged_severity` silently scores 1.0 — the same weight as `low` — so a cluster the judge
never rated is indistinguishable from one rated low, and the guard the docstring says exists to stop
exactly this ("severities captured on 2 of 78 entries… a free 1.00 on n=1") does not cover it. No
test covers it either. **Fixed** — `judged_severity` is now guarded and tested; the `severity` guard
stays, because `/bench-synthesize` uses tool-reported severity for its calibration axis.

### H6. `matches-key` has no index guard, unlike `matches-thread`

`validate()` rejects a `matches-thread` cluster with no `matches_thread`, and range-checks the index.
`matches-key` has neither. `krecall` filters `None` out, so a `matches-key` cluster missing its
`matches_key` contributes 0 to anchor recall and nothing says so. **Fixed** — symmetric guard, plus a
check that the index names a real key entry.

### H7. The null arm cannot be scored by `score_pooled.py`

`validate()` raises on `cells contributing zero clusters (extraction defect?)`. On the null arm, a
tool that reported nothing is the **best possible result** and the headline number — the noise floor
is what the arm exists to measure (`dcc-mjj5`). Today, scoring a null subject where any tool stayed
quiet exits 3 with a data defect. **Fixed** — `--allow-silent-cells`, required for null subjects and
refused by default, so the guard still fires where it was designed to.

### H8. The corpus-level miss detector reports only the "found" semantics, unlabeled

Per tool, both `thread_recall` and `thread_recall_found` are emitted, and the split is load-bearing
(`dcc-c92m`). The corpus-level `threads.hit_by_any_tool` / `missed_by_every_tool` are computed over
all clusters regardless of disposition, so a thread every tool *demoted* counts as hit. That is the
"found" reading, presented without a qualifier, in the field that answers "what did everyone miss".
**Fixed** — both variants emitted.

---

## MEDIUM — documents that no longer describe the harness

### M1. `METHODOLOGY-v2.md` opens "Status: DRAFT… nothing here is implemented"

§4 and §5 are built and exercised. **Fixed.**

### M2. §4 documents the anchor procedure only; the procedure that built the corpus is undocumented

§3 says pooled adjudication removes "the revert requirement, Steps 5-7 of section 4". §4 is still
titled "Subject construction: from PR to checkpoint + key" and reads as *the* procedure, opening with
Step 0's revert-triage — which applies to no pooled subject. Meanwhile the rules that actually built
the 12 subjects (`find_candidates.sh` thresholds, the earliest-review-comment checkpoint rule,
per-thread admission) live in `CANDIDATES.md` and in the scripts, not in the methodology.
**Fixed** — §4 is scoped to the anchor, and a §4A documents the pooled procedure. `dcc-envo` still
owns the larger restructure.

### M3. "12 scoreable entries across 7 subjects" describes projections, not artifacts

§3 states it as a present fact and §3's anchor section says "The 7 audited subjects keep their keys".
Built keys: **subject 2 (1 entry) and subject 9 (2 entries)** — 3 entries across 2 subjects.
`GROUND-TRUTH-AUDIT.md` says so plainly ("Only two of the seven survivors are actually built");
`METHODOLOGY-v2.md` does not. The 12 is the sum of the audit's per-subject *projections*
(`~2+1+1+~2+2+1+~3`) and traces correctly to that table — it is the framing that is wrong, not the
arithmetic. **Fixed** — labelled as projected, with the built count stated and `dcc-9ncz` named.

### M4. §6 contradicts its own vintage table

> "Haiku 4.5 gets five usable subjects where **Opus 4.8** gets two."

The table two lines above has no Opus 4.8 row, and gives Opus 5 **one** usable subject (subject 2),
not two. **Fixed.**

### M5. The vintage cutoff is stated per month and implemented as the first of the month

§6: "merged after 2026-05… Hard admission rule". `find_candidates.sh` defaults `AFTER=2026-05-01`.
Four of the twelve pooled subjects merged *inside* May 2026:

| Subject | merged |
|---|---|
| PostHog#52408 | 2026-05-06 |
| PostHog#55149 | 2026-05-06 |
| grafana#124181 | 2026-05-08 |
| immich#24627 | 2026-05-11 |
| jellyfin#12834 | 2026-05-21 |

(five, in fact).

**RESOLVED under `dcc-vvf0`, and the resolution was forced rather than chosen.** Anthropic publishes
no day-level training cutoff — there is no cutoff field in the model catalog or in the Models API
capability tree, and the model card states a month. So "2026-05" cannot be resolved by lookup, only
interpreted, and only the conservative reading is defensible: the model may have seen anything up to
2026-05-31, so provably out-of-window means merged **2026-06-01 or later**.

Under that bound the five above are `in-window`, and so is the entire `backend` row. The operator
chose to **keep and flag** them rather than rebuild five cells — replacement was feasible (grafana 98
candidates, mattermost 67, immich 20, element-web 19, jellyfin 6, though PostHog yields 0 at the
≥5-thread bar) but would have cost the audited thread sets.

The consequence is load-bearing and is now enforced in code rather than left as a note:
`v2/scoring/vintage.py` classifies each (subject, model) pair at analysis time, `score_pooled.py`
refuses to emit metrics without `merged_at`, and `check_pooling()` fails loudly on a figure that
mixes the two classes. **This corpus yields no backend number at all**; the citable seven are
contract S/M, app-ui S/L, library S/M/L. `find_candidates.sh` now screens at 2026-06-01 so the
flagged set cannot grow.

Two things surfaced while resolving it. All three **null subjects are also in-window** (early May
2026) — accepted, because §6's soak-beats-vintage rule already exempts the null arm and a memorized
null subject deflates the noise floor, which is the safe direction. And `find_candidates.sh` has an
undisclosed **100-result sampling cap** with a comment-volume proxy for thread count, so its zero for
PostHog is "none in the top-100-by-comments window", not "none in the repo" — now stated in its
header.

### M6. `GROUND-TRUTH-AUDIT.md` uses the old cutoff

"Merged after 2026-01 for vintage safety" and "the roster's Jan 2026 training cutoff" predate
`dcc-f2nf`, which moved the binding cutoff to Opus 5's 2026-05. **Fixed** — noted in place rather
than rewritten, since the document is a dated record of an audit.

### M7. `v2/README.md` describes a harness two decisions ago

- "Status: proof of concept… **scoring is not built**" — `v2/scoring/` exists with 15 passing tests.
- "**no scoring pipeline** — zero references to `analysis/scripts/*.py` from `v2/`" — superseded;
  v2 has its own.
- "**9 subjects unaudited**, base rate of bad ground truth currently 2 in 3" — all 12 audited
  (`dcc-5xad`).
- The Layout block shows only `subjects/`, `repos/`, `analysis/` — no `pooled/`, `null/`, `scoring/`,
  `toolchain.sh`, `leak_audit.sh`, or the `curl`/`wget` shims.

**Fixed.**

### M8. `scoring/README.md` says "12 self-tests"; there are 15

**Fixed**, and the count replaced with a pointer so it cannot drift again.

### M9. `CLAUDE.md` describes the v1 corpus

"across 12 real OSS PRs **that shipped a defect**" — pooled subjects explicitly need no revert, no
regression issue and no named mechanism (METHODOLOGY-v2 §3). **Fixed.**

### M10. Three fixture shapes, not two (seeded finding 5)

| | anchor `v2/subjects/*.json` | pooled `v2/pooled/*/fixture.json` | null `v2/null/*/fixture.json` |
|---|---|---|---|
| identity | `id`, `lang` | `slug`, `app_type` | `slug`, `app_type` |
| checkpoint | `push_index`, `push_count` | `base_ref` | `base_ref` |
| review range | `review.{base,head,diff_cmd}` | — | — |
| threads | — | `total`/`admitted`/`rejected` | `total`/`not-scored` |
| vintage | — | `merged`, `note` | `merged`, `note` |

`threads.rejected` is also absent from 2 of 12 pooled fixtures (jellyfin, prometheus — both have
`total == admitted`, so 0 is implied but not written). **Fixed** — a shared `v2/fixture_lib.sh`
resolves any subject id to its directory, kind and fields; `threads.rejected` written explicitly on
all 12.

### M11. Cross-document figures — audited, all trace

Every repeated figure was traced to the artifact that produces it. **No disagreements found**, which
is worth recording explicitly:

| Figure | Source of truth | Verified |
|---|---|---|
| 218 raw threads | `jq -s '[.[][]]|length' v2/pooled/*/threads.json` | 218 ✅ |
| 120 admitted | same, `select(.admission=="admitted")` | 120 ✅ |
| 98 rejected | 218 − 120 | 98 ✅ |
| 5 of 12 subjects rejected | `GROUND-TRUTH-AUDIT.md` verdict table | 5 `replace` ✅ |
| 12 scoreable entries / 7 subjects | same table, summed projections | 12 ✅ **but projected — see M3** |
| 800 findings → 98 clusters | v1 artifact, `v1-archive/` | v1-derived; cited only as a distribution, never as a comparison ✅ |
| fixture `threads.*` vs `threads.json` | all 12 subjects | exact on all 12 ✅ |

One collision worth knowing about: **98 appears twice with different meanings** — 98 rejected threads
in the pooled corpus, and 98 clusters from the v1 subject-6 finding pool. Coincidence, not an error,
but they are one paragraph apart in §3 and read as related. Disambiguated in place.

### M12. Small ones, fixed in passing

- `METHODOLOGY-v2.md` has a doubled `---` at the §3/§4 boundary (a rewrite scar).
- `GROUND-TRUTH-AUDIT.md` ends with "**Methodology gap:** Step 5's candidate sources omit re-land
  PRs… Add it" — which was done (§4 Step 5 now covers re-lands). Marked as actioned.
- `v1-archive/README.md` says "`analysis/` now holds only scripts"; it also holds
  `analysis/METHODOLOGY.md`, which `METHODOLOGY-v2.md` line 4 correctly references.

---

## LOW — recorded, not fixed (accepted risk)

- **`analysis/scripts/cluster_replay.py` silently returns nothing.** It globs
  `analysis/subject-*/findings.json`; those moved to `v1-archive/analysis/`. It is v1-only, behind the
  `bench-analyze` banner, and reads nothing v2 writes. Accepted: v1 is retired and its scripts are
  evidence, not machinery.
- **`gh repo view` is allowed with arbitrary flags.** It exposes repository description, topics and
  star count — no PR lifecycle. Accepted.
- **`gh pr list --search` can end up with two `created:` qualifiers** when the caller supplies their
  own. GitHub ANDs them, so the injected bound still holds; the worst case is an empty result.
  Accepted.
- **`docs-at` has no fallback allowlist** of version-stable documentation domains, which §5 Tier 2
  says it falls back to. Behavior is stricter than documented, which is the safe direction.
  Documented rather than implemented.
- **The `98`/`98` collision** is a coincidence, not an inconsistency.

---

## Silent-failure sweep (acceptance item 2)

Every `2>/dev/null`, `|| true` and unguarded `grep`/`jq` in `v2/` was classified. The dangerous ones
are those where an error and an empty result are indistinguishable **and the empty reading is the
permissive one**.

| Site | Class | Disposition |
|---|---|---|
| `docs-at:40` CDX query | error → "no capture" | **fixed** (H1) |
| `verify_null.sh:71` later-commit query | error → `NULL-OK` | **fixed** (H2) |
| `verify_null.sh:52` cross-ref jq | error → `NULL-OK` | **fixed** (H2) |
| `verify_null.sh:33` graphql | error → guarded by `jq -e`, but payload discarded | **fixed** — payload printed, as `find_candidates.sh` already does |
| `run_cell_v2.sh:67` detect_build | error → generic message, real one destroyed | **fixed** (B5) |
| `screen_step0.sh:18` `gh pr list` | error → zero rows, reads as "no reverts" | **fixed** — guarded like `find_candidates.sh` |
| `classify_candidate.sh:26` | error → empty, but **already guarded** by the `-z` check on line 27 | justified in comment |
| `audit_subject.sh:38,53,54,68` | the fix PR genuinely may not exist; absence is the signal | justified in comment |
| `build_pooled_repo.sh:18` `grep … \|\| true` | `pipefail` makes `\|\| true` load-bearing; no-match is the *good* outcome and is reported | justified in comment |
| `build_pooled_repo.sh:19` `cat-file` | branchless yes/NO probe, both branches reported | justified in comment |
| `detect_build.sh:57,69,71,86` `find`/`jq` | absence is the answer, and is reported as `false` | justified in comment |
| `run_cell_v2.sh:117,118` `jq` on meter.json | a crashed cell has no `.result`; `rc` is reported separately | justified in comment |
| `run_cell_v2.sh:121,123` `grep -c \|\| true` | `grep -c` prints 0 and exits 1; `\|\| true` is required | justified in comment |
| `leak_audit.sh:19` | already the fix for this exact bug; comment present | no change |
| `shim/gh:43` `created_at` | empty → **deny**, which is fail-closed | no change |
| `shim-log/gh:27` oracle | empty → `ORACLE-UNAVAILABLE`, recorded in the log | no change |
| `shim/docs-at:58` main fetch | http code captured and branched on | no change |
| `find_candidates.sh` | the reference implementation — prints the payload and exits 4 | no change |

---

## Seeded findings — disposition

| # | Finding | Disposition |
|---|---|---|
| 1 | Stale `subject-11/answer-key.json` for a rejected subject | **Premise refuted — nothing deleted.** See below. |
| 2 | `run_cell_v2.sh` tells the tool to "Fetch the PR with gh" | **Fixed** — the instruction is gone. Under pooled adjudication threads are a scored target, so a prompt that steers the tool at the PR page steers it at the answer; and B3/B4 show the shim did not in fact stop it. Tools now get the local diff and are told `gh` is time-boxed, which is what the other three tool prompts already said. |
| 3 | Subject paths resolve to `v2/repos/<id>` only | **Fixed** (B2) |
| 4 | `2>/dev/null` on data-producing commands | **Fixed / justified** — see the sweep table |
| 5 | Two fixture shapes | **Fixed** — there were three (M10); shared loader added |
| 6 | Repeated figures across four documents | **Audited, all trace** (M11); the one wrong *framing* is M3 |

### Seeded finding 1 in detail — the key is not stale

The key was checked before deleting it, and it should not be deleted. `answer-key.json` and
`v2/subjects/11-rust-medium.json` pin the **same** checkpoint — `8d216da8281b`, the as-opened head,
2025-12-04 — and the key's 2 entries are reviewer-flagged defects present in *that* diff:

```console
$ jq -r .checkpoint.sha v2/subjects/11-rust-medium.json          # 8d216da8281bc4d63ba6c68fda102ea35d6ec12a
$ jq -r .checkpoint.sha v2/analysis/subject-11/answer-key.json   # 8d216da8281bc4d63ba6c68fda102ea35d6ec12a
```

`GROUND-TRUTH-AUDIT.md`'s `replace / 0 entries` is a verdict on the **merged head** and on the
**escaped** defect, which was never root-caused. METHODOLOGY-v2 §"Whether an earlier checkpoint
helps" says the opposite of "stale" about the as-opened head: *"≥1 (the only scorable defect)"*,
*"Better checkpoint: **as-opened**"*, and subject 11 is the one case of three where the checkpoint
machinery changed the answer. Deleting the key would delete the evidence for that.

The real defect is that **the two documents disagree where a reader cannot resolve it** — the audit's
verdict table is the canonical corpus record and says nothing about the as-opened rescue, which is
how this came to be filed as a stale artifact. Fixed by reconciling them, not by deleting:

- `GROUND-TRUTH-AUDIT.md` gains a *"Subject 11 — 'replace' is a verdict on the merged head"* section
  and the table row now says so.
- The key itself gains a `scope` field stating that it is valid at the as-opened checkpoint only,
  that its 2 entries are **not** part of the anchor's 12-entry projection, and that scoring must read
  the checkpoint from the fixture rather than assume the merged head — which is exactly the mismatch
  that invalidated the *v1* ground truth for this subject.

---

## Changes applied

| File | Change |
|---|---|
| `v2/shim/gh` | `--json` blocklist → allowlist; URL targets parsed and date-checked; unresolvable target fails closed |
| `v2/shim/{curl,wget}` | host denial matched case-insensitively; `wget` header named the wrong env var |
| `v2/shim/docs-at` | CDX failure distinguished from absence, 3 retries, logs `ERROR` ≠ `MISS`; dropped `filter=statuscode:200` |
| `v2/fixture_lib.sh` | **new** — resolves any subject id (pooled / null / anchor) to kind, fixture, checkout, threads |
| `v2/run_cell_v2.sh` | uses the loader, so the pooled corpus is addressable; `detect_build` path fixed and its diagnostic kept; PR reference removed from the anthropic prompt; empty output warns; isolation check wired in |
| `v2/detect_build.sh` | accepts a subject dir *or* a checkout |
| `v2/verify_cell_isolation.sh` | **new** — per-cell transcript check for filesystem reads of the answers |
| `v2/verify_null.sh` | falsifying check fails closed; file cap and query failures reported; excluded vs probed split |
| `v2/screen_step0.sh` | transport failure exits 4 with the payload; zero-row ambiguity stated |
| `v2/leak_audit.sh` | `git`, filesystem and docs-at `ERROR` surfaced as their own rows |
| `v2/scoring/score_pooled.py` | guards `judged_severity` (the field the metric divides by) and `matches_key`; `--allow-silent-cells` for the null arm; corpus miss detector split by disposition |
| `v2/scoring/test_score_pooled.py` | 6 new tests, 21 passing |
| `v2/pooled/*/fixture.json` | `threads.rejected` written on the two fixtures that omitted it |
| docs | `METHODOLOGY-v2.md` (status, §4 scoping, **new §4A**, Tier 3 channels, vintage, the 12-entry framing, the Opus contradiction), `v2/README.md`, `v2/scoring/README.md`, `v1-archive/README.md`, `GROUND-TRUTH-AUDIT.md`, `CLAUDE.md` |

Verification after the changes: `test_score_pooled.py` 21/21; the shim probe suite re-run with every
previously-leaking field now DENY and the safe set still ALLOW; `docs-at` serving the SvelteKit page
it used to refuse; all four existing cells checked CLEAN by `verify_cell_isolation.sh`.

## What still needs an operator decision

| Nib | Question |
|---|---|
| `dcc-suz4` | B1 — prevention posture for cell isolation: permission allowlist, sandbox, or accept detection-only |
| `dcc-vvf0` | M5 — resolve "merged after 2026-05" to a date, or accept month-granularity and flag the five May subjects per cell |
| `dcc-nvrt` | The null arm's file probe covered 12 of 33 files on the large subject; seven unadjudicated hits, one in the production file central to the PR |

`dcc-suz4` and `dcc-vvf0` block `dcc-vkeh`.

## One finding that changed the corpus, not just the harness

Fixing `docs-at`'s `filter=statuscode:200` did not only remove false MISSes. It made SvelteKit's
documentation reachable at all — `svelte.dev/docs/kit/routing` now resolves to its 2026-03-31
snapshot where it previously returned "no capture at or before 2026-04-09". Any earlier cell on
`sveltejs/kit#15685` reviewed without documentation it was told it had.
