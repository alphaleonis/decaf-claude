# subagent agent-aa0d41abae0cd07de

I have fully traced the causal chain and verified the canonical-type semantics. I have everything needed to produce the compliance report.

---

## Spec Compliance Review — PR #127146 "Handle canonical types in casting logic"

**Spec source**: `linked` — GitHub issue dotnet/runtime#126604 (via "Fixes #126604"). Reviewed at full strength; per task instruction, finding severity capped at **High**.

### Verdict summary

The change **faithfully implements** the reported requirement. I traced the complete causal chain from the spec symptom to the fixed code and confirmed the exact repro instantiation now passes constraint validation and gets its metadata rooted. The generalization to `__UniversalCanon`, special constraints, variance, base chains, and arrays is **root-cause–justified, not scope creep**. One genuine gap: no test reproduces the *exact* reported shape (self-referential interface constraint on a struct param).

### Causal chain (spec symptom → fix), verified

Repro: `TypeHandler.Handle<TestRequest,string>()` calls `typeof(GenericType<,>).MakeGenericType(typeof(TRequest), typeof(TResponse))`, with `GenericType<TRequest,TResponse> where TRequest : struct, IRequest<TRequest,TResponse>`.

1. In the shared/canonical body of `Handle<TRequest,TResponse>`, the reference-type param `TResponse` (`string`) canonicalizes to `__Canon`; the struct param `TRequest` (`TestRequest`) stays concrete. The dataflow site builds `GenericType<TestRequest, __Canon>` — `HandleCallAction.cs:785` `InstantiateSignature`, then `:788` new `NormalizeInstantiation()`.
2. `CheckConstraints` → `VerifyGenericParamConstraint` for `TRequest=TestRequest` against constraint `IRequest<TestRequest, __Canon>` (`TypeSystemConstraintsHelpers.cs:62-78`).
3. Falls through the new `CanCastToConstraintWithCanon` (`:68`, returns false here — neither param nor constraint is a canon *definition* type) to `instantiationParam.CanCastTo(instantiatedType)` (`:76`).
4. `CanCastTo` → `CanCastToNonVariantInterface(TestRequest, IRequest<TestRequest,__Canon>)`. `TestRequest`'s runtime interface `IRequest<TestRequest,string>` now matches via the new `IsCanonEquivalent(...)` (`CastingHelper.cs:433`): same definition; arg0 `TestRequest==TestRequest`; arg1 `string` vs `__Canon` → `IsCanonicalTypeArgMatch` → `__Canon` is Specific canon and `string.IsGCPointer` → **true**.
5. `CheckConstraints` returns true → `RootingHelpers.TryGetDependenciesForReflectedType` roots metadata → the runtime `NotSupportedException` no longer occurs.

The chain from spec symptom to fixed code is **complete and correct**. Semantics confirmed against `IsCanonicalDefinitionType` (TypeSystemContext.Canon.cs:49) and `IsGCPointer` (TypeDesc.cs:430 — ref-shaped only, value types excluded, matching the `__Canon` accepts-reference-types intent).

```json
[
  {
    "file": "src/tests/nativeaot/SmokeTests/TrimmingBehaviors/Dataflow.cs",
    "line": 702,
    "severity": "Low",
    "category": "spec-compliance",
    "issue": "[SPEC_EDGE_CASE] The exact reported failure shape — a struct type argument satisfying a self-referential interface constraint 'where T : struct, IRequest<T,TResponse>' — is not reproduced by any added test. The end-to-end smoke test TestMakeGenericConstrainedDataflow uses a reference-type param with 'where U : IFoo, new()' (U canonicalizes to __Canon and satisfies interface+new()); the ILCompiler.TypeSystem unit test covers the invariant-interface-with-__Canon-in-type-arg mechanism but with a reference-type (class) param, no self-reference, and no simultaneous struct constraint. The fix's logic does handle the reported shape (verified by trace), so this is a regression-protection gap for the specific reported scenario, not a functional gap.",
    "fix": "Add a regression case mirroring the issue: a struct arg (T=TestRequest) implementing a self-referential invariant interface IRequest<T,U> where the U slot canonicalizes to __Canon, driven end-to-end through MakeGenericType/Activator.CreateInstance (or as a TestCanonicalTypeConstraints case with a struct param whose self-referential interface constraint's type arg is __Canon).",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Requirement Coverage Matrix

| Req | Description | Type | Status | Evidence |
|-----|-------------|------|--------|----------|
| R1 | `MakeGenericType`/`Activator.CreateInstance` on a closed generic whose param has `where T : struct, IRequest<T,TResponse>` must not throw at runtime under NativeAOT; required metadata/native code must be rooted | functional | **Covered** | `HandleCallAction.cs:788` normalize + `:790` CheckConstraints; `TypeSystemConstraintsHelpers.cs:68`; `CastingHelper.cs:426,433` `IsCanonEquivalent` in `CanCastToNonVariantInterface`. Full repro path traced above resolves to `true` → metadata rooted. |
| R2 | Constraint validation must stay *correct* — genuinely invalid instantiations still rejected (implicit in "handle constraints correctly") | constraint | **Covered** | Value-type-vs-`__Canon` negative assertions in `ConstraintsValidationTest.cs` (e.g. `int`/struct args `Assert.False`); permissive canon matches are compile-time rooting only, re-validated at runtime with concrete types (comment `TypeSystemConstraintsHelpers.Canon.cs:152-154`). |
| R3 | Baseline `where T : struct` (constraint removed) behavior must not regress | edge/behavior | **Covered** | Non-canon partials (`CastingHelper.NonCanon.cs`, `TypeSystemConstraintsHelpers.NonCanon.cs`) return `false`, so ILVerification and non-canon builds are behavior-preserving; canon-aware paths only activate for `__Canon`/`__UniversalCanon`. |
| R1a | Exact reported shape (self-referential interface constraint on a **struct** param) validated end-to-end by a regression test | functional/test-trace | **Partial** | Smoke test uses ref-type param + `IFoo,new()`; unit test covers canon-in-interface-typearg with a **class** param, non-self-referential. See Low finding. |

## Considered But Not Flagged

- **Breadth to `__UniversalCanon` + special constraints + variance + base chains + arrays is NOT scope creep.** The root cause is that shared-generic dataflow (`NormalizeInstantiation` / canonicalization) can hand `CheckConstraints` *any* canonical instantiation shape, and constraint validation previously had zero handling for canonical definition types. Correctly rooting the general MakeGenericType dataflow requires handling: `__UniversalCanon` (universal shared generics), `class`/`new()`/`struct` special constraints (`IsSpecialTypeMeetingConstraint`), invariant + variant interfaces, base-class constraints (`CanCastToClass:552`), and nested/array type args (`IsCanonicalTypeArgMatch` recursion). Each is the same latent bug on a different constraint kind; the unit test suite exercises all of them. Not a `SPEC_UNCOVERED` finding.
- **Permissiveness of canon wildcard matching is safe by design.** `CanCastToConstraintWithCanon` treating `__Canon`/`__UniversalCanon` as wildcards can only *over-root* metadata (a size cost, not a correctness bug); actual constraint enforcement re-runs at runtime against concrete type arguments. Any over-permissiveness concern is a design-reviewer matter, not a spec deviation.
- **`NormalizeInstantiation()` addition** (`HandleCallAction.cs:788`) is a necessary correctness precondition: `InstantiateSignature` can yield denormalized shapes (`Foo<object, __Canon>`) that must be normalized before constraint checking and rooting. In-scope of the root cause.
- **`allows ref struct` / ByRefLike path** (`TypeSystemConstraintsHelpers.cs:56`) is untouched and out of scope for the repro — `TestRequest` is an ordinary (non-ref) struct, so the `AllowByRefLike` gate is not exercised. No gap.
- **`ILVerification.projitems` / `.csproj` wiring** of the new `NonCanon`/`Canon` partials — correctly routes canon-aware behavior only to AOT compiler contexts and no-op stubs to ILVerification. Consistent with R3 (baseline preservation).

### Probe Requests
None. The compliance conclusion is fully determinable by static trace; no build or execution probe is needed.
