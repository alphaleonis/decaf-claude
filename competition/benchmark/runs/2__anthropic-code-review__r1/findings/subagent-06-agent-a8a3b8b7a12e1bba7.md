# subagent agent-a8a3b8b7a12e1bba7

## Findings — Prior-PR feedback review for dotnet/aspnetcore#67075

Critical result up front: **this exact PR was already merged and then reverted in the real GitHub history**, for precisely the change under review. The local checkout's HEAD (`3b00cfca`) *is* the merge commit of #67075. Upstream `main` shows the very next relevant commit is `56326e66` — PR **#67712**, "Revert 'Fixed AmbiguousMatchException in DataAnnotationsValidator for Hidden Members (#67075)'", merged 2026-07-10T16:33:34Z, one day after #67075 merged (2026-07-09T06:42:30Z).

### Issue 1 — The `FlattenHierarchy` fallback does not fix multi-level hiding; this is the exact defect that caused the revert of this same PR

- **File:line (current PR):** `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:370-382` (method `TryGetValidatableProperty`)
```csharp
propertyInfo = cacheKey.ModelType.GetProperty(
    cacheKey.FieldName,
    BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly);

if (propertyInfo is null)
{
    propertyInfo = cacheKey.ModelType.GetProperty(
        cacheKey.FieldName,
        BindingFlags.Public | BindingFlags.Instance | BindingFlags.FlattenHierarchy);
}
```
- **Why flagged:**
  1. PR **#67712** (the revert) body states verbatim: *"#67075's `DeclaredOnly` → `FlattenHierarchy` fallback in `TryGetValidatableProperty` doesn't actually fix the `AmbiguousMatchException` it targeted — `FlattenHierarchy` doesn't flatten instance members, so hiding at an intermediate base type still throws. It also silently drops validation attributes depending on which hierarchy level resolves, with no diagnostic, and adds a third property-resolution policy inconsistent with `PropertyHelper.GetVisibleProperties` and `Microsoft.Extensions.Validation`'s `TryFindProperty`."*
  2. Reviewer **Youssef1313** posted an inline comment on this exact PR (id 3549541503, on `EditContextDataAnnotationsExtensions.cs:378`, `2026-07-09T06:58:15Z` — 16 minutes *after* the PR had already merged): *"FlattenHierarchy is only relevant for statics IIRC. And this code can still throw if the previous call returned null and we get into here with some shadowing member in a base type."* This concern was never addressed in the diff — it is the code exactly as currently written.
  3. [Inference, corroborated by both sources above] `BindingFlags.FlattenHierarchy` only affects visibility of **static** members up the hierarchy per .NET docs; it changes nothing about instance-member ambiguity. When the fallback `GetProperty(name, Public|Instance|FlattenHierarchy)` runs, it is behaviorally identical to the *original*, unguarded `GetProperty(name)` call for instance properties — meaning if a property is hidden with `new` at an intermediate level that is *not* the runtime (`cacheKey.ModelType`) type itself (e.g., `A.X` hidden by `B.X`, with `C : B` not redeclaring `X`), the fallback reproduces the original `AmbiguousMatchException` uncaught. I could not execute a live repro in this sandbox (no `dotnet` CLI available), so this mechanism claim rests on the cited maintainer comment and the revert PR's own description, not my own execution.
  4. The current PR's added test suite does not cover this scenario: `ValidatesPropertyHiddenAtMultipleInheritanceLevels` uses `DeepDerivedModel`, which *itself* redeclares `Tag` via `public new int Tag`, so the first `DeclaredOnly` lookup succeeds directly and the buggy fallback path is never exercised. There is no test where the queried/runtime type does not declare the field itself but an intermediate ancestor hides it — exactly the gap Youssef1313 pointed out.

### Issue 2 — The approach is inconsistent with the codebase's established, precedented pattern for resolving hidden/shadowed members

- **File:line (current PR):** same location, `EditContextDataAnnotationsExtensions.cs:363-386`.
- **Why flagged:** The revert PR explicitly calls out inconsistency with two other in-repo mechanisms that already solve this correctly:
  - `Microsoft.Extensions.Validation`'s `ValidatableTypeInfo.TryFindProperty` (`src/Validation/src/ValidatableTypeInfo.cs:84-114`) walks the type hierarchy one level at a time (`FindLocalMember` at each type, then `Type.BaseType`), stopping at the first (most-derived) declaring type that has the member — this is functionally the "walk up and take the most-derived declaration" approach that reviewer **ilonatommy** originally proposed as an alternative in their first comment on #67075 (`2026-07-07T07:32:23Z`, quoted in the review data), which the PR author did not adopt.
  - `PropertyHelper.GetVisibleProperties` (`src/Shared/PropertyHelper/PropertyHelper.cs:394-451`) explicitly documents excluding "properties defined on base types that have been hidden by definitions using the `new` keyword," filtering by `DeclaringType == type` at each hierarchy level.
  - Also relevant: sibling PR **#67455** ("Fix ambiguous hidden-property lookup in validation," merged 2026-06-30, before #67075) fixed the same class of bug in `src/Validation/src/ValidatablePropertyInfo.cs` and the source generator by switching bare `GetProperty(name)` calls to `GetProperty(name, Instance|Public|DeclaredOnly)` **only** — no `FlattenHierarchy` fallback — because in that code the cache key already tracks the specific declaring type per hierarchy level (from compile-time generation), rather than falling back to a hierarchy-flattened, ambiguity-prone lookup.
  - Net effect: the current PR introduces a third, ad hoc resolution policy that neither matches the walk-the-hierarchy convention (`TryFindProperty`) nor the exclude-by-DeclaringType convention (`GetVisibleProperties`), and it's the one already shown not to work.

### Issue 3 — Silent attribute-dropping / non-deterministic resolution depending on hierarchy level (no diagnostic)

- **File:line (current PR):** `EditContextDataAnnotationsExtensions.cs:370-382`, plus the enshrining test `ValidatesPropertyHiddenAtMultipleInheritanceLevels` mentioned above.
- **Why flagged:** Per the revert PR body: *"It also silently drops validation attributes depending on which hierarchy level resolves, with no diagnostic."* In the two-level-hiding scenario that DOES pass through `DeclaredOnly` cleanly (the runtime type declares the hidden member directly), the resolution is well-defined; but the moment there's ambiguity *above* the runtime type, the code either throws (Issue 1) or — depending on exact hierarchy shape not covered by current tests — could resolve to an unintended property whose attributes silently differ from what the caller expects, with no exception or log to signal it. The revert PR notes it removed "the tests and model classes added by #67075, including the one that enshrined the silent attribute-dropping behavior as expected," implying the reviewers considered at least one of the added tests to codify buggy/undesirable behavior rather than guard against it.

### Not flagged as new issues (informational)
- The thread-safety comment ("No need to lock, because it doesn't matter if we write the same value twice" — line 381) is unchanged from the pre-existing code and was not challenged in any prior review; no prior-PR feedback contradicts it.
- Static-property and internal-property handling (`IgnoresStaticProperty`, existing `ThisWillNotBeValidatedBecauseItIsInternal` test) match existing conventions and were not subject to any prior criticism found.

### Bottom line
This is not merely "similar" prior feedback — it is feedback on the identical diff that led to an actual revert (#67712) the day after merge. The current PR reintroduces the exact reverted code verbatim (confirmed by diffing against `gh pr diff 67712`, whose reverted lines match the current file content), meaning the unresolved review comment from Youssef1313 and the rationale in the revert PR apply directly and should block merging again until the fallback path is replaced with a hierarchy-walk (matching `ValidatableTypeInfo.TryFindProperty`) or a `GetVisibleProperties`-style declaring-type filter.
