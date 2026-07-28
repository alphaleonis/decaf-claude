# subagent agent-ac64974b6a4fb260e

## PR Summary: Handle canonical types in casting logic

**Status:** Fix for issue #126604

**Author:** Michal Strehovský

**Scale:** 13 files changed, 417 additions, 7 deletions

---

## What the PR Does

This PR fixes constraint validation during `MakeGenericType`/`MakeGenericMethod` reflection calls when working with canonical types (`__Canon` and `__UniversalCanon`). The issue occurs because:

1. Dataflow analysis within the compiler extensively uses canonical types as placeholders
2. Canonical types have special wildcard semantics—they're not regular types but represent "any type at runtime"
3. Existing casting and constraint checking logic treated `__Canon` as a regular type (`class __Canon : object { }`), causing constraint validation to fail incorrectly

**Fix Strategy:** Partition casting and constraint logic into canonical-aware paths that understand canonical types as wildcards, with platform-specific (canonical vs. non-canonical) implementations.

---

## Files Modified & Nature of Changes

| File | Changes | Purpose |
|------|---------|---------|
| **`CastingHelper.Canon.cs`** (NEW, 93 lines) | 3 new methods: `IsCanonicalCastTarget()`, `IsCanonicalTypeArgMatch()`, `IsCanonEquivalent()` | Canonical-specific casting logic: `__Canon` matches ref types, `__UniversalCanon` matches all types |
| **`CastingHelper.NonCanon.cs`** (NEW, 17 lines) | No-op stubs for same 3 methods | Non-canonical platforms (always return false) |
| **`TypeSystemConstraintsHelpers.Canon.cs`** (NEW, 48 lines) | 2 new methods: `IsSpecialTypeMeetingConstraint()`, `CanCastToConstraintWithCanon()` | Constraint validation with canonical semantics |
| **`TypeSystemConstraintsHelpers.NonCanon.cs`** (NEW, 16 lines) | No-op stubs for same 2 methods | Non-canonical platforms |
| **`CastingHelper.cs`** (Modified, +11/-3 lines) | Made class partial; added 4 calls to new canonical methods in existing flows | Integrated canonical checks into `CanCastToInternal`, `CanCastToNonVariantInterface`, `CanCastByVarianceToInterfaceOrDelegate`, `CanCastToClass` |
| **`TypeSystemConstraintsHelpers.cs`** (Modified, +10/-4 lines) | Made class partial; added calls to new canonical validation methods | Enhanced `VerifyGenericParamConstraint` to check special constraints and type constraints with canonical awareness |
| **`HandleCallAction.cs`** (Modified, +4 lines) | Added `NormalizeInstantiation()` call after instantiation | Ensures denormalized types (e.g., `Foo<object, __Canon>`) are normalized before constraint checking |
| **`ConstraintsValidationTest.cs`** (NEW, 176 lines) | Comprehensive test method `TestCanonicalTypeConstraints()` with 12 test scenarios | Validates canonical type behavior in constraints, interfaces, base types, and complex generics |
| **`GenericConstraints.cs`** (Modified, +6 lines) | Added `INonVariantGen<T>`, `NonVariantGenImpl<T>`, `NonVariantInterfaceConstraint<T, U>` | Test fixtures for invariant interface constraint scenarios |
| **`Dataflow.cs`** (Modified, +21 lines) | Added `TestMakeGenericConstrainedDataflow` test class and call in `Run()` | Integration test for canonical types in dataflow MakeGeneric scenarios |
| **Project files** (3 files) | Added `<Compile>` entries linking Canon/NonCanon helper files | Ensure new partial implementations are included in builds |

---

## Key Logic Changes

**Canonical Type Matching Rules:**
- `__Canon` (specific canonical): matches reference types only; rejects value types
- `__UniversalCanon` (universal canonical): matches all types
- Canonical types can appear as:
  - **Instantiation params** (wildcards—runtime decides actual type)
  - **Constraint types** (the constraint itself is canonical)
  - **Constraint args** (inside parameterized constraints)

**New Methods & Behavior:**

1. **`IsCanonicalCastTarget(thisType, otherType)`** — checks if `otherType` is canonical and castable
   - Returns true if both conditions met: `otherType` is canonical AND compatibility (universal=always, specific=ref-type-only)

2. **`IsCanonicalTypeArgMatch(type, otherType)`** — recursively checks if two type arguments are canonically compatible
   - Handles direct canonical matches, recursive checks for parameterized types (arrays, generics)

3. **`IsCanonEquivalent(thisType, otherType)`** — checks if types have same definition with canon-compatible arguments
   - Used in interface/base-type matching to account for canonical substitutions

4. **`CanCastToConstraintWithCanon(...)`** — handles constraint checking when either param or constraint is canonical
   - If instantiation param is canonical → always passes (runtime will validate)
   - If constraint is canonical → checks compatibility based on canonical kind

5. **`IsSpecialTypeMeetingConstraint(type, constraint)`** — validates that canonical types satisfy special constraints
   - `__Canon` satisfies `class` and `new()`, rejects `struct`
   - `__UniversalCanon` satisfies all three

**Integration Points:**
- Casting chain now checks canonical targets before regular type walking
- Constraint validation layers canonical checks atop existing structural checks
- Instantiation is normalized before constraint checking to handle partially-canonical forms

---

## Tests Added

**Unit tests (176 lines):** Twelve exhaustive scenarios in `TestCanonicalTypeConstraints()`:
- Special constraints (class, new(), struct) with __Canon and __UniversalCanon
- Canonical as wildcard instantiation param
- Invariant interface constraints with canonical args
- Variant interface constraints with canonical args
- Base type constraints with canonical nesting
- Parameterized types (arrays) with canonical
- Nested __UniversalCanon under invariant generics
- Array type args in invariant positions

**Integration test:** `TestMakeGenericConstrainedDataflow` in smoke tests validates end-to-end MakeGenericType behavior with constrained generics and canonical types.
