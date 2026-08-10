# subagent agent-ae49499538979fba8

## Findings — PR #67075, `EditContextDataAnnotationsExtensions.cs`

**1. The fix does not actually eliminate `AmbiguousMatchException` — it only narrows the trigger condition, and this was flagged by a maintainer immediately after (unaddressed) merge.**

- File: `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:374-379`
```csharp
if (propertyInfo is null)
{
    propertyInfo = cacheKey.ModelType.GetProperty(
        cacheKey.FieldName,
        BindingFlags.Public | BindingFlags.Instance | BindingFlags.FlattenHierarchy);
}
```
- **Failure scenario**: `class GrandBase { public object Foo {get;set;} } class Base : GrandBase { [Range(1,100)] public new int Foo {get;set;} } class Leaf : Base { }` (Leaf does *not* itself hide `Foo`). For a `Leaf` model, the `DeclaredOnly` lookup on `Leaf` returns null (Leaf doesn't declare `Foo`), so execution falls into this fallback. `BindingFlags.FlattenHierarchy` has no effect on instance members (per MSDN, it only governs static members), so this call is functionally identical to the original buggy `GetProperty(name)` and will throw the very `AmbiguousMatchException` this PR is titled to fix, because it discovers both `Base.Foo` and `GrandBase.Foo`. This is exactly the pattern from a real-world consumer comment on the linked issue (#27095, "Simonl9l"): a subclass hides a 3rd-party base member with `new` + `base.X` delegation — any further type derived from that subclass without re-hiding would still crash.
- **Historical evidence this is a real, known gap, not just my inference**:
  - PR review comment from **Youssef1313 (MEMBER)**, posted on the final diff at `2026-07-09T06:58:15Z`: *"FlattenHierarchy is only relevant for statics IIRC. And this code can still throw if the previous call returned null and we get into here with some shadowing member in a base type."* — this is the identical defect. Critically, per `gh pr view --json commits` and the issue timeline, the PR's last code commit (`b9231fa7`) was at `2026-07-08T05:57:53Z` and the PR was **merged at `2026-07-09T06:42:30Z`**, roughly 16 minutes *before* this comment was posted. The comment landed after merge and was never incorporated — a correct, on-point maintainer objection shipped unaddressed.
  - An earlier reviewer, **ilonatommy (MEMBER)**, had proposed the historically-correct pattern during review — walking up the hierarchy one level at a time with `DeclaredOnly` at each step — but the PR author opted for the cheaper two-step version instead, reintroducing the gap for anything beyond one level of hiding.
  - This exact "hidden-by-`new` across an arbitrary number of levels" problem already has a **correct, established solution living elsewhere in this same codebase**: `PropertyHelper.GetVisibleProperties` (`src/Shared/PropertyHelper/PropertyHelper.cs:~440-470`, doc comment: *"GetVisibleProperties excludes properties defined on base types that have been hidden by definitions using the `new` keyword"*) and `MemberAssignment.GetPropertiesIncludingInherited` (`src/Components/Components/src/Reflection/MemberAssignment.cs:12-45`, used for Blazor `[Parameter]` discovery) both walk `currentType.BaseType` level-by-level with `DeclaredOnly`, keeping only the most-derived declaration per name. This PR's shallow "try declared, else try flattened" approach diverges from that established in-repo pattern and only handles the case where the model's *exact runtime type* performs the hide — which happens to be the only case the shipped issue reproduction and shipped tests exercise.

**2. Test coverage gap masks finding #1 — the "multi-level hiding" test never actually exercises the fallback path for a hidden property.**

- File: `src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs:241` (`ValidatesPropertyHiddenAtMultipleInheritanceLevels`) with fixtures at lines 411-427 (`ModelWithHiddenBaseProperty` → `MidLevelModelWithShadow` → `DeepDerivedModel`).
- In this test, `DeepDerivedModel` (the model's exact runtime type) itself redeclares `Tag` with `new int`, so `TryGetValidatableProperty`'s first `DeclaredOnly` call succeeds immediately and the buggy `FlattenHierarchy` fallback branch is never reached. Despite its name, the test does not cover a class that *inherits* an already-hidden property without redeclaring it — precisely the scenario Youssef1313 called out and the scenario in finding #1. No test in the PR would fail against the fallback bug.

**3. Minor: the `BindingFlags.FlattenHierarchy` flag on the fallback call is a no-op and its presence misrepresents what the code is doing.**

- Same location, line 378. `FlattenHierarchy` only affects `Static` member searches (undisputed by MSDN and confirmed by Youssef1313's review comment); since only `Instance` is set here, this flag does nothing — the call behaves identically to plain `GetProperty(name, Public | Instance)`. This is a knowledge-preservation issue: a future maintainer reading this code could reasonably (and incorrectly) believe `FlattenHierarchy` is what makes hierarchy-walking safe/complete here, when in fact it contributes nothing and the real (incomplete) safety comes only from having already failed the `DeclaredOnly` check.

No other historically-relevant regressions found in this file: the static-property exclusion (`IgnoresStaticProperty`), the base-attributes-ignored-when-hidden-without-attributes behavior (`SkipsValidationWhenDerivedShadowHasNoAttributes`), and the simple inherited-property case are all correctly handled by the new code and match the file's original design intent ("DataAnnotations only validates public properties").
