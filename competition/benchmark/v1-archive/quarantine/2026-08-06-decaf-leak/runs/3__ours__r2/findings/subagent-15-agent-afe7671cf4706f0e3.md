# subagent agent-afe7671cf4706f0e3

## Sibling-Consistency Review — PR #127146 "Handle canonical types in casting logic"

I built a census from the existing `.Canon.cs` partial-file family (17-18 files under `src/coreclr/tools/Common/TypeSystem/Canon/`), the two `.csproj`/`.projitems` files this PR edits, and `ConstraintsValidationTest.cs`'s existing test-fixture pattern, then compared every changed construct against it. 8 findings reported via `ReportFindings`, all Low/Medium severity (no functional divergence found — this is a well-executed, symmetric Canon/NonCanon split overall).

Highlights:
- **Project-file grouping break (2 files)**: `ILCompiler.TypeSystem.csproj:134` and `System.Private.TypeLoader.csproj:120` both place `CastingHelper.Canon.cs` away from the dedicated "Canon block" that groups all other `*.Canon.cs` includes together — notably, this same PR's own `TypeSystemConstraintsHelpers.Canon.cs` *does* follow that grouping correctly in both files, making the inconsistency self-evident within the diff.
- **Indentation anomaly**: `ILVerification.projitems:379` — the one anomaly flagged in the task brief, confirmed against 117 correctly-indented sibling `<Link>` elements.
- **Duplicated canonical-wildcard logic**: `TypeSystemConstraintsHelpers.Canon.cs`'s `CanCastToConstraintWithCanon` re-derives the exact same two-branch check as `CastingHelper.Canon.cs`'s `IsCanonicalCastTarget`, verbatim except for parameter names — a real desync risk since both were added in this PR without factoring a shared helper.
- **Naming drift**: `IsSpecialTypeMeetingConstraint` breaks the file's own `Check*` convention (sits directly beside `CheckGenericSpecialConstraint` at 3 call sites); `IsCanonEquivalent` uses short-form "Canon" where every sibling predicate (`IsCanonicalCastTarget`, `IsCanonicalTypeArgMatch`, `IsCanonicalDefinitionType`, `IsCanonicalSubtype`) uses "Canonical".
- **Test-fixture convention**: the two new test types (`NonVariantInterfaceConstraint`2`, `NonVariantGenImpl`1`) are fetched as method-locals in `ConstraintsValidationTest.cs`, while all 25 existing fixture types — including several used by only one test method, same as these — are cached as constructor-initialized fields.
- **Leftover unused `using System.Diagnostics;`** in `TypeSystemConstraintsHelpers.NonCanon.cs`, copied from the Canon.cs sibling where it backs an actual `UnreachableException`.

Considered but not flagged:
- Full Canon/NonCanon project-inclusion symmetry verified: every project including `CastingHelper.cs`/`TypeSystemConstraintsHelpers.cs` includes exactly one matching Canon or NonCanon variant — no missing project.
- NonCanon stub signatures mirror their Canon counterparts exactly (same order, same names, same parameter names) in both new file pairs.
- Namespace style (`namespace Internal.TypeSystem { }` block form) and MIT license header match all Canon.cs siblings.
- `NormalizeInstantiation()` in `HandleCallAction.cs` is a pre-existing, widely-used extension method (18+ call sites) — its use here is fully conventional, not a new pattern.
- New `GenericConstraints.cs` test types (`INonVariantGen<T>`, `NonVariantGenImpl<T>`, `NonVariantInterfaceConstraint<T,U>`) follow the file's existing naming/shape conventions (`IGen<in T>`, `Arg3<T> : IGen<T>`, `ComplexGenericConstraint3<T,U> where T : IGen<U>`) — no drift.
- `TestMakeGenericConstrainedDataflow` in `Dataflow.cs` structurally matches sibling test classes (`TestMakeGenericDataflow`, `TestMakeGenericDataflowInvalid`); `struct Atom;` is explicitly whitelisted per repo notes.
- Doc-comment phrasing "Check if..." in `CastingHelper.Canon.cs` matches existing phrasing already used in `CastingHelper.cs` (`AreVerificationTypesEqual`'s doc comment) — not a deviation.
- ILVerification.projitems insertions for `CastingHelper.NonCanon.cs` and `TypeSystemConstraintsHelpers.NonCanon.cs` are correctly alphabetized within that file's flat, per-directory-alphabetical convention (unlike the two `.csproj` Canon-block cases above).

Files read for this review: `src/coreclr/tools/Common/TypeSystem/Canon/*.cs`, `src/coreclr/tools/Common/TypeSystem/Common/CastingHelper*.cs`, `src/coreclr/tools/Common/TypeSystem/Common/TypeSystemConstraintsHelpers*.cs`, `src/coreclr/tools/ILVerification/ILVerification.projitems`, `src/coreclr/tools/aot/ILCompiler.TypeSystem/ILCompiler.TypeSystem.csproj`, `src/coreclr/nativeaot/System.Private.TypeLoader/src/System.Private.TypeLoader.csproj`, `src/coreclr/tools/aot/ILCompiler.TypeSystem.Tests/ConstraintsValidationTest.cs`, `src/coreclr/tools/aot/ILCompiler.TypeSystem.Tests/CoreTestAssembly/GenericConstraints.cs`, `src/tests/nativeaot/SmokeTests/TrimmingBehaviors/Dataflow.cs`, `src/coreclr/tools/aot/ILCompiler.Compiler/Compiler/Dataflow/HandleCallAction.cs`.
