I'll run the code review skill as requested.
I'll start by gathering context on the change under review.
Let me gather context before dispatching the review wave.
Let me announce the review team while dependencies install.

**Review team** (preset `bugs` — explicit · roster N=4 (capped by `bugs`; ~26 executable lines) · models=low · evidence=strong · reach=narrow):

- **quick-reviewer** (always) — mid tier
- **broad-reviewer** (always) — mid tier
- **adversarial-reviewer** — data-mutation domain (asset update + a deleted data migration) at any size — session model
- **test-reviewer** — test files present (hard gate) — mid tier
- `typescript-reviewer`: **dropped — roster cap N=4**: hard gate matched (zod/TS idiom surface dominates this diff), but it ranks below the measured specialists kept. Coverage traded away.
- `data-migration-reviewer`: **dropped — roster cap N=4**: hard gate matched (a migration file is deleted in this diff). Coverage traded away — consider `bugs roster=6`.
- `design-reviewer`, `security-reviewer`, `knowledge-reviewer`, `consistency-reviewer`: dropped — roster cap N=4, ranked below the specialists kept.
- `spec-compliance-reviewer`: skipped — no spec found (hard gate). `performance-reviewer`, `prior-feedback-reviewer`: skipped — gates unmatched.
Dependencies installed. Running shared pre-flight gates.
Pre-flight complete. Dispatching the review wave.
All four reports are in. Now running nominated probes (I'm the only actor on the tree).
Confirmed the schema asymmetry empirically. Now the tracked-file probe (test coverage), under the snapshot protocol.
Probe confirmed. Restoring the tree exactly.
Tree verified byte-identical. One more check for the metadata round-trip finding.
Probes complete and the tree is verified clean. Clustering inline (n=8 raw findings, grouping mechanically unambiguous — recorded as an orchestrator fallback), now screening each cluster against the `evidence=strong` bar.
Screen scores are in. Now the validation wave on surviving primaries, plus a check on the precedent that drove C3's score down.
All four validators confirmed. Checking the C3 precedent result and prior reviews.
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

