All four review agents independently converged on the same load-bearing finding, each with a concrete repro. I verified the reflection semantics myself: `GetProperty(name, Public|Instance|FlattenHierarchy)` throws `AmbiguousMatchException` when two ancestors declare the same-named instance property with *different* types via `new` — which is exactly the failure mode this PR exists to fix.

Per your REVIEW-ONLY instruction, I am **not** posting to GitHub. Here is the review, printed to the terminal.

---

### Code review

Found 1 issue:

**1. The `FlattenHierarchy` fallback still throws `AmbiguousMatchException` — the exact exception this change exists to eliminate — for multi-level `new`-shadowing where the runtime model type does not itself redeclare the property.**

`src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:272-281`

https://github.com/dotnet/aspnetcore/blob/3aa499ae7d2314f7bbf89a3232df8371cc351d2a/src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs#L271-L282

The `DeclaredOnly` lookup only disambiguates when the *most-derived runtime type* is the class that did the `new` shadowing. When the property is shadowed at an **intermediate** ancestor and the concrete model type does **not** redeclare it, the first call returns `null` and control falls to the unguarded `GetProperty(name, Public | Instance | FlattenHierarchy)` fallback. That flattened lookup finds two-or-more same-named instance properties with differing signatures across the hierarchy and throws `AmbiguousMatchException` — reintroducing the original bug (fixed one inheritance level higher).

Concrete repro against the PR's own test models — add `class Leaf : DeepDerivedModel { }` (no redeclaration) and validate `new FieldIdentifier(new Leaf(), "Tag")`: `DeepDerivedModel.Tag` (int), `MidLevelModelWithShadow.Tag` (string), and `ModelWithHiddenBaseProperty.Tag` (object) all match → the fallback throws. This is the same class of failure that commit `c9ab4012` reproduced and set out to fix.

The new tests do not cover this path — `ValidatesPropertyHiddenAtMultipleInheritanceLevels` uses `DeepDerivedModel`, whose leaf type **does** redeclare `new int Tag`, so `DeclaredOnly` short-circuits and the `FlattenHierarchy` fallback is never exercised:

https://github.com/dotnet/aspnetcore/blob/3aa499ae7d2314f7bbf89a3232df8371cc351d2a/src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs#L215-L228

A robust fix walks the hierarchy level-by-level with `DeclaredOnly` (start at `ModelType`, ascend `BaseType`, return the first declared match) instead of relying on a single flattened lookup for the inherited case.

---

Notes on things checked and cleared (not findings):

- **Case sensitivity** — earlier commits added `BindingFlags.IgnoreCase` and then deliberately removed it (`21dfb306`). The original `GetProperty(name)` was case-sensitive by default, so the final case-sensitive behavior is correct, not a regression.
- **Dropping `BindingFlags.Static`** — intentional (DataAnnotations validates instance properties) and covered by the new `IgnoresStaticProperty` test. Not a regression.
- **Null-caching** and the method-level `[UnconditionalSuppressMessage("Trimming", "IL2080")]` — both preserved and still cover the new calls.
- Minor/cosmetic (below reporting bar): `BindingFlags.FlattenHierarchy` is effectively a no-op for instance properties (it governs static-member flattening); `Public | Instance` already walks base types. It reads as if it guards the ambiguity it does not actually prevent.

No CLAUDE.md files exist in this repository, so there were no project-specific convention checks to apply.
