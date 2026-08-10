# subagent agent-ab4574df069b6fbea

## Test Review: `EditContextDataAnnotationsExtensionsTest.cs` (PR #67075)

Reviewed the 7 new `[Fact]` tests plus the 9 new model classes added by this PR, cross-referenced against the actual production fix (`TryGetValidatableProperty` in `EditContextDataAnnotationsExtensions.cs`, lines 362-386): a two-step `GetProperty` lookup — `DeclaredOnly` first, then `FlattenHierarchy` — replacing the single `GetProperty(name)` call that threw `AmbiguousMatchException` on hidden `new` members. All 7 tests and all 9 model classes are wholly new (no pre-existing versions to compare against).

### Summary
| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 1     |
| MEDIUM   | 3     |
| LOW      | 2     |

### HIGH Issues

#### 1. Missing edge case: the FlattenHierarchy fallback itself can still throw `AmbiguousMatchException`

**Problem:** `TryGetValidatableProperty`'s step 2 (`GetProperty(name, Public | Instance | FlattenHierarchy)`, line 376-378) is only reached when step 1 (`DeclaredOnly`) finds nothing on the model's *exact runtime type*. None of the 7 new tests reach step 2 in a way that could reproduce ambiguity: every hidden-member scenario in this file (`DerivedModelWithHiddenProperty.OrderID`, `DeepDerivedModel.Tag`, `DerivedModelWithUnattributedHiddenProperty.Name`) redeclares the shadowed member *directly on the model's own runtime type*, so `DeclaredOnly` always resolves it in step 1 — step 2 is never exercised by a case where it could still be ambiguous.

`BindingFlags.FlattenHierarchy` is documented as affecting only *static* member visibility; for instance members (which is all that's requested here — no `Static` flag is passed), the hierarchy is already searched regardless of this flag. That means if a *leaf* type does **not** redeclare a member that is shadowed via `new` at two or more ancestor levels (e.g., a hypothetical `class Leaf : DeepDerivedModel { }` with no further `Tag` declaration, inheriting the already-doubly-shadowed `Tag`), `DeclaredOnly` fails (nothing declared on `Leaf`), and the `FlattenHierarchy` fallback would search the same multi-level-hidden-name space that caused the original bug — plausibly still throwing `AmbiguousMatchException` for that shape, meaning issue #27095 may not be fully closed for it.

**Confidence:** 75 — reasoning rests on documented `BindingFlags.FlattenHierarchy` semantics (instance-member behavior is unaffected by that flag) rather than something directly executable in this sandbox (no .NET SDK available).

**Pre-existing:** no — this whole test class/scenario is new to the PR.

**Current Code:** (existing model hierarchy, none of which triggers this path)
```csharp
class MidLevelModelWithShadow : ModelWithHiddenBaseProperty { public new string Tag { get; set; } }
class DeepDerivedModel : MidLevelModelWithShadow { [Range(1,100, ErrorMessage="Tag:range")] public new int Tag { get; set; } }
```

**Suggested Fix:**
```csharp
class DeepDerivedModel : MidLevelModelWithShadow
{
    [Range(1, 100, ErrorMessage = "Tag:range")]
    public new int Tag { get; set; }
}

// Add: a leaf type that does NOT redeclare the shadowed member, forcing the
// FlattenHierarchy fallback to resolve a name hidden at 2+ ancestor levels.
class LeafModelInheritingShadowedProperty : DeepDerivedModel
{
}

[Fact]
public void ValidatesPropertyShadowedAtMultipleLevelsWithoutRedeclaration()
{
    var model = new LeafModelInheritingShadowedProperty { Tag = 150 };
    var editContext = new EditContext(model);
    editContext.EnableDataAnnotationsValidation(_serviceProvider);

    var field = new FieldIdentifier(model, nameof(LeafModelInheritingShadowedProperty.Tag));
    editContext.NotifyFieldChanged(field); // must not throw AmbiguousMatchException
    Assert.Equal(new[] { "Tag:range" }, editContext.GetValidationMessages());
}
```

---

### MEDIUM Issues

#### 2. `SkipsValidationWhenDerivedShadowHasNoAttributes` cannot distinguish "correctly resolved the unattributed shadow" from "resolved nothing at all" in `EditContextDataAnnotationsExtensionsTest.cs:256-266`

**Problem:** The test's only assertion is `Assert.Empty(editContext.GetValidationMessages())` after `NotifyFieldChanged`. That result is produced identically whether (a) `TryGetValidatableProperty` correctly found the derived, attribute-free `Name` shadow and validation legitimately found nothing to complain about, or (b) property resolution silently found *no* property at all (e.g., a regression in the `DeclaredOnly` step for this shape) and no validator was ever registered. The file already has an established, stronger pattern for exactly this distinction: `IgnoresFieldChangesThatDoNotCorrespondToAValidatableProperty` (lines 135-156) asserts on `onValidationStateChangedCount` to prove a validator either did or didn't run. This new test omits that check, so it cannot prove the `DeclaredOnly` branch actually picked the derived property versus not finding anything.

Note: this test *does* still fail on a full revert of the fix (raw `GetProperty(name)` would throw `AmbiguousMatchException` at the `NotifyFieldChanged` call for this hidden-with-attributes-on-base scenario), so it isn't a complete false positive for the reported regression — its weakness is specifically that it can't verify *which* branch/behavior produced the observed "no messages" outcome.

**Confidence:** 100 — verifiable purely from the test code and the sibling convention already present in the same file; no BCL-internals inference required.

**Pre-existing:** no.

**Current Code:**
```csharp
[Fact]
public void SkipsValidationWhenDerivedShadowHasNoAttributes()
{
    var model = new DerivedModelWithUnattributedHiddenProperty { Name = null };
    var editContext = new EditContext(model);
    editContext.EnableDataAnnotationsValidation(_serviceProvider);

    var field = new FieldIdentifier(model, nameof(DerivedModelWithUnattributedHiddenProperty.Name));
    editContext.NotifyFieldChanged(field);
    Assert.Empty(editContext.GetValidationMessages());
}
```

**Suggested Fix:**
```csharp
[Fact]
public void SkipsValidationWhenDerivedShadowHasNoAttributes()
{
    var model = new DerivedModelWithUnattributedHiddenProperty { Name = null };
    var editContext = new EditContext(model);
    editContext.EnableDataAnnotationsValidation(_serviceProvider);
    var onValidationStateChangedCount = 0;
    editContext.OnValidationStateChanged += (sender, eventArgs) => onValidationStateChangedCount++;

    var field = new FieldIdentifier(model, nameof(DerivedModelWithUnattributedHiddenProperty.Name));
    editContext.NotifyFieldChanged(field);

    // Proves a validator actually ran against the resolved (derived, unattributed) property,
    // rather than silently finding no property at all.
    Assert.Equal(1, onValidationStateChangedCount);
    Assert.Empty(editContext.GetValidationMessages());
}
```

---

#### 3. `MatchesPropertyByExactName` duplicates `ValidatesHiddenPropertiesWithoutAmbiguousMatchException` in `EditContextDataAnnotationsExtensionsTest.cs:212-222`

**Problem:** Both tests build the identical model (`DerivedModelWithHiddenProperty { OrderID = 150 }`), call `NotifyFieldChanged` for `OrderID`, and assert the same `{"OrderID:range"}` message. `MatchesPropertyByExactName` is a strict subset (it omits the OrderID=50 toggle-to-valid check) of `ValidatesHiddenPropertiesWithoutAmbiguousMatchException`. Both exercise exactly the same `DeclaredOnly`-resolves-in-one-shot code path; the `"OrderID"` string literal vs. `nameof(...)` distinction gives no additional reflection coverage since `FieldIdentifier.FieldName` is a plain string either way. This adds test count without adding regression-guard coverage.

**Confidence:** 100 — directly comparable from the test bodies and the shared production code path.

**Pre-existing:** no.

**Suggested Fix:** Remove `MatchesPropertyByExactName`, or fold its distinguishing detail (asserting the field can be looked up by a raw string, not just `nameof`) into the existing test as a comment/assertion rather than a separate `[Fact]`.

---

#### 4. `ValidatesPropertyHiddenAtMultipleInheritanceLevels` name overstates what it verifies in `EditContextDataAnnotationsExtensionsTest.cs:240-254`

**Problem:** `DeepDerivedModel` itself declares `public new int Tag { get; set; }` directly (line 423-427). Since `fieldIdentifier.Model.GetType()` for this test's model is `DeepDerivedModel`, step 1 (`DeclaredOnly`) finds `Tag` immediately on the runtime type — the fact that `Tag` is *also* independently shadowed by `ModelWithHiddenBaseProperty` and `MidLevelModelWithShadow` further up the chain is irrelevant, because `DeclaredOnly` never looks past the runtime type. Mechanically this test resolves via the exact same single-step `DeclaredOnly` hit as `ValidatesHiddenPropertiesWithoutAmbiguousMatchException` — it does **not** exercise the `FlattenHierarchy` fallback (step 2) despite the name implying multi-level fallback coverage. See Finding #1 for the actual untested scenario this name suggests it covers.

**Confidence:** 100 — derivable purely from the class hierarchy declarations and the documented meaning of `BindingFlags.DeclaredOnly` (restricts to members declared directly on the queried type).

**Pre-existing:** no.

**Suggested Fix:** Rename to reflect what's actually verified (e.g., `ValidatesHiddenPropertyWhenAncestorsAlsoShadowSameName`), and add the genuinely-multi-level-fallback test from Finding #1 to cover the gap this name currently implies is covered.

---

### LOW Issues

#### 5. `IgnoresStaticProperty` conflates the hidden-member fix with an incidental static-exclusion behavior change, and skips the stronger sibling assertion pattern, in `EditContextDataAnnotationsExtensionsTest.cs:268-278`

**Problem:** The original code (`GetProperty(cacheKey.FieldName)`, single-arg) used .NET's default lookup flags, which include `BindingFlags.Static` — meaning static properties *were* matched by the pre-fix code. The new two-step lookup explicitly requests `BindingFlags.Instance` only (both steps), so excluding statics is a real but incidental side effect of this PR's fix, not the `AmbiguousMatchException` bug itself. The test is not tautological — `StaticValue`'s default (`0`) is deliberately outside `[Range(1,100)]`, so if statics were (bugged into being) matched again, the assertion would correctly flip to non-empty — but it still doesn't check `onValidationStateChangedCount` the way the established sibling test (`IgnoresFieldChangesThatDoNotCorrespondToAValidatableProperty`, lines 135-156) does, so it can't as precisely prove *why* no message appeared.

**Confidence:** 75 — relies on `Type.GetProperty(string)` default `BindingFlags` including `Static` (well-established but not executed here).

**Pre-existing:** no.

**Suggested Fix:** Rename/scope the test comment to make clear it guards static-member exclusion (a related but distinct behavior change), and optionally add the `onValidationStateChangedCount == 0` check for full parity with the sibling pattern.

---

#### 6. Static `_propertyInfoCache` couples `ValidatesHiddenPropertiesWithoutAmbiguousMatchException`, `ValidatesHiddenPropertiesWithPropertyCaching`, and `MatchesPropertyByExactName`

**Problem:** `DataAnnotationsEventSubscriptions._propertyInfoCache` (production code, line 46) is a `static readonly ConcurrentDictionary<(Type, string), PropertyInfo?>`, keyed by `(ModelType, FieldName)` and never cleared between tests. Three new tests use the identical key `(DerivedModelWithHiddenProperty, "OrderID")`. Whichever of these xUnit happens to execute first for that key is the only one that actually runs the live `DeclaredOnly`/`FlattenHierarchy` resolution logic; the other two merely hit a pre-warmed cache entry. This doesn't make any assertion wrong, but it means these tests are less independent than they appear, and reduces the value of having three of them (reinforces Finding #3).

**Confidence:** 50 — real coupling, but impact depends on xUnit's (unspecified) execution order within the class, which cannot be confirmed statically.

**Pre-existing:** no (the cache itself is pre-existing production code, but this specific cross-test coupling only arises because the new tests reuse the same model+field key).

---

### Probe Requests

#### 1. `ValidatesHiddenPropertiesWithoutAmbiguousMatchException`, `ValidatesHiddenPropertiesWithPropertyCaching`, `MatchesPropertyByExactName`, `ValidatesPropertyHiddenAtMultipleInheritanceLevels`, `SkipsValidationWhenDerivedShadowHasNoAttributes` in `EditContextDataAnnotationsExtensionsTest.cs`
**Remove:** `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:370-379` — replace the two-step `DeclaredOnly`/`FlattenHierarchy` lookup with the original single-arg `propertyInfo = cacheKey.ModelType.GetProperty(cacheKey.FieldName);`
**Expect:** all five tests throw an uncaught `System.Reflection.AmbiguousMatchException` at their respective `editContext.NotifyFieldChanged(...)` call, failing the test — confirming each is a genuine regression guard for the reported bug. As a control, `ValidatesInheritedPropertyFromBaseClass` (non-hidden `BaseName`) should **not** fail on this revert, since there is no name ambiguity for that member.
**Relates to:** confirms the baseline validity behind Findings #2-4 (none of them are complete false positives for the *reported* bug, even though #2-4 flag weaker/overlapping coverage).

#### 2. `IgnoresStaticProperty` in `EditContextDataAnnotationsExtensionsTest.cs`
**Remove:** same lines as above (`EditContextDataAnnotationsExtensions.cs:370-379`), reverting to `GetProperty(cacheKey.FieldName)`.
**Expect:** the test fails via an **assertion mismatch** (not an exception) — `Assert.Equal(new[]{ }, ...)` becomes `Assert.Equal` failure because `StaticValue`'s default `0` is out of `[Range(1,100)]`, so `GetValidationMessages()` would now contain `"StaticValue:range"`. Run this test in isolation for the probe, since `ModelWithStaticProperty.StaticValue` is a `static` field shared across any other test that might mutate it in the same process.
**Relates to:** Finding #5 (confirms the test's assertion is not tautological and does react to the specific `BindingFlags.Instance`-only change).

### Recommendations

1. Add the missing test from Finding #1 (a leaf type that inherits, without redeclaring, a property shadowed at 2+ ancestor levels) — this is the one shape the current fix's own `FlattenHierarchy` fallback could still throw on, and it's currently unguarded.
2. Strengthen `SkipsValidationWhenDerivedShadowHasNoAttributes` with an `onValidationStateChangedCount` check (Finding #2), matching the file's own established convention.
3. Remove or repurpose `MatchesPropertyByExactName` (Finding #3) and rename `ValidatesPropertyHiddenAtMultipleInheritanceLevels` (Finding #4) to avoid overstating coverage that isn't actually exercised.
