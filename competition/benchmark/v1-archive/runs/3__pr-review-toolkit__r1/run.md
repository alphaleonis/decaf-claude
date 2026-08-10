# Benchmark run: 3__pr-review-toolkit__r1

| field | value |
|---|---|
| tool | pr-review-toolkit |
| subject | 3 (csharp / large) — dotnet/runtime#127146 |
| review diff | `7bba2205c2a75e4364dc32dc79cc91fae13791af^1..7bba2205c2a75e4364dc32dc79cc91fae13791af` (merge 7bba2205c2a75e4364dc32dc79cc91fae13791af) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 1143 |
| longest single subagent (s) | 864 |
| duration_ms (orchestrator self) | 207697 |
| duration_api_ms (summed parallel API time, not wall) | 3424980 |
| num_turns | 1 |
| cost_usd | 14.709220250000005 |
| input_tokens | 2 |
| output_tokens | 20860 |
| cache_creation_tokens | 10419 |
| cache_read_tokens | 105318 |
| total_tokens (orchestrator only) | 136599 |
| **subagents** | 5 |
| **ws output_tokens** | 50023 |
| ws input_tokens | 212 |
| ws cache_creation | 641358 |
| ws cache_read | 7487648 |
| ws total_tokens | 8179241 |
| session_id | ea0c6e31-b95b-4ecd-bfe3-c107e55ae5a2 |
| findings (raw lines) | 297 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (1143s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a2c32fa6c7bf3962f | 198 | 1242391 | 534 |
| agent-a2f7eac49dfaae04e | 12139 | 980005 | 396 |
| agent-a364aece58ee3039e | 1204 | 2619634 | 864 |
| agent-a620053a003369dbf | 4658 | 1659604 | 720 |
| agent-a70b37b140f1777bf | 39 | 861194 | 564 |

## Findings (final result text)

```
All five agents have completed. Nothing was posted to GitHub — everything below is local output only.

**Note on verification status:** each agent traced its claims against the post-merge checkout (commit `7bba2205`); claims about *downstream runtime/JIT behavior* were not executed and are labeled **[Inference]** where the agents marked them so. Two agents independently converged on the same top finding (#1 below), which raises confidence but is still static analysis, not a reproduced miscompile.

---

# PR #127146 — "Handle canonical types in casting logic" (dotnet/runtime, merged)

13 files, +417/−7. Teaches ILC's type-system `CanCastTo`/constraint-validation logic about `__Canon`/`__UniversalCanon` via Canon/NonCanon partial-class files selected per project, adds `NormalizeInstantiation()` in dataflow's `MakeGenericTypeSite`, plus unit tests and a smoke test. Fixes #126604.

---

## 1. code-reviewer — complete findings

### Critical

**1.1 `compareTypesForCast` can now return `Must` for casts that may fail at runtime** (confidence 85)
`src/coreclr/tools/Common/JitInterface/CorInfoImpl.cs:2939-2979` (unmodified by the PR, but its assumptions are broken by it)

The PR changes `CanCastTo` semantics for every project compiling the Canon partials — including `ILCompiler.TypeSystem.csproj`, consumed by both the NativeAOT compiler and crossgen2 (`ILCompiler.ReadyToRun.csproj:26`). The JIT-EE bridge `compareTypesForCast` has a branch for "fromType is a canonical subtype, toType is a non-canonical interface" that passes positive `CanCastTo` results back as `TypeCompareState.Must` unconditionally (lines 2946-2953), justified by the comment: *"Pass back positive results unfiltered. The unknown type parameters in fromClass did not come into play. … `IFoo<__Canon> -> IFoo<string>  May`"*.

That invariant no longer holds. Trace: `IFoo<__Canon>.CanCastTo(IFoo<string>)` → `CanCastToNonVariantInterface` (`CastingHelper.cs:426`) → `IsCanonEquivalent(IFoo<__Canon>, IFoo<string>)` → arg pair `(__Canon, string)` → `IsCanonicalTypeArgMatch` (`CastingHelper.Canon.cs:63-64`: `__Canon`/Specific → `string.IsGCPointer` = true) → **true**. Same for `Foo<__Canon> → IFoo<string>` via `RuntimeInterfaces`, and for variant interfaces via the new short-circuit at `CastingHelper.cs:477-478`. So the exact pair the comment documents as `May` now produces `Must`. `Must` tells RyuJIT the cast always succeeds, allowing it to delete `castclass`/`isinst` checks — but the object behind a `Foo<__Canon>` handle can be `Foo<object>`, which is not an `IFoo<string>`. That is a type-safety hole in shared generic code, for both NativeAOT and R2R images; the `#if READYTORUN` block at 2983-2992 converts `MustNot`→`May` but deliberately trusts `Must`. (CoreCLR's VM-side equivalent stays sound only because the VM's `TypeHandle::CanCastTo` still treats `__Canon` as an ordinary class.)

*Fix suggestion:* don't trust positives in the canonical-fromType branch that could have relied on canonical wildcard matching (re-check with a non-canonical-aware comparison, or return `May` when `fromType.IsCanonicalSubtype(CanonicalFormKind.Any)`), or scope the wildcard behavior to the constraint-validation entry point instead of the shared `CanCastTo`.

### Minor

**1.2 Inconsistent indentation in `ILVerification.projitems:379`** (confidence 95) — the new `<Link>` for `TypeSystemConstraintsHelpers.NonCanon.cs` is indented 8 spaces; every other `<Link>` in the file (including the sibling added at line 40) uses 6.

**1.3 Unused `using System.Diagnostics;`** (confidence 90) — `src/coreclr/tools/Common/TypeSystem/Common/TypeSystemConstraintsHelpers.NonCanon.cs:4`; the file's two methods are constant `=> false` bodies. The Canon counterpart needs it (`UnreachableException`), the stub does not.

### Observations (below reporting threshold)

- **System.Private.TypeLoader now gets wildcard semantics at runtime.** It had to pick a partial and got Canon (`System.Private.TypeLoader.csproj:120`) — a behavior *change* rather than status quo (NonCanon would preserve behavior). Its only `CanCastTo` consumer is GVM resolution (`TypeLoaderEnvironment.GVMResolution.cs:236`), where types come from concrete runtime handles, so the new paths appear latent — but any future canonical-template use of `CanCastTo` in the TypeLoader silently inherits wildcard matching. [Inference — author intent unverified.]
- **DevirtualizationManager call sites** (`src/coreclr/tools/Common/Compiler/DevirtualizationManager.cs:97, 133`) inherit the new semantics; traced reachable outcomes appear to fail safe, but these sites were not adjusted or tested by the PR.
- **`MergeTypesToCommonParent`/`isMoreSpecificType`** (`src/coreclr/tools/Common/Compiler/TypeExtensions.cs:244, 254`; `CorInfoImpl.cs:3010`) can now claim a canonical type "is a" concrete interface; no concrete miscompile constructed, but the same audit as 1.1 should cover them.

### Verified non-issues

1. **Project wiring is complete and correct.** Exactly three project files compile the shared files: `ILCompiler.TypeSystem.csproj` → Canon for both (lines 104, 134); `ILVerification.projitems` → NonCanon for both (lines 39, 378); `System.Private.TypeLoader.csproj` → `CastingHelper.Canon.cs` (line 120) and does **not** compile `TypeSystemConstraintsHelpers.cs` at all, so no constraint partial needed. TypeLoader already compiles `CanonTypes.cs` and `TypeSystemContext.Canon.cs`, so `IsCanonicalDefinitionType` is available.
2. **`IsCanonEquivalent` indexing `otherInst[i]` without a length check is safe** (`CastingHelper.Canon.cs:70-91`) — `HasSameTypeDefinition` (`TypeDesc.cs:631-634`) compares `GetTypeDefinition()` identity; same definition implies equal generic arity, and the `Length == 0` guard handles non-generic/array cases.
3. **ILVerification keeps exactly the old behavior** — the NonCanon stubs are constant `false`, making all five new hooks dead there; the verifier's soundness is untouched. The unsoundness concern is real only via the JIT interface (1.1).
4. **`NormalizeInstantiation` placement in `HandleCallAction.cs:788` is correct.** `ReflectedTypeNode` asserts normalized types (`ReflectedTypeNode.cs:28-29`), so normalization must precede rooting. Normalizing before `CheckConstraints` only widens — it can over-root but never under-root; runtime `MakeGenericType` still validates the real instantiation. The seemingly asymmetric `MakeGenericMethodSite` (line 769, no normalization) is fine: `RootingHelpers.TryGetDependenciesForReflectedMethod` normalizes at the end via `GetCanonMethodTarget(CanonicalFormKind.Specific)` (`RootingHelpers.cs:188`).
5. **Constraint-checker ordering is right.** `CanCastToConstraintWithCanon` runs before the value-type/Nullable early-out (`TypeSystemConstraintsHelpers.cs:68-74`) — necessary because `__UniversalCanon` has `TypeFlags.ValueType` (`CanonTypes.cs:206`) and would otherwise be rejected. `IsSpecialTypeMeetingConstraint` correctly rejects `__Canon` for `struct` (Universal only) while accepting it for `class`/`new()`.

### Strengths

- Clean partial-class seam: verification-sensitive consumers opt out at zero cost; a future project compiling `CastingHelper.cs` without picking a partial fails to build rather than silently choosing.
- Wildcard semantics faithful to CLR canonical-form rules (`__Canon` = GC pointers only, `__UniversalCanon` = anything, value types never match `__Canon`, including nested/array positions; recursive match handles rank and category mismatches).
- Thorough `TestCanonicalTypeConstraints` coverage plus an end-to-end smoke test reproducing the denormalized-shape scenario from #126604.

---

## 2. silent-failure-hunter — complete findings

**Finding 1 — CRITICAL: `CanCastTo` contract silently weakened; JIT cast folding can report "Must" for casts only *possibly* valid**
`CastingHelper.cs:176, 426, 433, 477, 552` (new hooks) + `CorInfoImpl.cs:2915-2994` (`compareTypesForCast`).
Before the PR, `CanCastTo == true` meant "castable for **all** runtime substitutions of `__Canon`"; now it means "castable for **some** substitution". No consumer was audited or updated. `CorInfoImpl.cs:2946-2952` passes `true` back as `TypeCompareState.Must` under a comment (2948-2949) whose invariant is now false; the comment block at 2964-2966 still documents `IFoo<__Canon> -> IFoo<string>  May` — the code now silently contradicts its own documentation. Silent-failure scenario [Inference — expected JIT behavior, not executed]: `Must` licenses RyuJIT to fold `isinst`/`castclass`; inside the shared body of `Foo<__Canon>`, `this is IFoo<string>` folds to always-true; executing as `Foo<object>` silently treats the object as `IFoo<string>` — no exception, no log, baked into the image. The READYTORUN block only sanitizes `MustNot`; a wrong `Must` flows through crossgen2 too.
Secondary consumer: `mergeClasses` (`CorInfoImpl.cs:3023`) → `MergeTypesToCommonParent` (`TypeExtensions.cs:227`, `CanCastTo` at 244/254) — a canon-"possible" cast (e.g., `__Canon[]` → `IList<string>` via `CastingHelper.cs:477`, bypassing variance entirely) can be reported as a definite common parent. [Inference on downstream effect.]
Proof the old contract was load-bearing: `TypeExtensions.cs:559-564` explicitly guards a `CanCastTo` call with *"no generic variables and __Canon used anywhere"* before trusting it.
*Recommendation:* (a) keep `CanCastTo` exact and expose wildcard semantics as a separate predicate (e.g., `CanCastToCanonically`) called only by constraint checking, or (b) audit every consumer and make `compareTypesForCast` return `May` when the positive came from canon matching. Currently the permissive semantics are reachable from all ~20 `CanCastTo` call sites in the compiler, silently.

**Finding 2 — HIGH: variant interface resolution and devirtualization now conflate `IFoo<__Canon>` with `IFoo<string>`**
`MetadataVirtualMethodAlgorithm.cs:783` (also 878, 907, 994, 1010, 1167 — static virtual resolution); `DevirtualizationManager.cs:97, 133`.
`iface.HasSameTypeDefinition(interfaceType) && iface.CanCastTo(interfaceType)` was a *variance* match (true for all substitutions); it now also fires for canon-equivalence (true for one substitution). Resolving `IFoo<string>.M` against `Foo<__Canon>` previously returned null (forcing runtime dispatch); it can now statically resolve. The `FAILED_CAST` bail-out at `DevirtualizationManager.cs:97` no longer triggers for these pairs. Scenario [Inference — plausible reachability, no constructed repro]: a devirtualized target or dispatch-map/static-virtual resolution correct only when `__Canon == string` gets baked into the image; other instantiations sharing the code silently dispatch wrong. No diagnostic anywhere in the chain.

**Finding 3 — MEDIUM: wiring correct today, but the Canon/NonCanon pairing is enforced by nothing, and the TypeLoader received a silent runtime semantics change**
Verified wiring (exhaustive grep): `ILCompiler.TypeSystem.csproj:131-135` Canon / `ILVerification.projitems:36-40` NonCanon / `System.Private.TypeLoader.csproj:117-121` Canon for `CastingHelper.cs`; `ILCompiler.TypeSystem.csproj:104, 353` Canon / `ILVerification.projitems:375-379` NonCanon for `TypeSystemConstraintsHelpers.cs`.
1. **No missing-partial gap** — TypeLoader doesn't compile `TypeSystemConstraintsHelpers.cs`; nativeaot runtime constraint checking lives in `System.Private.Reflection.Execution`'s `ConstraintValidator`. Omission fails loudly (CS0103 / duplicate-definition).
2. **Wrong-choice mistakes fail silently.** Nothing records which partial a consumer must take. Copying the NonCanon include into a canon-aware project silently resurrects #126604 with zero signal; the reverse makes an IL verifier silently accept canon casts. Recommend header comments in all four partial files + a debug assert in canon-aware contexts.
3. **TypeLoader choice is a silent runtime behavior change** — Canon chosen with no PR-visible justification; only `CanCastTo` site is GVM variant dispatch (`TypeLoaderEnvironment.GVMResolution.cs:236`), [Inference] concrete instantiations only today, so NonCanon would have preserved behavior exactly; deserved a comment.
4. **Silent semantic inheritance**: crossgen2, ILTrim, dotnet-pgo, R2RDump, r2rtest, ILCompiler.MetadataTransform, ILCompiler.Diagnostics all reference `ILCompiler.TypeSystem.csproj` (verified) and inherited the new permissive `CanCastTo` with no change in their own code. cDAC does not (verified).
5. Cosmetic: `ILVerification.projitems:379` 8-space vs 6-space indentation.

**Finding 4 — MEDIUM: `MakeGenericMethodSite` left without `NormalizeInstantiation()` — works today only via a non-obvious coincidence, undocumented**
`HandleCallAction.cs:760-774` vs the fixed `MakeGenericTypeSite` at 776-794. The method path runs `InstantiateSignature` → `CheckConstraints` → rooting with no normalization and no comment. Verified why it doesn't reproduce the type-side bug: `RootingHelpers.cs:189` roots `factory.ReflectedMethod(method.GetCanonMethodTarget(CanonicalFormKind.Specific))`, so the emitted node is canonical regardless (the type-side helper has no such canonicalization, which is why the type site needed the fix); and `CheckConstraints` on the denormalized method is *stricter*, not looser. Remaining exposure: the two paths constraint-check different shapes for the identical scenario and will diverge if `TryGetDependenciesForReflectedMethod` ever stops canonicalizing — nothing pins this; no `MakeGenericMethod` smoke-test twin exists. Adjacent pre-existing: `RootingHelpers.cs:178-186` swallows all `TypeSystemException` and returns false — silent skip, no diagnostic [Inference — no concrete trigger identified]. Also: when `CheckConstraints` fails at 770/790 the dependency list is silently empty — pre-existing design; a debug-level compiler log note would shorten the next #126604-style investigation.
*Recommendation:* add the `MakeGenericMethod` smoke-test twin, and either normalize for symmetry or comment at line 769 pointing at `RootingHelpers.cs:189`.

**Finding 5 — LOW (verified): the "runtime will validate" claim holds, with one ordering subtlety worth documenting**
`TypeSystemConstraintsHelpers.Canon.cs:29-46`. The wildcard `return true` is backed by real runtime validation: `ConstraintValidator.EnsureSatisfiesClassConstraints` at `ExecutionEnvironmentImplementation.MappingTables.cs:203` (MakeGenericType) and `ValidateGenericMethodConstraints` at :223 (MakeGenericMethod). Consequence of over-permissive compile-time true is bounded: extra rooted templates (binary size); invalid concrete substitutions rejected at runtime with proper `ArgumentException`. Subtlety: `MappingTables.cs:183` returns statically-present concrete instantiations *before* the constraint check — the chain still holds because concrete instantiations are compile-time-validated by `EnsureLoadableType` (`CompilerTypeSystemContext.Validation.cs:366`, which deliberately skips canonical subtypes). That two-piece invariant is documented nowhere near the wildcard — one sentence in the doc comment naming both validation points would protect it. Also silently inherited: crossgen2's `TypeValidationChecker.cs:634` and `UnsafeAccessors.cs:399, 411` [Inference — no behavior change expected, but unmentioned in the PR].

**Finding 6 — LOW: `IsSpecialTypeMeetingConstraint`'s `UnreachableException` — unreachability verified today; the stub pair diverges**
`TypeSystemConstraintsHelpers.Canon.cs:19` vs `TypeSystemConstraintsHelpers.NonCanon.cs:10-11`. Only call sites are `TypeSystemConstraintsHelpers.cs:33, 42, 51`, each passing exactly one handled literal flag — default arm unreachable today; throwing is the right (loud) choice and strictly better than the pre-existing `default: Debug.Assert(false); break;` in `CheckGenericSpecialConstraint` (`TypeSystemConstraintsHelpers.cs:124-127`), which silently continues in release builds. Divergence: a hypothetical fourth special constraint crashes ilc loudly but is silently "not met" in ILVerification — happens to be semantically correct there, but the differing strictness should be stated in a comment. Also: the switch matches exact values, not flag masks — fine for current callers; a `Debug.Assert(PopCount == 1)` would make the contract explicit.

**Finding 7 — LOW: catch-all `return false` paths — conservative, but with enumerable silently-unhandled shapes**
`CastingHelper.Canon.cs:63` (final `return false`), `:77-78` (length-0 early false). Since call sites only *add* `true` on top of old logic, a false degrades to the old broken-for-canon behavior — silently missed matches → constraint failure → unrooted dependencies → runtime missing-artifact failures of the #126604 flavor for the unhandled shape. Falling through silently:
- **Function pointer types** containing canon (`delegate*<__Canon>` as generic arg): `FunctionPointerType` is not `ParameterizedType`, no recursion — consistent with `CanCastToInternal`'s own fnptr `return false` (`CastingHelper.cs:198-199`), but undocumented in `IsCanonicalTypeArgMatch`'s doc comment.
- **COM type-equivalent args**: loop at `CastingHelper.Canon.cs:82-88` compares with `==`, not `IsEquivalentTo`; mixed canon+equivalence instantiations silently fail. Vanishingly rare; conservative direction.
- **Mismatched instantiation lengths**: guarded by `HasSameTypeDefinition` [Inference: same typedef ⇒ equal arity, loop can't go out of range]. If ever violated: `thisInst` longer → loud `IndexOutOfRangeException`; `thisInst` *shorter* → prefix-compare can return a **silently wrong `true`**. A one-line `Debug.Assert(thisInst.Length == otherInst.Length)` after line 74 closes the only silent branch.
- The length-0 early-out makes `IsCanonEquivalent` answer "not equivalent" for *identical* non-generic types; safe today (all callers pre-check equality), but the name promises semantics it doesn't deliver — worth a doc sentence.
- Semantic note: lines 39/44 let `__UniversalCanon` match `__Canon` and vice versa — over-permissive under the wildcard doctrine, feeding Finding 1's direction.

**Done well:** loud compile failures for wiring omissions; `UnreachableException` over the file's own pre-existing silent `Debug.Assert(false)` pattern; genuine negative test cases.

| # | Severity | Where | Silent failure |
|---|---|---|---|
| 1 | CRITICAL | `CorInfoImpl.cs:2946-2952` + new hooks | "some-substitution" true consumed as "all-substitutions" → JIT folds casts wrongly in shared code (ilc + crossgen2) |
| 2 | HIGH | `MetadataVirtualMethodAlgorithm.cs:783,1167`; `DevirtualizationManager.cs:97,133` | Variant/devirt resolution conflates `IFoo<__Canon>` with `IFoo<concrete>` [Inference on reachability] |
| 3 | MEDIUM | project wiring; `GVMResolution.cs:236` | Pairing unenforced/undocumented; TypeLoader semantics changed without justification |
| 4 | MEDIUM | `HandleCallAction.cs:769-771` | Method path unnormalized; safe via undocumented `RootingHelpers.cs:189` coincidence |
| 5 | LOW | `TypeSystemConstraintsHelpers.Canon.cs:35` | Runtime-validates claim verified; two-piece invariant undocumented |
| 6 | LOW | `…Canon.cs:19` / NonCanon:10 | Canon-throws vs NonCanon-silent-false divergence |
| 7 | LOW | `CastingHelper.Canon.cs:63,77-78` | Conservative catch-alls; missing length assert leaves one theoretical silent-true |

---

## 3. pr-test-analyzer — complete findings

Load-bearing type-system facts: `__Canon` is category `Class` → `IsGCPointer == true` (`CanonTypes.cs:120`); `__UniversalCanon` is category `ValueType` → `IsGCPointer == false` (`CanonTypes.cs:206`). All branch-reachability claims established by static tracing (tests not executed); "would fail without the fix" claims labeled [Inference].

**Summary:** `TestCanonicalTypeConstraints` (`ConstraintsValidationTest.cs:358-532`) covers the *constraint-checking* entry point well — all four `CanCastToConstraintWithCanon` branches, both `__Canon`-vs-ref/value polarities, nested canon, one array case. But all coverage funnels through `CheckConstraints()`; there are **zero direct `CanCastTo` tests with canonical types** (`CastingTests.cs` has no canon references). Because `CanCastToConstraintWithCanon` intercepts top-level canonical constraints before `CanCastTo` runs, the entire positive half of `IsCanonicalCastTarget` and the "canon on the left" branches of `IsCanonicalTypeArgMatch` are never executed by any test. Several assertions are vacuous — they pass with the PR reverted.

### Critical gaps

- **C1. `IsCanonicalCastTarget` never returns `true` in any test** (`CastingHelper.Canon.cs:17-21`; integration `CastingHelper.cs:176-179`). Both `return true` arms — `__UniversalCanon` wildcard and `__Canon`+`IsGCPointer` — are dark; inverting `IsGCPointer` or deleting the Universal arm passes the entire suite. Production reaches these via array-element casts, `CanCastConstraint` with generic-parameter args, and any `CanCastTo` with a canonical target. Suggested tests in `CastingTests.cs`: `string.CanCastTo(__Canon)` true, `int.CanCastTo(__Canon)` false, `int.CanCastTo(__UniversalCanon)` true, `string[].CanCastTo(__Canon[])` true, `int[].CanCastTo(__Canon[])` false.
- **C2. "Canon on the left" branches of `IsCanonicalTypeArgMatch` untested** (`CastingHelper.Canon.cs:40-44`). Every test puts the canonical type on the constraint side. Nothing exercises e.g. `CanCastTo(NonVariantGenImpl<__Canon>, INonVariantGen<object>)` — the exact "all we have are canonical types" shape from the PR description. Also untested: canon-vs-canon (`__UniversalCanon` arg vs `__Canon` constraint arg, the `Any` disjuncts at lines 38/44). Deleting lines 40-44 passes the suite.

### Important gaps

- **I1. Array rank/category checks have no negative test** (`CastingHelper.Canon.cs:53-58`). Only SzArray/SzArray rank-1 ref-element positive is covered (test:525-530). Untested: rank mismatch, category mismatch (`string[]` vs `__Canon[,]`), multidim positive, element-type negative (`int[]` vs `__Canon[]`). Note the category guard rejects SzArray↔MdArray-rank-1, *diverging* from `CanCastArrayTo` (`CastingHelper.cs:256-261`) — correct for invariant positions, but no test pins the intent.
- **I2. `CanCastToNonVariantInterface` first check untested** (`CastingHelper.cs:426`, `thisType` itself the interface). All tests route through the `RuntimeInterfaces` loop (line 433). `NonVariantInterfaceConstraint<INonVariantGen<string>, __Canon>` would cover it. Deleting the line-426 addition passes the suite.
- **I3. `CanCastToClass` base-chain: canon-equivalence only ever matches at the first iteration** (`CastingHelper.cs:550-556`). No test where a *base class* is the match (needs e.g. `class DerivedFromArg2 : Arg2<string>` checked against `Arg2<__Canon>`). Hoisting the check out of the loop would go undetected.
- **I4. Variance fallback with canon below the immediate arg** — all variance tests are satisfied by the shortcut at `CastingHelper.cs:477`; nothing forces the `Covariant`/`Contravariant` `IsBoxedAndCanCastTo` recursion (486/491) to handle a deeper canonical type (e.g., `Arg3<Arg2<string>>` vs `IGen<Arg2<__Canon>>`), nor array covariance with canon.
- **I5. `IsCanonEquivalent` multi-arg / equal-skip branch — the actual issue #126604 shape** (`CastingHelper.Canon.cs:83-84`) never executes: every canon-equivalence test uses arity-1 generics. #126604's repro is arity-2 with one equal + one canon-matched arg (`TestRequest : IRequest<TestRequest, string>` vs `IRequest<TestRequest, __Canon>`). Neither unit nor smoke test replicates it; an index-handling bug in the loop would pass. Suggested: arity-2 interface + self-referential constraint fixture.
- **I6. `MakeGenericMethod` dataflow path — no normalization, no smoke test** (`HandleCallAction.cs:766-773` vs 788). [Inference] latent if the denormalized-shape problem applies to methods; either way no smoke test covers `MakeGenericMethod` on a constrained generic method from a shared-generic body.

### Minor gaps

- `__UniversalCanon` inside parameterized types (`int[]` vs `__UniversalCanon[]` via `CastingHelper.Canon.cs:60→34`): untested.
- Pointer/byref vs `__Canon`: the doc comment (`CastingHelper.Canon.cs:11`) promises rejection; no test asserts the `IsGCPointer == false` outcome.
- `NotNullableValueTypeConstraint` + `__UniversalCanon` arm (`TypeSystemConstraintsHelpers.Canon.cs:18`) is [Inference] **dead code** — the caller guard `(!IsValueType || IsNullable)` (`TypeSystemConstraintsHelpers.cs:49`) is already false for UC (a value type), so the arm can't be covered as written. Remove or document.
- `int[].CanCastTo(__UniversalCanon[])` traces to `false` (integral-normalization path, `CastingHelper.cs:304-311`) while `IsCanonicalTypeArgMatch(int[], __UniversalCanon[])` is `true` — [Inference] possibly intended (castability vs canonical compatibility), but no test or comment pins the divergence.

### Q2 — Does `TestMakeGenericConstrainedDataflow` reproduce #126604?

**Partially — it reproduces the failure class and [Inference] would fail without the fix, but not the issue's exact shape.** Mechanism (`Dataflow.cs:702-720`): `Atom` is a struct so `Handle<Atom, Foo>` compiles as `Handle<Atom, __Canon>`; dataflow analyzes `MakeGenericType(typeof(T), typeof(U), typeof(object))` with `U=__Canon` — exactly "constraint check needed, only canonical types available". Pre-fix, both `new()` and `IFoo` checks fail for `__Canon` → dependencies never rooted → runtime `Activator.CreateInstance` throws `NotSupportedException` (the #126604 symptom) → test fails. Post-fix both pass via wildcard branches. The `typeof(object)` third arg deliberately produces the denormalized shape, exercising `NormalizeInstantiation` too ([Unverified] whether omitting only that line fails the test). **Fidelity gap:** in #126604 the failing param is the concrete struct and canon sits *inside* the instantiated constraint (arity-2, equal+canon args — see I5); the smoke test's failing param is `__Canon` itself, the simpler wildcard branch.

### Q3 — NonCanon stub behavior asserted?

**No test asserts it, but the risk is largely structural, not behavioral.** Stubs restore the exact pre-PR expressions; wiring errors are compile-enforced; the existing ILVerify suite implicitly locks old behavior. Residual: (a) nothing pins which flavor each project gets; (b) `System.Private.TypeLoader` newly includes `CastingHelper.Canon.cs` (runtime-side change) with no dedicated test. Rating: Minor.

### Q4 — Test quality issues

1. **Vacuous assertions** (pass with the PR reverted; verified by tracing pre-PR short-circuits): `ConstraintsValidationTest.cs:374-375` (`ReferenceTypeConstraint<__Canon>` passes via pre-existing `IsGCPointer` at `TypeSystemConstraintsHelpers.cs:31`); `:390-391` (UC is a value type → had a default ctor pre-PR); `:393-394` (caller guard already false pre-PR; combined with the dead arm, the header "__UniversalCanon satisfies all special constraints" attributes to new code what old code already did). Genuinely new assertions in those blocks: `:377-378, :381-382, :387-388`.
2. **Mis-describing comments:** `:454-458` claims "__Canon[] as type arg in constraint" but contains no `__Canon[]` — it duplicates the wildcard branch (`:400-405`); the described scenario is actually at `:520-531`. `:430` says "invariant arg position of IGen" — `IGen<in T>` is contravariant, and the match happens via the shortcut *before* variance is consulted.
3. **Duplication:** `:400-401, :404-405, :461-462, :484-488` all exercise the same wildcard branch — five assertions, one mechanism; `:432-434` and `:470-471` exercise the identical variance-shortcut path.

### Positive observations

- `CanCastToConstraintWithCanon`: all four branches covered with positive/negative pairing (`:491-508`) — best-covered piece of the PR.
- Tests exercise the public `CheckConstraints()` contract, not private helpers — refactor-resilient.
- Ref-vs-value distinctions carry matching negatives (`:419-422, :447-451, :498-500`).
- The new fixtures (`GenericConstraints.cs:72-76`) were exactly what was needed to separate the non-variant path from the contravariant `IGen`.
- The smoke test is a minimal, well-constructed model of shared generics; its `typeof(object)` arg deliberately covers normalization, not just constraints.

**Bottom line:** constraint-checking is well covered; the raw `CanCastTo` surface is essentially untested, and neither test reproduces the exact arity-2 shape of the original issue. C1/C2 are cheap to close with direct `CanCastTo` assertions plus one arity-2 fixture.

---

## 4. comment-analyzer — complete findings

### Critical issues

**4.1 Test comment mis-describes canonicalization; block header describes the wrong scenario — High**
`ConstraintsValidationTest.cs:454-458`. (a) `"U=int[] stays"` is factually wrong: under `CanonicalFormKind.Specific`, arrays canonicalize to `__Canon` (`StandardCanonicalizationAlgorithm.cs:117-119`); the canonical form of `ComplexGenericConstraint3<IGen<int[]>, int[]>` is `<__Canon, __Canon>`. The shape actually tested (`<__Canon, int[]>`) can only arise as a *denormalized* instantiation, never from canonicalization — a reader learns the wrong rule. (b) The header promises `__Canon[]` as a type arg, but the block contains no `__Canon[]` — that scenario is covered at lines 520-531. Suggested rewording provided. Nit: "IGen<int[]> implements IGen<int[]>" — "satisfies" would be correct.

**4.2 "invariant arg position" contradicts the contravariant declaration two lines earlier — Medium**
`ConstraintsValidationTest.cs:430` vs line 426 (`IGen<in T>` is contravariant, matching `GenericConstraints.cs:8`). What actually happens: `IsCanonicalTypeArgMatch(object, __Canon)` at `CastingHelper.cs:477` fires *before* the variance switch. [Inference] the author meant "matched without needing variance", but as written it mis-describes the declaration and contradicts the block's own line 426.

**4.3 Wrong rationale for array compatibility — Medium**
`ConstraintsValidationTest.cs:524`: `// string[] is a ref type, so string[] should be compatible with __Canon[]`. The code (`CastingHelper.Canon.cs:53-60`) recursively matches the *element* type. "string[] is a ref type" is true of every array — `int[]` too, yet `int[]` is *not* compatible with `__Canon[]`. The stated rationale, applied consistently, predicts the wrong outcome for value-element arrays.

### Improvement opportunities

**4.4 `CanCastToConstraintWithCanon` doc reads as a precondition, but the method is called unconditionally — Medium** (`TypeSystemConstraintsHelpers.Canon.cs:23-28` vs call site `TypeSystemConstraintsHelpers.cs:68`). The method self-guards and returns false when neither side is canonical; a future maintainer could read the "when" clause as a caller contract and add an assert/pre-filter. Suggested rewording: "Returns true only if the param or the constraint is a canonical definition type; returns false otherwise so the caller falls back to the full CanCastTo." (Second sentence verified accurate.)

**4.5 `IsCanonicalTypeArgMatch` summary omits half the method — Medium** (`CastingHelper.Canon.cs:26-29`). Summary covers only leaf wildcard semantics; lines 46-61 handle cases where *neither* argument is a canonical definition type (canon-equivalence + recursion). Add a sentence about structural matching.

**4.6 `IsCanonEquivalent` summary doesn't match the zero-arg behavior — Medium (drift risk)** (`CastingHelper.Canon.cs:66-69` vs 78-79). "Same type definition with all type arguments either equal or canon-compatible" implies `true` for non-generics; the code returns `false` for `Length == 0`. Safe today (callers pre-check equality), but the documented contract is wrong for the non-generic case. Add: "Returns false for non-generic types; callers are expected to check exact equality/equivalence first."

**4.7 "Pointers, byrefs, and function pointers are not valid instantiation arguments" corresponds to no code in the method — Low** (`CastingHelper.Canon.cs:11`). The claim is accurate (reflection rejects all three, `RuntimeType.cs:757`), but the method contains no such check — the sentence is an unstated justification for why `IsGCPointer` suffices. Note the type system's own `CheckValidInstantiationArguments` (`TypeSystemConstraintsHelpers.cs:178`) rejects pointers/byrefs but *not* function pointers, so the claim rests on the reflection layer. Suggested: connect rationale to check. Related nit: "__Canon accepts any reference type" is `IsGCPointer` in code, which excludes `class`-constrained generic parameters; those are handled upstream — [Inference] parenthetical worth adding only if new callers appear.

**4.8 Missing comments on non-obvious new logic — Low–Medium**
- `CastingHelper.cs:176-179`: the early return's placement is load-bearing (must precede the category switch — e.g., pointer/byref/fnptr `thisType` would return false before a `__UniversalCanon` target could match) and uncommented; nothing hints the helpers compile as no-op stubs in canon-less consumers (the NonCanon stubs are entirely uncommented).
- `CastingHelper.Canon.cs:38,44`: the `|| IsCanonicalDefinitionType(…, Any)` disjuncts are unexplained. [Inference] line 44's disjunct appears unreachable and line 38's only fires for UC-vs-`__Canon`, which line 40 would also catch — unexplained redundancy invites cargo-cult edits; comment the intent (defensive symmetry) or simplify.
- `TypeSystemConstraintsHelpers.Canon.cs:10-21`: `IsSpecialTypeMeetingConstraint` has no doc comment despite encoding non-obvious policy (why `__Canon` meets `class`/`new()` but not `struct`), while its sibling in the same file is documented.
- `HandleCallAction.cs:787` is accurate, but the sibling `MakeGenericMethodSite` (line 769) is unnormalized and uncommented — a reader will ask "why not for methods?"; worth a note.

### Recommended removals

None — no added comment merely restates the code.

### Positive findings

- `HandleCallAction.cs:787` comment verified fully accurate: `NormalizeInstantiation` (`TypeExtensions.cs:674-684`) does exactly this; `Foo<object, __Canon>` is genuinely denormalized (mixed shapes never come out of canonicalization, per the "no mixture" note in `StandardCanonicalizationAlgorithm.cs:70-74`).
- `CastingHelper.Canon.cs:46-47, 51-52` inline comments accurate; concrete examples traced successfully.
- `TypeSystemConstraintsHelpers.Canon.cs:33-34` — "any concrete type substituted at runtime will be validated then" verified in-tree: `ConstraintValidator.EnsureSatisfiesClassConstraints` (`ExecutionEnvironmentImplementation.MappingTables.cs:203`, `:223`).
- Most test scenario comments verified accurate against `CoreTestAssembly/GenericConstraints.cs` (`IGen<in T>` :8, `Arg3<T> : IGen<T>` :14, `ClassArgWithDefaultCtor : IGen<object>` :23, `ComplexGenericConstraint2` :57, `MultipleConstraints` :63, new fixtures :74/:76); "Arg2<string> canonicalizes to Arg2<__Canon>" (test:440) correct per `ConvertToCanon`. All comments other than the three flagged describe declarations and assertion outcomes correctly.

---

## 5. type-design-analyzer — complete findings

### The partial-class variance pattern and its invariant

**Enforcement properties (verified):** Missing both variants → CS0103 at the call sites (`CastingHelper.cs:176, 426, 433, 477, 552`; `TypeSystemConstraintsHelpers.cs:33, 42, 51, 68`). Including both → CS0111 duplicate member. Caveats: (a) this is per-project *compile* time, not link time; (b) the "at least one" half is **contingent** — it exists only because the shared file happens to call all the methods; a refactor removing the last call site silently degrades it, and no declaration in the shared file states "an implementation must be supplied elsewhere."

A second invariant is **not** enforced: "a canon-capable project must pick the Canon variant." Canon variant → canon subsystem is compiler-enforced (the Canon file needs `IsCanonicalDefinitionType`, `TypeSystemContext.Canon.cs:49`); the reverse is convention only — a project could compile `TypeSystemContext.Canon.cs` *and* `CastingHelper.NonCanon.cs` with no error, silently reverting to the pre-PR bug. That is the real enforcement gap.

**Wiring (verified):** `CastingHelper.cs` has three consumers — `ILCompiler.TypeSystem.csproj:575-577` (Canon), `System.Private.TypeLoader.csproj:120-122` (Canon), `ILVerification.projitems:39-41` (NonCanon). `TypeSystemConstraintsHelpers.cs` has two — `ILCompiler.TypeSystem.csproj:565-567` (Canon), `ILVerification.projitems:378-380` (NonCanon). Correctly applied per-type. The seam is per-assembly: every downstream consumer of ILCompiler.TypeSystem (crossgen2/ReadyToRun, dotnet-pgo, ILTrim — verified via ProjectReference) gets canonical-aware casting; coarse but apparently intended.

**Idiomatic?** Mostly. Per-project partial-file composition is *the* dominant idiom here (~24 `*.Canon.cs` partials, plus `Sorting/`, `RuntimeDetermined/`, `CodeGen/` suites). But existing `.Canon.cs` precedents are **additive**; this PR introduces the tree's first **alternative-implementation** pair — the two `.NonCanon.cs` files are the only ones in the repository (verified by find). So it follows the composition convention while setting a new "required stub" precedent. A directly relevant in-class precedent not followed: `CastingHelper.cs:168` declares `static partial void IsEquivalentTo(...)` (optional impl in `CastingHelper.TypeEquivalence.cs:15`) — that mechanism declares its extension point in the shared file. (A defaulted partial-void here would be *wrong* — it would let a new consumer silently get NonCanon semantics; forcing an explicit choice via compile error is defensible. A C# 9 extended partial declaration would give the same forcing with better expression.) Minor placement wobble: the NonCanon stubs live in `Common/` ("compiled by everyone") yet must be *excluded* by canon-aware projects; a `NonCanon/` sibling directory would express the mutual exclusion. [Inference] placement chosen so ILVerification pulls only from `TypeSystem\Common\`.

### Encapsulation

Private statics inside existing public static partial classes — appropriate; no public API change; wildcard rules can't be misused from outside. **Stub vs interface/strategy vs `#if`: the stub is right.** An interface/strategy would thread an instance through static extension chains or hang a virtual off `TypeSystemContext`, adding runtime dispatch for a per-assembly constant and dragging canon vocabulary into canon-free builds (cf. the runtime-enforced `ConvertToCanon` throwing `NotSupportedException`, `TypeSystemContext.Canon.cs:79-91` — strictly weaker than compile-time selection). `#if` would need per-project `DefineConstants` and interleave both behaviors. ILVerification's *binary* contains zero canonical concepts — the stubs are a dependency cut, not a behavioral fork (constant `false` is what the Canon code would compute in a context that can't manufacture canonical types). Only leak is lexical. One contract asymmetry: the Canon variant enforces its precondition with `UnreachableException` (`TypeSystemConstraintsHelpers.Canon.cs:19`) while the NonCanon stub accepts any input — the precondition exists in only one variant. Trivial: unused `using System.Diagnostics;` at `TypeSystemConstraintsHelpers.NonCanon.cs:4`.

### API shape

All five methods are pure boolean predicates — consistent and appropriate.
- `IsCanonicalCastTarget` (`CastingHelper.Canon.cs:13`): directional; naming follows the file-wide source→target convention. Honest.
- `IsCanonicalTypeArgMatch` (`:30`): **verified symmetric by case analysis** — wildcard clause pairs mirror each other; recursion delegates only to symmetric checks. "Match" honestly conveys commutativity vs the directional "CastTarget" — good discrimination. At the call site (`CastingHelper.cs:477`) the argument names sound directional; the symmetry is intentional over-approximation — a one-line comment would remove ambiguity.
- `IsCanonEquivalent` (`:70`): symmetric with directional-sounding names — mirrors the pre-existing `IsEquivalentTo` (`CastingHelper.cs:150`), so file-consistent.
- `CanCastToConstraintWithCanon` (`TypeSystemConstraintsHelpers.Canon.cs:29`): parameter names match the host file's vocabulary verbatim; directional name matches directional semantics.
- `IsSpecialTypeMeetingConstraint` vs sibling `CheckGenericSpecialConstraint` (`TypeSystemConstraintsHelpers.cs:85`): naming styles diverge, and "special type" is new, undefined vocabulary (means "canonical definition type", which the shared file can't say without leaking canon vocabulary) — the weakest name in the PR.

Three parameter vocabularies coexist, but each locally matches its host file — convention-following, not sloppiness.

### The `IsCanonEquivalent` indexing invariant

Guaranteed (via `HasSameTypeDefinition` = reference equality of `GetTypeDefinition()`, `TypeDesc.cs:631-634` ⇒ equal arity, including open-definition cases), but entirely implicit — and the codebase's own precedent expresses exactly this assumption explicitly: `CastingHelper.cs:467-468` has `Debug.Assert(instantiationThis.Length == instantiationTarget.Length && …)` in the sibling method with the identical loop shape; `CastingHelper.TypeEquivalence.cs:78-81` defensively length-checks. The Canon file should carry the same assert. Also: the `IsCanonicalTypeArgMatch` ↔ `IsCanonEquivalent` mutual recursion has no `StackOverflowProtect`, unlike every other recursive walk in the file — sound (structural recursion over finite acyclic trees, vs the cyclable casting relations), but a "structural recursion, no cycle protection needed" comment would preempt a future maintainer "fixing" it or copying the unprotected shape into a relational walk.

### Ratings

**(a) Canon/NonCanon pattern — `CastingHelper`**
Invariants: exactly-one-variant (compile-enforced; "at least one" contingent); Canon→canon-subsystem (enforced); canon-subsystem→Canon (convention only — the gap); equal arity in `IsCanonEquivalent` (guaranteed, unasserted); structural-recursion termination (guaranteed, undocumented).
- Encapsulation: **8/10** — private statics, zero public-surface change, canon fully absent from the NonCanon binary; docked for stubs in `Common/` and lexical leak.
- Invariant expression: **6/10** — real but nowhere declared; the file's own `static partial void IsEquivalentTo` shows the codebase knows how to declare a seam; errors surface as generic CS0103, not intent-revealing diagnostics.
- Usefulness: **9/10** — exactly the right seam: ILVerification stays canon-free, zero runtime dispatch, fixes a real silent-wrong-answer bug, forces each new consumer to choose explicitly.
- Enforcement: **7/10** — both compile-error properties hold today; "at least one" contingent; pairing enforced in one direction only.

**(b) Same pattern — `TypeSystemConstraintsHelpers`**
- Encapsulation: **8/10** — same virtues as (a).
- Invariant expression: **6/10** — same undeclared seam; plus the two variants state different contracts for the same signature (`UnreachableException` vs accept-anything).
- Usefulness: **9/10** — the three-clause composition at `TypeSystemConstraintsHelpers.cs:31-51` cleanly layers canon semantics onto existing constraint logic without touching it.
- Enforcement: **7/10** — same asymmetric pairing gap; unused `using` in the stub.

**(c) Test-assembly types — `GenericConstraints.cs:72-76`** (`INonVariantGen<T>`, `NonVariantGenImpl<T>`, `NonVariantInterfaceConstraint<T,U>`)
- Encapsulation: **8/10** — public empty metadata fixtures, correct for purpose.
- Invariant expression: **9/10** — names state exactly the property they provide: the file's only generic interface `IGen<in T>` is contravariant, so the invariant-interface path was unreachable from existing fixtures; "NonVariant" makes the gap and its fill explicit.
- Usefulness: **9/10** — minimal and exactly sufficient (interface, one implementor, one constraint holder).
- Enforcement: **8/10** — nothing to enforce at runtime by design; the C# compiler guarantees the declared shape.

### Recommended improvements

1. **Declare the seam with C# 9 extended partial methods** (`private static partial bool IsCanonicalCastTarget(...);` in the shared files, `partial` on both variants) — converts CS0103/CS0111 into intent-revealing CS8795/CS0757, makes "at least one" independent of call-site survival, documents the extension point where readers look first.
2. **Add `Debug.Assert(thisInst.Length == otherInst.Length)`** in `IsCanonEquivalent` (after `CastingHelper.Canon.cs:96`), matching the house precedent at `CastingHelper.cs:467-468`.
3. **One comment** noting the recursion is structural and intentionally unprotected.
4. Optional polish: drop the unused `using`; consider a `NonCanon/` directory if more stub pairs accumulate.

Would not pursue an interface/strategy or `#if` redesign — the chosen mechanism is the pragmatic optimum for this codebase.

---

# Consolidated summary

## Critical (1, independently confirmed by two agents)

1. **[code-reviewer + silent-failure-hunter] `CanCastTo`'s contract silently changed from "castable for all substitutions" to "castable for some substitution", and the JIT-EE bridge still trusts positives as definite** — `CorInfoImpl.cs:2946-2952` returns `TypeCompareState.Must` for pairs its own comment (2964-2966) documents as `May` (`IFoo<__Canon> → IFoo<string>`), licensing RyuJIT to fold `isinst`/`castclass` in shared code for both ilc and crossgen2. [Inference on the downstream JIT folding — statically traced, not executed.] Both agents recommend the same class of fix: keep `CanCastTo` exact and give constraint validation a separate canonical-wildcard predicate, or audit/guard every consumer.

## Important

2. **[silent-failure-hunter] Variant interface / static-virtual resolution and devirtualization inherit the conflation** — `MetadataVirtualMethodAlgorithm.cs:783, 1167`; `DevirtualizationManager.cs:97, 133`. [Inference on reachability.]
3. **[pr-test-analyzer] The raw `CanCastTo` surface is essentially untested**: `IsCanonicalCastTarget` never returns true in any test; the canon-on-the-left branches (`CastingHelper.Canon.cs:40-44`) can be deleted without failing the suite; the exact arity-2 shape of #126604 is reproduced nowhere (C1, C2, I5).
4. **[silent-failure-hunter + pr-test-analyzer + comment-analyzer] `MakeGenericMethodSite` asymmetry** (`HandleCallAction.cs:769`) — correct today only via `RootingHelpers.cs:189`'s canonicalization (code-reviewer verified this), but the coincidence is uncommented and there is no `MakeGenericMethod` smoke test.
5. **[silent-failure-hunter + type-design-analyzer] The Canon/NonCanon pairing rule is undeclared and enforced in only one direction** — a wrong-choice wiring mistake silently resurrects #126604 or silently weakens ILVerify; the TypeLoader's Canon choice is an unjustified runtime behavior change.
6. **[comment-analyzer + pr-test-analyzer] Three test comments are factually wrong** (`ConstraintsValidationTest.cs:454-458` mis-teaches canonicalization; `:430` "invariant" vs contravariant; `:524` wrong array rationale), and several assertions in the special-constraints blocks are vacuous (pass with the PR reverted).

## Suggestions

- `Debug.Assert(thisInst.Length == otherInst.Length)` in `IsCanonEquivalent`; doc-comment fixes for `IsCanonEquivalent` (non-generic false), `IsCanonicalTypeArgMatch` (structural half), `CanCastToConstraintWithCanon` (precondition wording + the two-piece compile-time/runtime validation invariant); comment the [Inference] redundant disjuncts at `CastingHelper.Canon.cs:38/44` or simplify; document/remove the [Inference] dead `NotNullableValueTypeConstraint`+UC arm; declare the seam with extended partial methods; negative array-rank/category tests; drop the unused `using`; fix `ILVerification.projitems:379` indentation.

## Strengths (cross-agent consensus)

- The partial-class seam fails loudly on wiring omissions, costs zero runtime dispatch, and keeps ILVerification's binary canon-free.
- The wildcard semantics themselves are faithful to CLR canonical-form rules, with verified symmetry and correct `__Canon`-vs-value-type polarity throughout.
- Constraint-checking tests are behavior-focused with genuine negative cases; the smoke test is a well-constructed minimal model that [Inference] would fail without the fix.
- The `HandleCallAction.cs` normalization comment and the "runtime will validate" claim were both fully verified in-tree.

## Recommended action (were this pre-merge; it is already merged, so as follow-ups)

1. Address the `compareTypesForCast`/`CanCastTo` contract question first — either confirm with the ILC team that canonical pairs cannot reach that branch in practice, or split the predicate.
2. Add the missing `CanCastTo`-level canon tests (C1/C2) and an arity-2 #126604-shape fixture.
3. Fix the three inaccurate test comments and add the pairing-rule comments to the four partial files.
4. Add the `MakeGenericMethod` smoke-test twin or a pinning comment at `HandleCallAction.cs:769`.

Nothing was posted to GitHub; this report is the only output.
```
