I've verified the findings against the actual code and tests. Here is the review.

## Code Review: PR #67075 — AmbiguousMatchException fix for hidden validatable properties

**Change under review:** `TryGetValidatableProperty` previously called `GetProperty(name)` (default flags `Public|Instance|Static`), which throws `AmbiguousMatchException` when a derived model hides a base property with `new`. The fix first queries `DeclaredOnly`, then falls back to `FlattenHierarchy`.

### Finding 1 — The fallback still throws `AmbiguousMatchException` for an *inherited* shadowed property (correctness gap; the primary defect)

`src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:278`

The two-step lookup handles the case where the *concrete model type itself* redeclares the property (`new`), because step 1 (`DeclaredOnly`) finds it and the ambiguous fallback is never reached. But it does **not** handle the case where the shadowing happens on an *intermediate* base class and the concrete leaf type inherits it without redeclaring:

```
class Base       { public object Tag { get; set; } }
class Mid : Base { public new string Tag { get; set; } }   // shadows
class Leaf : Mid { }                                        // inherits, redeclares nothing
```

For a model instance of runtime type `Leaf`:
- Step 1 — `GetProperty("Tag", Public|Instance|DeclaredOnly)` → `null` (Leaf declares nothing).
- Step 2 — `GetProperty("Tag", Public|Instance|FlattenHierarchy)` → walks the hierarchy, matches both `Mid.Tag` and `Base.Tag`, and throws `AmbiguousMatchException` — the exact crash the PR set out to fix.

[Inference] This follows from .NET reflection semantics: `GetProperty` considers inherited instance members unless `DeclaredOnly` is set, and two same-named properties across the hierarchy produce `AmbiguousMatchException`. This is expected behavior, not guaranteed; I have not executed it.

Note this leaf case was already broken *before* this PR, so it is an incomplete fix rather than a regression — but it leaves the stated goal only partially met. The existing tests do not cover it: `MidLevelModelWithShadow` (the intermediate shadow) is only ever exercised through `DeepDerivedModel`, which redeclares `Tag` and so is caught by step 1. A test using an intermediate-shadow type directly as the model, or a leaf that inherits the shadow, would expose the gap.

### Finding 2 — Silent behavior change: `BindingFlags.Static` dropped, so static validated properties are no longer found

`src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:272`

The original `GetProperty(name)` used default flags `Public|Instance|Static`, so a public static property carrying a validation attribute (`[Range]`, `[Required]`) would be located and validated on a field-changed notification. Both new lookups specify `BindingFlags.Instance` only, so such a property now resolves to `null` and is skipped. The new `IgnoresStaticProperty` test codifies this.

[Inference] This is very likely intended (per-instance validation of static properties is dubious), but it is an unannounced behavior change with no code comment explaining the deliberate exclusion. Worth a one-line comment so a future maintainer doesn't "restore" `Static` and reintroduce ambiguity.

### Finding 3 — `BindingFlags.FlattenHierarchy` is a no-op in this lookup (clarity)

`src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:280`

`FlattenHierarchy` only affects inheritance of **static** members. The lookup is `Instance`-only, and inherited public instance properties are already returned by `Public|Instance` without it. So the fallback behaves identically to `GetProperty(name, Public|Instance)`. The flag is misleading: it suggests it is the mechanism resolving the shadowing, when it does nothing here — obscuring that the real mechanism (and its limitation, Finding 1) is the `DeclaredOnly`-first ordering. Consider dropping the flag or adding a comment.

---

**Summary:** The fix resolves the common case (concrete type redeclares the hidden property) and is well-tested for it, including caching and multi-level redeclaration. The main concern is Finding 1 — the fallback re-enters the ambiguous path for an inherited (non-redeclared) shadow, and that path is untested. Findings 2 and 3 are lower-severity clarity/behavior-documentation issues.

Per instructions, nothing was posted to GitHub and no code was modified.
