✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_18-11-35.md`

Tracked source is untouched (only the untracked report directory was added). No prior reviews exist, so the Recurring Findings step was skipped.

## Verdict: ❌ NEEDS_CHANGES — 3 High, 2 Medium

The change re-allows `rating: -1` on the asset update DTO, but the commit it reverses (`99281de`, "refactor!: disallow star rating < 1") had removed `-1` from **five** places. Only the first is restored, leaving `-1` accepted on write, rejected on search, discarded on import, and out-of-range on read.

**#1 🟠 High — `server/src/schema/migrations/1780592070031-ConvertNegativeRatingToNull.ts` (deleted)**
Kysely's `Migrator` throws `corrupted migrations: previously executed migration … is missing` when a row in `kysely_migrations` has no file. The migration was on `main` for three days, so every nightly/dev database that ran it now fails at boot. `allowUnorderedMigrations` guards only the *ordering* check, so dev isn't exempt (`kysely/dist/cjs/migration/migrator.js:447,491-497`). Fix: keep the file, empty the `up()` body. Anchor 75 — the library mechanism is settled from source, but "some real deployment ran it" stays inferential (no Postgres was stood up).

**#2 🟠 High — `server/src/dtos/search.dto.ts:38`** — `BaseSearchSchema.rating` still has `.min(1)`, so a "rejected" asset can be set but never searched for (400 on metadata/random/smart/statistics search). The `x-immich-history` blocks now contradict each other for the same concept.

**#3 🟠 High — `server/src/services/metadata.service.ts:308`** — `validateRange(exifTags.Rating, 1, 5)` nulls out XMP `Rating: -1` on import, which is the Lightroom/Bridge "rejected" convention this feature exists for. Immich writes `-1` to sidecars at `:509,523` but refuses to read it back. User-set values survive refresh (locked-column logic), so damage is confined to ingest.

**#4 🟡 Medium — `server/src/dtos/asset.dto.ts:17-21`** — moving bounds into `.refine()` hides them from the JSON-Schema emitter; the spec now publishes `minimum: -9007199254740991, maximum: 9007199254740991`. `.min(-1).max(5).refine(v => v !== 0)` yields identical runtime validation while keeping `minimum: -1, maximum: 5` in the contract.

**#5 🟡 Medium — `server/src/dtos/exif.dto.ts:32`** — the response schema still declares `minimum: 1` for a field that can now return `-1`. Documentation-vs-behavior divergence only (no `@ZodSerializerDto` is applied), hence Medium.

The predicate itself is correct on every boundary (`-1/1/5/null/undefined` pass, `0/6/-2` rejected), the `.nullable().refine().optional()` ordering is sound, and the "Using 0 as a rating is no longer valid" history entry is factually accurate — verified against `99281de`, where `0` really was coerced to `null`. `asset.controller.spec.ts` passes 42/42.

Caveat worth weighing: `bugs-sp` is the experimental single-seat preset, so these results carry one agent's variance with no validation wave, no clustering, and no evidence screen behind them.
