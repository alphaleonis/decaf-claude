# subagent agent-a02b6c8522ffe52c1

I have everything I need. My key correctness claims are now empirically verified against .NET 10's reflection, not memory. Here is the review.

---

### Strengths

- **The core fix is correct and verified.** I reproduced the exact `GetProperty` calls on .NET 10. The original `ModelType.GetProperty(FieldName)` (default flags `Public | Instance | Static`) throws `AmbiguousMatchException` when a derived type hides a base member with `new` and a different type. The new two-step lookup resolves it correctly: `BindingFlags.Public | Instance | DeclaredOnly` returns exactly the most-derived declaration (`Int32 DerivedHidesDirectly.OrderID`), with no ambiguity because `DeclaredOnly` restricts the search to the model's own type. This directly satisfies requirement #67075 for the common case.
- **The fallback is well-motivated and works for plain inheritance.** When the property isn't declared on the model type itself, the `FlattenHierarchy` fallback correctly resolves an ordinary inherited property (verified: `String BaseName2.BaseName`), so non-hidden inherited members keep validating.
- **Good, targeted test coverage.** Seven new tests exercise: single-level hiding, hiding across multiple inheritance levels (`DeepDerivedModel`), inherited-only members, an unattributed derived shadow, a static property, plus a caching-stability test that re-notifies the same field repeatedly. The caching test is a nice touch since the resolved `PropertyInfo` is memoized in `_propertyInfoCache`.
- **Minimal, surgical change.** Only the resolution logic in `TryGetValidatableProperty` changed; the cache semantics, hot-reload cache clearing, and null-caching-on-miss behavior are all preserved. Clear inline comments.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)

**1. The fix still throws `AmbiguousMatchException` when the hidden member lives on an intermediate ancestor and the model (leaf) type does not redeclare it.**
`src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:370-379`

The fix handles the case where the model type *itself* declares the `new` member (Case A). It does **not** handle the case where hiding happens at an intermediate base and the concrete model type is a further-derived class that doesn't redeclare the member (Case B):

```
class Base { public object Foo { get; set; } }
class Mid  : Base { public new int Foo { get; set; } }   // hides
class Leaf : Mid  { /* does not redeclare Foo */ }        // model bound to the form
```

Verified empirically on .NET 10:
- `DeclaredOnly` on `Leaf` → `null` (Foo isn't declared on Leaf), so control falls through to the fallback.
- The `FlattenHierarchy` fallback on `Leaf` for `"Foo"` → **`AmbiguousMatchException`** (both `Mid.Foo` and `Base.Foo` are candidates with differing signatures).

This is the *same* failure mode (#67075 is about) — an unhandled exception raised from the `OnFieldChanged` event handler when the user edits a field — just for a narrower model shape. So the fix is incomplete rather than wrong.

Why it matters: multi-level domain models where a mid-level DTO/entity hides a base property with `new` and a concrete leaf is bound to the form are plausible in real code. Whoever hits it sees exactly the crash this PR claims to fix. [Inference] this shape is less common than Case A, so it's Important rather than Critical, but it should be either fixed or consciously scoped out.

How to fix: replace the two-lookup approach with a most-derived-to-base hierarchy walk using `DeclaredOnly` at each level and returning the first match. Verified this resolves all three cases (A → `int Leaf/Derived`, B → `Int32 Mid.Foo`, C → inherited `BaseName`):

```csharp
for (var t = cacheKey.ModelType; t is not null; t = t.BaseType)
{
    propertyInfo = t.GetProperty(
        cacheKey.FieldName,
        BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly);
    if (propertyInfo is not null)
    {
        break;
    }
}
```

This also subsumes the current `FlattenHierarchy` fallback (it naturally finds inherited members) and always yields the most-derived declaration, matching the requirement's "resolve the appropriate (most-derived) member." I'd add a test for the leaf-not-redeclaring shape, since no current test covers it (`DeepDerivedModel` still declares `new int Tag` directly, so it's Case A).

#### Minor (Nice to Have)

**2. Behavior change: static properties are no longer resolved for validation.**
`src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:370-379`

The original default flags included `BindingFlags.Static`; both new lookups omit it. Verified: for a `public static int StaticValue`, the original returned the static property, the new code returns `null`. The new `IgnoresStaticProperty` test documents this as intended, and DataAnnotations instance validation doesn't meaningfully validate static members, so this is arguably *more* correct — but it is a behavior change worth calling out explicitly in the PR description so it's a conscious decision, not incidental fallout of the flag choice.

**3. Two reflection lookups vs. one on cache miss.** Negligible (results are cached, and the hierarchy-walk recommendation in issue #1 also does at most a few lookups), so no action needed beyond noting it if you keep the two-lookup form.

### Recommendations

- Adopt the hierarchy-walk resolution (issue #1); it's the idiomatic, complete solution and collapses the two special cases into one loop while guaranteeing most-derived resolution.
- Add a regression test for the leaf-not-redeclaring hierarchy (Case B), and, if you keep dropping `Static`, keep the `IgnoresStaticProperty` test and mention the static behavior change in the PR notes.

### Assessment

**Ready to merge?** With fixes.

**Reasoning:** The change correctly and verifiably fixes the reported `AmbiguousMatchException` for the common case (model type declares the hidden member) with good test coverage, but I empirically confirmed it still throws the same exception when the hiding occurs on an intermediate ancestor and the bound model is a leaf that doesn't redeclare the member — a hierarchy walk closes that gap and is the cleaner solution.

*Verification note: I directly executed the `GetProperty` calls under .NET 10 to confirm the ambiguity/resolution behavior for every case above. I could not run the actual xUnit suite (the repo pins SDK `11.0.100-preview` via global.json, which isn't installed here), so the test assertions themselves are reasoned about, not executed.*
