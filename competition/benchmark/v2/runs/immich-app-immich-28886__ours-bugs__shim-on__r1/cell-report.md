I'll run the code review skill as requested.
I'll start by gathering context on the change under review.
Small, focused change. Let me classify it and check the project's gates.
Dependencies build now. Running the pre-flight gates.
**Pre-flight gates**: `tsc --noEmit` clean; `asset.controller.spec.ts` 42/42 pass. (Required building `packages/sdk` and `packages/plugin-sdk` first — unrelated to this change.)

**Changeset classification**: ~26 changed executable lines (excl. generated `open-api/*.json`, `packages/sdk/src/fetch-client.ts`, Dart binaries) — a Zod validation-schema change on an API contract, a test update, and a deleted DB migration.

```
Review team (preset `bugs` — explicit · roster N=4 (derived: 26 executable lines) · models=low · evidence=strong · reach=narrow):
- quick-reviewer (always) — mid tier
- broad-reviewer (always) — mid tier
- adversarial-reviewer — data-mutation domain (asset rating writes); rank-1 specialist by measured drop cost — session model
- data-migration-reviewer — hard gate: a production data migration is DELETED in this diff — mid tier
- test-reviewer: dropped — roster N=4 (derived): hard gate matched (test file changed) but only 4 assertion lines, covered by the floor
- typescript-reviewer: dropped — roster N=4 (derived): hard gate matched, ranked below the 2 specialists kept
- design-reviewer / security-reviewer / knowledge-reviewer / consistency-reviewer: dropped — roster N=4 (derived): ranked below the 2 specialists kept
```

⚠️ Two hard-gate agents (`test-reviewer`, `typescript-reviewer`) were traded away to the `bugs` preset's cap of 4. Re-run with `bugs roster=6` if you want that coverage.
All four reviewers returned. Running verification probes now that I'm the only actor on the tree.
Static trace confirmed end-to-end. Dispatching the validation wave on the four findings the screen left open.
All four validators confirmed. Writing the report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_17-36-23.md`

Working tree unchanged — only the untracked `.decaf/` report was added.

## Verdict: ❌ NEEDS_CHANGES

**The change does not deliver what its title promises.** Commit `99281de` restricted `rating` in **four** server files; this change reverts only `asset.dto.ts`.

| # | Sev | Finding |
|---|---|---|
| 1 | 🔴 | Deleting the already-merged migration makes affected databases **fail to boot** |
| 2 | 🔴 | A `-1` rating is accepted, then **silently destroyed** by the server's own job pipeline |
| 3 | 🟠 | `.refine()` **erases the bound** from the published OpenAPI contract |
| 4 | 🟠 | Search DTOs still reject `-1` — rejected assets are settable but **unfindable** |
| 5 | 🟡 | EXIF response schema still declares `[1-5]`, so `-1` violates the published contract |

All four validators returned **confirmed**; zero refuted.

### The two that matter most

**#2 — `server/src/services/metadata.service.ts:308`.** I traced every link and a validator re-derived it independently. `PUT /assets/:id {rating:-1}` → `updateExif` locks `rating` and queues `SidecarWrite` → `handleSidecarWrite` writes `Rating: -1` to XMP then **unlocks** `rating` (`metadata.service.ts:539`) → `job.service.ts:75-81` chains to `AssetExtractMetadata` → line 308 still reads `validateRange(exifTags.Rating, 1, 5)`, which returns `null` for `-1` → `upsertExif` with `lockedPropertiesBehavior: 'skip'` no longer skips, so **`NULL` overwrites the `-1`**. Ratings 1–5 round-trip fine; only the newly re-enabled value is lost. `99281de` also deleted the unit and e2e tests that would have caught this, and neither is restored.

**#1 — the deleted migration.** Kysely's `#ensureNoMissingMigrations` (migrator.js:491-498) throws `corrupted migrations: …` and runs at line 447, *before* the `allowUnorderedMigrations` gate. `runMigrations()` rethrows, and the validator traced the throw all the way up through `event.repository.ts:227-237` with no `try/catch` anywhere — restart loop until an operator hand-edits `kysely_migrations`. The population is real: the migration was on `main` for 3 days, `.github/workflows/docker.yml` pushes images on every `main` push, the *following* migration is retained, and this repo already did exactly this once (`0975b15`).

### Two things to know about the run

- **Roster cap traded away hard-gate coverage.** The `bugs` preset capped the roster at 4, dropping `test-reviewer` and `typescript-reviewer` despite both hard gates matching. Re-run as `bugs roster=6` if you want it.
- **One confirmed bug was tiered down by `evidence=strong`** and sits in Considered But Not Flagged: `duplicate.service.ts:258-267` computes `let rating = 0; … if (rating > 0)`, so merging a rejected (`-1`) duplicate into an unrated keeper silently discards the rejection. Single finder, score 60 — real, but below the `bugs` bar. Worth a look.

I deviated from the skill on two steps — clustering (4.9) and screening (4.95) were done inline rather than by dispatched agents, since the overlaps were exact and I had already verified each claim against source. Both deviations, plus the four nominated probes I did *not* execute as tree mutations, are recorded in the report's Anomalies section.

