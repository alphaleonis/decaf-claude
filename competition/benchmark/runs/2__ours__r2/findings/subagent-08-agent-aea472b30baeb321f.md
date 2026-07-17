# subagent agent-aea472b30baeb321f

I have what I need. The production change is exactly 11 lines (the two-step `GetProperty` resolution); the cache and hot-reload machinery are untouched by this PR. Let me record my analysis.

## Depth

Depth: quick — the production change is ~10 executable lines and the domain (client-side Blazor form validation) is not one of the strict high-risk domains (auth/payments/persistence/external-API). Focused on assumption-violation scenario construction, ≤3 findings. Deeper mechanical tracing was still warranted because the change is a reflection-semantics fix where correctness hinges on inheritance-shape assumptions.

## Findings

```json
[
  {
    "file": "src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs",
    "line": 376,
    "severity": "High",
    "category": "error-handling",
    "issue": "[ADV_ASSUMPTION] Model is a subclass of a class that hides a base property with `new` of a different type, and the leaf does NOT redeclare it (e.g. `class C : MidLevelModelWithShadow {}` where MidLevelModelWithShadow declares `new string Tag` over base `object Tag`) → Step-1 DeclaredOnly on C returns null (C declares no Tag) → Step-2 FlattenHierarchy fallback sees TWO instance 'Tag' properties with different signatures (string vs object), which do not hide-by-name+signature → GetProperty re-throws the exact AmbiguousMatchException the fix was meant to eliminate → exception propagates synchronously out of OnFieldChanged during NotifyFieldChanged, unhandled by the validator (Blazor Server: circuit teardown; WASM: unhandled error). The fix only disambiguates when the LEAF type itself redeclares the hidden member; intermediate-level hiding is uncovered.",
    "fix": "Do not rely on the flat GetProperty for the fallback. Walk the type hierarchy explicitly from the model type upward calling GetProperty(name, Public|Instance|DeclaredOnly) at each level and return the first (most-derived) match; this mirrors TypeDescriptor's most-derived-wins semantics used by Validator and never triggers AmbiguousMatchException. Add a regression model that is a non-redeclaring subclass of a class with an intermediate `new` shadow.",
    "confidence": 75,
    "pre_existing": true
  }
]
```

### Probe Requests

**Probe (added scenario — confirms finding #1):** the test file already declares `MidLevelModelWithShadow : ModelWithHiddenBaseProperty` with `public new string Tag`. Add a non-redeclaring leaf and a test:

- Add model: `class LeafOverMidShadow : MidLevelModelWithShadow { }`
- Test body:
  ```
  var model = new LeafOverMidShadow();
  var editContext = new EditContext(model);
  editContext.EnableDataAnnotationsValidation(_serviceProvider);
  var field = new FieldIdentifier(model, "Tag");
  editContext.NotifyFieldChanged(field);
  Assert.Empty(editContext.GetValidationMessages()); // desired post-fix behavior
  ```
- Expected failure TODAY: `System.Reflection.AmbiguousMatchException` thrown from `TryGetValidatableProperty` at the FlattenHierarchy fallback (line 376-378) during `NotifyFieldChanged`. A complete fix would instead resolve the most-derived `Tag` (the `string` one, no attributes) and produce empty messages without throwing.
- (I am nominating this, not running it — production tree is read-only.)

## Considered But Not Flagged

- **#2 Property-identity mismatch across cache vs `Validator` (field path).** `ValidateFieldWithValidatorAsync` passes the DeclaredOnly (derived) value plus `MemberName`, and `Validator.TryValidateProperty` re-resolves the property by name via `TypeDescriptor.GetProperties`, which also returns the most-derived property for `new`-hidden members. For the leaf-declares case both paths agree (proven by `ValidatesHiddenPropertiesWithoutAmbiguousMatchException` asserting `OrderID:range` fires and `SkipsValidationWhenDerivedShadowHasNoAttributes` asserting the derived unattributed shadow wins). For the intermediate-hiding case the reflection path throws before ever reaching `Validator`. I could not construct a state where the two resolvers pick *different* properties and validation silently diverges — the step "reflection picks derived, Validator picks base" never holds because both are most-derived-wins. Fell apart at that step.

- **#3 Static-flag removal.** Old code used single-arg `GetProperty(name)` = `Public|Instance|Static`; new code is Instance-only, so static properties are no longer found (`IgnoresStaticProperty` asserts this is intended). This is not a lost-validation regression: a static property routed to `Validator.TryValidateProperty` would have thrown `ArgumentException` (DataAnnotations' `ValidationAttributeStore` enumerates instance properties only), so the old path crashed rather than validated. New behavior (skip) strictly removes a crash. The static/instance name-collision variant (`class B : A { public static new int Foo }` hiding an instance `Foo`) resolves to the inherited instance property without throwing — exotic and non-crashing; no concrete bad outcome constructed.

- **#4 Cache / MetadataUpdate.** The `static _propertyInfoCache`, `OnClearCache`, and `ClearCache` machinery are untouched by this PR (diff is only the two `GetProperty` calls). The two-step resolution composes cleanly with the cache: results (including the derived `PropertyInfo` and null misses) are cached under `(ModelType, FieldName)`; hot-reload `Clear()` forces consistent re-resolution. One interaction worth noting but not new here: the intermediate-hiding throw (finding #1) occurs *before* the cache write, so it is never cached and recurs on every field change rather than once — an amplifier folded into #1, not a separate finding. The undisposed-subscription-keeps-static-event-alive leak (`OnClearCache += ClearCache` with no Dispose) is real but pre-existing, dev-only (`MetadataUpdater.IsSupported`), and unrelated to this change.
