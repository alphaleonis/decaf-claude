# subagent agent-a1b4c87cf9ad5ed54

## Edge Case Analysis

### Pass 1: Path Walk

Traced 1 modified method (`TryGetValidatableProperty`, `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:363-386`) plus its sole caller (`OnFieldChanged`, line 94). Found 2 branching constructs: the cache-hit guard (`if (!_propertyInfoCache.TryGetValue(...))`) and the `if (propertyInfo is null)` fallback from `DeclaredOnly` to `FlattenHierarchy` lookup. 5 candidate hierarchy shapes were traced per the prompt (leaf-redeclares, intermediate-hides/leaf-inherits, non-hidden inherited, static, case-mismatch). To avoid speculation about CLR reflection internals, all 5 were verified empirically by compiling and running equivalent reflection calls against `dotnet` (SDK 10.0.203, present at `/home/decaf/.dotnet/dotnet`) rather than inferred from memory.

1 candidate confirmed as a finding after Pass 2; 4 discarded (ruled out by empirical verification).

### Pass 2: Validated Findings

#### Critical

- **[Missing else/default — incomplete fallback]** The `FlattenHierarchy` fallback still throws `AmbiguousMatchException` when the hiding `new` property is declared on an ancestor above the immediate model type, rather than on the model type itself — `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:374-379`
  - **Unhandled path:** Any hierarchy where (a) `ModelType` (the leaf, i.e. `fieldIdentifier.Model.GetType()`) does **not** itself declare the property (so step 1's `DeclaredOnly` lookup at line 370-372 returns `null`), and (b) two or more ancestor types declare a same-named property with **different property types**, e.g.:
    ```csharp
    class GrandBase { public object Tag { get; set; } }
    class Mid : GrandBase { public new string Tag { get; set; } }  // hides with a different type
    class Leaf : Mid { }  // leaf declares nothing — this is the model bound to the form
    ```
    Verified with an actual run against `Type.GetProperty("Tag", BindingFlags.Public | BindingFlags.Instance | BindingFlags.FlattenHierarchy)` on `typeof(Leaf)`:
    ```
    THREW: AmbiguousMatchException: Ambiguous match found for 'MidA System.String Tag'.
    ```
    A 3-level variant (hide at the grandparent-to-mid boundary, with two more no-op inheritance levels below) reproduces the identical throw, confirming this isn't limited to exactly-one-level-removed hierarchies.
  - **Consequence:** `TryGetValidatableProperty` (line 363) has no try/catch around the step‑2 `GetProperty` call, and its caller `OnFieldChanged` (line 94: `else if (TryGetValidatableProperty(fieldIdentifier, out var propertyInfo))`) has no try/catch either. The exception propagates out of the `EditContext.OnFieldChanged` multicast event, producing the exact unhandled `AmbiguousMatchException` crash this PR (#67075, fixing issue #27095) was written to eliminate — just one inheritance level deeper than the tested repro. This is a realistic shape: shared "base entity"/"base DTO" classes with a further-derived leaf used as the bound form model is a common .NET pattern.
  - **Remediation:** Step 2 needs the same signature-collision handling logic recursed up the hierarchy — e.g. walk `ModelType.BaseType` chain with `DeclaredOnly` at each level and take the first non-null match, instead of a single `FlattenHierarchy` call that re-introduces the multi-candidate ambiguity for non-leaf hides. Alternatively wrap the fallback call in try/catch for `AmbiguousMatchException` and walk up manually on catch.
  - **Confidence:** 96/100

### Positive Observations

- **Leaf-redeclares case (the originally reported bug, issue #27095)** is correctly fixed: `DeclaredOnly` finds the property directly on the leaf without ever reaching the ambiguous `FlattenHierarchy` path. Verified empirically (`LeafF.OrderID` resolves cleanly via step 1).
- **Purely inherited, non-hidden property** resolves correctly via step 2 (`BaseB.Name` returned, no ambiguity) — no gap.
- **Same-type hiding at a non-leaf level** (`Mid` hides `GrandBase.Tag` with the *same* `int` type, `Leaf` inherits without redeclaring) does **not** throw — the CLR's property cache dedupes identical-signature hides across the chain. Only differing-type hides trigger the gap above.
- **Static properties**: confirmed via test run that neither `DeclaredOnly` nor `FlattenHierarchy` (both using `Public | Instance` only, no `Static` flag) matches a static property — `IgnoresStaticProperty` test at `src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs` covers this and the behavior is intentional/correct, not a gap. (Note: this is a *behavior change* from the original single-arg `GetProperty(name)`, whose implicit default flags include `Static`, but it's covered by an explicit new test, so not an unhandled path.)
- **Case-sensitivity / no `IgnoreCase`**: `GetProperty` is case-sensitive in both step 1 and step 2, identical to the pre-existing single-arg overload's default behavior. This is unchanged by the diff, not a regression introduced here.

```json-findings
[{"severity":"Critical","confidence":96,"category":"edge-case","file":"src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs","line":376,"finding":"The DeclaredOnly -> FlattenHierarchy fallback in TryGetValidatableProperty still throws AmbiguousMatchException when a `new`-hidden property with a different type is declared on an ancestor above the immediate model (leaf) type -- e.g. GrandBase.Tag (object) hidden by Mid.Tag (string) via `new`, with Leaf : Mid declaring nothing. Verified by running the exact BindingFlags combination against dotnet: Type.GetProperty(name, Public|Instance|FlattenHierarchy) throws AmbiguousMatchException in this shape. TryGetValidatableProperty and its only caller (OnFieldChanged, line 94) have no try/catch, so the exception propagates unhandled out of EditContext's OnFieldChanged event -- reproducing the exact crash this PR was meant to fix, one hierarchy level deeper than the tested case.","remediation":"Recurse the DeclaredOnly lookup up the ModelType.BaseType chain (taking the first non-null match) instead of falling back to a single FlattenHierarchy call, or wrap the fallback in try/catch for AmbiguousMatchException and walk the hierarchy manually on catch.","source":"edge-case-hunter"}]
```

Relevant files:
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/2/src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs` (method under review: lines 362-386; caller: line 94)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/2/src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs` (added tests, none of which cover the multi-level/non-leaf hide shape)
