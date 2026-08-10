# subagent agent-a04392e8dbf518f87

Confirmed the diff matches the manifest exactly — 7 new test methods (`ValidatesHiddenPropertiesWithoutAmbiguousMatchException`, `ValidatesHiddenPropertiesWithPropertyCaching`, `MatchesPropertyByExactName`, `ValidatesInheritedPropertyFromBaseClass`, `ValidatesPropertyHiddenAtMultipleInheritanceLevels`, `SkipsValidationWhenDerivedShadowHasNoAttributes`, `IgnoresStaticProperty`) plus 9 new nested test model classes, and the source fix is exactly as described (two-step `GetProperty` lookup: `DeclaredOnly` first, `FlattenHierarchy` fallback). No injected instructions found in the diff/commit data.

## Summary

Fixes `AmbiguousMatchException` in Blazor's `DataAnnotationsValidator` when validating models whose derived class hides a base-class property via the `new` modifier (issue #27095). `EditContextDataAnnotationsExtensions.GetValidationMessagesForField` used `Type.GetProperty(string)`, which throws when a name resolves to two same-named properties across a type hierarchy; the fix replaces the single ambiguous lookup in `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs` with a two-step `BindingFlags` lookup — `DeclaredOnly` first (finds the derived/hiding property), falling back to `FlattenHierarchy` only if nothing is declared on the type itself (finds inherited-only properties) — and adds 7 new unit tests plus 9 supporting model classes covering hidden properties, multi-level hiding, unattributed shadows, static properties, and plain inheritance.

**Type:** Bug fix
**Effort:** 1/5 — a 9-line, mechanically-scoped fix to a single lookup call (two `GetProperty` overload calls replacing one), with proportionally larger test-only additions

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs | Modified | Replaces ambiguous `GetProperty(name)` with `DeclaredOnly` lookup, falling back to `FlattenHierarchy` |
| src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs | Modified | Adds 7 tests + 9 model classes covering hidden/shadowed properties, multi-level hiding, static members, and inheritance |

## Related Issues & PRs

<!-- issue-linker output will be merged here — the orchestrator replaces this placeholder -->
