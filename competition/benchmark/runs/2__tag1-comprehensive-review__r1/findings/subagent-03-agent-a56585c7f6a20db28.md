# subagent agent-a56585c7f6a20db28

I have everything I need. My reflection reasoning is empirically confirmed, the service-provider path is confirmed, and no other test in the repo covers the ambiguous inherited case.

## Summary

The 7 added tests give solid coverage of the common hidden-property scenarios (leaf-declared `new` shadow, simple base inheritance, unattributed shadow, static property, and cache reuse). Most assertions are meaningful and behavioral. However, the one test that names itself after the fix's documented known risk — `ValidatesPropertyHiddenAtMultipleInheritanceLevels` — does not actually exercise the dangerous fallback path. The exact scenario the PR title claims to address ("Hidden Members") has a residual latent bug that no test guards, and I verified empirically that the shipped code still throws `AmbiguousMatchException` on that path.

## Critical Gap (severity 9/10)

**The known-risk fallback path is not exercised; the test name overstates coverage, and the underlying code is still broken for it.**

- Test: `src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs:241` (`ValidatesPropertyHiddenAtMultipleInheritanceLevels`)
- Model: `DeepDerivedModel` at `EditContextDataAnnotationsExtensionsTest.cs:423`
- Source under test: `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:376-379` (the `FlattenHierarchy` fallback)

Why the test doesn't cover what its name claims: `DeepDerivedModel` itself declares `[Range] new int Tag`. In `TryGetValidatableProperty`, step 1 (`GetProperty("Tag", Public|Instance|DeclaredOnly)`) resolves that leaf-declared property and returns immediately. Step 2 (`FlattenHierarchy` over the whole chain) is never reached. So the test only re-covers the same "leaf declares the shadow" path already covered by `ValidatesHiddenPropertiesWithoutAmbiguousMatchException` (line 177) — just at three levels instead of two. The intermediate `MidLevelModelWithShadow` (`:418`, `new string Tag`) exists in the fixtures but no test binds a leaf that inherits `Tag` without redeclaring it.

The genuine dangerous path — leaf declares nothing, and an intermediate ancestor shadows a base property with a different type — is where step 1 returns null and step 2's `FlattenHierarchy` sees two `Tag` properties of different types (`object` and `string`) and re-throws `AmbiguousMatchException`. I verified this empirically with a standalone reflection program on net10.0:

- `DeepDerivedModel`-shaped (leaf declares `int Tag`) → step 1 resolves to `Int32`, no throw. (Matches the test.)
- Leaf-with-no-own-`Tag` (subclass of `MidLevelModelWithShadow`) → step 1 null, step 2 → `THROW AmbiguousMatchException`.

Because `OnFieldChanged` calls `TryGetValidatableProperty` synchronously (line 94), this exception propagates straight out of `NotifyFieldChanged`, crashing field-change validation — exactly the failure class the PR set out to fix. This gap is more than "untested": adding the test below fails against the merged code, exposing that the fix is incomplete for the multi-level inherited-shadow case.

Concrete suggested test (add fixture + fact). Note this currently fails against the merged code, which is the point — it pins the real known-risk scenario:

```csharp
// New fixture: leaf inherits MidLevelModelWithShadow.Tag (string), which shadows
// ModelWithHiddenBaseProperty.Tag (object); the leaf declares no Tag of its own.
class LeafInheritingIntermediateShadow : MidLevelModelWithShadow
{
    public int Other { get; set; }
}

[Fact]
public void ValidatesLeafInheritingIntermediateHiddenProperty()
{
    var model = new LeafInheritingIntermediateShadow();
    var editContext = new EditContext(model);
    editContext.EnableDataAnnotationsValidation(_serviceProvider);

    var field = new FieldIdentifier(model, "Tag");
    // Must not throw AmbiguousMatchException (step 1 DeclaredOnly returns null on the leaf,
    // step 2 FlattenHierarchy sees two 'Tag' properties of differing types).
    var ex = Record.Exception(() => editContext.NotifyFieldChanged(field));
    Assert.Null(ex);
    Assert.Empty(editContext.GetValidationMessages());
}
```

To make the fixture assert a validation outcome rather than just "no throw," give `MidLevelModelWithShadow.Tag` a `[Required]`/`[Range]` attribute so the inherited shadow's validation is observable once the source is fixed to handle the ambiguity.

## Test-Quality / Minor Observations

- **`MatchesPropertyByExactName` (`:213`) is largely redundant and mis-named (severity 3).** It duplicates the field-change portion of `ValidatesHiddenPropertiesWithoutAmbiguousMatchException` and asserts nothing about "exact name" that distinguishes it — there is no negative case (e.g., a wrong-case `"orderid"`). If the intent is to document exact/case-sensitive matching, add the negative case; otherwise the test adds little.

- **Missing case-insensitive / wrong-case field-name case (severity 2-3, optional).** `GetProperty(name, ...)` here is case-sensitive (no `IgnoreCase` flag). A `FieldIdentifier(model, "orderid")` silently resolves to null and skips validation. This is pre-existing behavior unchanged by the PR, but it is untested; a one-line negative fact (`Assert.Empty` after notifying a wrong-case field) would document the contract. Low value.

- **`SkipsValidationWhenDerivedShadowHasNoAttributes` (`:257`) has a slightly weak assertion (severity 3).** `Assert.Empty` cannot distinguish "found the leaf's unattributed `new string Name` and validated it with no errors" from "found no property at all." Behaviorally the outcome (base's `[Required]` is correctly not applied) is what matters, so this is acceptable, but the assertion doesn't prove the leaf property was the one selected.

## Positive Observations

- `ValidatesInheritedPropertyFromBaseClass` (`:225`) is a good, meaningful test: it genuinely covers the step-2 `FlattenHierarchy` fallback for the non-ambiguous inherited case (leaf declares only `Description`, `BaseName` lives on the base), asserting both the error and the cleared state after correction.
- `ValidatesHiddenPropertiesWithPropertyCaching` (`:194`) meaningfully exercises the `_propertyInfoCache` reuse across repeated lookups with boundary values (1, 99, 101, …), catching regressions where caching or range logic breaks.
- `IgnoresStaticProperty` (`:269`) correctly verifies the `BindingFlags.Instance` restriction excludes static properties on both lookup steps.
- Assertions are DAMP and behavioral (error-message strings via `GetValidationMessages()`), resilient to reasonable refactoring of the reflection internals.

Because there is a real, concrete coverage gap on the fix's own documented risk, the answer is not NONE.
