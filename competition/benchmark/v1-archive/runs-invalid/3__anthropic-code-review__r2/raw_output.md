Review complete — 10 angles run, deduplicated, swept. All analysis was done locally against the merged commit (7bba2205); nothing was posted to GitHub.

## Review: dotnet/runtime #127146 — "Handle canonical types in casting logic"

**Context:** The PR makes `CanCastTo`/constraint checking treat `__Canon`/`__UniversalCanon` as wildcards so dataflow analysis of `MakeGenericType` doesn't reject/crash on canonical shapes (fixes #126604). The core mechanism is sound for its stated goal, but it's implemented inside the *shared* `CanCastToInternal` primitive, and that primitive has other consumers whose correctness depends on the old "canon is an opaque `class __Canon : object`" semantics — including one caller whose in-code comment documents the exact contract this PR breaks.

```json
[
  {
    "file": "src/coreclr/tools/Common/JitInterface/CorInfoImpl.cs",
    "line": 2950,
    "summary": "compareTypesForCast now returns TypeCompareState.Must for shared-to-concrete interface casts because the canon-widened CanCastTo violates this caller's documented false-negative-only contract, letting the JIT fold away runtime type checks that can fail.",
    "failure_scenario": "Shared code `bool Test<T>(Foo<T> f) => f is IFoo<string>;` with `class Foo<T> : IFoo<T>` compiles as Test<__Canon>; the JIT queries compareTypesForCast(Foo<__Canon>, IFoo<string>). New IsCanonEquivalent(IFoo<__Canon>, IFoo<string>) makes CanCastTo true, so line 2952 returns Must ('Pass back positive results unfiltered') and the isinst folds to constant true — the comment table at lines 2964-2966 says this case must be May. At runtime Test<object>(new Foo<object>()) returns true though Foo<object> does not implement IFoo<string>: a type-safety miscompile. Affects both ILC and crossgen2 (the READYTORUN sanitizer at line 2988 only converts MustNot→May, not the new wrong Must)."
  },
  {
    "file": "src/coreclr/tools/aot/ILCompiler.Compiler/Compiler/Dataflow/HandleCallAction.cs",
    "line": 769,
    "summary": "MakeGenericMethodSite.InstantiateDependencies was not given the NormalizeInstantiation() fix that MakeGenericTypeSite received, so MakeGenericMethod dataflow still checks constraints on and roots denormalized shapes.",
    "failure_scenario": "The analog of the PR's own smoke test via methods — e.g. `typeof(Gen).GetMethod(\"M\").MakeGenericMethod(typeof(U), typeof(object))` in code shared over U — makes _method.InstantiateSignature produce a denormalized `M<__Canon, object>`; CheckConstraints runs on that shape and TryGetDependenciesForReflectedMethod roots it, hitting the same denormalized-shape hazard (#126604) the PR fixes at line 788 for types."
  },
  {
    "file": "src/coreclr/tools/Common/TypeSystem/Common/MetadataVirtualMethodAlgorithm.cs",
    "line": 878,
    "summary": "Default-interface-method and static-virtual variant resolution (lines 878, 907, 1167) now unify canonical and concrete interface instantiations via the widened CanCastTo, changing which candidate implementation is selected when building dispatch maps for canonical templates.",
    "failure_scenario": "A canonical template `Gen<__Canon>` implementing both IFoo<string> (from `class Gen<T> : IFoo<string>, IFoo<T>`) and IFoo<__Canon>: TryGetCandidateImplementation's `currentMT.CanCastTo(interfaceMT)` and the allowVariance check at line 907 now report IFoo<string> ↔ IFoo<__Canon> as a variance match where before only exact equality matched — a DIM or static-virtual can resolve to a different implementation in compiled dispatch maps than the runtime/spec resolution would pick, with no test in this PR covering dispatch-map behavior."
  },
  {
    "file": "src/coreclr/tools/Common/Compiler/DevirtualizationManager.cs",
    "line": 133,
    "summary": "Devirtualization's variant DIM decl selection (`iface.CanCastTo(declMethod.OwningType)`) and the sanity guard at line 97 now accept canon-vs-concrete interface matches, so devirtualization can proceed on pairs it previously rejected as FAILED_CAST.",
    "failure_scenario": "With implType canonical (Foo<__Canon>) and declMethod.OwningType a concrete IFoo<string>, line 97's `!implType.CanCastTo(...)` guard no longer bails and line 133 selects IFoo<string>'s method as the DIM dispatch decl for a shared type whose actual instantiation may not implement IFoo<string> — resolving the call to a wrong target instead of leaving it a virtual dispatch."
  },
  {
    "file": "src/coreclr/tools/Common/Compiler/TypeExtensions.cs",
    "line": 590,
    "summary": "TryResolveConstraintMethodApprox's single-matching-interface branch trusts CanCastTo without the canonical-exactness guard that the multiple-match branch has (lines 559-563), so canonical constrained calls can now be 'exactly' resolved statically.",
    "failure_scenario": "constrainedType=Foo<__Canon> with one same-typedef runtime interface and interfaceType=IFoo<string>: before, CanCastTo was false and resolution fell through (runtime lookup); now the wildcard match resolves an 'exact' interface method from a canonical type, statically binding a constrained call whose concrete instantiation may need a different target — precisely the situation the >1 branch explicitly excludes with IsCanonicalSubtype checks."
  },
  {
    "file": "src/coreclr/nativeaot/System.Private.TypeLoader/src/System.Private.TypeLoader.csproj",
    "line": 118,
    "summary": "Including CastingHelper.Canon.cs (rather than the behavior-preserving NonCanon stub) in the runtime TypeLoader silently changes runtime CanCastTo semantics for its one call site, variant GVM dispatch, whenever canonical types flow through it.",
    "failure_scenario": "TypeLoaderEnvironment.GVMResolution.cs:236 uses `currentIfaceType.CanCastTo(declaringType)` to pick a variant interface match at runtime; if a canonical/template-derived interface type (e.g. IEnumerable<__Canon>) ever reaches this check it now 'casts to' any concrete IEnumerable<string>, selecting a wrong GVM slot. [Unverified] whether canonical types actually reach this path at runtime — but the NonCanon stub was available to keep runtime behavior provably unchanged, and no TypeLoader test covers the change."
  },
  {
    "file": "src/coreclr/tools/Common/TypeSystem/Canon/CastingHelper.Canon.cs",
    "line": 13,
    "summary": "Altitude: wildcard-canon semantics are injected into the shared CanCastToInternal primitive instead of a constraint-checking-scoped entry point, flipping the codebase's established pattern where callers guard canonical inputs before calling CanCastTo.",
    "failure_scenario": "Existing consumers (ComparerIntrinsics.cs:215-225, TypeExtensions.cs:559-563, CorInfoImpl.cs:2931/2954-2966) each pre-filter canonical types because CanCastTo was a definite answer; the PR's goal only requires wildcard matching inside TypeSystemConstraintsHelpers (which already has its own partial-class seam via CanCastToConstraintWithCanon). Widening the global primitive forces every present and future CanCastTo caller to be audited for 'is true still Must?', which findings 1 and 3-5 show was not done."
  },
  {
    "file": "src/coreclr/tools/Common/TypeSystem/Common/MethodDesc.cs",
    "line": 257,
    "summary": "Covariant-return signature compatibility (MethodSignature.Equals with allowCovariantReturn → IsCompatibleWith → CanCastTo) is widened for canonical signatures, so override/MethodImpl matching on canonical forms can accept return-type pairs it previously rejected.",
    "failure_scenario": "Comparing a canonical override returning __Canon (from `override T M()`) against a base returning a concrete IFoo<string>: IsCompatibleWith now succeeds via the canon wildcard where it previously failed, so vtable/override validation computed over canonical templates diverges from the same computation over concrete instantiations."
  },
  {
    "file": "src/coreclr/tools/Common/TypeSystem/Canon/CastingHelper.Canon.cs",
    "line": 38,
    "summary": "IsCanonicalTypeArgMatch treats __UniversalCanon as matching __Canon (via CanonicalFormKind.Any), though __UniversalCanon also stands for value types that __Canon cannot represent.",
    "failure_scenario": "Gen<__UniversalCanon> is reported canon-equivalent/castable to Gen<__Canon>-shaped targets; any consumer treating the true result as definite (the Must consumers above) over-claims for value-type instantiations covered by __UniversalCanon but not by __Canon."
  },
  {
    "file": "src/coreclr/tools/Common/TypeSystem/Canon/CastingHelper.Canon.cs",
    "line": 17,
    "summary": "Doc comment says 'Pointers, byrefs, and function pointers are not valid instantiation arguments' but the __UniversalCanon branch returns true for any thisType, including pointers/byrefs/function pointers, relying on callers to have pre-filtered.",
    "failure_scenario": "`int*`.CanCastTo(__UniversalCanon) and `ref int`-typed TypeDescs now return true from the primitive itself; a future caller that doesn't route through CheckValidInstantiationArguments first gets a cast-success answer for shapes the comment declares invalid — comment and code disagree on where the invariant is enforced."
  },
  {
    "file": "src/tests/nativeaot/SmokeTests/TrimmingBehaviors/Dataflow.cs",
    "line": 702,
    "summary": "TestMakeGenericConstrainedDataflow exercises only the MakeGenericType path; there is no MakeGenericMethod analog for the constrained + mixed concrete/canonical instantiation scenario this PR fixes.",
    "failure_scenario": "The unnormalized MakeGenericMethodSite path (finding 2) stays untested end-to-end: a regression or the existing denormalized-method-shape hazard in MakeGenericMethod dataflow would pass this smoke-test suite."
  },
  {
    "file": "src/coreclr/tools/ILVerification/ILVerification.projitems",
    "line": 379,
    "summary": "The new TypeSystemConstraintsHelpers.NonCanon.cs entry indents its <Link> element with 8 spaces, inconsistent with the 6-space indentation of every sibling Compile entry in the file (e.g. lines 39-40).",
    "failure_scenario": "Cosmetic inconsistency in the shared projitems; the next mechanical edit or diff review trips over the odd indentation."
  }
]
```

### Summary of the most important items

1. **`CorInfoImpl.cs:2950` (critical)** — `compareTypesForCast` explicitly documents that `CanCastTo` "may return false negatives" for `__Canon` and that `IFoo<__Canon> -> IFoo<string>` must be **May**. The widened `CanCastTo` makes it **Must**, and positive results are "passed back unfiltered" — the JIT will delete runtime cast checks that can legitimately fail, in both NativeAOT and crossgen2.
2. **`HandleCallAction.cs:769` (high)** — the fix normalizes `MakeGenericTypeSite` but not the adjacent `MakeGenericMethodSite`, leaving the same denormalized-shape hazard for `MakeGenericMethod`.
3. **Interface/devirt/constrained-call resolution (`MetadataVirtualMethodAlgorithm`, `DevirtualizationManager`, `TypeExtensions`)** — all consume the same widened primitive and can now unify canon-vs-concrete instantiations when selecting dispatch targets; none of this is covered by the PR's tests.
4. **Altitude** — the wildcard semantics the dataflow fix needs could live behind the constraint-checking seam the PR already created (`CanCastToConstraintWithCanon`), rather than inside the global `CanCastToInternal` that Must-consumers depend on.
