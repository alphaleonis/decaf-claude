No prior reviews, so no recurring-findings section applies.

✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-10_17-15-10.md`

## Summary

**Verdict: ❌ NEEDS_CHANGES** — the change fixes the reported `AmbiguousMatchException` for the common case but leaves the same crash reachable in a narrower shape, and its tests don't actually cover the branch it added.

All four reviewers (quick, broad, dotnet, test) independently converged on one core defect.

### 🟠 High #1 — The fix is incomplete; the `FlattenHierarchy` fallback still throws `AmbiguousMatchException`
`EditContextDataAnnotationsExtensions.cs:276-280`. The `DeclaredOnly`-first lookup only saves the case where the **leaf** type redeclares the `new` property. When the property is hidden at an **intermediate** ancestor and the runtime type inherits it without redeclaring, `DeclaredOnly` returns null and the fallback walks the full hierarchy — finding two same-named properties of different types and throwing the very exception the change targets. `TryGetValidatableProperty` runs on `OnFieldChanged`, so this faults validation.

This is **confirmed, not speculative**: the original bug proves reflection throws (rather than picking most-derived) on a `new`-with-different-type shadow — the pre-fix full-hierarchy `GetProperty` demonstrably threw on `int OrderID` vs base `object OrderID`. `FlattenHierarchy` is a no-op for instance lookups, so the fallback is the same ambiguous walk minus `Static`. Fix: walk the base chain applying `DeclaredOnly` at each level (drops the misleading flag too).

### 🟡 Medium #2 — The added tests never drive the fallback branch
`EditContextDataAnnotationsExtensionsTest.cs:221-235`. Every model-under-test declares the property on its leaf type, so `DeclaredOnly` always hits. `ValidatesPropertyHiddenAtMultipleInheritanceLevels` doesn't actually test multi-level hiding (`DeepDerivedModel` redeclares `new int Tag`). Deleting the entire fallback block would leave all six new tests green — they can't catch #1's regression. Needs a `class Leaf : DeepDerivedModel {}`-style leaf-inherits test.

### 🔵 Minor (4)
- No rationale comment on the two-step lookup — a maintainer could collapse it back into the crash.
- `BindingFlags.FlattenHierarchy` is a misleading no-op for instance lookup.
- `MidLevelModelWithShadow` is inert scaffolding (only appears as an unexercised base).
- `IgnoresStaticProperty`'s `Assert.Empty` has no positive control — it'd pass on a wholesale lookup failure.

**Not a defect** (all agents agree): dropping `BindingFlags.Static` is intentional and safe for instance-oriented validation, and is locked in by `IgnoresStaticProperty`.

Note: no dotnet SDK in this environment, so build/tests couldn't be run — findings are static analysis, though the central claim is grounded in the observed pre-fix behavior.
