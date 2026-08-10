All findings verified and line numbers confirmed. Note on one inter-agent dispute: the test-review agent claimed `IgnoresStaticProperty` "passes even on revert" because it assumed `Type.GetProperty(name)`'s default flags are `Public|Instance`. That's incorrect — the parameterless overload's defaults are `Public|Instance|Static`, so the old code *would* have found the static property. That test therefore does exercise the change, and I'm dropping that as a false positive.

Here is the consolidated review. **Per your instructions, nothing has been posted to GitHub — this is terminal-only output.** Below is exactly what I would post, in the skill's comment format.

---

### Code review

Found 1 primary issue (plus 1 related lower-severity point). No CLAUDE.md files exist in the repo root or the modified directories, so there were no project-specific conventions to check against.

**1. The fix does not fully eliminate `AmbiguousMatchException` — the `FlattenHierarchy` fallback can still throw it (regression vs. this PR's earlier try/catch iteration).**

The `DeclaredOnly` first pass only resolves member hiding when the **runtime/most-derived type itself** redeclares the `new` property. When a property is hidden at an *intermediate* ancestor and the leaf runtime type does not redeclare it — e.g. `A { object P } → B : A { new string P } → C : B { }`, validating a `C` instance's `"P"` — the `DeclaredOnly` call at L272-274 returns `null`, control reaches the fallback at L278-280, and `GetProperty(name, Public|Instance|FlattenHierarchy)` again sees two same-named, different-signature candidates (`B.P`, `A.P`) and throws the very `AmbiguousMatchException` this PR fixes. This is a regression relative to the intermediate commit (`c9ab4012`) in this same PR, whose `try/catch (AmbiguousMatchException)` swallowed it and returned `null`. No test covers the leaf-inherits-from-hidden-intermediate case (all hiding tests redeclare on the most-derived type). A maintainer (Youssef1313) raised exactly this on 2026-07-09, after the latest commit, and it is unaddressed: https://github.com/dotnet/aspnetcore/pull/67075#discussion_r3549541503

https://github.com/dotnet/aspnetcore/blob/3aa499ae7d2314f7bbf89a3232df8371cc351d2a/src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs#L275-L282

**2. (Lower severity, same lines) `BindingFlags.FlattenHierarchy` is inert here.** `FlattenHierarchy` only affects inheritance of *static* members; since `Static` is not in the flags, the fallback is functionally identical to `Public | Instance`. It still correctly finds ordinary inherited instance properties (why single-level inheritance works), but the flag is misleading. Same maintainer comment flags this.

https://github.com/dotnet/aspnetcore/blob/3aa499ae7d2314f7bbf89a3232df8371cc351d2a/src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs#L278-L281

🤖 Generated with [Claude Code](https://claude.ai/code)

---

### Notes not included in the postable review (below the confidence bar)

- **`MatchesPropertyByExactName` (test L209-219)** is a redundant, misnamed duplicate — its body is behaviorally identical to the first iteration of `ValidatesHiddenPropertiesWithPropertyCaching`, and despite its name it has no negative/case-insensitive case, so it doesn't actually prove exact-name matching. Real but minor (adds no coverage; not a false positive since it fails on revert).
- **`Static`-flag drop is intentional and benign.** Dropping `BindingFlags.Static` means static properties are no longer validated; this is a deliberate tightening, covered by `IgnoresStaticProperty`, and correct for instance-model validation.
- **Caching, trimming suppression (`IL2080`), and `MetadataUpdater`/`ClearCache` wiring** are all preserved correctly.
- **PR description is stale**: it says the fix "Added handling for AmbiguousMatchException [on exception, retried with DeclaredOnly]," describing the earlier try/catch approach, not the committed `DeclaredOnly` + `FlattenHierarchy` two-call form. Documentation-only, no code impact.

**Bottom line:** The change correctly fixes the common case (leaf type shadows a base property with `new`). The one substantive concern is Finding 1 — the fallback still throws `AmbiguousMatchException` for properties hidden at an intermediate ancestor when the leaf doesn't redeclare them, which is both untested and a regression against this PR's earlier guarded version. Suggested direction (per the maintainer and my agents): keep the `DeclaredOnly` result and walk `BaseType` manually on miss, or restore a `try/catch (AmbiguousMatchException)` around the fallback, and add a test for the leaf-inherits-hidden-intermediate case.
