# subagent agent-a7629e1dbdf807bbc

I have complete context: the changed method (lines 363-386), its sole caller `OnFieldChanged` (line 94, synchronous, no try/catch), the cache (line 46), and the test types. Now reasoning statically about the reflection semantics.

Key mechanism confirmed from the original bug: `GetProperty` on a flattened candidate set throws `AmbiguousMatchException` only when two same-named candidates have **different signatures** (the same-signature `new` case is collapsed by the runtime's property-cache filter; different-signature shadows are both retained). That is exactly why the original 2-level case (`int OrderID` shadowing `object OrderID`) threw. The fix's `DeclaredOnly`-first lookup resolves that by returning the type's own declaration — but only when the type declares the property itself.

---

Depth: quick — 11 executable lines changed (source), no high-risk persistence/auth/payment domain. Orchestrator-directed cascade construction on scenario 1; ≤3 findings.

```json
[
  {
    "file": "src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs",
    "line": 376,
    "severity": "High",
    "category": "error-handling",
    "issue": "[ADV_CASCADE] Leaf type inherits a different-signature shadow declared at an intermediate base (C : B : A, B has `public new string Tag` over A's `public object Tag`, C does not redeclare Tag). Validating C.Tag: DeclaredOnly lookup on C returns null (C declares nothing) -> the FlattenHierarchy fallback runs against C, whose inherited candidate set is {B.Tag string, A.Tag object} = two same-name/different-signature properties -> GetProperty re-throws AmbiguousMatchException, the exact bug the PR claims to fix. The throw occurs synchronously inside OnFieldChanged before the cache write (line 382), so nothing is cached; every subsequent NotifyFieldChanged for that field re-throws. Unhandled in the OnFieldChanged event path -> in Blazor Server the circuit is torn down; the form session dies on each keystroke to that field. The fix covers direct/leaf shadows (DeclaredOnly finds them) but leaves the inherited-shadow-leaf shape live. Not in the test matrix (DeepDerivedModel redeclares Tag at the leaf; no empty subclass of a shadowing base is tested).",
    "fix": "Wrap the FlattenHierarchy fallback in a try/catch (AmbiguousMatchException) and on catch walk the type hierarchy base-by-base with DeclaredOnly, taking the most-derived public instance property whose signature you accept (the runtime-type property). Alternatively enumerate GetProperties(Public|Instance) and pick the most-derived declared 'Tag' explicitly. Whichever path: ensure the chosen (possibly null) result is still written to _propertyInfoCache so the lookup cannot repeatedly throw.",
    "confidence": 75,
    "pre_existing": true
  },
  {
    "file": "src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs",
    "line": 372,
    "severity": "Low",
    "category": "other",
    "issue": "[ADV_ASSUMPTION] Original GetProperty(name) used default flags Public|Instance|Static; both new lookups are Instance-only, silently dropping Static. A model with a validated public static property ([Range] public static int X) that was validated on field-change before now resolves to null -> TryGetValidatableProperty returns false -> the field is silently skipped with no validation error surfaced (fails open). Invalid data on such a field now passes the field-level check unnoticed.",
    "fix": "If dropping static validation is intended (test IgnoresStaticProperty enshrines it), leave as-is but document the intentional behavior change in the method comment so it is not mistaken for an oversight. If not intended, add BindingFlags.Static to the DeclaredOnly (and fallback) lookup.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Scenario 2 (ambiguity within a single type)** — Two same-name public instance properties in one type is a C# compile error, so DeclaredOnly cannot hit a within-type ambiguity for ordinary properties. The only real shape is two indexers (both named `Item`) with different parameter types; that requires `FieldIdentifier.FieldName == "Item"`, which DataAnnotations field validation does not produce for indexed members. Also not introduced by this change (original threw identically). Fell apart at "no realistic validated FieldName reaches an indexer."

- **Scenario 3 (which property wins changes / attribute-set change)** — For same-signature `new` shadows, both original (cache collapses the base duplicate) and new (DeclaredOnly) return the derived property — identical result, no divergence. For different-signature shadows the original *threw* (returned nothing), so the new code returning the derived shadow is strictly the intended improvement, not a silently different valid property. I could not construct a shape where the original returned one valid non-throwing property and the new code returned a different one. Fell apart at "original was already throwing, not selecting a different property."

- **Scenario 5 (cache poisoning of the exception path)** — Real, but it is the amplifier of Finding 1, not an independent defect: it only manifests when the fallback throws (Finding 1's trigger). Folded into Finding 1 (uncached throw -> repeated re-throw on every NotifyFieldChanged). No separate finding.

## Probe Requests
No SDK available; the reflection outcome was reasoned statically from the identical mechanism that produced the fixed bug. When an SDK is available, this minimal probe confirms Finding 1 (expected: `GetProperty("Tag", Public|Instance|DeclaredOnly)` returns null on `Leaf`, and the `Public|Instance|FlattenHierarchy` fallback throws `AmbiguousMatchException`):

```csharp
class A { public object Tag { get; set; } }
class B : A { public new string Tag { get; set; } }
class Leaf : B { }   // does NOT redeclare Tag
// var d = typeof(Leaf).GetProperty("Tag", BindingFlags.Public|BindingFlags.Instance|BindingFlags.DeclaredOnly); // null
// typeof(Leaf).GetProperty("Tag", BindingFlags.Public|BindingFlags.Instance|BindingFlags.FlattenHierarchy);    // throws AmbiguousMatchException
```

---

Relevant file: `/home/decaf/code/decaf-claude/competition/benchmark/repos/2/src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs` (method lines 363-386; caller `OnFieldChanged` line 94, no exception guard; cache line 46). Test file `/home/decaf/code/decaf-claude/competition/benchmark/repos/2/src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs` — the multi-level test `DeepDerivedModel` (line 423) redeclares `Tag` at the leaf, so the inherited-shadow-leaf shape in Finding 1 is uncovered.

Headline: the fix is incomplete for the inherited-shadow-leaf hierarchy shape — a live `AmbiguousMatchException` path to the same class of bug the PR set out to eliminate (confidence 75, corroborated by the existing human review comment the orchestrator cited). The pre-existing flag is `true` because the leaf shape also threw under the original code, but the PR's stated scope ("Hidden Members") implies it should have been covered.
