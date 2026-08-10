# subagent agent-a47759a771cd80f3d

I have enough to complete the review. I could not run a live .NET reflection experiment (no `dotnet` SDK in this environment), so the reflection-behavior claims below are based on documented .NET `RuntimeType.GetProperty` semantics rather than an in-session execution — I've labeled the key one accordingly.

## Review scope

- `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs` — the production fix in `TryGetValidatableProperty` (lines 362–386)
- `src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs` — 7 new `[Fact]` tests (lines 176–278) and 9 new model classes (lines 405–457)

I traced the full call path: `OnFieldChanged` (line 94) → `TryGetValidatableProperty` (363) → `ValidateFieldWithValidatorAsync` (273). There is **no** try/catch around `TryGetValidatableProperty` in `OnFieldChanged`, so any exception it raises propagates out to the caller of `EditContext.NotifyFieldChanged`.

---

## Important (confidence 85)

### 1. The two-phase lookup still throws `AmbiguousMatchException` when a property is shadowed at an intermediate level and NOT redeclared on the leaf type
`src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:376-378`

The fix only inspects the leaf type with `DeclaredOnly` (phase 1, lines 370–372); if that misses, it falls back to a hierarchy-spanning `FlattenHierarchy` lookup (phase 2, lines 376–378). Phase 2 re-introduces the exact ambiguity the PR set out to remove.

Failure scenario (all three levels in the same hierarchy, leaf does not redeclare):
```csharp
class Base { public object Tag { get; set; } }
class Mid  : Base { public new string Tag { get; set; } }   // shadow, different type
class Leaf : Mid  { /* does NOT redeclare Tag */ }
```
For a `Leaf` instance with a field change on `"Tag"`:
- Phase 1 `GetProperty("Tag", Public|Instance|DeclaredOnly)` on `Leaf` → **null** (Leaf declares no `Tag`).
- Phase 2 `GetProperty("Tag", Public|Instance|FlattenHierarchy)` on `Leaf` → the hierarchy contains `Mid.Tag` (string) and `Base.Tag` (object). Because they differ in signature, reflection keeps **both** candidates and, with no return-type/args to disambiguate, `GetProperty` **throws `AmbiguousMatchException`**. [Inference — based on documented `RuntimeType.GetPropertyImpl` behavior; I could not execute .NET in this session to confirm empirically.]

`FlattenHierarchy` does not help here: for *instance* members the lookup already spans the base chain, and `FlattenHierarchy` only affects *static* member surfacing — so phase 2 is functionally just `Public|Instance` and offers no protection against the shadow ambiguity.

This is a genuine "hidden member" shape, i.e., exactly the class of bug the PR title targets, yet it remains unfixed and now surfaces as an uncaught exception reaching user code on every field change for that property (nothing is cached because the throw happens before line 382).

Recommended fix — walk the hierarchy doing a `DeclaredOnly` lookup at each level and return the first (most-derived) hit, which is never ambiguous:
```csharp
for (var t = cacheKey.ModelType; t is not null; t = t.BaseType)
{
    propertyInfo = t.GetProperty(cacheKey.FieldName,
        BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly);
    if (propertyInfo is not null) break;
}
```

**Test-coverage tie-in:** `MidLevelModelWithShadow` (test lines 418–421) sets up precisely the intermediate `new string Tag` shadow, but the only test that uses it (`ValidatesPropertyHiddenAtMultipleInheritanceLevels`, line 241) goes through `DeepDerivedModel`, which **redeclares** `Tag` on the leaf (line 426) — so phase 1 always resolves it and phase 2 is never exercised for the shadow case. No test instantiates a type that inherits `MidLevelModelWithShadow`'s shadow without redeclaring it, so this gap is untested. Adding such a model/test would both catch the bug and validate the fix above.

---

## Lower-confidence notes (below the 80 reporting bar, but directly answering the focus areas)

- **`BindingFlags.Static` removal (behavior change) — benign/intentional (confidence it's benign ~75).** The old `GetProperty(name)` overload used `Public|Static|Instance|FlattenHierarchy`, so a static property matching the field name would previously be returned and validated; both new phases use `Instance` only, so static properties are now skipped (`TryGetValidatableProperty` returns false → no validation). This is a real behavior change, but it aligns field-level validation with DataAnnotations object-graph validation, which does not validate static members. It is covered by `IgnoresStaticProperty` (test lines 268–278), and the `[Range]`-with-default-0 setup on `StaticValue` (lines 442–443) meaningfully distinguishes "ignored" (empty) from "would-be-validated" (a range error). I consider this correct, not a defect — noting it only because it was called out for attention.

- **`FlattenHierarchy` in phase 2 is misleading/redundant (confidence ~85 that it's a no-op; low severity).** For instance-member property lookups `FlattenHierarchy` has no effect. Its presence suggests an intent for phase 2 to "traverse the hierarchy safely," which it does not do — it neither adds coverage over plain `Public|Instance` nor prevents the ambiguity in finding #1. If the loop-based fix above is adopted, this flag goes away entirely.

- **Behavior differences vs. the original single call — none beyond the above in resolvable cases.** I walked the cases (leaf-only property, inherited-only unshadowed, same-type `new`, different-type `new` on leaf): the new code returns the same `PropertyInfo` the old code would have, except it no longer throws for the leaf-redeclared shadow (the intended fix) and no longer returns static properties (noted above). `ValidatesInheritedPropertyFromBaseClass` (line 225) correctly exercises the phase-2 unshadowed-inheritance path.

- **Test models / dead code — none found.** All 9 new model classes are referenced (directly in a test, or as a base of one that is). `MidLevelModelWithShadow` and `ModelWithHiddenBaseProperty.Tag` are used only transitively via `DeepDerivedModel`'s three-level `Tag` shadow, but they are not dead. The new tests assert final validation state correctly and clear/re-validate as expected; I found no false-positive or always-passing tests.

**Net:** The fix resolves the common hidden-member case (leaf redeclares the shadow) but leaves one hidden-member shape — intermediate shadow inherited by a leaf that does not redeclare it — still throwing `AmbiguousMatchException` (finding #1), and that shape is not covered by the added tests.
