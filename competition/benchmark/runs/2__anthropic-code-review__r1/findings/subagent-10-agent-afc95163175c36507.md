# subagent agent-afc95163175c36507

## Review findings — PR dotnet/aspnetcore#67075

### Issue 1: Fallback path does not actually fix `AmbiguousMatchException` when the hiding property is declared at an intermediate ancestor, not at `ModelType` itself

**File/lines:** `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:370-379`

```csharp
propertyInfo = cacheKey.ModelType.GetProperty(
    cacheKey.FieldName,
    BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly);

if (propertyInfo is null)
{
    propertyInfo = cacheKey.ModelType.GetProperty(
        cacheKey.FieldName,
        BindingFlags.Public | BindingFlags.Instance | BindingFlags.FlattenHierarchy);
}
```

**Why flagged:**

- `BindingFlags.FlattenHierarchy` only affects *static* member lookup. Per Microsoft's own docs: "Specifies that public and protected **static** members up the hierarchy should be returned... Static members include fields, methods, events, and properties." Since the fallback call omits `BindingFlags.Static`, `FlattenHierarchy` is a no-op here — the fallback is functionally identical to `GetProperty(name, Public | Instance)`.
- `GetProperty(name, Public | Instance)` (no `DeclaredOnly`) is documented/known to throw `AmbiguousMatchException` whenever the *entire* type hierarchy reachable from the starting type contains two or more same-named properties with different signatures (i.e., hidden via `new` with a different type) — regardless of which ancestor level actually declares them. This is confirmed by a Microsoft archive blog post ("Overriding a property using new and reflection") showing exactly this pattern: `typeof(Derived).GetProperty("MyName", BindingFlags.Instance | BindingFlags.Public)` throws `AmbiguousMatchException` even though `Derived` itself declares the hiding property — the exception comes from the walk reaching `Base`'s property of the same name too.
- Consequence: the two-step fix only prevents the exception when `cacheKey.ModelType` (the model's *runtime* type) is the exact type that redeclares/hides the property (handled by the first, `DeclaredOnly` call). If a property is hidden at an *intermediate* ancestor (e.g., `Grandparent.Tag: object` → `Parent` does `public new string Tag` → `Child : Parent` does **not** redeclare `Tag` again) and the model instance's runtime type is `Child`, then:
  - Call 1 (`DeclaredOnly` on `Child`) returns `null` (`Child` doesn't declare `Tag`).
  - Call 2 (the "fallback") walks the full hierarchy from `Child`, finds both `Parent.Tag` (string) and `Grandparent.Tag` (object) as distinct candidates, and — by the exact mechanism this PR is meant to fix — throws `AmbiguousMatchException`, uncaught, out of `TryGetValidatableProperty`.
- This is not a hypothetical edge case invented in isolation: it's the same failure mode the PR title/tests target ("Hidden Members"), just one hierarchy level removed from where the fix currently checks. The added test `ValidatesPropertyHiddenAtMultipleInheritanceLevels` (test file, using `DeepDerivedModel : MidLevelModelWithShadow : ModelWithHiddenBaseProperty`) does **not** exercise this gap, because `DeepDerivedModel` itself redeclares `Tag` (`public new int Tag`), so the first `DeclaredOnly` call already succeeds and the fallback path is never reached. `MidLevelModelWithShadow` is only ever used as a base class in the test file — it's never instantiated/validated directly, so the "hidden at an intermediate level, not re-hidden at the leaf" scenario has no coverage and is not verified to be fixed.

**Confidence note [Inference]:** I did not execute .NET code to reproduce this directly (no `dotnet` available in this environment), but the conclusion follows directly from (a) Microsoft's documented, static-only scope of `BindingFlags.FlattenHierarchy`, and (b) a Microsoft-authored example demonstrating the exact ambiguous-hierarchy-walk exception this reasoning depends on. I'd flag this for the PR author to explicitly test (a 3-level hiding hierarchy where the leaf doesn't redeclare) before treating the fix as complete.

No other significant bugs found in the diff. The `DeclaredOnly` change for the common case (leaf type redeclares the hidden property) is correct and well-tested; caching behavior (`_propertyInfoCache[cacheKey] = propertyInfo`) is unaffected by the change.
