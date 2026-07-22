# subagent agent-a6f0845f9b6201e74

I have enough evidence to reach a verdict. Let me summarize my re-derivation.

## Verification findings

**1. The asymmetry is real and part of this changeset.** Commit `7bba2205` (#127146, fixes #126604) — the change under review — adds `NormalizeInstantiation()` only to `MakeGenericTypeSite`:
- `MakeGenericTypeSite.InstantiateDependencies` (HandleCallAction.cs:785-790): `InstantiateSignature` → `NormalizeInstantiation()` → `CheckConstraints`.
- `MakeGenericMethodSite.InstantiateDependencies` (HandleCallAction.cs:769-770): `InstantiateSignature` → `CheckConstraints`, **no normalization**.

**2. The method site reaches the identical vulnerable constraint path.** `CheckConstraints(this MethodDesc)` (TypeSystemConstraintsHelpers.cs:208-226) does two things: it calls `method.OwningType.CheckConstraints(context)` — literally the same `CheckConstraints(TypeDesc)` → `VerifyGenericParamConstraint` path the normalization fix was added to protect on the type side — and then validates the method's own instantiation through the same `VerifyGenericParamConstraint`. So the method's owning-type constraint check is invoked on a **non-normalized** owning type, exactly the condition the type-site fix guards against.

**3. `InstantiateSignature` does not normalize for methods.** `MethodDesc.InstantiateSignature` (MethodDesc.cs:734-769) only substitutes signature variables in both the method's own instantiation and its owning-type instantiation; no normalization. A runtime-determined method with a baked-in concrete arg mixed with a signature variable (e.g. `Gen<object, T, V>.Method`) can therefore yield a denormalized `Foo<object, __Canon>` owning type — the same mechanism the type-site comment describes.

**4. No exemption; the method path is untested.** Both sites are fed by the same `INodeWithRuntimeDeterminedDependencies` machinery with the same `typeInstantiation`/`methodInstantiation`, so denormalization is equally possible. The test added by the commit (`TestMakeGenericConstrainedDataflow` in Dataflow.cs) exercises only `MakeGenericType`, not `MakeGenericMethod` — the method path received neither the fix nor coverage.

**Attribution/citation:** Correct. The fix and thus the asymmetry are new in this commit (not pre-existing). Cited lines (769 for the method site, ~786-788 for the type fix) are accurate.

The finding is anchored at "100 for the symmetry; bug-reachability uncertain," and that is precisely what re-derives: the asymmetry is definite, and the method's `CheckConstraints` provably invokes the same constraint-validation path on an unnormalized instantiation. I could not construct a fully concrete failing repro (the residual uncertainty the finding itself acknowledges), but the parallel gap holds under scrutiny.

```json
{
  "finding": "#unknown",
  "verdict": "confirmed",
  "reason": "MakeGenericTypeSite (HandleCallAction.cs:788) gained NormalizeInstantiation() in commit 7bba2205 but the structurally-identical MakeGenericMethodSite (line 769) did not; CheckConstraints(MethodDesc) at TypeSystemConstraintsHelpers.cs:210 calls the very same OwningType.CheckConstraints/VerifyGenericParamConstraint path the fix protects, on a non-normalized owning type, and MethodDesc.InstantiateSignature (MethodDesc.cs:734) performs no normalization. The added test covers only the MakeGenericType path. The asymmetry and its shared vulnerable code path are re-derived; concrete bug-reachability remains uncertain exactly as the finding's own anchor states."
}
```
