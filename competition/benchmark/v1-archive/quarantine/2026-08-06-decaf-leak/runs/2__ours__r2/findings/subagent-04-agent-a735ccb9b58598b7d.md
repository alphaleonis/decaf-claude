# subagent agent-a735ccb9b58598b7d

## Sibling-Consistency Review

### Context gathered
- Read `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs` (full, 393 lines) and `src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs` (full, 458 lines).
- No repo-root or `src/Components` CLAUDE.md exists in this checkout — nothing to defer to quick-reviewer.
- Sibling census: other `GetProperty`/reflection-by-name lookups in `src/Components/` (`DefaultClientValidationService.cs`, `ComponentProperties.cs`, `SessionCascadingValueSupplier.cs`, `TempDataCascadingValueSupplier.cs`, `PersistentValueProviderComponentSubscription.cs`), plus `src/Shared/PropertyHelper/PropertyHelper.cs` (hidden-property-aware helper, but not linked into the Forms project) and `src/Components/Components/src/Reflection/MemberAssignment.cs` (`GetPropertiesIncludingInherited`, a different assembly).
- Confirmed `DataAnnotationsValidator.cs` (`src/Components/Forms/src/DataAnnotationsValidator.cs`) wires up *both* `EnableDataAnnotationsValidation` (the fixed path in this diff) and `IClientValidationService` (which resolves to `DefaultClientValidationService.BuildMetadata`) for the same model — confirming these two lookups are genuine counterparts in the same feature.

```json
[
  {
    "file": "src/Components/Forms/src/ClientValidation/DefaultClientValidationService.cs",
    "line": 283,
    "severity": "High",
    "category": "design",
    "issue": "[CONS_SYMMETRY] BuildMetadata still does `modelType.GetProperty(fieldName, BindingFlags.Public | BindingFlags.Instance)` with no DeclaredOnly/FlattenHierarchy fallback — the exact unguarded pattern this PR just replaced at EditContextDataAnnotationsExtensions.cs:370-379 because it threw AmbiguousMatchException on hidden (`new`) members. Both lookups map a FieldIdentifier's field name to a PropertyInfo on the same model for the same DataAnnotationsValidator feature (wired together in DataAnnotationsValidator.cs:38/45-47), so a model with a hidden/shadowed property that server-side validation now handles correctly will still crash client-side validation metadata building.",
    "fix": "Apply the same two-step (DeclaredOnly on the model type, then FlattenHierarchy fallback) lookup used in EditContextDataAnnotationsExtensions.TryGetValidatableProperty to DefaultClientValidationService.BuildMetadata, or extract a shared helper both call.",
    "confidence": 75,
    "pre_existing": true
  }
]
```

## Considered But Not Flagged

- **`MidLevelModelWithShadow` (test file line 418-421)**: flagged by the task brief as possibly unused — verified it is the base class of `DeepDerivedModel` (line 423), so it is used. Not a leftover.
- **`ErrorMessage` string convention** (`"OrderID:range"`, `"Tag:range"`, `"Name:required"`, `"BaseName:required"`): matches the pre-existing `"IntFrom1To100:range"` / `"RequiredString:required"` `{Property}:{rule}` format exactly (test file lines 394-396 vs. 407, 425, 436, 455). No drift.
- **Bare `class X` vs. `private sealed class X` for test model fixtures**: the new model classes (`DerivedModelWithHiddenProperty`, `ModelWithHiddenBaseProperty`, etc.) use the bare `class` form, matching pre-existing `TestModel` (line 392) but *not* matching pre-existing `AsyncTestModel`/`AsyncThrowingModel` (`private sealed class`, lines 382-390). Since siblings within the same file already disagree on this point, this is not a convention — anchor 0, not reportable.
- **Arrange/Act/Assert comment banding**: the 7 new `[Fact]` methods (lines 176-278) have no `// Arrange`/`// Act`/`// Assert` comments, unlike the file's earliest tests (`GetsValidationMessagesFromDataAnnotations` etc., lines 24-174). However the pre-existing async-validation tests added later in the same file (`FormLevelAsyncValidationProducesMessages`, `FieldLevelAsyncValidationBecomesPendingThenSettles`, etc., lines 280-336) *also* omit AAA comments — so the file already contains two competing conventions and the new tests follow the more recent one. Siblings disagree — anchor 0, not reportable.
- **`src/Shared/PropertyHelper/PropertyHelper.cs` (`GetVisibleProperties`)**: a genuinely hidden-property-aware helper exists in the shared source tree, but it is only linked into `Components/Endpoints`, not `Components/Forms` (checked both csproj files), and it solves a different-shaped problem (enumerate-and-filter all visible properties vs. look up one named property). Too weak a fit to assert as a canonical helper this diff should have reused — anchor 25.
- **`MemberAssignment.GetPropertiesIncludingInherited`** (`src/Components/Components/src/Reflection/MemberAssignment.cs`): same reasoning — different assembly (`Components` core, not `Forms`), different job shape (component-parameter binding, not DataAnnotations field lookup). Not a strong enough sibling to cite as a missed-helper convention.
- **Test-method naming** (`ValidatesHiddenPropertiesWithoutAmbiguousMatchException`, `MatchesPropertyByExactName`, etc.): consistent PascalCase behavioral-description style matching every existing `[Fact]` name in the file (`GetsValidationMessagesFromDataAnnotations`, `IgnoresFieldChangesThatDoNotCorrespondToAValidatableProperty`, …). No drift.
- **New model-class placement**: all new nested model classes are appended after `TestModel`, matching the sibling convention of placing test-fixture model classes at the bottom of the file (`AsyncTestModel`/`AsyncThrowingModel`/`TestModel` already follow this). No drift.
- **`ValidatesPropertyHiddenAtMultipleInheritanceLevels`** appears not to actually exercise the `FlattenHierarchy` fallback branch (since `DeepDerivedModel` itself redeclares `Tag`, so `DeclaredOnly` on the exact model type already resolves it) — this is a test-adequacy/false-confidence concern about what the test proves, not a sibling-convention deviation, so it belongs to test-reviewer, not this lane.
