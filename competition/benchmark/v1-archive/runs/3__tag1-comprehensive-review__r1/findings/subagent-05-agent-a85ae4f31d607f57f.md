# subagent agent-a85ae4f31d607f57f

## Summary

Fixes #126604: constraint validation and `CanCastTo` logic during NativeAOT dataflow analysis of `MakeGenericXXX` calls previously treated canonical placeholder types (`__Canon`, `__UniversalCanon`) as if they were the concrete type `object`/`class __Canon : object {}`, causing incorrect constraint-satisfaction results when only canonical types are available. Adds dedicated canon-aware casting/constraint helpers (as new `partial` methods split into `.Canon.cs`/`.NonCanon.cs` files per project), wires them into the existing `CastingHelper`/`TypeSystemConstraintsHelpers` checks, and normalizes a denormalized instantiation shape before constraint-checking in `HandleCallAction`.

**Type:** bugfix
**Effort:** 4/5 — 417 net added lines across 13 files touching core shared type-system casting/constraint logic (recursive canon-equivalence matching, variance, generic constraint checks) plus new partial-class stub wiring into three separate build projects (`ILCompiler.TypeSystem`, `ILVerification`, `System.Private.TypeLoader`); correctness depends on subtle canonical-form semantics, though the change is scoped to one well-defined bug rather than a broad redesign.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| **Casting & Constraint Logic** | | |
| src/coreclr/tools/Common/TypeSystem/Canon/CastingHelper.Canon.cs | Added | New `IsCanonicalCastTarget`, `IsCanonicalTypeArgMatch`, `IsCanonEquivalent` helpers implementing __Canon/__UniversalCanon-aware cast/type-arg matching (incl. recursive array/parameterized-type matching) |
| src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.cs | Modified | Declares `CastingHelper` `partial`; calls new canon helpers from `CanCastToInternal`, `CanCastToNonVariantInterface`, `CanCastByVarianceToInterfaceOrDelegate`, `CanCastToClass` |
| src/coreclr/tools/Common/TypeSystem/Canon/TypeSystemConstraintsHelpers.Canon.cs | Added | New `IsSpecialTypeMeetingConstraint` and `CanCastToConstraintWithCanon` helpers for canon-aware special/type constraint checks |
| src/coreclr/tools/Common/TypeSystem/Common/TypeSystemConstraintsHelpers.cs | Modified | Declares `TypeSystemConstraintsHelpers` `partial`; calls the new canon checks in `VerifyGenericParamConstraint` for special constraints and type constraints |
| src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.NonCanon.cs | Added | Stub partial implementations (always `false`) for projects (e.g. `ILVerification`) that don't include canon support |
| src/coreclr/tools/Common/TypeSystem/Common/TypeSystemConstraintsHelpers.NonCanon.cs | Added | Stub partial implementations (always `false`) mirroring the canon file for non-canon builds |
| **Dataflow Analysis** | | |
| src/coreclr/tools/aot/ILCompiler.Compiler/Compiler/Dataflow/HandleCallAction.cs | Modified | Normalizes `instantiatedType` via `NormalizeInstantiation()` before `CheckConstraints` in `MakeGenericTypeSite`, to collapse denormalized shapes like `Foo<object, __Canon>` |
| **Tests** | | |
| src/coreclr/tools/aot/ILCompiler.TypeSystem.Tests/ConstraintsValidationTest.cs | Modified | Adds `TestCanonicalTypeConstraints`, a 176-line suite covering __Canon/__UniversalCanon in special constraints, type constraints, variance, arrays, and nested generic shapes |
| src/tests/nativeaot/SmokeTests/TrimmingBehaviors/Dataflow.cs | Modified | Adds `TestMakeGenericConstrainedDataflow` smoke test exercising `MakeGenericType` with a `new()`-constrained parameter |
| src/coreclr/tools/aot/ILCompiler.TypeSystem.Tests/CoreTestAssembly/GenericConstraints.cs | Modified | Adds `INonVariantGen<T>`, `NonVariantGenImpl<T>`, `NonVariantInterfaceConstraint<T,U>` test fixture types |
| **Build Config** | | |
| src/coreclr/tools/aot/ILCompiler.TypeSystem/ILCompiler.TypeSystem.csproj | Modified | Adds compile includes for the new `*.Canon.cs` helper files |
| src/coreclr/tools/ILVerification/ILVerification.projitems | Modified | Adds compile includes for the new `*.NonCanon.cs` stub files |
| src/coreclr/nativeaot/System.Private.TypeLoader/src/System.Private.TypeLoader.csproj | Modified | Adds compile include for `CastingHelper.Canon.cs` |

## Related Issues & PRs

<!-- issue-linker output will be merged here — the orchestrator replaces this placeholder -->

Files read: `/home/decaf/code/decaf-claude/competition/benchmark/repos/3` (repo root, HEAD = 7bba2205, base = HEAD~1 = 2102b6b5); context at `/tmp/cr-context-127146.txt`; diff at `/tmp/cr-diff-127146.txt`.
