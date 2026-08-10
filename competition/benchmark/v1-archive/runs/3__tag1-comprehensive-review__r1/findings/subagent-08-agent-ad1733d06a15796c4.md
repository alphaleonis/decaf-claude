# subagent agent-ad1733d06a15796c4

I reviewed the full diff for dotnet/runtime PR #127146 ("Handle canonical types in casting logic", squash commit `7bba2205`, base `2102b6b5`), covering:

- `src/coreclr/tools/Common/TypeSystem/Canon/CastingHelper.Canon.cs` (new) — `IsCanonicalCastTarget`, `IsCanonicalTypeArgMatch`, `IsCanonEquivalent`
- `src/coreclr/tools/Common/TypeSystem/Canon/TypeSystemConstraintsHelpers.Canon.cs` (new) — `IsSpecialTypeMeetingConstraint`, `CanCastToConstraintWithCanon`
- `src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.NonCanon.cs` / `TypeSystemConstraintsHelpers.NonCanon.cs` (new stub partials)
- `src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.cs` and `TypeSystemConstraintsHelpers.cs` (call-site wiring for the above)
- `src/coreclr/tools/aot/ILCompiler.Compiler/Compiler/Dataflow/HandleCallAction.cs` (`NormalizeInstantiation()` addition in `MakeGenericTypeSite`)
- The three `.csproj`/`.projitems` files wiring the new partials into `ILCompiler.TypeSystem`, `System.Private.TypeLoader`, and `ILVerification`
- The new tests in `ConstraintsValidationTest.cs`, `GenericConstraints.cs`, and `Dataflow.cs`

I traced the partial-class wiring across all three consuming projects to confirm no project ends up with an unmatched `CastingHelper.cs`/`TypeSystemConstraintsHelpers.cs` missing its `.Canon.cs`/`.NonCanon.cs` counterpart (all three are correctly paired). I manually walked several of the new constraint/casting code paths by hand against the newly added `ConstraintsValidationTest.cs` cases (nested generics, array element canon-matching, variant/non-variant interface constraints, `__Canon` vs `__UniversalCanon` distinctions) and they check out. I also investigated whether the `NormalizeInstantiation()` fix applied to `MakeGenericTypeSite` should have been mirrored in the neighboring `MakeGenericMethodSite` (same file); on closer inspection this isn't a functional gap — `RootingHelpers.TryGetDependenciesForReflectedMethod` already canonicalizes via `method.GetCanonMethodTarget(CanonicalFormKind.Specific)` before creating the dependency node, whereas `TryGetDependenciesForReflectedType` does not self-canonicalize, which is why only the type path needed the explicit call.

I did not find any issue I'd stake reputation on at confidence ≥80 — no logic errors, no missed edge cases in the canonical-type matching, no build-wiring gaps, and no convention violations per the C# review profile.

NONE
