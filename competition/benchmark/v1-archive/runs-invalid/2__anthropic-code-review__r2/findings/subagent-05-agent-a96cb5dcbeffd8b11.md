# subagent agent-a96cb5dcbeffd8b11

## Sibling-Consistency Review — dotnet/aspnetcore #67075 (commit 3b00cfca)

**Scope examined:** `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs` (`TryGetValidatableProperty`, lines 362–386) and `src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs` (7 new `[Fact]`s + 9 new nested model classes), plus sibling property-resolution call sites across `src/Components/`.

### Sibling census

| Construct | This change | Sibling(s) |
|---|---|---|
| Resolve a model's property from a `FieldIdentifier`'s field name, for DataAnnotations-style validation, cached by `(Type, string)` key | `EditContextDataAnnotationsExtensions.cs:365-379` — two-pass `GetProperty(name, Public\|Instance\|DeclaredOnly)` then `GetProperty(name, Public\|Instance\|FlattenHierarchy)` | `DefaultClientValidationService.cs:283` — single-pass `modelType.GetProperty(fieldName, BindingFlags.Public \| BindingFlags.Instance)`, same `(Type ModelType, string FieldName)` cache-key shape (`DefaultClientValidationService.cs:24,39`) |
| Test body structure | 7 new `[Fact]`s (lines 177-282), no comments | Original 6 `[Fact]`s (lines 16-174) use `// Arrange` / `// Act` / `// Assert` |
| Error-message literal convention | `"OrderID:range"`, `"Tag:range"`, `"Name:required"`, `"BaseName:required"`, `"StaticValue:range"` | `"RequiredString:required"`, `"IntFrom1To100:range"` (line 40-41) — `<PropertyName>:<attrtype>` |
| New nested test-model classes | 9 classes, bare `class X` | `TestModel` (bare `class`, line ~389) vs. `AsyncTestModel`/`AsyncThrowingModel` (`private sealed class`, lines ~365-371) |

### Findings

```json
[
  {
    "file": "src/Components/Forms/src/ClientValidation/DefaultClientValidationService.cs",
    "line": 283,
    "severity": "High",
    "category": "design",
    "issue": "[CONS_HELPER] BuildMetadata resolves a model's validatable property via a single-pass modelType.GetProperty(fieldName, BindingFlags.Public | BindingFlags.Instance) — the exact pre-fix pattern EditContextDataAnnotationsExtensions.cs:370-378 just replaced with a DeclaredOnly-then-FlattenHierarchy two-pass lookup for the identical job (resolving a FieldIdentifier's property for DataAnnotations validation, cached by the same (Type, string) key shape at DefaultClientValidationService.cs:24,39 vs EditContextDataAnnotationsExtensions.cs:365). This is the only other Forms call site with the same purpose and it was left on the ambiguity-prone pattern.",
    "fix": "Apply the same two-pass DeclaredOnly-then-FlattenHierarchy GetProperty lookup (or extract a shared helper) in DefaultClientValidationService.BuildMetadata so hidden/new-shadowed properties are resolved consistently across both Forms validation code paths.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

### Considered But Not Flagged

- **Arrange/Act/Assert comments missing from the 7 new tests** — the first 6 pre-existing tests in this file (lines 16-174) consistently use `// Arrange`/`// Act`/`// Assert`, but the later pre-existing async tests (`FormLevelAsyncValidationProducesMessages`, `FieldLevelAsyncValidationBecomesPendingThenSettles`, etc., lines 281-333) already dropped that convention before this PR. Siblings disagree among themselves (anchor 0) — not reportable.
- **Nested test-model class modifiers (`class X` vs `private sealed class X`)** — `TestModel` is bare `class`; `AsyncTestModel`/`AsyncThrowingModel` are `private sealed class`. The 9 new model classes use bare `class`, matching `TestModel` but not the more recently-added async models. Existing siblings disagree — not reportable.
- **`GetPropertiesIncludingInherited` helper in `MemberAssignment.cs`** (used by `ComponentProperties.cs:188`, `PersistentServicesRegistry.cs:237`, `DefaultComponentPropertyActivator.cs:52`) already walks a type hierarchy level-by-level with `DeclaredOnly` at each level specifically to dedupe hidden/shadowed members. It solves a different problem shape (collect *all* properties across levels, several call sites) than `TryGetValidatableProperty` (resolve *one* named property, preferring the most-derived) — not a drop-in canonical helper for this job, so not flagged as CONS_HELPER; noted for awareness only.
- **`GetProperty` call sites in Endpoints (`TempDataCascadingValueSupplier.cs:47`, `SessionCascadingValueSupplier.cs:55`) and `ComponentProperties.cs:196`/`PersistentValueProviderComponentSubscription.cs:241`** — none use the new two-pass pattern either. These reinforce that the plain-GetProperty pattern is the wider Components norm (used as corroborating "uniform presence elsewhere" evidence for the DefaultClientValidationService finding above), but are farther from this PR's feature area (parameter/cascading-value binding, not DataAnnotations validation) so not filed as separate findings.
- **9 new nested model classes all exercised** — `DerivedModelWithHiddenProperty`, `ModelWithHiddenBaseProperty`, `MidLevelModelWithShadow`, `DeepDerivedModel`, `DerivedModelWithUnattributedHiddenProperty`, `ModelWithNamedBase`, `ModelWithStaticProperty`, `DerivedModelWithInheritedOnly`, `ModelWithBaseName` — each is either directly instantiated by a test or is a base class in an inheritance chain that is. No unused/leftover scaffolding found.
- **Error-message literal format** (`"<PropertyName>:<attrtype>"`) — new tests (`OrderID:range`, `Tag:range`, `Name:required`, `BaseName:required`, `StaticValue:range`) match the existing convention (`RequiredString:required`, `IntFrom1To100:range`) exactly. No drift.
- **`orderIdIdentifier` variable casing** (`OrderID` → `orderId` rather than `orderID`) vs. existing `intFrom1To100Identifier` (which preserves the source property's internal casing) — too weak/single-instance to cite two agreeing siblings; not reportable.

[Inference, not executed in this review] The functional consequence of the flagged divergence — `DefaultClientValidationService.GetClientValidationAttributes` throwing `AmbiguousMatchException` for a model with a `new`-hidden public instance property (the same shape as this PR's own `DerivedModelWithHiddenProperty` repro) — follows from documented `Type.GetProperty(string, BindingFlags)` behavior (omitting `DeclaredOnly` does not suppress the hierarchy walk) but was not verified by running code in this session.
