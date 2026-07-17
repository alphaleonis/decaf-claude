# subagent agent-a9f5c8b406f60e81b

## Depth Tier

**Depth: quick-to-standard** — 11 executable source lines changed (below the 50-line bar), and validation-reflection is not a listed high-risk domain, so the dispatch gate nominally puts this at Quick. But the change sits in a per-field hot path with a cache-cascade dimension and I was explicitly tasked to enumerate inheritance topologies, so I applied **assumption + composition + cascade** techniques rather than assumption-only. Findings below.

## Analysis

I confirmed the reflection mechanic that is the whole premise of bug #27095: `Type.GetProperty(name, flags)` with no `types`/`returnType` and **no `DeclaredOnly`** collects candidates across the whole hierarchy; two same-named properties whose signatures differ (e.g. `object` vs `int`) are **not** collapsed by hide-by-signature, so `count == 2` → `AmbiguousMatchException`. `FlattenHierarchy` only affects *static* inheritance; for *instance* properties Pass 2 (`Public|Instance|FlattenHierarchy`) is candidate-equivalent to the original buggy `Public|Instance` call.

The new tests only exercise topologies where the **leaf runtime type itself redeclares** the shadowed property (`DerivedModelWithHiddenProperty`, `DeepDerivedModel` — both declare `new … Tag/OrderID` on the leaf). Those are caught by Pass 1 (`DeclaredOnly`) and never reach Pass 2. The gap is the topology where the shadow lives on an **intermediate** class and the leaf merely inherits it.

Files:
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/2/src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs` (lines 370–383, method `TryGetValidatableProperty`; caller `OnFieldChanged` line 94)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/2/src/Components/Forms/src/ClientValidation/DefaultClientValidationService.cs` (line 283, `BuildMetadata`)

```json
[
  {
    "file": "src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs",
    "line": 378,
    "severity": "High",
    "category": "error-handling",
    "issue": "[ADV_CASCADE] Model whose leaf type inherits (does not redeclare) a `new`-shadowed differing-type property → Pass 1 DeclaredOnly returns null → Pass 2 FlattenHierarchy still sees 2 differing-signature candidates → AmbiguousMatchException (the exact original bug) → exception escapes before line 382 so nothing is cached → every subsequent OnFieldChanged re-throws → unhandled exception in the field-changed handler tears down the Blazor circuit on each keystroke.",
    "fix": "Do not let Pass 2 walk the hierarchy ambiguously. Either (a) loop up the type hierarchy calling GetProperty(name, Public|Instance|DeclaredOnly) on each base type and return the first (most-derived) match, or (b) wrap the fallback GetProperty in try/catch(AmbiguousMatchException) and resolve the most-derived candidate manually; in all cases still write the (possibly null) result into _propertyInfoCache so a failure is not recomputed every field change.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Components/Forms/src/ClientValidation/DefaultClientValidationService.cs",
    "line": 283,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_COMPOSITION] Same hidden-member model that the Forms fix now validates (e.g. DerivedModelWithHiddenProperty: base `object OrderID`, leaf `new int OrderID`) still throws AmbiguousMatchException here — BuildMetadata uses the original unpatched flags (Public|Instance, no DeclaredOnly). Server interactive DataAnnotations validation succeeds while the client-validation path throws for the identical model, and the throw inside GetOrAdd's factory means nothing is cached → re-throws per field.",
    "fix": "Apply the same two-pass (DeclaredOnly then hierarchy-walk) or try/catch(AmbiguousMatchException) resolution here so both validation paths agree on hidden members; add a regression test mirroring the Forms hidden-property tests.",
    "confidence": 75,
    "pre_existing": true
  }
]
```

### Dual-path check (Finding 1)
- **Forward:** `Base{object Foo}` → `Mid: new int Foo [Range]` → `Leaf: Mid {}`. Field "Foo" on a `Leaf` instance. Pass 1 DeclaredOnly on Leaf → null → Pass 2 FlattenHierarchy → {Mid.Foo(int), Base.Foo(object)} differ in signature → `AmbiguousMatchException` → thrown before line 382 → OnFieldChanged throws → circuit teardown; next change misses cache → re-throw.
- **Backward:** teardown ⇐ OnFieldChanged throws ⇐ Pass 2 throws ⇐ ≥2 differing-signature candidates survive ⇐ shadow at non-leaf level **and** leaf does not redeclare (else Pass 1 catches it). Every prior step is necessary and holds. Paths converge.

## Considered But Not Flagged

- **Dropping `Static` from the flags** — behavioral change (a `[Range]`-attributed `static` property previously matched by default flags is now ignored; test `IgnoresStaticProperty` codifies this). This is an intentional, tested improvement (DataAnnotations' `TryValidateObject` doesn't validate statics), no cascade, no failure chain. Not a finding.
- **Pass 1 (`DeclaredOnly`) throwing** — impossible: C# cannot declare two same-named properties on one type, so the DeclaredOnly candidate set is ≤1. Only Pass 2 can throw.
- **Leaf redeclares shadow without attributes** (`SkipsValidationWhenDerivedShadowHasNoAttributes`) — Pass 1 binds the leaf's unattributed member and validation is skipped. Matches C# member-hiding semantics; correct, not a bug.
- **Static + shadow interaction** — even if constructed, the consequence is "property silently not validated," benign and self-contained; fell apart as a failure scenario.

## Probe Requests

To confirm Finding 1 without modifying tracked source, add a throwaway test (new model + fact) to `src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs`:

- **Models:** `class Grand { public object Foo { get; set; } }` → `class Parent : Grand { [Range(1,100, ErrorMessage="Foo:range")] public new int Foo { get; set; } }` → `class Child : Parent { }`
- **Test line:** bind `new Child { Foo = 150 }`, call `editContext.NotifyFieldChanged(new FieldIdentifier(model, "Foo"))`.
- **Expected failure (current code):** the `NotifyFieldChanged` call throws `System.Reflection.AmbiguousMatchException` from `TryGetValidatableProperty` Pass 2 (line 378), instead of producing `["Foo:range"]`. A passing (post-fix) implementation would return the message with no exception.
