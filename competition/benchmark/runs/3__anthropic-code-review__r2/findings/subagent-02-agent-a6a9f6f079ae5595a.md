# subagent agent-a6a9f6f079ae5595a

## Summary

The most important finding didn't come from a genuinely "previous" PR — it came from what happened to files right after this PR (#127146) merged. That history is directly on-point and is the strongest evidence I found.

**Note on method**: this repo is a shallow clone (2 commits only), so local `git log -- <path>` was unreliable — it listed commit `2102b6b5` for all three files, but `git show 2102b6b5 -- <paths>` proves that commit touches none of them. I instead used `gh api repos/dotnet/runtime/commits?path=...` to get the real GitHub history, which surfaced a critical chain of PRs.

## Critical finding: this exact PR was merged, broke CI, was reverted, and was redesigned

File-history lookup on all three files of interest shows the same sequence immediately following #127146:

```
9619cf56 Revert "Handle canonical types in casting logic" (#127301)
7bba2205 Handle canonical types in casting logic (#127146)   <- the PR under review / current repo HEAD
ee2a8a9d Handle canonical types in constraints checks (#129278)  <- later re-fix
```

- **#127146** (this PR) merged 2026-04-21.
- **Issue #127259** filed 2026-04-22: R2R/crossgen2 outerloop failures in `JIT/opt/Casts/shared_Casts` across every platform.
- **#127301** reverted #127146 on 2026-04-23 to resolve #127259.
- **#129278** (merged 2026-06-18) reintroduced the feature with a materially different design.

AndyAyersMS's root-cause analysis on issue #127259 (https://github.com/dotnet/runtime/issues/127259) is unambiguous:

> "This is a regression from #127146 ('Handle canonical types in casting logic')... `fromType.CanCastTo(toType)` is `I<__Canon>.CanCastTo(I<object>)`. Before #127146 that returned `false`; after #127146 it returns `true`, because the new `IsCanonEquivalent` check in `CanCastToNonVariantInterface` treats any `I<__Canon>` as matching `I<X>` for any reference type `X`... The canon-equivalence rule is correct for the dataflow/constraint-check scenario that #127146 targeted (#126604), but it violates the invariant `compareTypesForCast` depends on — namely that a true result from `CanCastTo` implies the cast must succeed for every concrete instantiation the shared code can see... A broader/cleaner long-term option is to scope the canon-equivalence additions in `CastingHelper.cs` to only the reflection/constraint-check code paths that need them (e.g., via an explicit `CanCastToWithCanonEquivalence` entrypoint), since `compareTypesForCast` is not the only consumer of `CanCastTo` — `DevirtualizationManager`, `MetadataVirtualMethodAlgorithm`, and `ILImporter.StackValue` also call it and have the same trust assumption."

**How this applies to the current change, concretely (verified against the repo checked out at HEAD == #127146):**

- `src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.cs:424-436` — `CanCastToNonVariantInterface` adds `|| IsCanonEquivalent(...)` unconditionally to the single public `CanCastTo`/`CanCastToInternal` path.
- `src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.cs:506-552` — `CanCastToClass` does the same at line 552.
- `src/coreclr/tools/Common/TypeSystem/Common/TypeSystemConstraintsHelpers.cs:76` and `:167` — these are the only call sites that actually *need* canon-equivalent behavior, but in the current PR they call the plain `CanCastTo`, which is now globally canon-permissive rather than scoped.
- Because there is no separate "canon-aware" entry point in this PR, every other consumer of the shared `CanCastTo` inherits the same over-permissive semantics without realizing it. I confirmed these other call sites still exist on the same `CanCastTo`:
  - `src/coreclr/tools/Common/JitInterface/CorInfoImpl.cs:2934,2946` (`compareTypesForCast` — this is literally the code path that broke)
  - `src/coreclr/tools/Common/Compiler/DevirtualizationManager.cs:97,133`
  - `src/coreclr/tools/Common/TypeSystem/Common/MetadataVirtualMethodAlgorithm.cs:783,878,907,994,1010,1167`
  - `src/coreclr/tools/ILVerification/ILImporter.StackValue.cs:303,305,483,504`

The eventual fix (#129278) confirms the diagnosis exactly: it splits `CastingHelper` into a generic `CastingHelper<T> where T : ICanonicalTypeCastingHandler`, adds an `INonCanonicalTypeCastingHandler` (canon-equivalence off — used by the public `CanCastTo`) and a `CanonicalTypeCastingHandler` (canon-equivalence on — used by a new, separate `CanCastToWithCanon`), and switches `TypeSystemConstraintsHelpers.cs` to call `CanCastToWithCanon` / `CanCastToConstraintWithCanon` instead of the shared `CanCastTo`. That is precisely the "explicit `CanCastToWithCanonEquivalence` entrypoint" AndyAyersMS's comment recommended.

## Secondary finding: this exact risk was raised (and only partly addressed) during #127146's own review

From the current PR's own review thread (`gh api repos/dotnet/runtime/pulls/127146/comments`):

> jkotas (on `System.Private.TypeLoader.csproj:120`): "Do we actually need the real CastingHelper.Canon.cs in the runtime type loader?"
> MichalStrehovsky: "Probably not right now. However, the runtime type system does use canonical forms, so it's just a question of whether canonical forms ever reach `CanCast`. It felt like an easier rule to make it 'if you include .Canon.cs file, you include .Canon.cs files'. I can make it include .NonCanon.cs here and we can fix the bug if this ever becomes a bug."

This exchange is about a different consumer (the NativeAOT runtime type loader) than the one that actually broke (crossgen2's `compareTypesForCast`), but it shows the reviewer and author both recognized — and explicitly deferred — the general risk that canon-aware casting changes could leak into consumers that assume strict, unscoped cast semantics. That's exactly the class of bug that materialized in #127259. Neither reviewer raised the broader "audit every `CanCastTo` consumer" concern before merge; it only surfaced from CI after the fact.

## Other prior PRs on these files

Genuinely prior (pre-#127146) history on these files (`#95602` whitespace, `#91788` variant casting fix, `#87899` type equivalence, `#85743` type-loader perf, `#72667`/`#74825` analyzer enablement, `#64259` ILVerify array-cast fix, `#50212`/`#44973` infra) has no review comments with applicable, unresolved guidance — I checked #91788 (closest in topic, "variant casting") and it has no PR body detail or inline review comments beyond the fix description. Nothing else in that older history bears on the canon-equivalence scoping problem.

## Bottom line

No genuinely *prior* PR left applicable unaddressed feedback beyond trivial style nits (unused usings, invalid C# syntax in a test, flagged and presumably fixed by Copilot's automated review comments on #127146 itself). But the file history *following* #127146 is directly and strongly applicable: this PR's core design decision (unscoped `IsCanonEquivalent` checks baked into the single shared `CanCastTo`) is the confirmed, documented root cause of a merge → revert → redesign cycle on these exact files, with the eventual fix (#129278) validating the precise architectural change (a separate canon-aware entry point) that would have avoided the regression.
