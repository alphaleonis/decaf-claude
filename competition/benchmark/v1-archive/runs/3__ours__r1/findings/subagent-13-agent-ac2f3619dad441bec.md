# subagent agent-ac2f3619dad441bec

```json
[
  {
    "file": "src/coreclr/tools/Common/TypeSystem/Canon/CastingHelper.Canon.cs",
    "line": 30,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[DOTNET_EXCEPTIONS] IsCanonicalTypeArgMatch/IsCanonEquivalent recurse through nested generic instantiation arguments (via ParameterizedType.ParameterType and Instantiation[i]) without threading the codebase's existing StackOverflowProtect/CastingPair cycle-guard. The call site immediately after this new check, CanCastByVarianceToInterfaceOrDelegate (CastingHelper.cs:477), explicitly threads `protect` through the analogous recursive generic-argument comparison specifically to guard against unbounded recursion from variance-driven/recursive generic shapes. The new canonical-match path bypasses that protection entirely.",
    "fix": "Thread a StackOverflowProtect/visited-set (or reuse CastingPair) through IsCanonicalTypeArgMatch and IsCanonEquivalent so deeply nested or self-referential canonical instantiations can't drive unbounded recursion; StackOverflowException is uncatchable in .NET and would crash the AOT compiler or NativeAOT type loader process rather than failing the cast/constraint check gracefully.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Partial-class build completeness** (explicitly requested check): Verified by grepping every `.csproj`/`.projitems` under `src/coreclr` for `CastingHelper.cs` and `TypeSystemConstraintsHelpers.cs`. Exactly 3 projects compile `CastingHelper.cs` (`ILCompiler.TypeSystem.csproj`, `System.Private.TypeLoader.csproj`, `ILVerification.projitems`), each now linking exactly one companion (`.Canon.cs`/`.Canon.cs`/`.NonCanon.cs` respectively). Exactly 2 projects compile `TypeSystemConstraintsHelpers.cs` (`ILCompiler.TypeSystem.csproj`, `ILVerification.projitems`), each linking exactly one companion (`.Canon.cs`/`.NonCanon.cs`). `System.Private.TypeLoader.csproj` correctly omits the `TypeSystemConstraintsHelpers` companion because it never compiles `TypeSystemConstraintsHelpers.cs` at all — not a gap. No other project (StackTraceMetadata, Reflection.Execution, CoreLib, Test.CoreLib, ILTrim.Core) references either base file. No CS0103/CS0111 risk.
- **`_ => throw new UnreachableException()`** in `IsSpecialTypeMeetingConstraint`: confirmed via repo-wide grep that the method has exactly 3 call sites (`TypeSystemConstraintsHelpers.cs:33,42,51`), each passing one of `ReferenceTypeConstraint`/`DefaultConstructorConstraint`/`NotNullableValueTypeConstraint` — the three cases the switch handles. Genuinely unreachable; correct use of `UnreachableException`.
- **`NormalizeInstantiation()` on the `InstantiateSignature` result** in `HandleCallAction.cs`: the method (`TypeExtensions.cs:678`) dispatches to `TypeDesc.IsCanonicalSubtype`/`ConvertToCanonForm`, which are `abstract`/overridden on every `TypeDesc` subclass (verified overrides exist for `InstantiatedType`, `GenericParameterDesc`, `MetadataType`, `SignatureVariable`, `ParameterizedType`, `FunctionPointerType`, `RuntimeDeterminedType`, plus the canon types themselves) and is already used safely elsewhere in the same assembly (`Compilation.cs`, `ILScanner.cs`, `EETypeNode.cs`, etc.). Safe to call on any instantiated shape.
- **Nullable reference types**: `System.Private.TypeLoader.csproj` sets `<Nullable>disable</Nullable>` explicitly; no `<Nullable>` setting found for `ILCompiler.TypeSystem.csproj`/`ILVerification.projitems` or up the `Directory.Build.props` chain. NRT is not in effect for this file set, so DOTNET_NULLABILITY concerns (lying annotations, null-forgiving misuse) don't apply here.
- **`IsCanonicalCastTarget`'s unconditional `true` for `CanonicalFormKind.Universal`** even when `thisType` is a Pointer/ByRef/FunctionPointer: this matches the documented, pre-existing semantics of `CanonicalFormKind.Universal` ("works for any type", `TypeSystemContext.IsCanonicalDefinitionType`), and pointer/byref types can't reach this as real instantiation arguments because `CheckValidInstantiationArguments` already rejects them upstream. Domain-design question, not a language-idiom defect — left to design/domain review.
- **Unused `using System.Diagnostics;`** in `TypeSystemConstraintsHelpers.NonCanon.cs` (the stub returns `false` unconditionally and never references the namespace): a trivial lint nit with no runtime consequence, below the reporting bar.
- **`MakeGenericMethodSite` (HandleCallAction.cs:766-774) not calling `NormalizeInstantiation`** the way the sibling `MakeGenericTypeSite` (line 788) now does: possibly the same denormalization issue (`Foo<object, __Canon>` shape) could affect method-level generic instantiation too, but this is a question of fix completeness/scope for the underlying bug (#126604), not C#/.NET idiom misuse — better suited to spec-compliance-reviewer or design-reviewer.
