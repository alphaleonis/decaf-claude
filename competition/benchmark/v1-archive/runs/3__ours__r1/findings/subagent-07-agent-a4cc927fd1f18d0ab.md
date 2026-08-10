# subagent agent-a4cc927fd1f18d0ab

I have completed my system-model extraction and traced each cast/constraint path. Here is my design review.

## System Model

- **Boundary mechanism**: `CastingHelper` and `TypeSystemConstraintsHelpers` are `public static partial` classes. Their base files (`Common/*.cs`) now *unconditionally* reference five new private methods. Each consuming project must link exactly one companion: `Canon/*.Canon.cs` (real wildcard-aware impl) or `Common/*.NonCanon.cs` (stubs returning `false`). Consumers: ILCompiler.TypeSystem → Canon (both); ILVerification → NonCanon (both); System.Private.TypeLoader → Canon (CastingHelper only; it does not compile the constraints helper).
- **Contract flow**: `CheckConstraints` → `VerifyGenericParamConstraint` → {`IsSpecialTypeMeetingConstraint`, `CanCastToConstraintWithCanon`, `CanCastTo`} → `CanCastToInternal` → cast-path switch. Canon wildcard hatches were inserted at the top of `CanCastToInternal` (`IsCanonicalCastTarget`), in `CanCastToNonVariantInterface` + non-variant `CanCastToClass` (`IsCanonEquivalent`), and in `CanCastByVarianceToInterfaceOrDelegate` (`IsCanonicalTypeArgMatch`).
- **Data flow**: `MakeGenericTypeSite.InstantiateDependencies` → `InstantiateSignature` → `NormalizeInstantiation()` (new) → `CheckConstraints` → `TryGetDependenciesForReflectedType` (roots the raw type unchanged).

I traced the completeness question (2): variant class casts are covered because the variant `CanCastToClass` path delegates to the patched `CanCastByVarianceToInterfaceOrDelegate`; array-covariance element casts recurse through `CanCastToInternal` which carries the top-level hatch; each is exercised by the new tests. The hatches are consistent and complete for the constraint-check use. I found no under-approximating (dangerous-direction) gap in the cast paths.

The main design concern is **blast radius**: the shared partial class carries a compile-time-motivated behavior change into the runtime type loader.

```json
[
  {
    "file": "src/coreclr/nativeaot/System.Private.TypeLoader/src/System.Private.TypeLoader.csproj",
    "line": 120,
    "severity": "Medium",
    "category": "design",
    "issue": "[BOUNDARY_VIOLATION] Linking CastingHelper.Canon.cs (the real wildcard impl) rather than the CastingHelper.NonCanon.cs stub into System.Private.TypeLoader extends the __Canon/__UniversalCanon-as-wildcard casting behavior into the RUNTIME type loader, beyond the PR's stated compile-time ILC-dataflow intent. The type loader's only CanCastTo consumer is variant GVM resolution (TypeLoaderEnvironment.GVMResolution.cs:236, `currentIfaceType.CanCastTo(declaringType)`), where currentIfaceType is built over targetType.Instantiation and can be canonical in shared generics. The new IsCanonEquivalent/IsCanonicalTypeArgMatch/IsCanonicalCastTarget paths make more casts succeed, changing which interfaces are 'variant-compatible' and therefore potentially which GVM target is selected (or triggering the Diamond/ambiguous or Reabstraction throw). This runtime behavior change is uncommented and unexercised by the added tests (all compile-time ILCompiler.TypeSystem.Tests plus one trim smoke test). The conservative alternative (NonCanon stub) would have preserved runtime behavior identically and confined the fix to the compiler.",
    "fix": "Decide and document the intent: if the runtime type loader must NOT change GVM variant-dispatch behavior, link CastingHelper.NonCanon.cs there instead. If the wildcard-canon behavior IS wanted at runtime, add a comment at the companion include and a GVM-resolution test over canonical instantiations that pins the intended dispatch outcome.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.cs",
    "line": 8,
    "severity": "Low",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] The Canon/NonCanon partial split introduces an undocumented boundary contract: every project that compiles CastingHelper.cs (or TypeSystemConstraintsHelpers.cs) must link exactly one companion — Canon (real) or NonCanon (stub). The contract is compiler-enforced and safe (omitting both is a missing-method build error; linking both is a duplicate-definition error — never a silent wrong behavior), which is a sound property. However, nothing in the base partial files nor near the new method references documents the requirement, and this is the first use of a NonCanon-stub companion in the tree (all pre-existing *.Canon.cs are optional clusters referenced only from other canon-only files, not from an always-compiled Common file). A future consumer that adds these Common files hits an opaque 'IsCanonicalCastTarget does not exist' error with no pointer to the design.",
    "fix": "Add a short comment on each base partial class (CastingHelper / TypeSystemConstraintsHelpers) stating that consumers must link exactly one of the .Canon.cs or .NonCanon.cs companion, and why (canon-aware vs canon-agnostic projects).",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **MakeGenericMethodSite not normalized (question 3, sibling site).** `MakeGenericMethodSite` (HandleCallAction.cs:766) is the structural twin of `MakeGenericTypeSite` and does *not* call any normalization, so at first glance it looks like an un-fixed sibling with the same denormalized-shape hazard. On tracing the rooting paths, the asymmetry is justified: `TryGetDependenciesForReflectedType` roots the type *as-is* (`factory.ReflectedType(type)`, RootingHelpers.cs:262) so a denormalized `Foo<object,__Canon>` would become an ill-formed node — hence the explicit `NormalizeInstantiation()`. The method path instead canonicalizes internally via `method.GetCanonMethodTarget(CanonicalFormKind.Specific)` (RootingHelpers.cs:189), so its rooted node is already normalized. For constraint checking, the new wildcard hatches make canon args pass regardless of normalization, and the method site only rejects genuinely-invalid *concrete* args (which correctly fail at runtime too) — no missing-dependency/under-root in the dangerous direction. Verdict: defensible asymmetry, not a gap.

- **__UniversalCanon-as-wildcard masking invalid instantiations (question 4).** `NormalizeInstantiation` → `ConvertToCanonForm(Specific)` turns *all* reference-type args (including genuinely-concrete `object` literals from the `MakeGenericType` call) into `__Canon`, after which the wildcard hatches let CheckConstraints pass for instantiations the runtime will reject. This is real masking, but only in the *safe* direction: the consequence is over-approximation of the dependency graph (rooting a shared canonical template that may be unneeded), never an omitted dependency. The runtime type loader still enforces the real constraints and throws on the genuinely-invalid instantiation. Normalization can only make constraints easier to satisfy (ref→wildcard; value types stay concrete and precisely checked), so the fix introduces no under-rooting. Acceptable engineering trade-off, not a defect.

- **Casting-path completeness (question 2).** Traced variance, array covariance, non-variant interface, class base-chain, and generic-parameter-constraint paths. The variant `CanCastToClass` exact-match line uses only `IsEquivalentTo` (no `IsCanonEquivalent`), but the same-def canon case is subsumed by the patched `CanCastByVarianceToInterfaceOrDelegate` it calls in the same loop, so no gap. Hatch placement is consistent.

- **Companion-choice mapping across the three consumers.** ILVerification correctly gets the NonCanon stub (a verifier should not treat `__Canon` as a wildcard; canon types should never appear in verified IL), and ILCompiler.TypeSystem correctly gets Canon. Both are sound; only the System.Private.TypeLoader choice (flagged above) warrants scrutiny.

- **`IsCanonEquivalent` length-0 early return / `otherInst[i]` indexing.** Guarded by `HasSameTypeDefinition`, so instantiation lengths are equal; the length-0 case returning false is harmless because callers always OR it with `IsEquivalentTo` (identity). Line-level correctness detail, out of design scope.
