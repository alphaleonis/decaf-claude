All five agents have completed. Nothing was posted to GitHub — this is read-only output. Below are each agent's complete findings, followed by a consolidated summary. All line numbers refer to the post-merge tree (merge commit `7bba2205`).

---

# PR #127146 — "Handle canonical types in casting logic" (dotnet/runtime)

**Scope reviewed:** 13 files, +417/−7. New canonical-type (`__Canon`/`__UniversalCanon`) wildcard semantics in `CastingHelper` and `TypeSystemConstraintsHelpers` via a Canon/NonCanon partial-class split, plus `NormalizeInstantiation` in ILC dataflow. Fixes #126604.

---

## 🔍 Agent 1: code-reviewer

### Critical (confidence 90–100)

**1. `CanCastTo` can now return canon-wildcard false positives, breaking the documented contract of `compareTypesForCast` — possible elision of required runtime casts in shared generic code** (confidence 85)
`src/coreclr/tools/Common/JitInterface/CorInfoImpl.cs:2946-2979`, caused by `src/coreclr/tools/Common/TypeSystem/Canon/CastingHelper.Canon.cs:70-91` via integration points at `src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.cs:426, 433, 477, 552`.

Before this PR, `CanCastTo` with canonical types could only produce **false negatives** (`__Canon` behaved as `class __Canon : object` and never matched a concrete type argument). `compareTypesForCast` depends on exactly that property:

```csharp
// CorInfoImpl.cs:2946-2953
bool canCast = fromType.CanCastTo(toType);
// Pass back positive results unfiltered. The unknown type
// parameters in fromClass did not come into play.
if (canCast)
    result = TypeCompareState.Must;
```

with the comment table documenting `IFoo<__Canon> -> IFoo<string>  May` (CorInfoImpl.cs:2965). That invariant is now broken. Verified trace for `fromType = Foo<__Canon>` (where `class Foo<T> : IFoo<T>`, `IFoo` invariant), `toType = IFoo<string>`: `CanCastToInternal` → `CanCastToNonVariantInterface` (CastingHelper.cs:424-440) → runtime interface `IFoo<__Canon>` vs `IFoo<string>` → `IsCanonEquivalent` → same typedef, arg pair (`__Canon`, `string`) → `IsCanonicalTypeArgMatch` → `type` is Specific canon → returns `otherType.IsGCPointer` = **true** (CastingHelper.Canon.cs:43-44). `compareTypesForCast` now returns `Must` where it previously returned `May`; the same flip occurs through the variance path (CastingHelper.cs:477) for `IEnumerable<__Canon> → IEnumerable<string>`.

The JIT trusts `Must` unconditionally: `src/coreclr/jit/importer.cpp:5530-5537` elides the entire castclass/isinst (`return op1`); `src/coreclr/jit/gentree.cpp:35198` and `src/coreclr/jit/assertionprop.cpp:2623` similarly elide type checks. A shared body compiled for `Foo<__Canon>` executes for *all* reference-type instantiations, so eliding `(IFoo<string>)x` where `x` may actually be `Foo<object>` skips a required `InvalidCastException` — a type-safety hole. Applies to both NativeAOT and crossgen2 (the `#if READYTORUN` filter at CorInfoImpl.cs:2983-2992 converts `MustNot` → `May` but passes `Must` through).

[Inference] — return-value change and JIT consumption verified by code reading; no executed repro. At minimum, the documented contract comment at CorInfoImpl.cs:2948-2966 is now factually wrong and the interplay is unreviewed in this PR.

*Suggested fix:* harden `compareTypesForCast` (don't report `Must` when the positive answer involved canon matching), or scope the wildcard semantics to constraint validation via a separate entry point (e.g. `CanCastToCanonically`).

### Important (80–89)

**2. Semantics of a widely shared helper changed without auditing its other exact-answer consumers** (confidence 80)
`src/coreclr/tools/Common/Compiler/DevirtualizationManager.cs:97, 133`; `src/coreclr/tools/Common/TypeSystem/Common/MetadataVirtualMethodAlgorithm.cs:783, 878, 907`; `src/coreclr/nativeaot/System.Private.TypeLoader/src/Internal/Runtime/TypeLoader/TypeLoaderEnvironment.GVMResolution.cs:236`.

- `DevirtualizationManager.ResolveVirtualMethod` (line 97) uses `implType.CanCastTo(declMethod.OwningType)` as a bail-out guard, with explicit canonical-ambiguity handling just above (lines 74-95). Verified: `Foo<__Canon>.CanCastTo(IFoo<string>)` flips false→true, so devirtualization now proceeds where it previously rejected with `CORINFO_DEVIRTUALIZATION_FAILED_CAST`.
- `MetadataVirtualMethodAlgorithm.ResolveVariantInterfaceMethodToVirtualMethodOnType` (line 783) and `TryGetCandidateImplementation` (lines 878, 907) use `CanCastTo` to select variance candidates; concrete-vs-canon queries can now match where they previously did not.
- `System.Private.TypeLoader` now compiles the Canon implementation, so runtime GVM variant-dispatch resolution picks up the new semantics too.

[Unverified] whether each site produces an observable bug — reachability of changed answers traced, but not concrete end-to-end failures. The PR's stated motivation is constraint checking in dataflow, yet the behavior change lands in devirtualization, virtual-method resolution, and the runtime type loader with no changes, comments, or tests at those sites.

### Minor

**3. Canon matching incomplete for value-type shapes — conservative false rejections of the exact kind this PR fixes** (confidence 82)
`src/coreclr/tools/Common/TypeSystem/Common/TypeSystemConstraintsHelpers.cs:73` and `src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.cs:283`.
- The value-type prefilter (`IsValueType && IsValueType && !IsEquivalentTo` → fail) fires before any canon awareness: `where T : U` with `T = MyStruct<string>`, `U = MyStruct<__Canon>` returns false even though `CanCastToClass` at CastingHelper.cs:552 would match via `IsCanonEquivalent`.
- `CanCastParamTo` (CastingHelper.cs:283) requires exact equivalence for value-type array elements, so `GenStruct<string>[].CanCastTo(GenStruct<__Canon>[])` returns false — while the same pair *does* match through `IsCanonicalTypeArgMatch`'s array recursion. Asymmetric coverage. Both failures are conservative and match pre-PR behavior (incomplete coverage, not a regression).

**4. No method-level constraint tests with canonical types** (confidence 85)
`src/coreclr/tools/aot/ILCompiler.TypeSystem.Tests/ConstraintsValidationTest.cs:366-539` exercises only `TypeDesc.CheckConstraints`. The `MakeGenericMethodSite` path (`HandleCallAction.cs:760-774`) goes through `MethodDesc.CheckConstraints`, and the smoke test (`src/tests/nativeaot/SmokeTests/TrimmingBehaviors/Dataflow.cs:702-720`) covers only `MakeGenericType`. Existing fields (`_simpleGenericConstraintMethod`, `_complexGenericConstraintMethod`) are ready to reuse.

### Nits

5. **Indentation** — `src/coreclr/tools/ILVerification/ILVerification.projitems:379`: `<Link>` indented 8 spaces; every sibling uses 6.
6. **Unused using** — `src/coreclr/tools/Common/TypeSystem/Common/TypeSystemConstraintsHelpers.NonCanon.cs:4`: `using System.Diagnostics;` unused.
7. **Include placement inconsistency** — `ILCompiler.TypeSystem.csproj:134-136` and `System.Private.TypeLoader.csproj:120-122`: `CastingHelper.Canon.cs` (a `Canon\` file) inserted into the alphabetized `Common\` block, while `TypeSystemConstraintsHelpers.Canon.cs` was correctly placed in the Canon block (`ILCompiler.TypeSystem.csproj:104-106`).
8. **Test comment wording** — `ConstraintsValidationTest.cs:432-441`: says both "`IGen<in T>` is contravariant" and "__Canon matches object … in invariant arg position"; `IGen` is contravariant (`GenericConstraints.cs:8`) and the match actually happens via the canon-arg check before variance is consulted.

### Partial-class linking audit — complete and correct

| Project | CastingHelper.cs | ConstraintsHelpers.cs | Implementation |
|---|---|---|---|
| `ILCompiler.TypeSystem.csproj` | yes | yes | Canon + Canon — correct; serves ILCompiler.Compiler, ReadyToRun/crossgen2, RyuJit, ILTrim.Core, dotnet-pgo via assembly reference |
| `ILVerification.projitems` | yes | yes | NonCanon + NonCanon — correct (no Canon subsystem; behavior unchanged) |
| `System.Private.TypeLoader.csproj` | yes | no | Canon — correct (has Canon subsystem; doesn't compile the constraints helper) |

No project missing an implementation or getting two.

### Verified non-issues
- `IsCanonicalTypeArgMatch` is properly symmetric (incl. `__UniversalCanon` vs `__Canon` via the `IsCanonicalDefinitionType(..., Any)` disjuncts; `__UniversalCanon` is `TypeFlags.ValueType` per `CanonTypes.cs:206`).
- `IsCanonEquivalent`'s arity assumption is safe: `HasSameTypeDefinition` implies equal arity; arrays hit the `Length == 0` early-out; open definitions don't spuriously match.
- SzArray vs MdArray distinguished via `Category` before the rank check; recursion is structural over finite type trees, terminates without `StackOverflowProtect`.
- `MakeGenericMethodSite` not normalizing is consistent: the method rooting path normalizes via `GetCanonMethodTarget(CanonicalFormKind.Specific)` at `RootingHelpers.cs:189`; the type path needed it because type nodes assert normalized shapes (`ILScanner.cs:771-785`).
- `ComparerIntrinsics.ImplementsInterfaceOfSelf` unaffected (calls `CanCastTo` on type *definitions*).
- The variant-class path in `CanCastToClass` (line 521) not gaining `IsCanonEquivalent` is fine — subsumed by `CanCastByVarianceToInterfaceOrDelegate`.

### Strengths
Clean Canon/NonCanon split following the repo's `*.Canon.cs` convention with ILVerification bit-for-bit unchanged; correct asymmetric wildcard semantics (`__Canon` = ref types only, `__UniversalCanon` = anything); correct special-constraint mapping; thorough positive+negative unit tests plus an end-to-end #126604 repro; well-commented `NormalizeInstantiation` fix.

---

## 🕳️ Agent 2: silent-failure-hunter

Framing fact: the PR changes the semantics of the **general-purpose** `CanCastTo` API for every consumer of `ILCompiler.TypeSystem` (ILC *and* crossgen2 via `ILCompiler.ReadyToRun.csproj:26`), but the diff only updates and tests the constraint-checking consumer.

**Finding 1 — CRITICAL: `compareTypesForCast` now returns `Must` for a case its own comment documents as `May`**
`src/coreclr/tools/Common/JitInterface/CorInfoImpl.cs:2946-2979`, broken by `CastingHelper.Canon.cs:30-64` and the `IsCanonEquivalent` hooks at `CastingHelper.cs:426,433,552`. Same trace as code-reviewer's finding 1 (independently discovered): `IsCanonEquivalent(IFoo<__Canon>, IFoo<string>)` → true → `canCast == true` → **`Must`**, where pre-PR the answer fell through to `toType.HasInstantiation` → `May`, exactly as the comment table prescribes. `Must` is the JIT's license to elide the cast check; at runtime the shared body may execute with `Foo<object>`, which does not implement `IFoo<string>` — the `InvalidCastException` that should be thrown is silently removed. [Inference — path verified by reading, not executed.] Hidden errors: eliminated `castclass`/`isinst` checks in shared generic code; objects flowing under a wrong static interface type. User impact: silently wrong program behavior with no diagnostic — strictly worse than the `MissingMetadataException` the PR fixes. Recommendation: opt-in canonical wildcard behavior (e.g. `CanCastToAllowingCanonMatches` used only by constraint checking), or downgrade positive results involving canonical wildcards to `May`.

**Finding 2 — HIGH: Devirtualization guards silently pass where they previously conservatively bailed**
`src/coreclr/tools/Common/Compiler/DevirtualizationManager.cs:97` and `:133`; `MetadataVirtualMethodAlgorithm.cs:783` (also `:878, :907, :994, :1010, :1167`). Canonical `implType`s demonstrably reach here (the canonical-match counting loop at lines 74-95; the only rejection in `resolveVirtualMethod` at `CorInfoImpl.cs:1360` is for `objType` being `__Canon` itself, not `Foo<__Canon>`). Pre-PR, `implType.CanCastTo(declMethod.OwningType)` for `Foo<__Canon>` vs `IFoo<string>` returned false → `CORINFO_DEVIRTUALIZATION_FAILED_CAST` → safe no-devirtualization. Post-PR the guard passes and resolution proceeds; the DIM arm at line 133 has the same newly-passing check. [Inference] The resolved target is *probably* sound for same-typedef non-variant cases, but nothing in the PR mentions that devirtualization behavior changed — if unsound in any corner (variant DIMs; the "prefer exact match" loop now matching multiple canon-compatible interfaces), the result is a virtual call bound to the wrong target with no warning. Also inheriting the new semantics unaudited: `TypeExtensions.cs:244,254` (type merging) and `MethodDesc.cs:257` (covariant-return signature compatibility).

**Finding 3 — MEDIUM: Function pointer types silently fall through `IsCanonicalTypeArgMatch` — the PR's own bug class survives for this corner**
`CastingHelper.Canon.cs:30-64` (no arm for function pointers); producers: `FunctionPointerType.Canon.cs:21-33` + `StandardCanonicalizationAlgorithm.cs:121-129`. Canonicalization recurses into fn-ptr signatures (`delegate*<string, void>` → `delegate*<__Canon, void>`), so a constraint can legally contain such a type. `IsCanonicalTypeArgMatch(delegate*<string,void>, delegate*<__Canon,void>)` hits no case: neither side is a canonical *definition* type; `IsCanonEquivalent` fails (`FunctionPointerType.GetTypeDefinition()` returns `this`); `FunctionPointerType` is not a `ParameterizedType` → silent `return false`. Fn-ptr instantiation args are structurally valid (`CheckValidInstantiationArguments` at `TypeSystemConstraintsHelpers.cs:174-188` rejects pointers/byrefs but not fn-ptrs). Consequence: constraint check fails → `MakeGenericTypeSite.InstantiateDependencies` silently returns an empty list → dependency dropped → runtime `MissingMetadataException`, identical to #126604 for a narrower input. Not even a comment acknowledges the gap.

**Finding 4 — MEDIUM: `MakeGenericMethodSite` not normalized; method path untested, validates different shapes than the type path**
`HandleCallAction.cs:766-773` (method site) vs `:782-793` (type site). Graph-node identity on the method path is rescued downstream by `GetCanonMethodTarget(CanonicalFormKind.Specific)` at `RootingHelpers.cs:189` (verified; `NormalizeInstantiation` exists only for `TypeDesc`, `TypeExtensions.cs:678`). But `CheckConstraints` now runs on a *normalized* (laxer) shape on the type path and a *denormalized* (stricter) shape on the method path — two different validation regimes for the same app pattern, undocumented. Trace says both regimes are individually sound, but the smoke test (`Dataflow.cs:702-717`) covers only `MakeGenericType`, so any residual method-path issue surfaces only as a runtime `MissingMetadataException`. Recommendation: normalize the method site too, or comment the deliberate omission and add a `MakeGenericMethod` smoke case.

**Finding 5 — MEDIUM/LOW: `IsCanonicalCastTarget` contradicts its own doc comment for `__UniversalCanon`**
`CastingHelper.Canon.cs:13-24`. Doc says "Pointers, byrefs, and function pointers are not valid instantiation arguments," but the `Universal` branch returns `true` unconditionally — `int*`, byrefs, fn-ptrs, even `void` "cast to" `__UniversalCanon`. Same asymmetry in `CanCastToConstraintWithCanon` (`TypeSystemConstraintsHelpers.Canon.cs:36-37`). Latent in ILC because `SupportsUniversalCanon => false` (`CompilerTypeSystemContext.cs:319`), but the code is compiled into `System.Private.TypeLoader` and exercised by the test context; future re-enablement would silently over-approve.

**Finding 6 — LOW: TypeLoader (runtime) silently inherits wildcard cast semantics**
`System.Private.TypeLoader.csproj` now includes `CastingHelper.Canon.cs`; runtime consumer `TypeLoaderEnvironment.GVMResolution.cs:236` (`currentIfaceType.CanCastTo(declaringType)` under variant GVM dispatch). This changes an at-runtime dispatch-resolution predicate on devices. [Unverified] whether canonical types ever reach that call site; no test in this PR covers the TypeLoader.

**Verified as correct / appropriate conservative defaults:**
1. The `_ => throw new UnreachableException()` arm (`TypeSystemConstraintsHelpers.Canon.cs:19`) is genuinely unreachable (call sites at `TypeSystemConstraintsHelpers.cs:33,42,51` pass exactly the three single flags); a future misroute fails fast — *better* than the pre-existing `CheckGenericSpecialConstraint` default arm (`TypeSystemConstraintsHelpers.cs:125`, `Debug.Assert(false); break;`) which silently treats unknown constraints as unsatisfied in release builds (predates the PR).
2. `IsCanonEquivalent` indexing is safe (equal arity implied by `HasSameTypeDefinition`; violation would throw `IndexOutOfRangeException` — fail-fast, not corruption).
3. Recursion terminates (structural, finite, no cycles; same exposure as `InstantiateSignature`).
4. Partial-class wiring cannot fail silently — missing or duplicate implementations are compile errors; matrix verified. ILVerification's NonCanon choice is forced and semantically exact.
5. The silent empty `DependencyList` on `CheckConstraints` failure (`HandleCallAction.cs:790-792`) is appropriate for genuinely failing constraints (runtime throws `ArgumentException` from `MakeGenericType` itself), and the "wildcard, runtime re-validates" direction (`TypeSystemConstraintsHelpers.Canon.cs:29-34`) is the right failure asymmetry — though the design has zero telemetry, so residual false negatives (Finding 3) manifest only at runtime.

*(Note: findings caveat — if follow-up commits after the merge already addressed 1 and 2, this tree pinned at the merge commit would not show it.)*

---

## 🧪 Agent 3: pr-test-analyzer

**Overall rating: 7/10** — the regression that motivated the PR is well-pinned; the surface the PR *added* is roughly half-exercised. Mapping is manual static tracing, not instrumented coverage.

### Branch-by-branch coverage map

**`IsCanonicalCastTarget` (`CastingHelper.Canon.cs:33-44`)** — **never returns true in any test**:
| Branch | Covered? |
|---|---|
| `__UniversalCanon → true` (:37-38) | **NOT covered** |
| `__Canon → IsGCPointer` true (:40-41) | **NOT covered** |
| `__Canon → IsGCPointer` false | Covered indirectly (test :499-500 via `CanCastTo(struct, __Canon)`) |
| fallthrough false (:43) | Covered |

Every unit test with naked canon on the constraint side is short-circuited earlier by `CanCastToConstraintWithCanon` (`TypeSystemConstraintsHelpers.cs:68-69`); the positive branches only fire from *nested* positions (e.g. `CanCastParamTo`, `CastingHelper.cs:294`) and no test constructs that shape. **Deleting the entire hook at `CastingHelper.cs:176-179` leaves the suite green.**

**`IsCanonicalTypeArgMatch` (`CastingHelper.Canon.cs:50-84`)**:
- A. `otherType == __UniversalCanon → true` (:54-55) — covered (test :510-517 via nested recursion).
- B. `otherType == __Canon` (:57-58) — GCPointer half covered both ways (:408-434 true; :419-422/:447-451 false); the `|| IsCanonicalDefinitionType(type, Any)` sub-clause (canon-vs-canon) — **NOT covered**.
- C. `type == __UniversalCanon → true` (:60-61) — **NOT covered** (canon always sits on the constraint side in tests).
- D. `type == __Canon → …` (:63-64) — **NOT covered**, same reason.
- E. `IsCanonEquivalent → true` (:68-69) — covered (:437-445).
- F. ParameterizedType recursion (:73-81) — positive covered (`string[]` vs `__Canon[]`, :520-531); Category-mismatch negative — **NOT covered**; **Rank check (:76-78) only trivially covered** (SzArray rank 1==1) — a genuine `string[,]` vs `__Canon[,,]` mismatch is untested; deleting the Rank check would break nothing in the suite.
- G. fallthrough false (:83) — covered.

**`IsCanonEquivalent` (`CastingHelper.Canon.cs:90-111`)**: definition-mismatch and `Length == 0` covered; the `thisInst[i] == otherInst[i] → continue` mixed-instantiation path (:103-104) — **NOT covered** (no test compares e.g. `Foo<int, string>` vs `Foo<int, __Canon>` — precisely the "denormalized shape" the PR's own HandleCallAction comment calls out).

**`IsSpecialTypeMeetingConstraint` (`TypeSystemConstraintsHelpers.Canon.cs:129-140`)**:
- `ReferenceTypeConstraint` true arm covered only via `__UniversalCanon` (:387-388) — for `__Canon` the caller's `IsGCPointer` check (`TypeSystemConstraintsHelpers.cs:31`) short-circuits first, so **test :374-375 passes even without this PR** (behavior pin, not coverage).
- `DefaultConstructorConstraint` — covered for both (:377-378, :390-391).
- `NotNullableValueTypeConstraint` true arm is **dead by construction**: `__UniversalCanon` is Category ValueType (`CanonTypes.cs:198-206`), so `IsValueType` at `TypeSystemConstraintsHelpers.cs:49` short-circuits — test :393-394 exercises pre-existing code, not the new arm. False arm covered (:380-382).

**`CanCastToConstraintWithCanon` (`TypeSystemConstraintsHelpers.Canon.cs:148-165`)** — all live branches covered; best-covered new function. The struct-under-`__UniversalCanon` test (:506-507) also regression-guards check *ordering* before the value-type early-out at `TypeSystemConstraintsHelpers.cs:73`.

**Four CastingHelper.cs integration points**: (1) :176-179 reached but never true — **effectively untested**; (2) :426 self-equivalence — **NOT covered** (needs `T = INonVariantGen<string>` vs constraint `INonVariantGen<__Canon>`; the only interface-as-param test uses variant `IGen`, :474-480); :433 loop — covered both ways; (3) :477-478 — positive covered three ways; the negative (canon arg falling into the variance switch, e.g. `Arg3<int>` vs `IGen<__Canon>`) — **NOT covered**; (4) :552 — covered both ways.

**HandleCallAction**: `MakeGenericTypeSite` (:776-794) end-to-end covered by `TestMakeGenericConstrainedDataflow` (`Dataflow.cs:702-720`) — a faithful minimal #126604 repro. `MakeGenericMethodSite` (:760-774) — **no smoke test, no unit test, and no `NormalizeInstantiation` call**; the denormalized-shape half is asymmetric with the type site and completely unverified.

**NonCanon stubs/ILVerification**: constant-`false` stubs make compiled behavior line-for-line identical to pre-PR (verified by reading the diff); no new ILVerification test, acceptable given structural equivalence.

**System.Private.TypeLoader**: now compiles Canon into the runtime type loader — runtime `CanCastTo` (e.g. GVM variant dispatch, `TypeLoaderEnvironment.GVMResolution.cs:236`) gains canonical wildcard semantics with **zero direct tests**. [Inference] presumably intentional, but nothing pins it.

### Recommended tests (priority order)
- **G1 (7/10) `MakeGenericMethod` end-to-end smoke test** — mirror `TestMakeGenericConstrainedDataflow` with a generic method (`typeof(Gen).GetMethod("M").MakeGenericMethod(typeof(T), typeof(U), typeof(object))`). Catches #126604 recurring on the one path that did *not* get `NormalizeInstantiation` (`HandleCallAction.cs:769` vs `:787-788`).
- **G2 (6/10) `IsCanonicalCastTarget` positives** — `SimpleGenericConstraint<string[], __Canon[]>` → True (routes `CanCastArrayTo` → `CanCastParamTo` → the :40-41 branch); `<string[], __UniversalCanon[]>` → True; `<int[], __Canon[]>` → False. Makes the guard at `CastingHelper.cs:176-179` visible to the suite for the first time.
- **G3 (6/10) canon on the param side** (branches C/D) — `NonVariantInterfaceConstraint<NonVariantGenImpl<__Canon>, string>` → True, plus `__UniversalCanon` analog and a value-type negative. Realistic shape: ILC instantiates over the calling method's canonical parameters.
- **G4 (5/10) rank/category negatives** — `string[,]` vs `__Canon` rank-2 → True, vs rank-3 → False; `string[]` vs `__Canon[,]` → False. Guards the Rank check against silent over-acceptance.
- **G5 (5/10) variance-path negative** — `ComplexGenericConstraint3<Arg3<int>, __Canon>` → False (walks the variance switch with a canon target arg — currently never walked).
- Nice-to-have (3-4): :426 self-equivalence positive; method-level `MethodDesc.CheckConstraints` canon test (`TypeSystemConstraintsHelpers.cs:208-226` has zero canon coverage); mixed-position `IsCanonEquivalent` (`Pair<int, string>` vs `Pair<int, __Canon>`); `__UniversalCanon` vs `__Canon` cross-match.

### Test quality issues
- Comment inaccuracies: `ConstraintsValidationTest.cs:430` ("invariant arg position" of a contravariant interface); :454-463 (block titled "__Canon[] as type arg" never constructs `__Canon[]`; its single assert re-exercises the already-covered wildcard-param branch — the real parameterized coverage is :520-531).
- Assertions that don't exercise new code: :374-375 and :393-394 (fine as pins, not coverage).
- One monolithic ~30-assert `[Fact]` — consistent with the file's convention (`TestTypeConstraints` has ~60), but assertion messages would be a cheap improvement.
- Not brittle: all assertions go through the public `CheckConstraints`/`CanCastTo` contract; the tests survive refactoring of the private helpers.

### Positives
Negative assertions accompany most blocks (guarding the over-acceptance risk); the :506-507 ordering guard; faithful minimal smoke repro; constant-false stubs prove ILVerification unchanged by construction.

---

## 💬 Agent 4: comment-analyzer

### Critical

**C1. Test comment "invariant arg position" contradicts the contravariant interface it cites — inaccurate**
`ConstraintsValidationTest.cs:430`. The block says both "(IGen\<in T\> is contravariant)" (line 426, correct — `GenericConstraints.cs:8`) and "__Canon matches object (ref type) in invariant arg position of IGen" (wrong). Actual mechanism: `CanCastByVarianceToInterfaceOrDelegate` hits `IsCanonicalTypeArgMatch(arg, targetArg)` at `CastingHelper.cs:477` *before* the variance switch — the canon match succeeds without consulting variance at all. Suggested: "__Canon matches object (ref type); the canon-arg check applies before variance is considered."

**C2. Test comment "U=int[] stays" is false under canonicalization; block heading describes a scenario the block doesn't test**
`ConstraintsValidationTest.cs:454-458`. "Canonicalized: T becomes __Canon (ref type), U=int[] stays" — arrays canonicalize to `__Canon` (`StandardCanonicalizationAlgorithm.cs:117-120`: `else if (typeToConvert.IsArray) return context.CanonType;`), so canonicalizing yields `<__Canon, __Canon>`, not `<__Canon, int[]>`. The tested shape is a *denormalized* shape, not the result of canonicalization. The heading "Parameterized canonical types (e.g., __Canon[] as type arg in constraint)" (line 454) doesn't match the block — no `__Canon[]` appears in it (that scenario is lines 520-528). Only the final line ("__Canon is wildcard → true") is accurate.

### Improvement opportunities

**I1. `IsCanonicalCastTarget` XML doc — misleading third sentence** (`CastingHelper.Canon.cs:8-12`). "Pointers, byrefs, and function pointers are not valid instantiation arguments" is a true type-system fact enforced *elsewhere* (`CompilerTypeSystemContext.Validation.cs:354-361`) but this method doesn't check it: the `__Canon` branch excludes them only implicitly via `IsGCPointer` (`TypeDesc.cs:430-440`), and the `__UniversalCanon` branch (:17-18) *accepts* them — `CanCastToInternal(int*, __UniversalCanon)` returns true since the check runs before pointer/byref handling (`CastingHelper.cs:176`). Side observation: `CheckValidInstantiationArguments` (`TypeSystemConstraintsHelpers.cs:178`) checks `IsPointer || IsByRef || IsGenericParameter || IsVoid` but not `IsFunctionPointer` — enforcement isn't uniform across validators. Reword as rationale + pointer to the enforcer.

**I2. `IsCanonicalTypeArgMatch` XML doc — incomplete: the `CanonicalFormKind.Any` clause is load-bearing and undocumented** (`CastingHelper.Canon.cs:26-29` doc; :37-38, :43-44 code). Verified: `CanonType` is category Class (`CanonTypes.cs:120`, IsGCPointer true — half the clause redundant); `UniversalCanonType` is category ValueType (`CanonTypes.cs:206`, IsGCPointer *false*). For the pair (`__UniversalCanon`, `__Canon`) the early-return order means that without the `Any` clause the Specific branch would return false before the Universal check for `type` runs — silently breaking the documented "__UniversalCanon matches any type" symmetry. Exactly the kind of subtlety a future maintainer would "simplify" away; deserves an inline note. Minor: "non-leaf types" is vague; the `Arg2` example is a test-assembly type name used in product code comments (rot risk).

**I3. `IsCanonEquivalent` XML doc — incomplete/mildly misleading about non-generic types** (`CastingHelper.Canon.cs:66-69`, :78-79). The doc implies same-definition non-generic pairs are equivalent, but `Length == 0 → return false` always. Intentional — all three call sites (`CastingHelper.cs:426, 433, 552`) pair it with `IsEquivalentTo` — but that contract is undocumented, and the name strengthens the wrong reading. Add: "Returns false for non-generic types — plain equality is the caller's responsibility."

**I4. `CanCastToConstraintWithCanon` XML doc — incomplete: false-return semantics and call-site reality** (`TypeSystemConstraintsHelpers.Canon.cs:22-27`). "…when the param or constraint IS a canonical definition type" reads as a precondition, but the call site (`TypeSystemConstraintsHelpers.cs:68`) calls it **unconditionally**. More important: for a "CanCastTo…"-named method, `false` does *not* mean the cast fails — it means "no wildcard rule applies; caller falls back to the regular check" (lines 71-77). Undocumented. The "structural matching is in CastingHelper" sentence is accurate (verified: nested constraints like `INonVariantGen<__Canon>` fall through to `CanCastTo` → the new hooks). The inline "any concrete type substituted at runtime will be validated then" (:33-34) is a runtime-behavior claim — [Unverified] from this diff alone; consistent with the smoke test but stated as fact without a pointer. The "where T : U with U=__Canon" inline (:38-39) is accurate (verified against test :491-507).

**I5. `IsSpecialTypeMeetingConstraint` — no doc comment on a non-obvious asymmetry** (`TypeSystemConstraintsHelpers.Canon.cs:10-20`). Zero comments on why `__Canon` satisfies `class`/`new()` but not `struct` while `__UniversalCanon` satisfies all three. The neighboring `CheckGenericSpecialConstraint` has an explanatory comment; this deserves one line.

**I6. Test comment wording — minor.** :439 "constraint has canonical subtype" — it's a nested type *argument*, and "subtype" collides with the term of art `IsCanonicalSubtype` (ambiguous between two readings). :440 "Arg2\<string\> canonicalizes to Arg2\<__Canon\>" — true as intuition, but the actual mechanism is `IsCanonEquivalent` structural matching; "is canon-compatible with" would be precise.

**I7. Uncommented non-obvious insertions in CastingHelper.cs.** :477-478 — the canon short-circuit inside the variance loop makes a canon match satisfy *any* variance position; the most behaviorally significant insertion in the PR, no comment. :176-179 — `IsCanonicalCastTarget` checked before the category switch (i.e., before pointer/byref/fnptr rejection) — the ordering is what makes `__UniversalCanon` accept those categories; no comment.

### Missing documentation
**The Canon/NonCanon partial-class linking scheme is entirely undocumented.** The stubs are bare `=> false` with no explanation that each consuming project must compile exactly one counterpart (verified wiring: ILVerification → NonCanon, `ILVerification.projitems:36-38, 336-338`; ILCompiler.TypeSystem → Canon; System.Private.TypeLoader → `CastingHelper.Canon.cs` only). These are the only two `.NonCanon.cs` files in the tree — no precedent to pattern-match against. The codebase's existing idiom is different (`static partial void IsEquivalentTo`, `CastingHelper.cs:168` — calls vanish when unimplemented), which doesn't work for bool-returning methods — presumably *why* stubs were chosen; worth one comment per NonCanon file. Self-enforcing at compile time, so a discoverability problem, not correctness.

**Adjacent rot risk:** `MakeGenericMethodSite.InstantiateDependencies` (`HandleCallAction.cs:769`) doesn't normalize while its sibling (:788) now does, with a comment explaining only the type case — nothing records whether method sites are exempt by design.

### Recommended removals
None — no comment merely restates code. (Passing nits: unused `using System.Diagnostics;` at `TypeSystemConstraintsHelpers.NonCanon.cs:4`; 8-space indentation at `ILVerification.projitems:336-338`.)

### Positive findings
- `HandleCallAction.cs:787` — "InstantiateSignature could end up with a denormalized shape…" is **accurate**, matches `NormalizeInstantiation` exactly (`TypeExtensions.cs:674-684`), and downstream code demonstrably expects normalized shapes (`ILScanner.cs:771-785`). A model "why" comment.
- Test comment blocks otherwise verified fully accurate against `CoreTestAssembly/GenericConstraints.cs` (invariant-interface block :408-423; `Arg3<object> : IGen<object>` :427; `MultipleConstraints`/`ClassArgWithDefaultCtor` :465-468; canon-as-constraint :491-507; nested `__UniversalCanon` :510-512; `__Canon[]` invariant-position block :520-528 — traced through the `ParameterizedType` recursion end to end).
- The two `IsCanonicalTypeArgMatch` inline comments (:46-47, :51-52) accurately describe their code paths.

---

## 🏗️ Agent 5: type-design-analyzer

### Verified consumer matrix
Same three-project matrix as code-reviewer (ILCompiler.TypeSystem → Canon/Canon; System.Private.TypeLoader → Canon, no constraints helper; ILVerification → NonCanon/NonCanon). Ten further projects consume `ILCompiler.TypeSystem` as an assembly reference and never face the choice. The two `.NonCanon.cs` files are first-of-their-kind in the tree.

### 1. The partial-class file-splitting pattern
The base files call three/two methods they never declare; definitions come from whichever variant the project compiles (ordinary private static members, not C# `partial` methods). Failure modes [Inference — reasoned from C# rules, not compiled]: neither variant → CS0103-class error at the call site (loud, but the fix isn't discoverable from the error); both → duplicate-member error. **The "exactly one" invariant is compile-enforced in both directions, but it's an emergent property of name resolution, expressed nowhere** — no declaration in the base file, no header comment in any variant file, no README. Second undocumented layer: the Canon variant transitively requires the Canon file family (`CanonicalFormKind` in `CanonTypes.cs:20`, `IsCanonicalDefinitionType` in `TypeSystemContext.Canon.cs:49`) — for ILVerification the NonCanon choice is forced by compilation, invisible until you hit the errors.

Compared against in-tree precedent:
1. **Canon partial-file family** (24 files in `Canon/`) — the established idiom adds members, some abstract (`TypeDesc.Canon.cs:72`; `TypeSystemContext.Canon.cs:93-94`), and Common code never calls them. This PR is the first time *Common* code calls into canon-conditional members — which is why the NonCanon stub family had to be invented. Coherent extension of the strongest precedent.
2. **Classic partial-method hook in this very class** — `CastingHelper.cs:168` `static partial void IsEquivalentTo(..., ref bool)`, implemented only in `CastingHelper.TypeEquivalence.cs` (ILCompiler.TypeSystem only); calls elide when absent. The PR could have used this shape and avoided touching `ILVerification.projitems`; declining it for natural bool signatures is defensible, but the same class now embodies two different optional-behavior idioms.
3. **`#if` defines** — precedent exists at project level, but `#if SUPPORTS_CANON` would have a *worse* failure mode: a consumer forgetting the define silently compiles the non-canon path. The file-splitting choice fails loudly — its best property.
4. **Virtual on `TypeSystemContext`** — not viable without breaking layering (hook bodies need `CanonicalFormKind`, which doesn't exist in ILVerification's build), converts a per-distribution capability into per-instance dispatch on hot paths, and would force the helpers public; today they're `private` — strictly better encapsulation.
5. **Extended partial methods (C# 9) — the missed improvement.** `Directory.Build.props:278` sets `LangVersion=preview`, so `private static partial bool IsCanonicalCastTarget(TypeDesc, TypeDesc);` in the base file was available: same csproj wiring, both compile-error properties, but the contract becomes *declared* and a missing variant produces a self-explanatory CS8795 at the declaration. [Inference] A strict upgrade at near-zero cost — the single most consequential improvement available.

### 2. Static helper class design
Consistent with existing design (the class already mixes public extension entry points with private static helpers). `IsCanonicalCastTarget` should *not* move to `TypeSystemContext`: the context owns canonical *identity*; these methods encode canonical *cast/match semantics*, which belong with the casting lattice (`StandardCanonicalizationAlgorithm.cs` sets the precedent for keeping algorithmic canon logic off the context). DRY concern: the kernel rule "__Canon = any ref type; __UniversalCanon = any type" is re-encoded as an if-pair four times (`CastingHelper.Canon.cs:17-21`, twice in :34-44, `TypeSystemConstraintsHelpers.Canon.cs:34-40`).

### 3. Invariant expression
- `IsCanonEquivalent` (:70-91) — arity precondition self-protected by the `HasSameTypeDefinition` guard; but the sibling `CanCastByVarianceToInterfaceOrDelegate` asserts exactly this (`CastingHelper.cs:467-468`) — matching that with a `Debug.Assert` would document it. The `Length == 0 → false` behavior means the pairing-with-`IsEquivalentTo` invariant lives purely in call-site convention while name and doc read otherwise.
- `IsCanonicalTypeArgMatch` (:30-64) — "Match" correctly signals symmetric semantics; good naming; doc under-describes (also handles neither-canonical via recursion, :46-61).
- `IsCanonicalCastTarget` (:8-24) — doc/code mismatch on the pointer sentence (Universal branch returns true unconditionally); the invariant exists only as an ambiguous comment.
- `IsSpecialTypeMeetingConstraint` (`TypeSystemConstraintsHelpers.Canon.cs:10-21`) — "exactly one of three flags" precondition enforced at runtime by `UnreachableException` (stronger than the file's existing `Debug.Assert(false)` style at `TypeSystemConstraintsHelpers.cs:125`); wrinkle: the NonCanon stub returns `false` for the same invalid inputs the Canon variant throws on — the two implementations of one logical contract disagree about precondition violations (theoretical today; call sites pass literal single flags at :33, :42, :51).
- `HandleCallAction.cs:786-788` — the normalize call restores a convention-maintained invariant (each call site must remember; `NormalizeInstantiation` at `TypeExtensions.cs:678`) — a pre-existing weakness the PR conforms to.

**Overall: invariants encoded ~20% in structure, ~50% in comments, ~30% in unstated call-site convention.**

### 4. Test types (`CoreTestAssembly/GenericConstraints.cs:72-76`)
`INonVariantGen<T>` — good (name matches production vocabulary, `CanCastToNonVariantInterface`); `NonVariantInterfaceConstraint<T,U>` — exactly parallels `ComplexGenericConstraint3` and the file's naming convention; `NonVariantGenImpl<T>` — mild divergence from the positional `ArgN` implementer convention (`Arg3<T> : IGen<T>`, line 14) in favor of a clearer name — defensible.

### 5. Ratings

**CastingHelper / TypeSystemConstraintsHelpers (partial-class Canon/NonCanon contract):**
- **Encapsulation: 8/10** — all hooks private; canonical awareness invisible to callers; zero added public surface. Docked for the invisible companion-file contract and undocumented transitive Canon-family dependency.
- **Invariant Expression: 5/10** — the central "exactly one variant" invariant is declared nowhere; one doc contradicted by code (`IsCanonicalCastTarget`), one under-describing, one over-promising (`IsCanonEquivalent`).
- **Invariant Usefulness: 9/10** — exactly the right invariant for the domain (ILVerification must never special-case `__Canon`; ILC/TypeLoader must); loud failure over silent default is the design's most valuable property.
- **Invariant Enforcement: 8/10** — both violation modes are hard compile errors [Inference — standard C# rules, not compiled here]; docked because enforcement is emergent rather than declared, the arity assert is missing, and the two variants disagree on invalid-input behavior.

Recommended improvements: (1) declare the hooks as C# 9 extended partial methods; (2) two-line header comment in all four variant files; (3) `Debug.Assert(thisInst.Length == otherInst.Length)` in `IsCanonEquivalent`; (4) reword the pointer/byref doc sentence; (5) optionally centralize the canon kernel predicate; drop the unused using.

**Test fixtures (`INonVariantGen<T>`, `NonVariantGenImpl<T>`, `NonVariantInterfaceConstraint<T,U>`):** Encapsulation 7/10, Invariant Expression 8/10, Usefulness 8/10, Enforcement 8/10 — variance and constraint shape fully encoded in declarations; only nit is the `ArgN` naming divergence.

---

# 📋 Consolidated Summary

## Critical (1)
- **[code-reviewer + silent-failure-hunter, independently converged]** New canon-wildcard `CanCastTo` positives violate `compareTypesForCast`'s documented "positive results are exact" contract — `IFoo<__Canon> → IFoo<string>` now yields `Must` instead of the documented `May`, licensing the JIT to elide required cast checks in shared generic code (`CorInfoImpl.cs:2946-2979`; root cause `CastingHelper.Canon.cs` via `CastingHelper.cs:426,433,477,552`). [Inference — verified by code trace, not an executed repro.] Both agents independently recommend the same fix: scope the wildcard semantics to constraint checking via a separate entry point, or downgrade canon-involved positives to `May`.

## Important (4)
- **[both]** Devirtualization/virtual-method-resolution guards silently absorb the new semantics unaudited (`DevirtualizationManager.cs:97,133`; `MetadataVirtualMethodAlgorithm.cs:783,878,907`; also `TypeExtensions.cs:244,254`, `MethodDesc.cs:257`) [Inference/Unverified as to observable bugs].
- **[silent-failure-hunter]** Function-pointer canon shapes fall through `IsCanonicalTypeArgMatch` to `false` — #126604's bug class survives for that corner (`CastingHelper.Canon.cs:30-64`).
- **[3 agents]** `MakeGenericMethodSite` asymmetry: no `NormalizeInstantiation`, no smoke/unit test for the method path (`HandleCallAction.cs:760-774`). The agents *disagree on severity*: code-reviewer verified the omission is functionally consistent (rescued by `GetCanonMethodTarget` at `RootingHelpers.cs:189`) but flags the test gap; silent-failure-hunter and pr-test-analyzer flag the divergent validation regimes and total lack of coverage. Converged recommendation: add a `MakeGenericMethod` smoke test + explanatory comment.
- **[pr-test-analyzer]** `IsCanonicalCastTarget`'s positive branches never execute in any test — deleting the hook at `CastingHelper.cs:176-179` leaves the suite green; canon-on-param-side branches (C/D) and the array Rank check are similarly unguarded.

## Suggestions
- Doc fixes: `IsCanonicalCastTarget` pointer sentence (doc/code mismatch, flagged by 3 agents); load-bearing `CanonicalFormKind.Any` clause; `IsCanonEquivalent` non-generic-false contract; `CanCastToConstraintWithCanon` false-return semantics; comment on the variance short-circuit at `CastingHelper.cs:477-478`.
- Two factually wrong test comments: `ConstraintsValidationTest.cs:430` ("invariant" vs contravariant, flagged by 3 agents) and :454-458 ("U=int[] stays" contradicts `StandardCanonicalizationAlgorithm.cs:117-120`).
- Document the first-of-its-kind Canon/NonCanon linking scheme — ideally as C# 9 extended partial method declarations (contract becomes declared; missing variant → self-explanatory CS8795).
- Nits: unused using (`TypeSystemConstraintsHelpers.NonCanon.cs:4`), projitems indentation (:379), Canon-file placement in the `Common\` csproj block.

## Strengths (cross-agent consensus)
- Core wildcard semantics are correct and carefully asymmetric (`__Canon` = ref types only; `__UniversalCanon` = anything); the `UnreachableException` arm is genuinely unreachable and fails faster than the file's pre-existing pattern.
- Partial-class wiring is complete and correct across all three consuming projects, and cannot fail silently (compile errors both ways); ILVerification is provably unchanged by construction.
- Well-designed conservative failure direction ("wildcard now, runtime re-validates"), a faithful minimal end-to-end #126604 repro, and strong positive+negative unit assertions on the constraint entry path — including a subtle check-ordering regression guard.
- The `NormalizeInstantiation` comment is a model "why" comment, verified accurate against implementation and downstream asserts.

**Bottom line:** the constraint-checking fix itself is well-built and well-tested for its intended consumer. The dominant cross-agent theme is that it was implemented by widening a *global* predicate (`CanCastTo`) whose other consumers — JIT cast elision, devirtualization, runtime GVM dispatch — assume exact positive answers and were neither touched nor tested. That's where any follow-up scrutiny should go first. (Caveat from the agents: this tree is pinned at the merge commit; follow-up commits, if any, are not visible here.)
