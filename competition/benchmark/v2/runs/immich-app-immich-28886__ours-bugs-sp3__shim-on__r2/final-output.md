✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_18-27-40.md`

**Mode**: `bugs-sp` (explicit) · roster=1 fixed · reach=narrow · single seat on the session model. No screen, no validation wave — every anchor below is the seat's own self-calibration with no independent check, so treat it as bearing one agent's variance.

**Verdict: ❌ NEEDS_CHANGES** — 3 High, 3 Medium, 2 Low.

The organizing observation: this is a *partial* revert of `99281de` ("refactor!: disallow star rating < 1"). That commit tightened six server files plus mobile; this change reverts one of them (`asset.dto.ts`) and drops the migration. The **write path accepts `-1` again while the read path, the search path, and the response contract still reject it.**

**High**

1. `server/src/services/metadata.service.ts:308` — still `validateRange(exifTags.Rating, 1, 5)`. A `-1` set via the API is written to the sidecar, the property lock is then *released* (`:539`), and the next metadata extraction clamps `-1` → `NULL`. The rejection silently disappears; the same clamp also drops `-1` on import from Lightroom/Bridge. Full round trip traced through source (not executed — no Postgres available).
2. `server/src/dtos/search.dto.ts:38` — still `.min(1).max(5)`, inherited by metadata/smart/random/statistics search. `-1` becomes a **write-only state**: you can set it but no query can filter for it (400). Its `x-immich-history` also still publishes "Using -1 as a rating is no longer valid" while `asset.dto.ts` now documents `-1` as valid — the shipped spec carries both claims.
3. Deleting `1780592070031-ConvertNegativeRatingToNull.ts` — the migration already merged to `main` (2026-06-04) and `main` publishes images per push, so upgraded and dev DBs have it in `kysely_migrations`. Kysely 0.28.17 `#ensureNoMissingMigrations` runs unconditionally and throws `corrupted migrations`; bootstrap rethrows. Those instances won't start. (Precedent exists — `0975b15` did the same — but the failure mode is unchanged.) Suggested fix: keep the file, make `up()` an explicit no-op.

**Medium**

4. `server/src/dtos/asset.dto.ts:17-21` — `.refine()` isn't expressible in JSON Schema, so the bounds vanish from the contract: the spec now advertises `minimum: -9007199254740991, maximum: 9007199254740991`, and the generated Dart client documents that range. Verified by running `z.toJSONSchema` on both chains. A `.min(-1).max(5)` + `refine(v => v !== 0)` variant was verified to behave identically while keeping real bounds.
5. `server/src/dtos/exif.dto.ts:32` — response DTO still declares `[1,5]` while `GET /assets/:id` can now return `-1`. Not a runtime failure yet (no `@ZodSerializerDto` in use), but it will be one when the file's own TODO lands.
6. `server/src/dtos/asset.dto.ts:24-29` — the shipped `v2.6.0` history entry is *deleted* rather than superseded (`HistoryBuilder` is append-only), and nothing records that the `-1` deprecation was rescinded; the surviving `v3` entry documents someone else's `0` change instead.

**Low**: web renders `-1` identically to unrated (`-1 || null` → `-1`, no star fills), with `as Rating` masking the type violation; and nothing in the suite asserts `-1` is *accepted* — the seat ran the changed spec (42/42 pass) and confirmed the tests pass either way, so the change's purpose is unverified.

Verified as genuinely correct: the refinement's runtime behavior (executed against `-1`, `0`, `-2`, `7`, `3.5`, `null`, `undefined`), the updated test expectations (real messages, not loosened matchers), and the OpenAPI regeneration (byte-identical to the committed file — codegen is in sync). Working tree verified clean afterward; nothing was modified or posted.
