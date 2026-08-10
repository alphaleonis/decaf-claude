# subagent agent-ac34e8492f66b9db6

## PR Summary: #127146 in dotnet/runtime

**PR Title & Author:**  
"Handle canonical types in casting logic" by Michal Strehovský

---

**What Changed & Why:**

This PR fixes issue #126604 by adding proper support for canonical types (`__Canon` and `__UniversalCanon`) in casting and generic constraint validation logic. 

**The problem:** During dataflow analysis of `MakeGenericXXX` calls, the compiler validates generic constraints to prevent precompilation of invalid types. Most reflection analysis in the compiler uses canonical types, which act as "wildcards" — `__Canon` accepts any reference type, and `__UniversalCanon` accepts any type. However, the existing constraint-checking and `CanCastTo` logic treated canonical types as regular types (like `class __Canon : object { }`), leading to false validation failures.

**The solution:** Introduces conditional-compilation patterns (`.Canon.cs` for canonical-specific logic, `.NonCanon.cs` for non-canonical stubs) to handle canonical types correctly as wildcard types. Also adds a normalization step in the dataflow analyzer to handle denormalized type shapes like `Foo<object, __Canon>`.

---

**Files Changed (13 total):**

1. **System.Private.TypeLoader.csproj** — Added reference to CastingHelper.Canon.cs
2. **CastingHelper.Canon.cs** (NEW) — Canonical casting helpers: `IsCanonicalCastTarget`, `IsCanonicalTypeArgMatch`, `IsCanonEquivalent`
3. **TypeSystemConstraintsHelpers.Canon.cs** (NEW) — Canonical constraint helpers: `IsSpecialTypeMeetingConstraint`, `CanCastToConstraintWithCanon`
4. **CastingHelper.NonCanon.cs** (NEW) — Stubs returning false for non-canonical builds
5. **CastingHelper.cs** — Integrated canonical casting checks into `CanCastToInternal`, `CanCastToNonVariantInterface`, `CanCastByVarianceToInterfaceOrDelegate`, and `CanCastToClass`
6. **TypeSystemConstraintsHelpers.NonCanon.cs** (NEW) — Stubs for constraint helpers in non-canonical builds
7. **TypeSystemConstraintsHelpers.cs** — Made class partial; integrated canonical constraint checks into special constraint and base type constraint validation
8. **ILVerification.projitems** — Added references to NonCanon.cs stubs
9. **HandleCallAction.cs** — Added `NormalizeInstantiation()` call to handle denormalized generic shapes
10. **ConstraintsValidationTest.cs** (NEW TEST) — Added `TestCanonicalTypeConstraints` with 10+ test cases covering canonical type matching, constraint satisfaction, variance, and parameterized types
11. **GenericConstraints.cs** — Added test types: `INonVariantGen<T>`, `NonVariantGenImpl<T>`, `NonVariantInterfaceConstraint<T, U>`
12. **ILCompiler.TypeSystem.csproj** — Added references to Canon.cs files
13. **Dataflow.cs** — Integrated smoke test `TestMakeGenericConstrainedDataflow`

---

**Commit SHAs:**

- **Head commit:** `8289ab18da1b7dca261eccc098d44e69c9989837`
- **Merge commit:** `7bba2205c2a75e4364dc32dc79cc91fae13791af`
