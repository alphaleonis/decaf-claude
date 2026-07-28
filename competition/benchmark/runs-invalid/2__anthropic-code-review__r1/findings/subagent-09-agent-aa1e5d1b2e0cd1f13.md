# subagent agent-aa1e5d1b2e0cd1f13

Analysis complete. I have verified the reflection semantics and traced the reachable code path. Here is my spec-compliance report.

---

Spec source: `linked` — GitHub issue #27095 (via "Fixes #27095"). Reviewed at full strength; severities not capped.

```json
[
  {
    "file": "src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs",
    "line": 376,
    "severity": "High",
    "category": "spec-compliance",
    "issue": "[SPEC_PARTIAL] The generalized requirement 'no AmbiguousMatchException for hidden members' is only partially met. The DeclaredOnly probe (Call 1) only suppresses ambiguity when the RUNTIME (most-derived) type is the one redeclaring the member with 'new'. When the leaf/runtime type merely INHERITS a member that was hidden by an intermediate ancestor (A defines Foo, B:A hides with 'new int Foo', C:B does not redeclare), Call 1 returns null and the FlattenHierarchy fallback (Call 2) sees both B.Foo and A.Foo and throws the exact AmbiguousMatchException the issue is about — via the same OnFieldChanged/NotifyFieldChanged path.",
    "fix": "Handle ambiguity in the FlattenHierarchy fallback too: walk the base-type chain resolving the most-derived declared property per name (e.g. loop over BaseType with DeclaredOnly, or catch AmbiguousMatchException and pick the most-derived declaration). Add a test whose runtime type inherits (does not redeclare) a member hidden in an intermediate base.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs",
    "line": 372,
    "severity": "Low",
    "category": "spec-compliance",
    "issue": "[SPEC_UNCOVERED] Both new GetProperty calls use BindingFlags.Instance only, dropping BindingFlags.Static that the original default GetProperty(name) flags (Public|Instance|Static) included. Public static properties carrying validation attributes that were previously discovered and validated are now silently skipped. This behavior change is not required by issue #27095 (which says nothing about static members) and contradicts the PR's 'No breaking changes' self-claim. The added IgnoresStaticProperty test locks in the new, changed behavior.",
    "fix": "If preserving prior behavior is intended, add BindingFlags.Static to both probes (Public|Instance|Static|DeclaredOnly, then ...|FlattenHierarchy). If dropping static support is intentional, state it explicitly (the fix should not silently narrow an unrelated behavior) rather than claiming no breaking changes.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Requirement Coverage Matrix

| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| R1 | No AmbiguousMatchException for the reported repro: most-derived type redeclares `new int OrderID` hiding base `object OrderID`; triggered via NotifyFieldChanged | **Covered** | `EditContextDataAnnotationsExtensions.cs:370-372` — DeclaredOnly probe returns the single leaf-declared property; tests `ValidatesHiddenPropertiesWithoutAmbiguousMatchException`, `...WithPropertyCaching`, `MatchesPropertyByExactName` |
| R2 | Handle "hidden members" generally (issue title + reporter's note that the OO pattern is in a library they cannot modify → arbitrary hierarchies) | **Partial** | `:374-379` — FlattenHierarchy fallback still throws when the runtime type inherits a member hidden by an intermediate ancestor. No test exercises this shape |
| R3 | Preserve existing validation for normal inherited / directly-declared public properties (no regression) | **Covered (with one deviation)** | Inherited non-hidden props resolved by Call 2 (`ValidatesInheritedPropertyFromBaseClass`); direct props by Call 1. Deviation: public **static** props no longer resolved (see Low finding) |
| C1 (PR claim) | "No breaking changes" | **Deviated** | `:370-378` drop `BindingFlags.Static` present in the original default flags |
| C2 (PR claim) | "Consistent behavior across reflection-based validation scenarios" | **Partial** | Same gap as R2 — inconsistent for leaf-inherits-hidden hierarchies |

## Considered But Not Flagged

- **Point 1 (exact repro) — confirmed fixed, not a finding.** `DerivedModelWithHiddenProperty.GetProperty("OrderID", Public|Instance|DeclaredOnly)` yields exactly one match (the leaf `new int OrderID`); DeclaredOnly restricted to a single type can never be ambiguous (a type cannot declare two same-named properties). Validation then applies the `[Range]` attribute correctly.
- **`ValidatesPropertyHiddenAtMultipleInheritanceLevels` gives false confidence for R2.** Its model `DeepDerivedModel` is itself the leaf and *redeclares* `new int Tag`, so it exercises the R1 (Call 1) path, not the leaf-inherits-hidden path. The genuinely uncovered R2 shape (runtime type inherits a member hidden by an intermediate base — e.g. a `MidLevelModelWithShadow` leaf whose own base further hides) remains untested. Reported as supporting evidence for the SPEC_PARTIAL finding rather than a separate test-quality finding (test quality is test-reviewer scope).
- **Shadowed base attributes dropped when leaf `new` member is unattributed** (`SkipsValidationWhenDerivedShadowHasNoAttributes`): Call 1 returns the leaf unattributed property, so the base `[Required]` no longer applies. This matches C# member-hiding semantics (the leaf member is what a compile-time-derived reference binds to) and is a reasonable interpretation, not a deviation.
- **Call 1 DeclaredOnly safety**: cannot throw AmbiguousMatchException, so the fix does eliminate ambiguity for the common (leaf-declares) case — the design is sound as far as it goes.

## Probe Requests

None required — findings are verifiable statically from the diff plus documented `Type.GetProperty` / `BindingFlags` semantics. (If desired, a confirming probe would be a unit test with `class A { object Foo }` → `class B : A { new int Foo }` → `class C : B {}`, validating a `FieldIdentifier(new C(), "Foo")` and asserting no `AmbiguousMatchException`; expected to currently throw. I did not run it per read-only constraints and no .NET SDK.)

Relevant file: `/home/decaf/code/decaf-claude/competition/benchmark/repos/2/src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs` (`TryGetValidatableProperty`, lines 363-386).
