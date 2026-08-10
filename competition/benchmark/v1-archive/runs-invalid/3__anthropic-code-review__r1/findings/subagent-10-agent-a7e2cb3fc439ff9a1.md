# subagent agent-a7e2cb3fc439ff9a1

## Sibling-Consistency Review

Compared the new `CastingHelper.Canon.cs`/`.NonCanon.cs` and `TypeSystemConstraintsHelpers.Canon.cs`/`.NonCanon.cs` against the established sibling files in `src/coreclr/tools/Common/TypeSystem/Canon/` (`TypeDesc.Canon.cs`, `TypeSystemContext.Canon.cs`) and cross-checked the three project-wiring blocks (`ILCompiler.TypeSystem.csproj`, `ILVerification.projitems`, `System.Private.TypeLoader.csproj`).

**Wiring census result**: all three consuming projects got exactly the right partner file (Canon.cs where the project always needs canon-aware behavior, NonCanon.cs where it needs a false-returning stub, and correctly *neither* where the project never referenced `TypeSystemConstraintsHelpers` before this PR — confirmed `System.Private.TypeLoader.csproj` still doesn't reference that class at all, pre- and post-PR). No missing-counterpart wiring gaps found.

```json
[
  {
    "file": "src/coreclr/tools/aot/ILCompiler.Compiler/Compiler/Dataflow/HandleCallAction.cs",
    "line": 769,
    "severity": "High",
    "category": "design",
    "issue": "[CONS_SYMMETRY] MakeGenericMethodSite.InstantiateDependencies calls CheckConstraints directly on _method.InstantiateSignature(...) with no normalization step, while its structural sibling MakeGenericTypeSite (same file, same INodeWithRuntimeDeterminedDependencies interface, same runtime-determined-instantiation purpose) now calls instantiatedType.NormalizeInstantiation() before CheckConstraints (HandleCallAction.cs:787-788), specifically because 'InstantiateSignature could end up with a denormalized shape (Foo<object, __Canon>)'. MethodDesc.InstantiateSignature (MethodDesc.cs:734-760) goes through the same TypeDesc.InstantiateSignature substitution path with no normalization performed internally, so a generic method instantiated with a mix of canonical/non-canonical type args appears exposed to the identical denormalized-shape problem this PR fixes for types.",
    "fix": "Either apply the equivalent normalization to instantiatedMethod (and/or its OwningType) before CheckConstraints in MakeGenericMethodSite, or add a comment explaining why methods are exempt from the denormalization issue that types are not.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/coreclr/tools/aot/ILCompiler.TypeSystem.Tests/ConstraintsValidationTest.cs",
    "line": 367,
    "severity": "Medium",
    "category": "design",
    "issue": "[CONS_SYMMETRY] nonVariantInterfaceConstraintType and nonVariantGenImplType are fetched via _testModule.GetType(...) as local variables inside TestCanonicalTypeConstraints, but every other type looked up the same way in this class (20 fields, e.g. _referenceTypeConstraintType at line 62, _simpleGenericConstraintType at line 67, _multipleConstraintsType at line 72) is declared as a private field and populated once in the constructor (lines 50-76), then reused across test methods.",
    "fix": "Promote nonVariantInterfaceConstraintType/nonVariantGenImplType to private fields (e.g. _nonVariantInterfaceConstraintType, _nonVariantGenImplType) initialized in the constructor alongside the other 20 fixture fields.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/coreclr/tools/ILVerification/ILVerification.projitems",
    "line": 379,
    "severity": "Low",
    "category": "design",
    "issue": "[CONS_SYMMETRY] The <Link> element for the new TypeSystemConstraintsHelpers.NonCanon.cs entry is indented 8 spaces, while every other <Compile>/<Link> pair in this file — including the immediately preceding TypeSystemConstraintsHelpers.cs entry (line 375-377) and the sibling CastingHelper.NonCanon.cs entry added in this same PR (line 39-41) — uses 6-space indentation for <Link>.",
    "fix": "Re-indent the <Link> line to 6 spaces to match every other entry in the file.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/coreclr/tools/Common/TypeSystem/Common/TypeSystemConstraintsHelpers.NonCanon.cs",
    "line": 4,
    "severity": "Low",
    "category": "unused-code",
    "issue": "[CONS_LEFTOVER] using System.Diagnostics; is unused in this file (both stub methods are one-line => false bodies with no Debug/UnreachableException reference). Its structural sibling, CastingHelper.NonCanon.cs — added in the same PR, same trivial-stub pattern — has zero using directives. The 'Apply suggestions from code review' cleanup commit (patch 5) removed the other unused using (System.Collections.Generic) from this exact file but missed this one.",
    "fix": "Remove the unused `using System.Diagnostics;` line.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/coreclr/tools/Common/TypeSystem/Canon/CastingHelper.Canon.cs",
    "line": 30,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_NAMING] IsCanonicalTypeArgMatch(TypeDesc type, TypeDesc otherType) names its first parameter 'type', while its own file siblings IsCanonicalCastTarget(TypeDesc thisType, TypeDesc otherType) (line 13) and IsCanonEquivalent(TypeDesc thisType, TypeDesc otherType) (line 70) — both added in the same PR — use 'thisType', matching the dominant thisType/otherType convention used by 10 of 12 two-TypeDesc-parameter methods in the base CastingHelper.cs (e.g. CanCastToInternal, CanCastToNonVariantInterface, CanCastByVarianceToInterfaceOrDelegate).",
    "fix": "Rename the `type` parameter to `thisType` for consistency with its sibling methods in the same file.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- `.csproj`/`.projitems` `<Compile Include>` alphabetical placement — checked ordering in all three project files (ILCompiler.TypeSystem.csproj lines 101-110/130-136, ILVerification.projitems lines 36-41/375-380, System.Private.TypeLoader.csproj lines 117-122): every new entry is correctly alphabetically positioned relative to siblings. No drift.
- Wiring completeness across the three consuming projects — verified no project got a `.Canon.cs`/`.NonCanon.cs` file it shouldn't have, and none is missing one it needs (`System.Private.TypeLoader.csproj` never referenced `TypeSystemConstraintsHelpers` before or after this PR, confirmed via `git show 7bba2205~1` and grep of the project's source tree for usages — correctly left untouched).
- `NonVariantGenImpl<T>`/`INonVariantGen<T>`/`NonVariantInterfaceConstraint<T,U>` naming in `GenericConstraints.cs` — "Impl" suffix has no exact sibling precedent (Arg1/Arg2/Arg3 use a different naming scheme, ClassArgWithDefaultCtor etc. use descriptive names), but the file already mixes multiple naming schemes for test fixture types, so no single dominant convention is violated. Confidence too low (50) to report.
- `struct Atom;` / `interface IFoo;` / `class Foo : IFoo;` semicolon-body (C# 12) declarations in the new `TestMakeGenericConstrainedDataflow` (Dataflow.cs:704-709) vs. 6 brace-body (`{ }`) empty-type declarations by its direct siblings `TestMakeGenericDataflow`/`TestMakeGenericDataflowInvalid` in the same file — a real, quotable divergence, but it doesn't cleanly map to any of the defined subcategories (not naming/vocabulary, not a canonical helper, not leftover scaffolding) and is a widely-accepted modern C# idiom; judged too trivial/off-target for this taxonomy to report as a finding.
- `CanCastToConstraintWithCanon`'s updated doc comment claiming "structural matching (interface walking, base chain, variance) is in CastingHelper" — verified accurate against the final CastingHelper.Canon.cs/.cs content (IsCanonEquivalent is invoked from CanCastToNonVariantInterface and CanCastToClass, IsCanonicalTypeArgMatch from CanCastByVarianceToInterfaceOrDelegate). No comment/code mismatch.
- `IsSpecialTypeMeetingConstraint` naming/placement follows the file's existing `Is...`-prefixed boolean-predicate convention (`IsCanonicalSubtype`, `IsCanonicalDefinitionType`, `IsGCPointer`) — consistent, not flagged.

### Probe Requests

None — all findings were verified statically against on-disk sibling files and grep evidence; no revert-probe needed.
