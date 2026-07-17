# subagent agent-ad5b97b0ba22b1f2d

## Summary

Fixes `AmbiguousMatchException` thrown by `Type.GetProperty(string)` in `EditContextDataAnnotationsExtensions.cs:370` when a model has a property hidden via `new` in a derived class (issue dotnet/aspnetcore#27095). The fix queries with `BindingFlags.Public | Instance | DeclaredOnly` first (finding the most-derived declaration), and falls back to `BindingFlags.Public | Instance | FlattenHierarchy` if nothing is found on the declaring type — no exception is caught or retried; this differs from the PR narrative's description of catching `AmbiguousMatchException` and retrying with `DeclaredOnly` on failure. Adds 7 new unit tests (`ValidatesHiddenPropertiesWithoutAmbiguousMatchException`, `ValidatesHiddenPropertiesWithPropertyCaching`, `MatchesPropertyByExactName`, `ValidatesInheritedPropertyFromBaseClass`, `ValidatesPropertyHiddenAtMultipleInheritanceLevels`, `SkipsValidationWhenDerivedShadowHasNoAttributes`, `IgnoresStaticProperty`) plus supporting model fixtures, covering hidden-property shadowing, caching, multi-level inheritance, unattributed shadows, and static-property exclusion — not the 3 tests the narrative claims.

**Type:** Bug fix
**Effort:** 2/5 — a 10-line, two-lookup change to one method plus test additions; no schema or API surface change.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs | Modified | `GetProperty` lookup now tries `DeclaredOnly` binding flags first, falling back to `FlattenHierarchy` if not found, to avoid ambiguous matches on `new`-hidden properties (lines 370–379) |
| src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs | Modified | Adds 7 `[Fact]` tests and several nested fixture classes (`DerivedModelWithHiddenProperty`, `DeepDerivedModel`, `ModelWithStaticProperty`, etc.) covering hidden/shadowed properties, caching, deep inheritance, and static-property exclusion |
