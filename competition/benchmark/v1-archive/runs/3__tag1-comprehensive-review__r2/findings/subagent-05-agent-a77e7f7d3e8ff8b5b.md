# subagent agent-a77e7f7d3e8ff8b5b

Good, confirms `NormalizeInstantiation` is a pre-existing extension method used elsewhere; this PR is just applying it in a new call site. I have enough context now to write the overview.

## Summary

Fixes `CanCastTo`/constraint-checking logic in the shared type system so it correctly handles canonical types (`__Canon`/`__UniversalCanon`) as constraint arguments during dataflow-driven `MakeGenericType`/`MakeGenericMethod` analysis. Previously, when dataflow analysis needed to validate `MakeGenericXXX` constraints but the type arguments were already canonicalized (as most reflection analysis in the AOT compiler operates on canonical types), the code incorrectly modeled canonical types as if they were the ordinary reference type `class __Canon : object { }`, causing constraint checks to reject or wrongly accept legitimate instantiations (root cause of #126604).

The fix adds dedicated canonical-type-aware helpers — `IsCanonicalCastTarget`, `IsCanonicalTypeArgMatch`, `IsCanonEquivalent` (casting) and `IsSpecialTypeMeetingConstraint`, `CanCastToConstraintWithCanon` (constraints) — implemented via a `Canon`/`NonCanon` partial-class split so the canon-aware logic only compiles into components that actually understand canonical types (e.g., `ILCompiler.TypeSystem`), while other consumers (like `ILVerification`) get no-op stubs. `HandleCallAction.cs` additionally normalizes a freshly instantiated type before constraint-checking it, since signature instantiation can produce a denormalized generic shape. Extensive new unit tests (`ConstraintsValidationTest.TestCanonicalTypeConstraints`) and a NativeAOT smoke test cover wildcard matching, ref/value-type distinctions, variance, nested/array type args, and interface implementation through canonical substitution.

**Type:** bugfix
**Effort:** 3/5 — Moderate-size, self-contained diff (~420 lines) confined to type-system casting/constraint logic plus new partial-class plumbing across three .csproj/.projitems files; correctness hinges on subtle canonical-type semantics (wildcard vs. concrete matching, GC-pointer checks, variance) that reviewers should trace against the new tests rather than skim.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| **Casting/Constraint Logic** | | |
| src/coreclr/tools/Common/TypeSystem/Canon/CastingHelper.Canon.cs | Added | New canon-aware `IsCanonicalCastTarget`, `IsCanonicalTypeArgMatch`, `IsCanonEquivalent` helpers implementing `__Canon`/`__UniversalCanon` wildcard-matching rules for casting |
| src/coreclr/tools/Common/TypeSystem/Canon/TypeSystemConstraintsHelpers.Canon.cs | Added | New canon-aware `IsSpecialTypeMeetingConstraint` and `CanCastToConstraintWithCanon` helpers for special/type constraint checks against canonical types |
| src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.cs | Modified | Wires the new canon helpers into `CanCastToInternal`, `CanCastToNonVariantInterface`, `CanCastByVarianceToInterfaceOrDelegate`, and `CanCastToClass` |
| src/coreclr/tools/Common/TypeSystem/Common/TypeSystemConstraintsHelpers.cs | Modified | Makes the class `partial`; calls new canon helpers in `VerifyGenericParamConstraint` for special/type constraints |
| src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.NonCanon.cs | Added | No-op (`false`-returning) stubs of the canon helpers for consumers without canonical type support |
| src/coreclr/tools/Common/TypeSystem/Common/TypeSystemConstraintsHelpers.NonCanon.cs | Added | No-op (`false`-returning) stubs of the canon constraint helpers for the same non-canon consumers |
| src/coreclr/tools/aot/ILCompiler.Compiler/Compiler/Dataflow/HandleCallAction.cs | Modified | Normalizes `instantiatedType` via `NormalizeInstantiation()` before `CheckConstraints` in `MakeGenericTypeSite`, avoiding denormalized shapes |
| **Tests** | | |
| src/coreclr/tools/aot/ILCompiler.TypeSystem.Tests/ConstraintsValidationTest.cs | Modified | Adds `TestCanonicalTypeConstraints`, a large new test covering `__Canon`/`__UniversalCanon` in special constraints, interface/base constraints, variance, and array/nested type args |
| src/coreclr/tools/aot/ILCompiler.TypeSystem.Tests/CoreTestAssembly/GenericConstraints.cs | Modified | Adds `INonVariantGen<T>`, `NonVariantGenImpl<T>`, `NonVariantInterfaceConstraint<T,U>` test fixtures |
| src/tests/nativeaot/SmokeTests/TrimmingBehaviors/Dataflow.cs | Modified | Adds `TestMakeGenericConstrainedDataflow` smoke test exercising `MakeGenericType` with a constrained generic parameter under trimming |
| **Config (project files)** | | |
| src/coreclr/nativeaot/System.Private.TypeLoader/src/System.Private.TypeLoader.csproj | Modified | Includes new `CastingHelper.Canon.cs` compile item |
| src/coreclr/tools/ILVerification/ILVerification.projitems | Modified | Includes new `CastingHelper.NonCanon.cs` and `TypeSystemConstraintsHelpers.NonCanon.cs` compile items |
| src/coreclr/tools/aot/ILCompiler.TypeSystem/ILCompiler.TypeSystem.csproj | Modified | Includes new `CastingHelper.Canon.cs` and `TypeSystemConstraintsHelpers.Canon.cs` compile items |

## Related Issues & PRs

<!-- issue-linker output will be merged here — the orchestrator replaces this placeholder -->

Relevant files read: `/tmp/cr-diff-SHDRTR3b.txt` (full PR diff). No repo files were modified; a read-only `grep` confirmed `NormalizeInstantiation()` is a pre-existing extension method used elsewhere in `ILCompiler.Compiler` (e.g. `src/coreclr/tools/aot/ILCompiler.Compiler/Compiler/RootingHelpers.cs:48`, `Compilation.cs`, `ILScanner.cs`), consistent with the PR's claim that it's reused rather than newly introduced.
