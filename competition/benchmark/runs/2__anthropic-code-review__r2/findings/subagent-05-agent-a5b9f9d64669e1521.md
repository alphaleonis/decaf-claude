# subagent agent-a5b9f9d64669e1521

## Findings

**1. Fallback branch reintroduces the exact `AmbiguousMatchException` it was meant to fix, for shadowing that occurs above the model's own runtime type**

- **File:line**: `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:374-378` (the `if (propertyInfo is null) { ... GetProperty(..., BindingFlags.Public | BindingFlags.Instance | BindingFlags.FlattenHierarchy) }` fallback)
- **Reason flagged**: `BindingFlags.FlattenHierarchy` only affects the visibility of **static** members up the hierarchy (confirmed via the official .NET docs: "Specifies that public and protected static members up the hierarchy should be returned... Static members include fields, methods, events, and properties"). It has no effect on the visibility of **public instance** properties — those are already searched up the whole inheritance chain by default whenever `DeclaredOnly` is not specified. That means the fallback call `cacheKey.ModelType.GetProperty(name, Public | Instance | FlattenHierarchy)` is functionally identical to the *original*, buggy `cacheKey.ModelType.GetProperty(name)` call this PR replaces.

  The two-pass approach only avoids `AmbiguousMatchException` when the hiding (`new`) declaration exists directly on the model's own most-derived runtime type (`fieldIdentifier.Model.GetType()`), because `DeclaredOnly` can never itself be ambiguous (a single type can't declare two same-named public properties). But if the `new` hiding happens on an *intermediate* base class, and the model's concrete runtime type does **not** itself redeclare the property, the first pass (`DeclaredOnly`) returns `null` and falls through to the second pass, which is equivalent to the old broken lookup and will still throw.

  Concrete repro shape:
  ```csharp
  class GrandBase { public object Foo { get; set; } }
  class MidShadow : GrandBase { public new string Foo { get; set; } }
  class Leaf : MidShadow { /* does not redeclare Foo */ }
  ```
  For `model = new Leaf()`, `cacheKey.ModelType = typeof(Leaf)`. Pass 1 (`DeclaredOnly` on `Leaf`) finds nothing since `Leaf` doesn't declare `Foo`. Pass 2 (`FlattenHierarchy` on `Leaf`) sees both `GrandBase.Foo` and `MidShadow.Foo` as public instance properties reachable from `Leaf`'s hierarchy and throws `AmbiguousMatchException`, exactly as before the fix.

  This exception is uncaught: `TryGetValidatableProperty` is called from `OnFieldChanged` (line 94) with no surrounding try/catch, so it would propagate out of the field-changed event handler unhandled.

  The new test `ValidatesPropertyHiddenAtMultipleInheritanceLevels` (test file, `DeepDerivedModel`) does **not** exercise this gap — in that test the leaf class (`DeepDerivedModel`) itself redeclares `Tag` with `new`, so the `DeclaredOnly` first pass succeeds immediately and the fallback path is never reached. No test covers shadowing at a non-leaf ancestor level, so this regression path is unverified/uncaught by the PR's own test suite.

No other large/obvious functional bugs were found in the diff; the caching key (`(ModelType, FieldName)`) itself is unchanged by this PR and is not affected by the two-pass change.
