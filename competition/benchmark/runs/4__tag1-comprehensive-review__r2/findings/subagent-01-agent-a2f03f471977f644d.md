# subagent agent-a2f03f471977f644d

Both classifier baselines confirm the intended `</` single-token behavior. I have completed a thorough sweep.

## Adversarial Review

### Summary

The token-kind sweep is, on inspection, complete and internally consistent: every JSX closing-tag `<` site in `completions.ts`/`utilities.ts` was migrated to `LessThanSlashToken` while opening-tag `<` (`LessThanToken`) and self-closing `/>` (`SlashToken`) were correctly left alone, and the untouched `breakpoints.ts` site converges to the identical breakpoint span for both token kinds. The behavior change is exercised by existing regression tests (`tsxCompletionOnClosingTag1/2`, `jsxBraceCompletionPosition`, and the two updated classifier baselines). The two genuine gaps are outside the specialist lanes: a **new public-API field shipped with zero documentation**, and a **shared mutable scanner whose newly-added `languageVariant` state is not restored on exception**.

### Findings

#### Medium

- **[docs]** New public API member `SourceFileLike.languageVariant` ships undocumented — `src/compiler/types.ts:4291`
  - **What's wrong/missing:** The field is added to `SourceFileLike` with no JSDoc and, unlike its two sibling members (`lineMap` and `getPositionOfLineAndCharacter`, both `@internal`), no `@internal` tag — so it lands in the public `tests/baselines/reference/api/typescript.d.ts` surface (confirmed in the diff). `Node.getChildren(sourceFile?: SourceFileLike)` is itself public, so an external caller that constructs a `SourceFileLike` and calls `getChildren` now has a behavior-affecting knob (JSX vs. Standard tokenization) with nothing telling them it exists, what the default is, or that they must set it to get correct `.tsx` scanning. Its only in-repo consumer is the internal `createChildren`.
  - **Why it matters:** Public API additions to the TypeScript compiler are effectively permanent commitments. Regenerating the api baseline makes the test pass but does not decide intent. If it was meant to be internal, the `@internal` tag was forgotten and the surface leaked; if it was meant to be public, it is a public contract with no documentation.
  - **Fix:** Decide intent explicitly. If internal-only, add `/** @internal */` to match the siblings. If public, add a doc comment stating who sets it, the `LanguageVariant.Standard` default, and that it controls JSX close-tag tokenization in `getChildren`.
  - **Confidence:** 78/100

- **[other]** Shared singleton scanner's new `languageVariant` mutation is not restored on exception — `src/services/services.ts:509`–`530`
  - **What's wrong/missing:** `createChildren` now mutates the module-level shared `scanner` (defined `export const scanner` in `src/services/utilities.ts:391`) via `setLanguageVariant(JSX)` and restores it with `setLanguageVariant(LanguageVariant.Standard)` at line 530 — but not inside a `try/finally`. If `node.forEachChild(...)` or `addSyntheticNodes` throws (e.g., the `Debug.fail` at line 544, or a corrupt node), the reset is skipped and the shared scanner is left in JSX variant. Other consumers of the *same* shared scanner do not set the variant and implicitly assume Standard: `src/services/preProcess.ts:338` (`scanner.setText(sourceText)` only) and `src/services/completions.ts:1898-1900` (`setText`/`resetTokenState`/`scan` only). Before this PR the variant was an invariant (never mutated); this PR weakens it to a mutate-and-restore that is not exception-safe.
  - **Why it matters:** In JSX variant the scanner merges `</` and admits `-`/`:` in identifiers (`scanner.ts:981`), so a leaked variant would silently change tokenization for import pre-processing and the `as`-keyword completion check. `createChildren` self-heals on its next call, so the window is narrow (an exception in `createChildren` followed by one of those consumers before the next `getChildren`), but the teardown guarantee is genuinely missing. The pre-existing `setText(undefined)` reset shares the non-`finally` weakness, but text is re-set by every consumer, whereas variant is not.
  - **Fix:** Wrap the scan body in `try { ... } finally { scanner.setText(undefined); scanner.setLanguageVariant(LanguageVariant.Standard); }`. (Rejected alternative: give `preProcess`/`completions` their own scanners like `classifier.ts`/`organizeImports.ts` already do — cleaner long-term but a larger change than this PR's scope.)
  - **Confidence:** 76/100

#### Low

- **[docs]** No comment explains the set/reset of `languageVariant` in `createChildren` — `src/services/services.ts:509`,`530`. The reset to `Standard` is non-obvious; it exists only because `scanner` is a shared exported singleton. A future maintainer will not know why it is there and may delete it. (Prose-level; confidence ~72, below the json threshold.)
- **[lint]** The classifier test diffs re-wrote four unrelated lines from LF to CRLF (`src/../syntacticClassificationsJsx1.ts`, hunk 2), spreading mixed line endings. Likely an editor artifact; surrounding lines were already CRLF, so possibly intentional normalization. (Prose-level; low confidence it is a real problem.)

### Undocumented-but-intentional divergence worth a note

`src/services/utilities.ts` now has three sibling checks for the JSX close-tag `</`: line 1892 (`JsxClosingElement`) migrated to `LessThanSlashToken`, while lines 1875 (`JsxText`) and 1880 (`JsxExpression`) were deliberately left as `LessThanToken`. I verified this is *not* a missed site: markers 5/6/7 of the unchanged `jsxBraceCompletionPosition.ts` exercise the JsxText/JsxExpression error-recovery paths, and the PR left that baseline untouched, which is strong evidence those checks still fire (they hit different, malformed-JSX token shapes than the well-formed `JsxClosingElement` path). Caveat: I could not build/run the suite to observe the tokens directly, so this rests on the test's continued passing. The divergence is undocumented — a comment noting that only the well-formed close tag re-scans to `LessThanSlashToken` would prevent a future "consistency fix" from breaking the error-recovery cases.

### Most Critical Gap

The `SourceFileLike.languageVariant` field is now permanently in the public `typescript.d.ts` surface with no documentation and no `@internal` decision — either an accidental API leak or an undocumented public contract, and either way harder to walk back after release than to get right before merge.

### Positive Observations

- The `SlashToken`/`LessThanToken` → `LessThanSlashToken` sweep across `completions.ts` and `utilities.ts` is complete and internally consistent (closing `</` migrated; opening `<` and self-closing `/>` correctly preserved at 3537, 4834, 4843, 5804).
- `getChildren` defaults `sourceFile` to `getSourceFileOfNode(this)`, and the parser populates `SourceFile.languageVariant` (`parser.ts:2009`), so the fix takes effect for real source files rather than silently defaulting to Standard.
- `breakpoints.ts:323` (untouched) provably converges to the same `spanInNode(node.parent)` result for both the old and new token kinds — no silent breakpoint regression.
- Formatting is insulated: it uses dedicated `standardScanner`/`jsxScanner` instances (`formattingScanner.ts:25-26`) rather than the shared `getChildren` token stream.
- The scanner state is reset symmetrically (both text and variant) on the normal path, and the change is covered by pre-existing tests without requiring hand-edited baselines beyond the two classifier files.

```json-findings
[{"severity":"Medium","confidence":78,"agent":"adversarial-general","category":"docs","file":"src/compiler/types.ts","line":4291,"finding":"New member `languageVariant?: LanguageVariant` added to `SourceFileLike` with no JSDoc and, unlike its two sibling members which are `@internal`, no `@internal` tag — so it leaks into the public typescript.d.ts surface (confirmed in the api baseline diff). `Node.getChildren(sourceFile?: SourceFileLike)` is public, so external callers now have an undocumented, behavior-affecting knob (JSX vs Standard tokenization) with no doc on who sets it or its default. Only in-repo consumer is internal createChildren.","remediation":"Decide intent: if internal-only, add `/** @internal */` to match the sibling members; if intentionally public, add a doc comment describing its purpose, the LanguageVariant.Standard default, and that it controls JSX close-tag tokenization in getChildren.","source":"adversarial-general"},{"severity":"Medium","confidence":76,"agent":"adversarial-general","category":"other","file":"src/services/services.ts","line":530,"finding":"createChildren mutates the module-level shared scanner (export const scanner in utilities.ts:391) with setLanguageVariant(JSX) and restores it with setLanguageVariant(Standard) at line 530, but not inside try/finally. If forEachChild or addSyntheticNodes throws (e.g. Debug.fail at line 544), the reset is skipped and the shared scanner is left in JSX variant. Other consumers of the same shared scanner assume Standard and never set the variant: preProcess.ts:338 (setText only) and completions.ts:1898-1900. In JSX variant the scanner merges `</` and admits `-`/`:` in identifiers, so a leaked variant can silently mis-tokenize import pre-processing and the `as`-keyword completion check. Before this PR the variant was an unmutated invariant.","remediation":"Wrap the scan body in try/finally so both scanner.setText(undefined) and scanner.setLanguageVariant(LanguageVariant.Standard) always run, even on exception.","source":"adversarial-general"}]
```
