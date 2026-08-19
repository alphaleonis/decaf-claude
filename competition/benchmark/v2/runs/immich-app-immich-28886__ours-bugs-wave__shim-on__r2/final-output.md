✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_17-58-00.md`

**Verdict: ❌ NEEDS_CHANGES** — 4 High, 2 Minor. All four primaries independently validated; nothing refuted.

The change restores `rating: -1` on exactly one surface — the asset update request DTO — while the commit it reverts (`99281de`) had removed it from six. Three of the four findings are that same omission seen from different endpoints:

1. **`server/src/dtos/search.dto.ts:36-49`** — still `.min(1).max(5)`. You can write `rating: -1` to mark an asset rejected, but filtering for it 400s on all four search endpoints. Verified by parsing through the real schemas: `UPDATE rating=-1 => ACCEPTED` / `SEARCH rating=-1 => REJECTED`. No alternative route to find rejected assets exists.

2. **`server/src/dtos/asset.dto.ts:16-23`** — swapping `.min(1).max(5)` for a `.refine()` erases the bounds from the generated OpenAPI contract, which now publishes `minimum: -9007199254740991` next to a description saying "range [1-5]". `quick-reviewer` dismissed this as a pre-existing spec-wide pattern; the validator overturned it by counting occurrences of the literal across both specs — 228 → 232, a delta of exactly the two `rating` fields this diff touches.

3. **`server/src/services/metadata.service.ts:308`** — still clamps to `validateRange(…, 1, 5)`. A user-set `-1` is written to the XMP sidecar, `rating` is then unlocked, and the next Refresh Metadata reads `-1` back, clamps it to `null`, and silently erases the mark. Every link re-derived from source twice, independently.

4. **`server/src/controllers/asset.controller.spec.ts:251`** — nothing in the repo asserts `-1` is accepted. I ran the probe: with `v === -1 ||` deleted from the predicate (feature entirely removed), the spec still reports 42 passed. Tree restored byte-identical afterwards, sha verified.

**Two things you should weigh yourself:**

**The deleted migration (M2).** I tiered it to Minor rather than Critical, and I'd rather you overrule me than not see the reasoning. The mechanism is certain — Kysely's `#ensureNoMissingMigrations` runs unconditionally and `runMigrations()` rethrows, so any DB carrying that row fails to boot permanently. What I could not establish is whether it reached a real deployment: the migration sat on mainline ~3 days, this clone has no git tags, and there's a close precedent (`0975b15` deleted a migration with a real `ALTER TABLE` after four days on mainline). **If you know a nightly or RC shipped in that window, this is a Critical** and the fix is keeping the file with a no-op `up()`.

**Roster coverage traded away.** The `bugs` preset caps the roster at 4, which dropped `data-migration-reviewer` (the agent that would have settled M2) and `typescript-reviewer` (whose zod idiom lane is where finding #2 originates) — both had matched their hard gates. Re-running as `bugs roster=6` would close that gap.

Two pre-flight gotchas worth knowing for this repo: `pnpm install --filter @immich/server...` matches nothing and exits 0 silently (the package is named `immich`), and the server won't typecheck or test until `packages/sdk` then `packages/plugin-sdk` are built.
