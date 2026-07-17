# subagent agent-a88e97446a386ea47

# Sibling-Consistency Review — PR #67075 (EditContextDataAnnotationsExtensions AmbiguousMatchException fix)

## Sibling Census

- Production reflection lookup counterpart: `src/Components/Forms/src/ClientValidation/DefaultClientValidationService.cs:283` (`modelType.GetProperty(fieldName, BindingFlags.Public | BindingFlags.Instance)`), a different call site doing the analogous field-name→PropertyInfo lookup — noted but not a violation of a *sibling* convention the diff should have followed (see "Considered But Not Flagged").
- Test-model sibling family with base/derived nesting in the same directory: `src/Components/Forms/test/DefaultClientValidationServiceTest.cs` (`BaseModel`/`DerivedModel`, `InheritedDisplayBaseModel`/`InheritedDisplayDerivedModel`).
- In-file siblings for attribute/property layout and symbol-vs-literal field references: the pre-existing `TestModel`, `AsyncTestModel`, `AsyncThrowingModel` classes and the pre-existing `[Fact]` methods in `EditContextDataAnnotationsExtensionsTest.cs`.

## Findings

```json
[
  {
    "file": "src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs",
    "line": 219,
    "severity": "Medium",
    "category": "other",
    "issue": "[CONS_LITERAL] MatchesPropertyByExactName hardcodes new FieldIdentifier(model, \"OrderID\") instead of nameof(DerivedModelWithHiddenProperty.OrderID); every other reference to this exact property in the same diff (line 186 ValidatesHiddenPropertiesWithoutAmbiguousMatchException, line 199 ValidatesHiddenPropertiesWithPropertyCaching) and the pre-existing sibling tests (lines 46, 51, 107-108, 231, 247, 263, 275) use nameof(...) to reference field names symbolically",
    "fix": "Use nameof(DerivedModelWithHiddenProperty.OrderID) instead of the literal \"OrderID\" string so a future rename of the property is caught at compile time rather than silently desyncing the test",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs",
    "line": 405,
    "severity": "Low",
    "category": "other",
    "issue": "[CONS_ORDER] DerivedModelWithHiddenProperty (line 405) is declared before the base class it extends, ModelWithHiddenBaseProperty (line 411); likewise DerivedModelWithUnattributedHiddenProperty (line 429) precedes its base ModelWithNamedBase (line 434), and DerivedModelWithInheritedOnly (line 448) precedes its base ModelWithBaseName (line 453). Sibling test-model hierarchies in the same directory declare the base class first: DefaultClientValidationServiceTest.cs:367-368 (BaseModel before DerivedModel) and :722-729 (InheritedDisplayBaseModel before InheritedDisplayDerivedModel)",
    "fix": "Reorder the three derived/base pairs so each base class is declared immediately before its derived class, matching the base-then-derived convention used elsewhere for test model hierarchies (this is already followed correctly for ModelWithHiddenBaseProperty -> MidLevelModelWithShadow -> DeepDerivedModel at lines 411/418/423)",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs",
    "line": 407,
    "severity": "Low",
    "category": "other",
    "issue": "[CONS_NAMING] New attributed test-model properties split the validation attribute and the property declaration across two lines (e.g. lines 407-408, 425-426, 436-437, 442-443, 455-456); every pre-existing attributed property in this file keeps attribute and property on one line: TestModel lines 394 and 396, AsyncTestModel line 384, AsyncThrowingModel line 389",
    "fix": "Collapse each attribute+property pair onto a single line (e.g. `[Range(1, 100, ErrorMessage = \"OrderID:range\")] public new int OrderID { get; set; }`) to match the established single-line style for attributed test-model properties in this file",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- `DefaultClientValidationService.cs:283` still uses a plain `GetProperty(fieldName, Public|Instance)` lookup vulnerable to the same `AmbiguousMatchException` this PR fixes in `EditContextDataAnnotationsExtensions.cs`. This is the reverse direction of my domain (an unchanged sibling not yet adopting the new pattern, not the diff deviating from an established one) — belongs to design-reviewer/security-reviewer if reported, not sibling-consistency.
- `MidLevelModelWithShadow` is declared but never directly instantiated in a test, only used transitively via `DeepDerivedModel` — this exactly mirrors the pre-existing sibling convention at `DefaultClientValidationServiceTest.cs:367-368` where `BaseModel` is likewise never directly exercised, only via `DerivedModel`. Convention holds; not a leftover.
- New `[Fact]` methods omit the `// Arrange`/`// Act`/`// Assert` comment scaffolding that all 8 pre-existing test methods in this file carry (lines 27, 32, 35, 57, 62, 65, 74, 81, 85, 91, 101, 111, 117, 129, 143, 149, 153, 161, 166, 170). This is a real drift by my method, but it reads as a comprehension/documentation-habit gap rather than a helper/attribute/literal deviation — left to knowledge-reviewer per the scope boundary.
- The stale two-line comment above the lookup ("DataAnnotations only validates public properties..." / "If we can't find it, cache 'null'...") no longer explains the new two-step `DeclaredOnly` → `FlattenHierarchy` fallback rationale. Both original claims remain literally true, so this isn't a contradiction (CONS_COMMENT requires a false claim); it's an undocumented decision, which is knowledge-reviewer's territory.
- Null-check idiom: new code uses `propertyInfo is null` (line 374) while the same method's own untouched return statement uses `propertyInfo != null` (line 385), and the file overall already mixes `is not null` (lines 119, 133) with `== null`/`!= null` (lines 65, 181, 385). No single convention holds across the file, so this doesn't clear the bar (anchor 0 — convention falls apart on inspection).
- `"Field:rule"` `ErrorMessage` literal convention (e.g. `"OrderID:range"`, `"Name:required"`) in all new attributes matches the pre-existing `TestModel` convention (`"RequiredString:required"`, `"IntFrom1To100:range"`) exactly — no drift.
- Multi-line reflection-call formatting (method name, then each argument on its own indented line) matches the existing `RegisterAsyncFieldValidator(...)` call sites at lines 89-91 and 96-98 — no drift.
- Bracing style (`if (...) { ... }` with braces even for one-line bodies) in the merged source change matches every other conditional in the file (lines 104, 193, 262, 332, 356) — no drift (the compact brace-less form shown in the prompt's diff excerpt does not match the actual merged file, which is fully braced).
