I'll start by invoking the requested skill.
I'll start by gathering context on the change.
**Review team** (preset `review` (explicit) · roster N=8 · models=norm · evidence=norm · reach=norm):

- `quick-reviewer` — always (floor), mid tier
- `broad-reviewer` — always (floor), mid tier
- `adversarial-reviewer` — data-mutation surface (asset rating persisted to `asset_exif`), session model
- `design-reviewer` — public API contract + OpenAPI schema change, session model
- `typescript-reviewer` — hard gate: TS files; idiom surface = Zod `nullable/refine/optional` composition, mid tier
- `data-migration-reviewer` — hard gate: a migration file is deleted in this diff, mid tier
- `test-reviewer` — hard gate: `asset.controller.spec.ts` in changeset, mid tier
- `consistency-reviewer` — sibling DTOs (`search.dto.ts`, `exif.dto.ts`) carry the same `rating` contract, mid tier
- `knowledge-reviewer`: dropped — roster N=8 (override): ranked last (measured drop cost 0.17)
- `security-reviewer`: dropped — roster N=8 (override): trust-boundary trigger is a validation *relaxation* only; ranked below the kept specialists
- `spec-compliance-reviewer`: skipped — no spec found (hard gate)
- `performance-reviewer`: skipped — no queries, loops, or caching in the diff
- `prior-feedback-reviewer`: skipped — local commit range, no PR threads (hard gate)

**Roster note:** the size-derived default was N=4 (26 executable lines). I raised it to 8 because three hard gates fire on this diff (migration artifact, test file, TS idiom surface) and the derived cap would have traded away two of them on a change whose entire substance is those domains.

**Pre-flight gates** (run once): `pnpm install --frozen-lockfile` OK (after building the `@immich/sdk` → `@immich/plugin-sdk` workspace chain, which is required and unrelated to this change); `tsc --noEmit` **clean**; `vitest run src/controllers/asset.controller.spec.ts` **42 passed**.
Now dispatching the wave.
All eight reports are in. Running the feasible nominated probes and resolving conflicting claims.
Wave complete. I verified several load-bearing claims directly (kysely's `#ensureNoMissingMigrations`, `metadata.service.ts:308`, the deleted e2e/unit tests, the "was 0 ever valid" question, and a project precedent for deleting a main-only migration). Now dispatching the validation wave on the three clusters those checks left unsettled.
All three validated as **confirmed**, and I verified the crux of #1 myself. Writing the report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_15-23-08.md`

**Verdict: ❌ NEEDS_CHANGES** — 1 Critical, 4 High, 3 Medium, 2 Minor, 1 pre-existing.

The change partially reverts commit `99281de` ("disallow star rating < 1"), which had touched **29 files**. This change touches **4** of them. Most findings are consequences of that.

**The headline — the change does not achieve its purpose.** `server/src/services/metadata.service.ts:308` still clamps ingested ratings to `[1,5]`; `99281de` narrowed it from `-1` in the same edit as the DTO, and this change does not revert it. I traced the full chain and confirmed it needs no unusual user action:

`PUT {rating:-1}` → 200 → `asset.service.ts:527` queues `SidecarWrite` → `metadata.service.ts:539` writes `Rating: -1` to the `.xmp` **and releases the property lock** → `job.service.ts:75-81` unconditionally chains `AssetExtractMetadata` → line 308 clamps `-1` → `null`. Silently, on the standard job pipeline. The two tests that would have caught it (an e2e and a `metadata.service.spec.ts` unit test) were deleted by `99281de` and are not restored.

**The other four High findings:**
- `search.dto.ts:36` still rejects `-1`, so a `-1`-rated asset is findable by no rating filter.
- Moving the bound into `.refine()` erased it from the OpenAPI contract — `minimum` is now `-9007199254740991`. Found by 6 of 8 agents; reproduced empirically against the repo's `zod@4.3.6`.
- Deleting an already-executed migration trips Kysely's unconditional `corrupted migrations` guard → boot loop for anyone on the `:main` image.
- No test anywhere asserts `-1` is accepted.

**Two things worth flagging about the review itself:**

1. I **overrode** the derived roster (4 → 8). Three hard gates fire on this 26-line diff and the derived cap would have dropped two of them. Documented in the report.
2. I **rejected one corroborated reviewer claim**. Two agents called the new `"Using 0 as a rating is no longer valid"` history entry fabricated. It is accurate — `git show 99281de^` shows the pre-v3 schema accepted `0` and coerced it to `null`, and `99281de` made it a 400. The surrounding history problems are real (a published `v2.6.0` entry deleted; `search.dto.ts` still carries it verbatim) and are Finding #7; that sub-claim is not.

One disagreement is unresolved rather than papered over: the validator on the Kysely boot-crash recommends Medium (narrow `:main`-only exposure, plus a project precedent at `0975b15`); I kept it at High. Both positions and their evidence are in the report.

Two probes could not be run — no Postgres instance or e2e stack — so the migration boot-crash and the sidecar round-trip were settled by static trace plus independent validation, not execution. Both are recorded as `probe not run` with the reason. No tracked file was modified.

