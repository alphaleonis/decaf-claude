I have everything I need. The change is a focused bug fix (production hunk is 10 lines; the rest is tests). I reviewed it directly plus verified the reflection semantics against the linked issue's stack trace. Per your instructions this is review-only — nothing posted to GitHub.

---

## Code review — PR #67075 (dotnet/aspnetcore) / diff `a2a5480e`..`3aa499ae`

**Change summary:** `TryGetValidatableProperty` previously called `ModelType.GetProperty(fieldName)` (default flags `Public | Instance | Static`), which throws `AmbiguousMatchException` when a derived type hides a base property with `new` and the two declarations have different types (issue #27095). The fix now does a two-step lookup: first `Public | Instance | DeclaredOnly`, then, if that is null, `Public | Instance | FlattenHierarchy`. Tests were added for the hidden-property scenarios.

The core case from the issue (leaf type redeclares the `new` property) is now handled correctly. Findings below.

### Finding 1 — Fallback can still throw `AmbiguousMatchException` when the hidden property is not redeclared on the leaf type

`src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:278-280`

The `DeclaredOnly` first pass only finds a property declared **directly on the model's own type**. When the property that triggers hiding lives on ancestor classes and the actual model (leaf) type does **not** redeclare it, the first lookup returns `null` and control falls through to:

```csharp
propertyInfo = cacheKey.ModelType.GetProperty(
    cacheKey.FieldName,
    BindingFlags.Public | BindingFlags.Instance | BindingFlags.FlattenHierarchy);
```

This fallback walks the full hierarchy with no return-type filter — exactly the condition that produces the original bug. Concrete failure case:

```csharp
class A       { public object Tag { get; set; } }
class B : A   { public new string Tag { get; set; } }   // hides with a different type
class C : B   { }                                        // leaf; does NOT redeclare Tag
```

Validating a `C` instance on field `"Tag"`: `DeclaredOnly` on `C` → `null`; fallback searches the hierarchy where `B.Tag` (string) and `A.Tag` (object) both match with incompatible signatures → `RuntimeType.GetPropertyImpl(..., returnType: null, ...)` throws `AmbiguousMatchException` — the same throw path shown in issue #27095's stack trace. There is no `try/catch` around either call, so the exception propagates just as before.

The added tests do not cover this: `DeepDerivedModel` (test line ~305) redeclares `new int Tag` on the leaf, so `DeclaredOnly` always resolves it and the ambiguous fallback is never exercised. Subclassing a model that hides a base member (e.g. a view-model derived from a library base) is a realistic way to hit this.

*Reason: correctness — incomplete fix; the stated goal ("prevent AmbiguousMatchException") is not met for the leaf-does-not-redeclare case.*

### Finding 2 — `BindingFlags.FlattenHierarchy` in the fallback is a no-op and is misleading

`src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:280`

`FlattenHierarchy` only affects **static** members ("public and protected static members up the hierarchy"). The flags request `Instance` and omit `Static`, so `FlattenHierarchy` has no effect here: `Public | Instance | FlattenHierarchy` behaves identically to `Public | Instance`. Inherited **instance** properties are already returned by a non-`DeclaredOnly` lookup, so the flag adds nothing.

Beyond being dead intent, it is misleading: it reads as if it resolves cross-hierarchy matches, which is likely the assumption that leaves Finding 1 unaddressed. Recommend dropping `FlattenHierarchy` and, if the goal is to reliably pick the most-derived declaration, walking the type hierarchy explicitly (`Type.BaseType`) with `DeclaredOnly` at each level instead of relying on a single ambiguity-prone call.

*Reason: correctness/clarity — flag has no effect for instance members; signals a misunderstanding of the hierarchy search.*

### Finding 3 (informational, likely intentional) — Static properties are no longer resolved

`src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:272-280`

The original `GetProperty(name)` used default flags `Public | Instance | Static`; both new lookups omit `Static`, so a public static property that previously resolved will now return `null`. The new `IgnoresStaticProperty` test codifies this. This is almost certainly desirable (DataAnnotations validation operates on instance values, and a `FieldIdentifier` targets an instance), so I'm flagging it only as an intended behavioral change to be aware of, not a defect.

*Reason: behavior change — noted for completeness; no action needed.*

---

**Tests:** The added tests are well-formed and correctly assert the fixed behavior for the covered cases (leaf redeclares the hidden property, caching path, multi-level hiding with leaf redeclaration, unattributed shadow, static ignored). The gap is the missing coverage for Finding 1 (leaf that inherits — rather than redeclares — a hidden property).

**Bottom line:** The fix correctly resolves the reported scenario, but does not fully eliminate `AmbiguousMatchException` (Finding 1), and `FlattenHierarchy` is inert (Finding 2). Finding 1 is the one worth addressing before considering the underlying issue fully closed.

Note: nothing was posted to GitHub; PR #67075 shows as already MERGED. This output is terminal-only per your instructions.
