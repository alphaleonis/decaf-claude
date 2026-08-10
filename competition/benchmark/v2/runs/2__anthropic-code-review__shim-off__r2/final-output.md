## Code Review — dotnet/aspnetcore PR #67075

Reviewing the diff `a2a5480e..3aa499ae` (fix for `AmbiguousMatchException` in `DataAnnotationsValidator` with hidden/`new` members). Output only — nothing posted to GitHub. No CLAUDE.md exists in this repo, so CLAUDE.md compliance is N/A.

### Summary of the change
`TryGetValidatableProperty` previously called `ModelType.GetProperty(fieldName)` (default flags), which throws `AmbiguousMatchException` when a derived type hides a base property with `new`. The fix now does a two-step lookup: first `Public | Instance | DeclaredOnly` (prefers the most-derived declaration), then falls back to `Public | Instance | FlattenHierarchy` if that returns null. Six tests were added.

---

### Findings

**1. The fallback path still throws `AmbiguousMatchException` — the exact bug this PR fixes — when a hidden property is *inherited* without being redeclared on the model type.**

`src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:276-281`

The `DeclaredOnly` lookup only resolves ambiguity when the **model's own type** redeclares the property with `new`. If the model type inherits an already-ambiguous hidden property (a `new` shadow introduced in a mid-level ancestor, with a further-derived type used as the model that does *not* redeclare it), the first lookup returns `null` and control falls through to the `FlattenHierarchy` call, which sees two same-named properties across the hierarchy and throws `AmbiguousMatchException` again — unhandled, propagating out of `Validate()`.

Concrete failing shape (not covered by the added tests):
```csharp
class Base            { public object Tag { get; set; } }
class Mid  : Base     { [Range(1,100)] public new string Tag { get; set; } }
class Leaf : Mid      { }              // inherits the ambiguity, redeclares nothing
// model = new Leaf(); field "Tag"  → DeclaredOnly on Leaf = null → FlattenHierarchy throws
```

The added `DeepDerivedModel` test looks superficially like this case but redeclares `Tag` at the leaf (`class DeepDerivedModel : MidLevelModelWithShadow` with `public new int Tag`), so it always resolves via the `DeclaredOnly` branch and never exercises the null → fallback path against an inherited ambiguity. The gap is real and untested.

A robust fix would walk the type hierarchy (`DeclaredOnly` at each level from most-derived to base, returning the first match) rather than relying on a single `FlattenHierarchy` fallback that can itself be ambiguous.

GitHub permalink (for reference, not posted):
`https://github.com/dotnet/aspnetcore/blob/3aa499ae7d2314f7bbf89a3232df8371cc351d2a/src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs#L275-L281`

---

### Considered and dismissed (below reporting bar)

- **Dropping `BindingFlags.Static`** vs. the original default flags: this is an intentional behavior change (a public static property that previously could resolve is now ignored), and it is explicitly codified by the new `IgnoresStaticProperty` test. Validating a static property via a model-instance `FieldIdentifier` is nonsensical, so this is a safe, deliberate narrowing — not a regression.
- **Two `GetProperty` calls instead of one**: negligible — the result is cached in `_propertyInfoCache` per `(type, field)`.
- Test-only helper class shapes, naming, formatting — CI/linters cover these.

### Verdict
One substantive finding: the fix is incomplete for hidden properties inherited (not redeclared) at the model type's level, where the `FlattenHierarchy` fallback re-throws the same `AmbiguousMatchException`. It's an edge case, but it re-opens the precise failure the PR targets, and the added tests don't cover it.
