I'll start by invoking the requested skill.
Context gathered. Announcing the team:

```
Review team (preset `review` — explicit · roster N=7 (orchestrator override, see rationale) · models=norm · evidence=norm · reach=norm):
- quick-reviewer (always) — mid tier
- broad-reviewer (always) — mid tier
- adversarial-reviewer — data-mutation domain: validation boundary + a dropped data migration — session model
- design-reviewer — public API contract + OpenAPI/generated-client surface changes — session model
- data-migration-reviewer — hard gate: a migration file is deleted in the diff — mid tier
- typescript-reviewer — hard gate: TS files; idiom surface = zod refine/nullable/optional composition at a runtime boundary — mid tier
- test-reviewer — hard gate: test files present — mid tier
- knowledge-reviewer: dropped — roster N=7: ranked last (measured drop cost 0.17)
- consistency-reviewer: dropped — roster N=7: ranked last (measured drop cost 0.00)
- security-reviewer: skipped — no trust-boundary trigger beyond input-range validation already covered
- performance-reviewer: skipped — no queries, loops, or caching in the diff
- spec-compliance-reviewer: skipped — no spec found (hard gate)
- prior-feedback-reviewer: skipped — local commit range, no PR threads (hard gate)
- cpp/go/rust/dotnet-reviewer: skipped — languages absent (hard gate)
```
All seven reviewers returned. Running Step 4.5 probes and verifying the load-bearing mechanisms myself.
Mechanisms verified. Dispatching the validation wave on the two Criticals.
Tree is clean — only the untracked `.decaf/` report was added; no tracked source touched, nothing posted anywhere.

✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_16-50-58.md`

## Verdict: ❌ NEEDS_CHANGES

2 Critical, 3 High, 4 Medium primary findings. Both Criticals were confirmed by independent validators, and I verified their mechanisms directly rather than relying on the reviewers.

**#1 — `server/src/services/metadata.service.ts:308`: the feature does not survive its own write path.** The DTO now accepts `rating: -1`, but extraction still clamps to `[1,5]`, and the write path routes every rating edit back through it: `updateExif` locks `rating` and queues `SidecarWrite` → `handleSidecarWrite` writes `Rating: -1` to XMP then **unlocks** `rating` (`:539`) → `onDone` queues `AssetExtractMetadata` (`job.service.ts:75`) → `validateRange(-1, 1, 5)` returns `null`, and `lockedPropertiesBehavior: 'skip'` no longer protects the column. `asset_exif.rating` becomes `NULL`. Ratings `1..5` survive the identical loop. A probe with the installed `exiftool-vendored` confirmed XMP `Rating: -1` round-trips, so extraction really does read `-1`. The validator corrected `pre_existing` to false: that clamp was tightened in lockstep with the DTO rejecting `-1`, so this change is what makes the cascade reachable.

**#2 — deleted migration blocks startup.** Kysely's `#ensureNoMissingMigrations` (`migrator.js:491`) throws unconditionally, and is called at `:447` *before* the `allowUnorderedMigrations` gate — so immich's dev-only flag cannot suppress it. `runMigrations()` rethrows; `onBootstrap` awaits it unguarded; `skipMigrations` defaults to false. `docker.yml` publishes a `main` image on every push, so instances tracking `main` ran it in the 3-day window. The precedent the design reviewer surfaced (`0975b15`) turned out to be a scratch file named `Test` for an unreleased table — it shows the practice has happened, not that this mechanism was considered.

**Highs:** `-1` is settable but not searchable (`search.dto.ts:36`, 4 finders); the published response contract can't represent it (`exif.dto.ts:32`); and no test asserts `-1` is accepted or `0` rejected — the diff edits that exact describe block.

Worth noting beyond the individual findings: the revert touched one of the four places the API expresses `rating`. A script over the committed spec shows one document simultaneously claiming `-1` is valid (update DTOs) and "no longer valid" (all four search DTOs). The structural fix is a shared `ratingSchema` in `validation.ts`, alongside the existing `latitudeSchema`/`longitudeSchema` — filed as P1.

Two caveats on the report itself, both recorded in it: pre-flight gates were **not runnable** (`@immich/plugin-sdk` has no built `dist/` here), so no finding rests on a test run; and I deviated from the skill in four places — sequential rather than single-message wave dispatch, and inline clustering/screening instead of dispatched agents, justified by having already settled the mechanisms with direct evidence.

