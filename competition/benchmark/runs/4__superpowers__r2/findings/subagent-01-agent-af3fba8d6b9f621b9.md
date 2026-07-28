# subagent agent-af3fba8d6b9f621b9

I have completed my analysis. Let me verify one final detail: that the two updated fourslash tests are the only syntactic-classification tests affected, and confirm the memoization isn't invalidated by the variant change (already confirmed cache is keyed per node+sourceFile). I have enough to write the review.

## Code Review: "Use jsx language variant for jsx file scanning in getChildren (#61928)"

### Strengths

- **Correct root cause.** The core fix in `src/services/services.ts:507-509` is exactly right. `createChildren` re-scans source text to synthesize the punctuation/trivia token nodes that the parser doesn't store (e.g. the `</` of a `JsxClosingElement`, which `parseJsxClosingElement` consumes via `parseExpected(SyntaxKind.LessThanSlashToken)` at `parser.ts:6339` but never keeps as a node). The shared `scanner` (`utilities.ts:391`) defaults to `LanguageVariant.Standard`, and in Standard mode the scanner splits `</` into `LessThanToken` + `SlashToken` (`scanner.ts:2204-2212`), whereas JSX mode emits a single `LessThanSlashToken`. Threading `sourceFile.languageVariant` into the scanner makes `getChildren` classify JSX tokens the way the parser actually produced them.
- **Good scanner-state hygiene.** `services.ts:530` resets the shared scanner back to `LanguageVariant.Standard` after use, matching the existing `scanner.setText(undefined)` teardown. This matters because the same module-level scanner is used by many other utilities that rely on the Standard default. The reset value matches the scanner's construction default (`createScanner(...) = LanguageVariant.Standard`).
- **Consistent, non-breaking API addition.** `SourceFileLike.languageVariant?` (`types.ts:4291`) is optional and additive, and the real `SourceFile.languageVariant` is already public (`types.ts:4359`), so exposing it on the base interface is consistent. The `typescript.d.ts` baseline was regenerated correctly.
- **Companion token-kind updates are mostly correct.** The changes in `utilities.ts:1892` (`isInsideJsxElementOrAttribute`) and `completions.ts:3521`, `:5808`, `:1598` all target genuine *closing-tag* (`</`) contexts and correctly switch to `LessThanSlashToken`. `utilities.ts:1937` does the right thing by *adding* `LessThanSlashToken` while *keeping* `SlashToken`.
- **Tests updated to assert real behavior.** `syntacticClassificationsJsx1/2.ts` now expect `c.punctuation("</")` instead of `c.punctuation("<"), c.punctuation("/")`, which is the actual observable output of the fix. These are the only two JSX syntactic-classification tests; no other fourslash test still asserts the split-token form, so nothing is silently left stale.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)

**1. `src/services/completions.ts:3511` — `SlashToken` → `LessThanSlashToken` is the wrong substitution for the self-closing case.**

```ts
case SyntaxKind.LessThanSlashToken:            // was SlashToken
    if (currentToken.parent.kind === SyntaxKind.JsxSelfClosingElement) {
        location = currentToken;
    }
    break;
```

- **What's wrong:** A `JsxSelfClosingElement` (`<div />`) never contains a `LessThanSlashToken`. Its `/` is a standalone `SlashToken` — the parser explicitly does `parseExpected(SyntaxKind.SlashToken)` for self-closing elements (`parser.ts:6215`), and the JSX scanner only merges `</`, never `/>`. So after this change the branch is unreachable, and the previous handling that fixed `location` when the cursor is on the self-closing `/` is gone.
- **Why it matters:** Unlike the other four hunks (which target closing tags), this one targets the *self-closing* `/`, whose token kind was **not** affected by the scanning change. This looks like an over-broad find/replace of `SlashToken → LessThanSlashToken`. It's inconsistent with the sibling code that handles the same situation correctly: `tryGetContainingJsxElement` at `completions.ts:4833-4834` lists **both** `case LessThanSlashToken:` and `case SlashToken:` for `JsxSelfClosingElement | JsxOpeningElement`, and `utilities.ts:1937` also keeps `SlashToken` alongside the new `LessThanSlashToken`.
- **Impact:** [Inference] The user-visible effect may be partially masked because `tryGetContainingJsxElement` (called with `contextToken`, and still matching `SlashToken`) can recover the containing element downstream — which likely explains why CI passed. But the `location`-fix branch is now dead for its intended input, and there is no test covering it, so any regression here would be silent.
- **How to fix:** Revert this case to `case SyntaxKind.SlashToken:`, or handle both kinds (`case SyntaxKind.LessThanSlashToken:` / `case SyntaxKind.SlashToken:`) to mirror `completions.ts:4833-4834`. Please confirm whether dropping the self-closing `/` handling was intentional.

#### Minor (Nice to Have)

**2. `src/services/services.ts:507-508` — asymmetric source resolution.** `languageVariant` is read from `sourceFile?.languageVariant`, but the text is read from `(sourceFile || node.getSourceFile())`. In practice `getChildren`'s default parameter (`services.ts:462`, `= getSourceFileOfNode(this)`) means `sourceFile` is effectively always defined, so this is correct today. But the two lines read from different sources; resolving once is clearer and more robust if `createChildren` is ever reached with an undefined `sourceFile`:
```ts
const sf = sourceFile || node.getSourceFile();
const languageVariant = sf.languageVariant ?? LanguageVariant.Standard;
scanner.setText(sf.text);
```

**3. `src/services/services.ts:509-530` — variant reset is not exception-safe.** If `addSyntheticNodes` hits its `Debug.fail(...)` (`services.ts:544`), the scanner is left in JSX mode (and with text set). This mirrors the pre-existing `setText(undefined)` teardown (also not in a `finally`), so it's not a regression, and `Debug.fail` signals a "cannot happen" compiler invariant. Low priority, but a `try { ... } finally { scanner.setText(undefined); scanner.setLanguageVariant(LanguageVariant.Standard); }` would make the shared-scanner teardown robust.

**4. `src/compiler/types.ts:4291` — public vs. internal.** The new `languageVariant?` is added *without* `/** @internal */`, unlike its neighbors `lineMap` and `getPositionOfLineAndCharacter`. It's the only non-internal, non-`text` member of `SourceFileLike`. This is additive/non-breaking and consistent with `SourceFile.languageVariant` being public, but it's a permanent public-API commitment whose only consumer is internal (`createChildren`). Worth a conscious confirm that public (not `@internal`) is intended.

**5. Test diff noise.** The second hunk in each fourslash test (the `const c2 = classification("2020")` block) is a pure LF→CRLF line-ending normalization (the base file had mixed endings; the rest of the file is CRLF). Benign and arguably a cleanup, but unrelated to the fix and adds noise to the diff.

### Recommendations

- **Add completion coverage for the JSX punctuation changes.** The new tests only exercise *syntactic classification* of the closing `</`. None exercise the four `completions.ts` behavior changes: closing-tag completion trigger (`isValidTrigger`, `:5808`), `getJsxClosingTagCompletion` walk (`:1598`), the `JsxClosingElement` `contextToken` path (`:3521`), or the self-closing location-fix (`:3511`, issue #1). A couple of fourslash completion tests — one at a closing `</` and one inside a self-closing `<div /|>` — would lock in the intended behavior and would have surfaced issue #1.
- **Run the full fourslash + services suites** before merge (I did not execute them here — this was a static, read-only review). Static analysis says nothing else regresses, but issue #1's masking makes an actual completion-test run worthwhile.

### Assessment

**Ready to merge?** With fixes.

**Reasoning:** The central change (JSX language variant in `createChildren`, with proper scanner reset) is correct, minimal, and well-targeted, and the baselines/tests are consistent. The one substantive concern is `completions.ts:3511`, where `SlashToken` was replaced by `LessThanSlashToken` for a `JsxSelfClosingElement` — a token kind that can't occur there — dropping self-closing-`/` handling and diverging from the correct both-kinds pattern used elsewhere in the same file; revert it to `SlashToken` (or handle both) or confirm the removal was intentional.
