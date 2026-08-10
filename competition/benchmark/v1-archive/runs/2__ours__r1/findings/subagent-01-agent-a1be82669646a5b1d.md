# subagent agent-a1be82669646a5b1d

I have enough to complete the analysis. Let me verify my reflection-semantics reasoning against the exact model shapes in the tests to confirm the gap.

The mechanism is confirmable from the change itself plus the original bug's demonstrated behavior:

- Step 1 `GetProperty(name, Public|Instance|DeclaredOnly)` only sees members declared on the exact runtime (model) type. For the repro shape (`OrderClass` declares `new int OrderID`), that yields exactly one candidate and resolves cleanly.
- Step 2 `GetProperty(name, Public|Instance|FlattenHierarchy)` is the fallback for the case where the model type does **not** declare the field itself. `FlattenHierarchy` does not add `DeclaredOnly`, so it collects inherited candidates up the whole chain. When a hidden (`new`) member with a different signature lives in a base (e.g. `int` shadowing `object`), both signatures survive as candidates and — with no `returnType`/`types` to disambiguate — `GetProperty` throws `AmbiguousMatchException`. This is the *same* mechanism the original bug demonstrated.

Below is my report.

---

[Inference — reflection semantics reasoned statically; no .NET SDK available to execute, but the mechanism is corroborated by the original bug's demonstrated behavior]

```json
[
  {
    "file": "src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs",
    "line": 376,
    "severity": "High",
    "category": "spec-compliance",
    "issue": "[SPEC_PARTIAL] The two-step lookup only resolves hidden members when the runtime (model) type itself declares the shadowing `new` property. When the model type inherits a hidden member from an intermediate base without redeclaring it (e.g. `class LeafOrder : OrderClass {}` where `OrderClass` does the `new int OrderID` hiding), step 1 (DeclaredOnly) returns null and the step-2 FlattenHierarchy fallback collects both the derived `int` and base `object` signatures from the chain — re-throwing AmbiguousMatchException. The acceptance requires the fix work for 'arbitrary hidden-member shapes the app cannot change'; this subset is left unmet.",
    "fix": "Make the fallback deterministic instead of re-running an ambiguous name lookup: walk the type hierarchy from most-derived to base, calling GetProperty(name, Public|Instance|DeclaredOnly) at each level and returning the first non-null match. That resolves the most-derived shadowing property for arbitrary hidden-member shapes, including where the model type inherits (rather than declares) the hidden member.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Requirement Coverage Matrix

| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| R1 | Exact repro shape (base `object`, derived `new int` with `[Range]`) validates without throwing AmbiguousMatchException on NotifyFieldChanged | Covered | Step-1 `DeclaredOnly` returns the single declared derived property; `EditContextDataAnnotationsExtensions.cs:370-372`; test `ValidatesHiddenPropertiesWithoutAmbiguousMatchException` |
| R2 | Fix resolves the **derived** (shadowing) property, i.e. the one carrying `[Range]`, not the base | Covered | `DeclaredOnly` biases to the most-derived declared property; test asserts `OrderID:range` fires |
| R3 | Ordinary inherited (non-hidden) property still validates | Covered | Step-2 `FlattenHierarchy` fallback; test `ValidatesInheritedPropertyFromBaseClass` |
| R4 | Works for **arbitrary** hidden-member shapes the app cannot change (incl. model type that inherits from an intermediate base that hides, without redeclaring) | **Partial** | `EditContextDataAnnotationsExtensions.cs:374-379` — step-1 returns null (nothing declared on the model type), step-2 `FlattenHierarchy` collects both base+derived signatures ⇒ AmbiguousMatchException. No test exercises this shape. |
| R5 | Static properties not mistakenly validated as instance fields | Covered | `Instance` flag on both lookups; test `IgnoresStaticProperty` |

## Considered But Not Flagged

- **`ValidatesPropertyHiddenAtMultipleInheritanceLevels` / `DeepDerivedModel`** — Appears to cover the multi-level scenario, but the *leaf* type (`DeepDerivedModel`) still declares `new int Tag` itself, so step-1 `DeclaredOnly` resolves it trivially. It does **not** exercise the unmet R4 case (a model type that inherits a hidden member without redeclaring). This is the closest test and its naming may give a false sense of coverage, but the deeper test-quality assessment is test-reviewer's scope; I use it only as evidence that R4 is untested.
- **`SkipsValidationWhenDerivedShadowHasNoAttributes`** — With `DeclaredOnly`, the unattributed derived `new string Name` shadows the base `[Required] object Name`, so no validation fires. The spec does not address this directly, but resolving the most-derived member matches C# member-access semantics and the spec's "resolve the derived property" intent. Reasonable interpretation; not a deviation.
- **Step-1 ambiguity** — `DeclaredOnly` can never yield >1 property for a single name on one type (C# forbids it), so the first lookup cannot itself throw. No finding.
- **Scope creep** — The diff is minimal (two-step lookup + supporting test model types). No code exists beyond what the fix requires. No `SPEC_UNCOVERED`.

Note on confidence: R4's gap depends on BCL reflection semantics (`Type.GetProperty` + `FlattenHierarchy` over hidden members) which I reasoned about statically without executing (no SDK). The finding is rated 75 rather than 100 because compliance turns on code outside the diff; however, the original bug proves the exact same "GetProperty collects both signatures and throws" mechanism, so the residual uncertainty is low. A single unit test with a model type that subclasses `DerivedModelWithHiddenProperty` (or `DeepDerivedModel`) without redeclaring the field would confirm it.

Relevant files:
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/2/src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs` (lines 362-386, `TryGetValidatableProperty`)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/2/src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs` (new tests + model types)
