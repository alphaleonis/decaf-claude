# subagent agent-ad3f773c4357a2a82

Depth: deep — high-risk domain (NativeAOT compiler codegen/type-system soundness) and broad blast radius. Commit 2 deliberately moved canon-awareness out of the constraint helper and into the general `CanCastTo`, so the change is no longer scoped to constraint validation — it silently alters `CanCastTo` for every caller: the JIT cast-folding hook (`compareTypesForCast`), the compiler devirtualizer (`DevirtualizationManager`), and the runtime TypeLoader GVM dispatch (`CastingHelper.Canon.cs` is now compiled into `System.Private.TypeLoader`). Several of those callers have documented reliance on `CanCastTo` returning **false-negatives** for canonical-vs-concrete comparisons.

## Findings

```json
[
  {
    "file": "src/coreclr/tools/Common/JitInterface/CorInfoImpl.cs",
    "line": 2946,
    "severity": "Critical",
    "category": "other",
    "issue": "[ADV_COMPOSITION] Shared-generic code casts IFoo<T> (static type IFoo<__Canon>) to concrete IFoo<string> → compareTypesForCast calls fromType.CanCastTo(toType), which now returns TRUE via the new IsCanonEquivalent (IsCanonicalTypeArgMatch(__Canon,string)=true) → reports TypeCompareState.Must → JIT elides the runtime cast check → at runtime the instantiation behind __Canon is a non-string ref type (e.g. object), the cast that should throw InvalidCastException silently succeeds → an IFoo<object> is used as IFoo<string> (type confusion / heap-safety hole).",
    "fix": "Do not let canon-vs-concrete matches flow into the general CanCastTo used by compareTypesForCast. Either keep canon-awareness confined to CanCastToConstraintWithCanon (as in commit 1) instead of moving it into CastingHelper, or add a guard in compareTypesForCast so that when fromType.IsCanonicalSubtype(Any) && !toType.IsCanonicalSubtype(Any) a positive CanCastTo is downgraded to May unless the match is exact (non-canon). The code comment at lines 2954-2958 documents the exact false-negative assumption this change breaks.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/coreclr/tools/Common/Compiler/DevirtualizationManager.cs",
    "line": 97,
    "severity": "High",
    "category": "other",
    "issue": "[ADV_COMPOSITION] declMethod.OwningType = IFoo<__UniversalCanon> (USG), implType implements both IFoo<int> and IFoo<string>. The pre-existing ambiguity guard (lines 74-95) counts matches via ConvertToCanonForm(Specific) equality, which does NOT collapse the value-typed __UniversalCanon (int stays int, string→__Canon), so it counts 0 matches and does not bail with MULTIPLE_IMPL. The newly canon-aware CanCastTo at line 97 returns TRUE via IsCanonicalTypeArgMatch(x, __UniversalCanon) (universal wildcard) → devirtualization proceeds and ResolveInterfaceMethodTargetWithVariance resolves to an arbitrary one of the two implementations → wrong method devirtualized (silent miscompilation).",
    "fix": "Make the ambiguity guard use the same matching predicate the widened CanCastTo now uses (or extend it to Universal canonicalization), so the guard's multi-impl count stays consistent with what CanCastTo accepts. Before the PR, CanCastTo returned false here for canon interfaces, so the guard's stricter counting was sufficient; it no longer is.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/coreclr/nativeaot/System.Private.TypeLoader/src/Internal/Runtime/TypeLoader/TypeLoaderEnvironment.GVMResolution.cs",
    "line": 236,
    "severity": "Medium",
    "category": "other",
    "issue": "[ADV_COMPOSITION] Commit 2 adds CastingHelper.Canon.cs to System.Private.TypeLoader.csproj, so the runtime's only CanCastTo caller (variant GVM resolution: currentIfaceType.CanCastTo(declaringType)) becomes canon-aware. If a universal-shared-generic target type feeds a __UniversalCanon-bearing interface into this comparison, the new optimistic canon match can make a sibling variant interface instantiation compare-compatible where it previously did not → variant generic-virtual-method call resolves to the wrong slot, or spuriously trips the Diamond/AmbiguousImplementationException path.",
    "fix": "Confirm whether canonical (USG) interface types can reach FindMatchingInterfaceSlot; if so, gate the canon-aware CanCastTo behavior out of the runtime GVM comparison (use an exact/variance-only comparison there) rather than inheriting the compiler's optimistic canon matching.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Probe Requests

I nominate (do not run) these focused probes to raise confidence on the findings; each is read-only or additive-test, no tracked-source mutation:

1. **JIT contract break (Finding 1) — unit-test probe.** In `ILCompiler.TypeSystem.Tests/CastingTests.cs`, add assertions on a non-variant generic interface `IFoo<T>`: `Assert.??? (context.CanonType-instantiated IFoo<__Canon>).CanCastTo(IFoo<string>)`. Expected pre-PR: `false`; post-PR this returns `true`. Then assert `compareTypesForCast` semantics (or reason from it) to show `IFoo<__Canon> → IFoo<string>` flips from `May` to `Must`. This mechanically demonstrates the elided-cast hazard the comment at CorInfoImpl.cs:2954-2958 warns about.

2. **Revert-probe (Finding 1 root cause).** Revert only the `CanCastToNonVariantInterface` / `CanCastToClass` / `CanCastByVarianceToInterfaceOrDelegate` edits in `CastingHelper.cs` plus `CastingHelper.Canon.cs`, keeping commit 1's `CanCastToConstraintWithCanon` self-contained implementation. Re-run the new `TestCanonicalTypeConstraints` to check whether the constraint-checking fix still passes without widening the general `CanCastTo`. If it does, the JIT/devirt/GVM blast radius was avoidable and the finding is confirmed as an unnecessary regression.

3. **USG devirt/GVM reachability (Findings 2 & 3).** A trace/log probe (or targeted smoke test) that exercises universal-shared-generic virtual/interface dispatch over a type implementing two instantiations of the same generic interface (one value-typed, one ref-typed), then checks the devirtualized/resolved target. Confirms whether `__UniversalCanon`-declaring interfaces actually reach `ResolveVirtualMethod` line 97 / `FindMatchingInterfaceSlot` line 236.

## Considered But Not Flagged

- **`string` vs `object` conflation (the "guard" the task flagged).** The commit-1 guard (`ConvertToCanonForm` equality gated on "at least one side contains canon") was dropped in the commit-2 refactor, but the replacement `IsCanonEquivalent`/`IsCanonicalTypeArgMatch` is purely structural: `IsCanonicalTypeArgMatch(string, object)` → different type definitions, neither is canon, not parameterized → `false`. `List<string>` vs `List<object>` likewise recurses to `false`. The conflation is structurally prevented; no finding. (Same reasoning clears `string[]` vs `object[]`.)

- **Unbounded recursion / stack overflow in the new helpers.** `IsCanonEquivalent` ↔ `IsCanonicalTypeArgMatch` recurse only through the `Instantiation` array and `ParameterizedType.ParameterType` — a finite constructed-type expression tree with no cycles (a real constructed type cannot be `T = List<T>`). Self-referential generics like `C : IGen<C<T>>` are not followed (recursion is on type args, not the interface graph). Bounded; no StackOverflowProtect needed. No finding.

- **Struct wrongly satisfying a `class` constraint via __UniversalCanon.** A concrete struct `S`: `S.IsGCPointer=false`, `IsSpecialTypeMeetingConstraint(S, ReferenceTypeConstraint)=IsCanonicalDefinitionType(S,Any)=false` → correctly rejected. Only the wildcard `__UniversalCanon`/`__Canon` *as the param* passes, which is the intended optimistic accept (concrete substitution validated where the concrete generic is formed). Tests' negative assertions corroborate.

- **Over-accept in constraint checking → suppressed AOT warning → runtime NotSupportedException (the task's cascade).** Fell apart under construction: an over-accepting `CheckConstraints` causes the dataflow site to **root more** (`TryGetDependenciesForReflectedType`), which is the safe direction (larger image, not missing metadata). The runtime `NotSupportedException` scenario requires *under*-rooting, which optimistic accept does not cause. The only residual is a lost trim-diagnostic for a genuinely-invalid program that throws at runtime anyway — a diagnostic-precision tradeoff (test-reviewer/design lane), not a correctness defect.

- **`NormalizeInstantiation` in HandleCallAction changing the rooted type.** Normalizing `Foo<object,__Canon>` → `Foo<__Canon,__Canon>` before rooting is correct (denormalized mixed forms are not real runtime types); concrete non-canonical types are returned unchanged. Over-accept post-normalization stays in the safe root-more direction.

- **SzArray vs MdArray-rank-1 under-match in `IsCanonicalTypeArgMatch`.** The parameterized branch requires `type.Category == otherType.Category`, so an SzArray arg won't canon-match an MdArray-rank-1 arg that the main `CanCastArrayTo` path would accept. This is an *under*-match (missed root / possible false warning), not a soundness over-accept. Minor precision loss; not flagged.

- **ILVerification unaffected.** It compiles the `.NonCanon.cs` stubs (all new helpers → `false`), so its `CanCastTo`/constraint behavior is byte-for-byte unchanged. No regression there.
