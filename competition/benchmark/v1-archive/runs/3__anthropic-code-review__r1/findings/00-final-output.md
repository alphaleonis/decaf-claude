Pipeline complete. Here is the full result. **Nothing was posted to GitHub** — this is terminal-only output as you instructed.

---

## Code-review run summary — dotnet/runtime PR #127146

**"Handle canonical types in casting logic"** by MichalStrehovsky · state: **MERGED** (2026-04-21) · CLAUDE.md files in repo: **none**

Pipeline: eligibility check → CLAUDE.md discovery (none exist) → PR summary → 5 parallel Sonnet reviewers (conventions / shallow-bug / git-history / prior-PR-comments / code-comments) → Haiku confidence scoring → filter at ≥80.

### Candidate issues and scores

| # | Issue | Score | Kept? |
|---|-------|------:|:-----:|
| 1 | Canon-equivalence wired into the shared `CanCastTo` API, miscompiling R2R shared-generic casts | **100** | ✅ |
| 2 | `NormalizeInstantiation()` applied to `MakeGenericType` path but not `MakeGenericMethod` | 15 | ❌ |
| 3 | `NonCanon` stub naming vs. repo's established `Dummy` convention | ~25 (style, no CLAUDE.md) | ❌ |
| 4 | Unused `using System.Diagnostics;` in `TypeSystemConstraintsHelpers.NonCanon.cs` | <25 (compiler/linter-caught) | ❌ |
| 5 | Test comment says "contravariant" and "invariant" for the same arg position | <25 (nitpick) | ❌ |

Issue #2 was downgraded because the **accepted** replacement fix (PR #129278) makes the exact same one-sided choice, so the asymmetry is deliberate. Issues #4/#5 fall into explicitly-excluded false-positive categories.

---

## The review I would post (1 issue passes the ≥80 filter)

### Code review

Found 1 issue:

1. Canon-equivalence checks were wired directly into the general-purpose `CanCastTo` (`CanCastToInternal`), whose `true` result is trusted by the JIT (`CorInfoImpl.compareTypesForCast`), `DevirtualizationManager`, `MetadataVirtualMethodAlgorithm`, and `ILImporter` to mean "this cast must succeed for every concrete instantiation." The new rule makes `I<__Canon>.CanCastTo(I<object>)` return `true` for the non-variant `I<T>`, so crossgen2/R2R folds `isinst`/cast checks to always-succeed and miscompiles shared generic code. Canon-wildcard semantics belong in a separate entry point used only by constraint-checking — which is exactly what the accepted fix ([#129278](https://github.com/dotnet/runtime/pull/129278)) does via a new `CanCastToWithCanon`. Confirmed by history: this PR was reverted two days after merge in [#127301](https://github.com/dotnet/runtime/pull/127301), closing the R2R regression [#127259](https://github.com/dotnet/runtime/issues/127259) (`JIT/opt/Casts/shared_Casts` failing on every R2R leg). (bug due to `CanCastToInternal` gaining `if (IsCanonicalCastTarget(thisType, otherType)) return true;`)

https://github.com/dotnet/runtime/blob/7bba2205c2a75e4364dc32dc79cc91fae13791af/src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.cs#L173-L179

Related call sites polluted by the same change (same root cause, same file):
- `CanCastToNonVariantInterface` — https://github.com/dotnet/runtime/blob/7bba2205c2a75e4364dc32dc79cc91fae13791af/src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.cs#L425-L434
- `CanCastByVarianceToInterfaceOrDelegate` — https://github.com/dotnet/runtime/blob/7bba2205c2a75e4364dc32dc79cc91fae13791af/src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.cs#L476-L478
- `CanCastToClass` — https://github.com/dotnet/runtime/blob/7bba2205c2a75e4364dc32dc79cc91fae13791af/src/coreclr/tools/Common/TypeSystem/Common/CastingHelper.cs#L551-L553

---

**Note on eligibility:** the skill's gate would normally stop here (the PR is already merged, so there is nothing to post). Since you asked for terminal-only output, I ran the full analysis and printed the finding above rather than posting. The finding is not merely hypothetical — it's confirmed by the PR's own revert (#127301) and its issue (#127259).
