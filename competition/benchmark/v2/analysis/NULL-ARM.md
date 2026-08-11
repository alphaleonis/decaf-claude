# The null arm — nullness adjudication per subject

Re-adjudicated 2026-08-11 (`dcc-nvrt`) against `verify_null.sh` with the file cap lifted. This is the
durable record the arm was missing: the first adjudication (`dcc-mjj5`) lived only in a nib summary
and covered a *subset* of two subjects, because the probe capped at 12 files and said nothing about
the rest.

The null arm gives pooled precision an absolute scale (METHODOLOGY-v2 §2). It only does that if the
subjects really have nothing to find, so **"no *known* defect" is a claim that has to be re-checked,
not a property recorded once.** Re-run this whenever a null subject is cited.

## Verdicts

| Subject | Size | Files | Probed | Excluded | Files with later fix-shaped commits | Verdict |
|---|---|---|---|---|---|---|
| `jellyfin/jellyfin#16695` | S | 3 | 3 | 0 | 0 | **NULL** |
| `grafana/grafana#122269` | M | 17 | 12 | 5 | 2 — both disjoint | **NULL** |
| `immich-app/immich#28204` | L | 33 | 33 | 0 | 8 — all disjoint | **NULL** |

No subject was replaced. Soak is ~99 days for all three, as of 2026-08-11.

## What the cap was hiding

The probe iterated `files[0:12]`, so coverage depended on the *order* GitHub returns files in:

| Subject | Probed then | Never queried | Hits found then | Hits found now |
|---|---|---|---|---|
| `jellyfin#16695` | 3 | 0 | 0 | 0 |
| `grafana#122269` | 8 | 5 | 1 | 2 |
| `immich#28204` | 12 | 21 | 3 | 8 |

On `immich#28204` the newly-reached files include `server/src/middleware/global-exception.filter.ts`
at index 29 — **the only production file the PR meaningfully changes**, in a PR titled *"structured
validation error responses"*. That is precisely the file the line-level test exists to adjudicate,
and it sat 17 files past the cap.

## Method — why a file hit is not a verdict

METHODOLOGY-v2 §2 already says file-level overlap is *a screen, not a verdict*. The adjudication
compares **the PR's added line texts against each later fix's removed line texts**, which is immune
to the line-number drift between the two commits — a fix that repairs something this PR wrote must
delete or rewrite a line this PR added. Trivial lines (`}`, `});`, short fragments) are dropped so
brace-matching cannot manufacture an overlap.

A fix that only *adds* lines to a file cannot have rewritten a line the PR wrote; those are marked
disjoint on that basis and then read for whether the addition repairs adjacent PR-written behavior.
Every such case here is a new test in an unrelated domain.

## `immich-app/immich#28204` — all 8 hits

PR surface: +456/−185 across 33 files, of which only three are production —
`server/src/middleware/global-exception.filter.ts` (+5/−5),
`open-api/typescript-sdk/src/fetch-errors.ts` (+7/−0), and `web/src/lib/utils/handle-error.ts`
(+12/−0). The other 30 are specs and test helpers. **Neither `fetch-errors.ts` nor
`handle-error.ts` has any later fix-shaped commit at all.**

| File | Later fix | Overlap with PR-added lines | Adjudication |
|---|---|---|---|
| `server/src/middleware/global-exception.filter.ts` | `e4352a781` fix: error log on aborted uploads (#28806) | 0 of 4 | **Different concern, non-overlapping region.** The PR changed the `ZodValidationException` branch of `fromError` (post-merge lines ~40–55). The fix rewrites lines 1–10 and 17–36: it threads `Request` through `catch`/`handleError` and moves error logging out of `fromError` into `handleError` (`logGlobalError` → `onRequestError`). The PR never touched logging, and did not introduce, move or modify any line the fix deletes. |
| `e2e/src/responses.ts` | `a316ba35c` fix: shared check for server setup availability (#30311) | 0 of 3 | Test helper; the fix's 2 removed lines are not PR-written. |
| `server/test/medium/responses.ts` | `a316ba35c` (#30311) | 0 of 3 | Same fix, same shape. |
| `server/src/controllers/auth.controller.spec.ts` | `a316ba35c` (#30311) | 0 of 10 | Addition-only in this file — new test cases for a server-setup check. |
| `e2e/src/specs/server/api/map.e2e-spec.ts` | `b633cc4f0` fix(server): hide partner archived asset locations from map (#29028) | 0 of 4 | Map privacy — an unrelated domain. |
| `e2e/src/specs/server/api/user-admin.e2e-spec.ts` | `f68815e35` (#30314), `6c86d39f6` (#30310) calendar heatmap permissions | 0 of 8 | Both addition-only; new heatmap-permission tests. |
| `server/src/controllers/asset-media.controller.spec.ts` | `83091d283` fix(server): allow non-utc datetime offsets (#29186) | 0 of 6 | Addition-only; datetime handling, unrelated. |
| `server/test/small.factory.ts` | `73329a8ce` OIDC logout (#29720), `b4cc406a3` search visibility (#29385) | 0 of 4 | Test factory; both fixes edit their own fields. |

**Verdict: NULL.** No later fix rewrote a line this PR wrote, and the one production file it changes
was repaired for an unrelated reason (where error logging happens), not for anything the PR did.

## `grafana/grafana#122269` — both hits

| File | Later fix | Overlap | Adjudication |
|---|---|---|---|
| `pkg/services/featuremgmt/registry.go` | `5cceba527` Revert "FeatureToggles: Remove kubernetesQueryCaching and querycaching.redirectToK8SApi…" (#130059) | 0 of 6 | Addition-only, and about different toggles. The registry is the append-only shared file the §2 screen names explicitly. |
| `pkg/setting/setting.go` | `9d7f3b569` fix(annotations): use grafana-apiserver tls config for annotation service client (#128543) | 0 of 13 | Annotation-service TLS, unrelated to the Grafana.com token this PR adds. |

`setting.go` is one of the five files the old cap never reached, so this hit is new.

The 5 files excluded as shared/generated are `conf/defaults.ini`,
`docs/sources/setup-grafana/configure-grafana/_index.md`, and the three
`pkg/services/featuremgmt/toggles_gen.{csv,go,json}`. All five are append-only in this PR (+1, +7,
+1, +4, +69 additions, zero deletions), so there is no PR-written line in them for a later fix to
rewrite. The exclusion is justified here; it is recorded rather than assumed.

**Verdict: NULL.**

## `jellyfin/jellyfin#16695`

3 files, all probed, no later fix-shaped commit on any of them, no revert or regression
cross-reference. **Verdict: NULL**, with no adjudication required.

## Reproducing

```sh
v2/verify_null.sh <owner/repo> <pr>          # default cap is now 100, was 12 (dcc-nvrt)
```

The verdict line distinguishes `NULL-OK`, `REVIEW` (file hits needing line-level adjudication),
`REJECT` (a revert or regression cross-reference) and `INCONCLUSIVE` (a query failed — not a pass).
A `REVIEW` is not a failure; it is the point at which this document gets another row.
