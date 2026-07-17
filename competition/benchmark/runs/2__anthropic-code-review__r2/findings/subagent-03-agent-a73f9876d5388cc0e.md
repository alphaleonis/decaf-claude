# subagent agent-a73f9876d5388cc0e

```json
[
  {
    "file": "src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs",
    "line": 374,
    "severity": "High",
    "category": "error-handling",
    "issue": "[BUG_LOGIC] Fallback GetProperty call still walks the full type hierarchy without DeclaredOnly, so AmbiguousMatchException reappears when a property is hidden with `new` at an intermediate level and the runtime (leaf) type does not itself redeclare it.",
    "fix": "Concrete repro: `class A { public object Foo {get;set;} } class B : A { [Range(1,100)] public new int Foo {get;set;} } class C : B { }`. For a field on an instance of `C`, cacheKey.ModelType is `C`. The first call (`DeclaredOnly` on `C`) returns null because `C` does not declare `Foo`. The second call (`Public|Instance|FlattenHierarchy`, no `DeclaredOnly`) walks `C -> B -> A` and finds both `B.Foo` (int) and `A.Foo` (object) with mismatched signatures, throwing `AmbiguousMatchException` again — the exact exception this PR sets out to fix. Because the throw happens before the `_propertyInfoCache[cacheKey] = propertyInfo;` write, nothing is cached and every subsequent field-changed event for that field re-throws, propagating out of the unguarded `OnFieldChanged` handler. Fix by walking the hierarchy manually (checking `DeclaredOnly` at each type from `cacheKey.ModelType` up through `BaseType` and returning the first match) instead of a single non-`DeclaredOnly` fallback call, or by wrapping the fallback in try/catch for `AmbiguousMatchException` and resolving to the most-derived declared property found via an explicit walk. Note the new tests do not cover this case: `ValidatesPropertyHiddenAtMultipleInheritanceLevels` uses `DeepDerivedModel`, which redeclares `Tag` directly on the leaf type, so it never reaches the second GetProperty call in the code path that actually needs hierarchy-walking disambiguation.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs",
    "line": 378,
    "severity": "Low",
    "category": "other",
    "issue": "[QUALITY_ERROR_HANDLING] `BindingFlags.FlattenHierarchy` is a documented no-op here: per .NET docs it only affects the search for *static* members up the hierarchy. Since this call passes `Public | Instance` (no `Static`), the flag does nothing — the search already walks the instance hierarchy by default without it, which is exactly why this fallback call is exposed to the ambiguity described above. Its presence misleadingly suggests it is what causes hierarchy traversal.",
    "fix": "Drop `BindingFlags.FlattenHierarchy` from the fallback call (use `BindingFlags.Public | BindingFlags.Instance`), or replace the fallback with an explicit per-type walk as suggested above, so the binding flags accurately communicate intent.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`DeclaredOnly` restricting the first lookup to `Public | Instance`** — correctly excludes fields, private/internal properties, and static members; matches existing `TestModel` behavior for non-validatable members. No issue.
- **Double reflection call cost** — an extra `GetProperty` call only occurs on a cache miss (once per `(Type, FieldName)` pair, then cached including the `null` case for the fully-unmatched scenario); not a meaningful perf concern given the existing cache design.
- **Thread-safety of the unsynchronized `_propertyInfoCache[cacheKey] = propertyInfo;` write** — unchanged from the pre-existing code and explicitly commented as intentional ("no need to lock, because it doesn't matter if we write the same value twice"); out of scope as a pre-existing pattern not modified by this diff.
- **`ValidatesPropertyHiddenAtMultipleInheritanceLevels` test naming vs. actual coverage** — the test name implies deep-hierarchy disambiguation, but `DeepDerivedModel.Tag` is declared directly on the leaf type, so it's satisfied entirely by the first (`DeclaredOnly`) call and never exercises the vulnerable fallback path. This is a test-quality/coverage-gap observation (test-reviewer's domain), not a production code defect in its own right, so I did not file it as a separate finding — it's folded into the primary finding above as supporting evidence that the intermediate-hiding case is unverified by this PR's test suite.
- **`SkipsValidationWhenDerivedShadowHasNoAttributes` and `MatchesPropertyByExactName`** — verified consistent with the two-call lookup logic (leaf-declared hidden property found via `DeclaredOnly`, no ambiguity possible for a single type). No issue.
- **`IgnoresStaticProperty`** — confirmed both calls correctly exclude statics since neither specifies `BindingFlags.Static`; consistent regardless of `FlattenHierarchy`'s no-op status. No issue.

### Probe Requests

- **Test**: none exists yet — this would be a new `[Fact]` in `EditContextDataAnnotationsExtensionsTest.cs`, not a removal of an existing line.
- **Suggested probe**: add a three-level hierarchy where the hiding `new` property is declared at the *middle* class and the leaf class does **not** redeclare it (e.g., `GrandBase { object Foo }` → `MidLevel : GrandBase { [Range] new int Foo }` → `LeafModel : MidLevel { }`), then call `editContext.NotifyFieldChanged(new FieldIdentifier(new LeafModel(), nameof(LeafModel.Foo)))` (accessing `Foo` via the inherited/hidden `MidLevel.Foo`).
- **Expected result if my finding is correct**: this throws `System.Reflection.AmbiguousMatchException` from `OnFieldChanged`, i.e., the fix does not fully resolve issue #27095 for this topology.
