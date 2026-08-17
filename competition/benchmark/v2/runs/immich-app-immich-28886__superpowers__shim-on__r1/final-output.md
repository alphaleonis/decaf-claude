Reviewer subagent's report, verbatim:

---

### Strengths

- **Runtime validation semantics are exactly right.** I ran the new schema in isolation against the repo's own Zod: `undefined`→pass, `null`→pass, `-1`→pass, `1`/`5`→pass, `0`/`7`/`-2`→"Must be -1, a number from 1 to 5, or null", `3.5`→"expected int". No accidental holes, and `.optional()` correctly placed after `.refine()` so an omitted field short-circuits.
- **Convention-conformant.** `{ error: ... }` (not `message:`) matches the dominant refine style in `server/src/dtos/` (activity, editing, bbox, maintenance, person, system-config all use `error:`).
- **Generated artifacts are genuinely in sync with the source.** I regenerated the JSON Schema for the new field by hand and it matches `open-api/immich-openapi-specs.json` byte-for-byte in shape (including the safe-integer bounds); the Dart and fetch-client deltas are comment-only and consistent. No stale-generation problem.
- **Migration removal is clean.** `grep` for `1780592070031` across `server/`, `e2e/`, `docs/` finds nothing; migrations are directory-discovered, and the neighboring `1780592071031-AssetOcrSync.ts` is unaffected. No dangling reference.
- **`server/src/controllers/asset.controller.spec.ts` passes** (`vitest run --config test/vitest.config.mjs src/controllers/asset.controller.spec.ts` → 42/42).

---

### Issues

#### Critical (Must Fix)

**1. The revert is incomplete: `-1` is still stripped on metadata extraction, and the sidecar round-trip silently destroys it**

`server/src/services/metadata.service.ts:308`
```ts
rating: exifTags.Rating === 0 ? null : validateRange(exifTags.Rating, 1, 5),
```
Commit #27896 changed this from `validateRange(exifTags.Rating, -1, 5)` and this diff did not change it back. Two consequences:

- **The original point of `-1` is not restored.** `xmp:Rating = -1` is the standard "rejected" flag written by Lightroom/darktable/Bridge. Importing such a file still discards it (`validateRange` returns `null` when out of range). So `-1` is now settable only via the API — the file-sourced path that motivates the value at all is still closed.
- **Data loss on round-trip.** `handleSidecarWrite` (`metadata.service.ts:510,523`) writes `Rating: asset.exifInfo.rating ?? 0` to the `.xmp`, then `metadata.service.ts:539` calls `unlockProperties(...)`, releasing the lock that `AssetService.updateExif` set (`asset.service.ts:525`, `lockedPropertiesBehavior: 'append'`). Any later extraction (file-change detection, "Refresh metadata" job) re-reads `Rating: -1`, `validateRange(-1, 1, 5)` returns `null`, and the asset's rating is overwritten with `NULL`. Documented write-back behavior confirms the flow: `docs/docs/features/xmp-sidecars.md:14,47`.

  [Inference] I traced this path by reading the code rather than executing the job chain end-to-end; each link (write `-1` → unlock → re-extract → clamp to null → `upsertExif`) is explicit in the source, but I did not run a live extraction to observe the final `NULL`.

**Fix:** restore `validateRange(exifTags.Rating, -1, 5)` and restore the `should handle valid negative rating value` test deleted from `server/src/services/metadata.service.spec.ts` by #27896.

**2. Search/filter DTOs still reject `-1`, so the API contradicts itself within one version**

`server/src/dtos/search.dto.ts:36-48` still has `.min(1)` and still carries the history entry `v3 — "Using -1 as a rating is no longer valid."`. Net effect today:

- `PUT /assets/:id  { "rating": -1 }` → **200**
- `POST /search/metadata { "rating": -1 }` → **400**

A user can mark assets rejected and then has no way to find them. This affects all four search schemas derived from `BaseSearchSchema` (`MetadataSearchDto`, `RandomSearchDto`, `SmartSearchDto`, `StatisticsSearchDto` — verified in the committed spec, all still `minimum: 1`). The v3 history text there is now factually wrong.

**Fix:** apply the same relaxation (and the same history correction) to `BaseSearchSchema.rating`.

#### Important (Should Fix)

**3. The published contract lost the `[1-5]` bound entirely**

`server/src/dtos/asset.dto.ts:16-23`. Because `.refine()` is opaque to JSON-Schema conversion, dropping `.min()/.max()` leaves an unconstrained `z.int()`. Confirmed output:

```json
"rating": { "maximum": 9007199254740991, "minimum": -9007199254740991, "type": "integer", ... }
```

This is not cosmetic: the generated Dart SDK now ships `/// Minimum value: -9007199254740991` in `mobile/openapi/lib/model/update_asset_dto.dart:82` and `asset_bulk_update_dto.dart:100`, any client-side or gateway validation driven by the spec now accepts `rating: 4000000000` (which the server rejects, and which would overflow the `int4` column if it didn't), and the docs page for the field is misleading. It also makes the description the *only* statement of the constraint.

**Fix (verified — I ran both):** keep the bounds in the type and use the refine only to punch out `0`:
```ts
rating: z.int().min(-1).max(5).refine((v) => v !== 0, { error: '0 is not a valid rating' }).nullish()
```
emits `{"type":"integer","minimum":-1,"maximum":5}` and accepts exactly `{-1, 1..5, null}`. A `z.union([z.literal(-1), z.int().min(1).max(5)])` also preserves the bounds but emits nested `anyOf` with a `const`, which is a bigger change for the OpenAPI 3.0 `nullable: true` pipeline and the Dart generator — I'd prefer the first form.

**4. `ExifResponseDto` still declares `minimum: 1`, so the response contract now lies**

`server/src/dtos/exif.dto.ts:32` — `rating: z.int().min(1).max(5).nullish()`, also tightened by #27896 and not reverted. The server can now return `rating: -1` in `exifInfo`, while the spec (and every generated client's doc/validation) says the minimum is 1. Runtime impact is currently nil because no controller uses `@ZodSerializerDto` (grep finds only the `// TODO: use ZodSerializerDto` comments), so the globally-registered `ZodSerializerInterceptor` is a pass-through — but the moment those TODOs are done, a `-1` rating becomes a serialization failure. **Fix:** revert to `.min(-1)` (or drop the bound) alongside the request DTOs.

**5. The behavior actually being restored has no positive test**

`server/src/controllers/asset.controller.spec.ts:238-258`. The diff only rewrote two expected *error strings*. `should leave correct ratings as-is` (line 251) still iterates `[{ rating: 1 }, { rating: 5 }]` — `{ rating: -1 }`, removed by #27896, was not put back. So nothing asserts that `-1` is accepted and forwarded to the service; the only mention of `-1` in the suite is inside an error message literal. Likewise the e2e case `should set the negative rating` (deleted from `e2e/src/specs/server/api/asset.e2e-spec.ts` by #27896) was not restored — `grep` shows the remaining e2e rating coverage is `rating: 2`, `rating: 5`, and `rating: 3`. **Fix:** add `{ rating: -1 }` to the as-is loop and restore the e2e case.

**6. Rejecting `0` is a second behavior change, unmentioned in the commit messages and untested**

Before #27896 the schema was `.min(-1).max(5).transform((v) => v === 0 ? null : v)` — `rating: 0` was accepted and coerced to `null`, and there was a test named `should convert rating 0 to null`. This diff restores `-1` but not the coercion, so `0` now returns **400** (I confirmed this against the live schema). That may well be the intent for a major version, and the new history entry documents it — but it is a distinct breaking change from "allow -1 again", it isn't in any commit message, and no test pins it. Immich's own web and mobile clients send `null` to clear (`web/.../DetailPanelStarRating.svelte:18`, `mobile/.../rating_details.widget.dart` post-#27896), so first-party impact is nil; third-party clients that sent `0` move from "silently cleared" to "hard 400". **Fix:** confirm the intent and add a `{ rating: 0 }` case to the rejection loop.

#### Minor (Nice to Have)

**7. Deleting the `v2.6.0` history entry rewrites the record of a shipped release** — `server/src/dtos/asset.dto.ts:25-29`. `-1` *was* deprecated in v2.6.0; that happened, and `x-immich-history` reads as an append-only changelog everywhere else. `search.dto.ts:46` still carries the identical v2.6.0 entry, so the two rating fields now tell different stories about the same past release. Preferred shape: keep `.updated('v2.6.0', ...)` and add a v3 entry stating that `-1` is valid again.

**8. The new v3 history text describes the wrong change** — `asset.dto.ts:28` says only `"Using 0 as a rating is no longer valid."` The headline v3 delta for a consumer coming from v2.6.0 (where `-1` was announced as going away) is that `-1` *survived*. Say both.

**9. Error-message wording** — `'Must be -1, a number from 1 to 5, or null'` mixes a literal, a range, and a nullability statement, and reads oddly for a field that may also be omitted. Something like `'Rating must be -1, an integer from 1 to 5, or null'` is closer to the surrounding style. Purely a nit.

**10. Release-note item, not a code fix** — anyone who ran a `main` build between #27896 and this revert already had `1780592070031` applied, converting their `-1` ratings to `NULL` irreversibly (`down()` was a documented no-op). Deleting the migration correctly prevents *new* damage but cannot undo it. Worth a line in the changelog for main-tracking users.

Context, no action needed: `server/src/services/duplicate.service.ts:258-266` merges ratings with a `0` baseline and `> 0` guard, so `-1` is ignored when consolidating duplicates. That's arguably correct for a "rejected" marker and is pre-existing behavior.

---

### Recommendations

1. **Treat this as "revert #27896's server behavior", not "edit one DTO".** #27896 touched five server source files (`asset.dto.ts`, `search.dto.ts`, `exif.dto.ts`, `metadata.service.ts`, plus specs) and one e2e file; this change touched one of them. Diffing against the commit being reverted (`git show 99281de -- server/ e2e/`) is the fastest way to find what's left — items 1, 2, 4, and 5 all fall out of that single comparison.
2. **Prefer schema-expressible constraints over `.refine()` on anything that reaches the OpenAPI spec.** In a codebase whose public contract, three SDKs, and docs are all generated from these schemas, a `.refine()` is invisible to every consumer. The `.min(-1).max(5).refine(v => v !== 0)` form gets identical runtime behavior with a truthful spec.
3. **Add a regression test at the boundary that actually broke.** The XMP round-trip (set `-1` → sidecar write → re-extract) is where the value silently dies and is exactly the case no unit test covers. A medium/e2e test asserting the rating survives a metadata refresh would catch this class of incomplete revert.
4. **Squash before merge.** `udpate tests` (typo) and `gen clientc` don't belong in the history of a `refactor(server):` change.

---

### Assessment

**Ready to merge?** No.

**Reasoning:** The DTO edit is correct in isolation and its runtime semantics check out, but the revert stops at the DTO: `metadata.service.ts` still clamps ratings to `1..5`, so `-1` cannot be imported from XMP and — worse — an API-set `-1` is written to the sidecar and then silently converted to `NULL` on the next metadata extraction, while `search.dto.ts` still rejects `-1` so those assets can't be filtered for. Items 1 and 2 are merge blockers; item 3 (the spec losing its `[1-5]` bound and shipping `Minimum value: -9007199254740991` into the public Dart SDK) should be fixed in the same pass since it requires regenerating the same artifacts.
