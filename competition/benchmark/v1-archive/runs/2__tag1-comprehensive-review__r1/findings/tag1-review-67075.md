# Comprehensive Review — dotnet/aspnetcore PR #67075

**PR:** #67075 — "Fixed AmbiguousMatchException in DataAnnotationsValidator for Hidden Members"
**Base:** `main` · **Head:** `gh27095BugFix` · **State:** MERGED (reviewed post-merge as a quality pass)
**Reviewed diff:** `2519925824867017abb95629d51d995df9c5663e...3b00cfca` · 2 files, +168/-1 · **Tier:** small · C#
**Mode:** `--local` (nothing posted) · Fixes issue [#27095](https://github.com/dotnet/aspnetcore/issues/27095)

## Summary

Fixes `AmbiguousMatchException` thrown by `Type.GetProperty(string)` in `EditContextDataAnnotationsExtensions.TryGetValidatableProperty` (`EditContextDataAnnotationsExtensions.cs:370`) when a Blazor form model has a property hidden via `new` in a derived class. The fix queries with `BindingFlags.Public | Instance | DeclaredOnly` first (resolving the most-derived declaration), then falls back to `BindingFlags.Public | Instance | FlattenHierarchy` if nothing is declared on the leaf type. **No exception is caught or retried** — this differs from the PR narrative, which describes catching `AmbiguousMatchException` and retrying with `DeclaredOnly`. Adds 7 unit tests (the narrative says 3) plus member-hiding model fixtures.

**Type:** Bug fix
**Effort:** 2/5 — a two-lookup change to one method plus test additions; no API-surface or schema change.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs` | Modified | `GetProperty` now tries `DeclaredOnly` first, falling back to `FlattenHierarchy`, to avoid ambiguous matches on `new`-hidden properties (lines 370–379) |
| `src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs` | Modified | Adds 7 `[Fact]` tests + nested fixture classes covering hidden/shadowed properties, caching, multi-level inheritance, unattributed shadows, and static-property exclusion (+158) |

---

## Review Findings

**Overall Risk:** High — the fix does not fully eliminate the exception it targets; a specific but realistic model-hierarchy shape still crashes on field edit.

### High (1)

- **[edge-case-hunter / code-reviewer / adversarial-general / blind-hunter / dotnet-reviewer] Incomplete fix — `AmbiguousMatchException` is still thrown for intermediate-ancestor member hiding.** — `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:376` — **CONFIRMED (empirically verified on the .NET 10 SDK by two independent review agents)**

  The `DeclaredOnly` first step (line 370) only disambiguates when the **leaf** model type (`fieldIdentifier.Model.GetType()`) itself redeclares the property — the exact repro in #27095. When the leaf declares nothing but a property is hidden with a differently-typed `new` member on an **intermediate** ancestor, step 1 returns `null` and control reaches the fallback. `GetProperty(name, Public | Instance | FlattenHierarchy)` then walks the whole hierarchy, finds two same-named/different-signature candidates, and throws — the identical mechanism behind the original bug. (`FlattenHierarchy` only affects *static* member flattening; for instance members it behaves like plain `Public | Instance`, so it does nothing to suppress the ambiguity.)

  **Confirmed failure scenario** (run against the .NET 10 SDK by review agents — threw `AmbiguousMatchException: Ambiguous match found for '... Tag'`):
  ```csharp
  class Base   { public object Foo { get; set; } }
  class Middle : Base   { public new int Foo { get; set; } }  // intermediate hides, different type
  class Leaf   : Middle { }                                    // leaf declares nothing
  // typeof(Leaf).GetProperty("Foo", Public|Instance|DeclaredOnly)     -> null
  // typeof(Leaf).GetProperty("Foo", Public|Instance|FlattenHierarchy) -> THROWS AmbiguousMatchException
  ```
  `TryGetValidatableProperty` (line 363) and its only caller `OnFieldChanged` (line 94) have no `try/catch`, so the exception propagates unhandled out of `EditContext.OnFieldChanged`, crashing field-change validation. It is never cached (the throw precedes line 382), so it re-fires on every field change. The full-form `Validator.TryValidateObject` path handles this shape, so `EditContext.Validate()` works while per-field editing throws — an inconsistent, hard-to-diagnose crash. The tests define the ingredients (`ModelWithHiddenBaseProperty` + `MidLevelModelWithShadow`) but no test binds a leaf that inherits `Tag` without redeclaring it, so the gap ships green.

  **Remediation:** Replace the single `FlattenHierarchy` fallback with a most-derived-first walk up the `BaseType` chain, calling `GetProperty(name, Public | Instance | DeclaredOnly)` at each level and returning the first non-null match. `DeclaredOnly` at a single level can never be ambiguous, so this eliminates the throw at any hiding depth. This mirrors the codebase's existing `MemberAssignment.GetPropertiesIncludingInherited` (`src/Components/Components/src/Reflection/MemberAssignment.cs:13`), which already walks `BaseType` with `DeclaredOnly`.
  *Rejected alternative:* wrap the fallback in `try/catch (AmbiguousMatchException)` and return `null` — matches the PR's stated intent and stops the crash, but silently disables validation for the ambiguous field (a silent bypass, worse than a visible crash) and still needs the per-level walk to pick the right member.

### Medium (3)

- **[pr-test-analyzer / type-design-analyzer] Test suite overstates member-hiding coverage; the dangerous fallback path is never exercised with ambiguity present.** — `src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs:241` (`ValidatesPropertyHiddenAtMultipleInheritanceLevels`)

  `DeepDerivedModel` (line 423) itself declares `[Range] new int Tag`, so step 1 (`DeclaredOnly`) resolves it and the `FlattenHierarchy` fallback is never reached — the test only re-covers the "leaf declares the shadow" path, one level deeper than `ValidatesHiddenPropertiesWithoutAmbiguousMatchException`. The only test that reaches the fallback (`ValidatesInheritedPropertyFromBaseClass`, line 225) uses a base with a single **non-hidden** property, so the fallback is exercised only where there is exactly one candidate. No test covers a leaf that inherits an intermediate-hidden property — i.e., the shape that reproduces the High finding.

  **Remediation:** Add a fixture `class LeafInheritingIntermediateShadow : MidLevelModelWithShadow { }` (no `Tag` redeclaration) and a `[Fact]` that binds `Tag` on it and asserts no exception (`Assert.Null(Record.Exception(() => editContext.NotifyFieldChanged(field)))`). This test fails against the merged code today, pinning the residual bug.

- **[comment-analyzer / adversarial-general / blind-hunter] Non-obvious two-step lookup is undocumented, and the PR/commit description diverges from the implementation — regression risk.** — `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:368-379`

  The only comment predates the change and explains neither why `DeclaredOnly` must run first nor that a single `GetProperty(name)` throws `AmbiguousMatchException` on `new`-hidden members. A future maintainer sees two nearly-identical `GetProperty` calls differing by one flag and the natural "simplification" — collapsing them back into one call — silently reintroduces the crash, unguarded by any intermediate-hiding test. Separately, the PR narrative describes a `try/catch (AmbiguousMatchException)` approach that does not match the `BindingFlags` code, which misleads anyone triaging a recurrence.

  **Remediation:** Add a "why" comment above line 370 (single `GetProperty(name)` throws `AmbiguousMatchException` for differently-signed `new`-hidden members; resolve the most-derived declaration first). Reconcile the PR/commit description with the actual implementation.

- **[architecture-reviewer] Sibling property-resolution path was not fixed, and an existing hidden-member-safe helper is not reused — contract divergence.** — `src/Components/Forms/src/ClientValidation/DefaultClientValidationService.cs:283` — **verified present**

  `DefaultClientValidationService.BuildMetadata` resolves the field with `modelType.GetProperty(fieldName, BindingFlags.Public | BindingFlags.Instance)` (no `DeclaredOnly`), which still throws `AmbiguousMatchException` on precisely the `new`-hidden models this PR fixes for server-side DataAnnotations. After this change, server-side validation tolerates hidden properties while the client-validation metadata builder does not — two implementations of the same conceptual contract behaving inconsistently on the same model types. The codebase already has a canonical hidden-member-safe resolver (`MemberAssignment.GetPropertiesIncludingInherited`, `src/Components/Components/src/Reflection/MemberAssignment.cs:13`) that neither Forms path uses.

  **Remediation:** Extract one shared first-match resolver modeled on `MemberAssignment`'s per-level `DeclaredOnly` walk, and route both `TryGetValidatableProperty` and `BuildMetadata` through it so the hidden-member contract is defined once.
  *Counter-argument:* the client-validation path only runs when client validation is wired up, so its blast radius is narrower; still, leaving it divergent means the same model crashes in one path and not the other.

### Low (1)

- **[code-reviewer / blind-hunter / adversarial-general] Undocumented behavior change: `BindingFlags.Static` was dropped, so static properties are no longer resolved.** — `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:370-378`

  The original `GetProperty(name)` used the default flags (`Public | Instance | Static`); both new calls omit `Static`, so a `[Range] public static int StaticValue` that the old code would have found is now silently skipped. This is **intentional and defensible** — it aligns per-field lookup with DataAnnotations' instance-only validation and is pinned by the new `IgnoresStaticProperty` test — but it is a silent behavior change shipped under a bug-fix title and mentioned nowhere in the description. No action required beyond noting it explicitly; do **not** restore `Static` (validating static members on an instance is nonsensical).

### Architectural Insights

- The direction (prefer the leaf-declared shadow via `DeclaredOnly`) is the semantically correct choice — it matches the property C# member access actually binds to. The weakness is that the two-step lookup is a point-fix that does not generalize to intermediate-level hiding, and it entrenches a property-resolution contract now implemented divergently in two places in the same package (see the Medium coupling finding). A most-derived-first `DeclaredOnly` walk would fix the correctness gap and, if centralized, the divergence at once.

### Security Analysis

- **NONE at Medium+.** The one candidate — an unattributed `new` shadow suppressing a base class's `[Required]`/`[Range]` — is by-design C# member-hiding semantics, is consistent with the authoritative form-submit path (`Validator.TryValidateObject` via `TypeDescriptor`, which already resolves the most-derived member), and requires authoring/compiling a model type (developer-controlled, not attacker-controlled runtime input). Not an exploitable bypass. Cache growth is keyed on `(Type, FieldName)`, both developer-controlled and unchanged by this diff.

### Adversarial Analysis

- **Most critical gap:** the intermediate-ancestor hiding case (High finding) — the fix's own documented risk class still crashes, and the test that names itself after multi-level hiding does not exercise it.

### Positive Observations

- The originally reported bug (leaf redeclares the shadow, #27095) is correctly fixed and well-tested; verified empirically.
- Good breadth of enshrining tests: leaf redeclare, multi-level redeclare, inherited-only (exercises the fallback for the non-ambiguous case), unattributed shadow, static exclusion, plus a caching-stability test over boundary values.
- The unattributed-shadow decision (`SkipsValidationWhenDerivedShadowHasNoAttributes`) keeps per-field and full-form validation consistent — a defensible, deliberately-pinned contract.
- Null-caching and the unlocked `ConcurrentDictionary` indexer write are correct (deterministic, idempotent) and preserved unchanged; the `[NotNullWhen(true)]` contract is honored.
- No nullable-reference-type (`CS8618`) concern: the Forms test project has `Nullable` disabled (`_IsSrcProject` gate), and existing test models use the same non-nullable auto-property pattern.

### Minor / Optional (test quality, Low)

- `MatchesPropertyByExactName` (line 213) largely duplicates the field-change portion of `ValidatesHiddenPropertiesWithoutAmbiguousMatchException` and asserts nothing distinctly about exact-name matching; add a wrong-case negative case or drop it.
- No test for case-insensitive/wrong-case field names (`GetProperty` here is case-sensitive; a wrong-case field silently resolves to null and skips validation). Pre-existing behavior, unchanged — a one-line negative test would document the contract.

### Recommended Actions

1. **Close the correctness gap (High):** replace the `FlattenHierarchy` fallback with a most-derived-first `DeclaredOnly` walk up the `BaseType` chain (reuse/model on `MemberAssignment.GetPropertiesIncludingInherited`).
2. **Add the missing test (Medium):** a leaf that inherits an intermediate-hidden property without redeclaring it — this test fails against the merged code and pins the fix.
3. **Document intent (Medium):** add a rationale comment for the two-step lookup; reconcile the PR/commit description (it claims `try/catch`, the code uses `BindingFlags`).
4. **Fix or consciously scope the sibling path (Medium):** `DefaultClientValidationService.BuildMetadata` still throws on the same models; centralize property resolution.
5. **Note the static-property behavior change (Low)** in the description; no code change needed.

---

## Review Metadata

- **Agents run (12):** pr-summarizer, code-reviewer, edge-case-hunter, adversarial-general, blind-hunter, pr-test-analyzer, dotnet-reviewer (C# idiom specialist), silent-failure-hunter, comment-analyzer, type-design-analyzer, architecture-reviewer, security-reviewer.
- **Deterministic checks:** CVE/dependency scan N/A (no dependency manifests changed). No secrets detected in finding text.
- **Empirical verification:** two agents compiled and ran a .NET 10 reflection repro confirming the High finding; the sibling-path and helper claims were verified by direct grep/read of the repo.
- **Mode:** `--local` — nothing was posted to GitHub.
