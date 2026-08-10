# subagent agent-aabb39184e94bc3f6

I have completed my investigation. Let me compile the findings.

## Code Review: PR #61928 "Use jsx language variant for jsx file scanning in getChildren"

**Reviewed:** the full diff (`/tmp/pr61928.diff`) plus surrounding source in `src/compiler/types.ts`, `src/services/services.ts`, `src/services/completions.ts`, `src/services/utilities.ts`, `src/services/classifier.ts`, `src/services/formatting/*`, and the two fourslash test baselines. I traced how `createChildren` re-scans tokens, which services consume those tokens, and audited every `SlashToken`/`LessThanToken` usage in `src/services` for JSX-closing relevance.

---

### Critical
None.

### Important

**1. `src/services/completions.ts:3511-3515` — `SlashToken → LessThanSlashToken` was wrongly applied to a self-closing-element case (unsatisfiable condition + lost behavior). Confidence ~85.**

```
case SyntaxKind.LessThanSlashToken:
    if (currentToken.parent.kind === SyntaxKind.JsxSelfClosingElement) {
        location = currentToken;
    }
```
A `LessThanSlashToken` (`</`) is only ever produced at the start of a **`JsxClosingElement`** (`</div>`), never inside a **`JsxSelfClosingElement`** (`<div />`). In a self-closing element the slash is preceded by the tag/attributes, so the scanner emits a plain `SlashToken` — and that is unchanged by the JSX language-variant fix (the merge into `</` only happens when `<` and `/` are adjacent). Therefore:
- The `if (currentToken.parent.kind === JsxSelfClosingElement)` guard is now **unsatisfiable** — this branch is dead.
- The original handling for the self-closing `/` (a genuine `SlashToken`) is **dropped**.

This is the one place where the blanket `SlashToken → LessThanSlashToken` replacement was over-applied. Contrast it with the correctly-paired sibling immediately below (line 3520-3521: `case JsxClosingElement` + `contextToken.kind === LessThanSlashToken`). **Fix:** revert this specific case back to `case SyntaxKind.SlashToken:` (self-closing slashes are not affected by this PR).

[Inference] Whether this produces a user-visible completions regression depends on whether `location` is already correct for self-closing elements via other paths; I could not confirm that without running the completions suite, and the PR adds no completions test covering it. Regardless, the condition is verifiably a dead/incorrect branch.

**2. `src/compiler/types.ts:4291` — new `languageVariant?` field is not marked `/** @internal */`, widening the public API. Confidence ~78 (judgment call).**

```
export interface SourceFileLike {
    readonly text: string;
    /** @internal */
    lineMap?: readonly number[];
    /** @internal */
    getPositionOfLineAndCharacter?(...): number;
    languageVariant?: LanguageVariant;   // <-- no @internal
}
```
The only consumer of this field is the internal `createChildren` (services.ts:507). Its two sibling optional members are both `/** @internal */`. Leaving `languageVariant` public expands the shipped surface — confirmed by the regenerated `tests/baselines/reference/api/typescript.d.ts` (line 5910), which now exposes it. If it is not intentionally public, add `/** @internal */` for consistency and to keep it out of the public `.d.ts`. (It is defensible to make it public so external callers of `node.getChildren(sourceFileLike)` over JSX text can opt in — worth confirming intent with maintainers.)

**3. `src/services/services.ts:507-530` — the language-variant reset is not exception-safe, and unlike the pre-existing stale-text case it can silently corrupt other consumers of the shared scanner. Confidence ~80 (low real-world trigger probability).**

```
scanner.setLanguageVariant(languageVariant);   // -> JSX
...
node.forEachChild(processNode, processNodes);
addSyntheticNodes(children, pos, node.end, node);
scanner.setText(undefined);
scanner.setLanguageVariant(LanguageVariant.Standard);   // reset skipped if the above throws
```
`addSyntheticNodes` can throw (`Debug.fail("Did not expect ... to have an Identifier in its trivia")`, services.ts:544), and `scanner.scan()` runs in the same region. If anything throws, the shared services scanner (`src/services/utilities.ts:391`, an exported singleton) is left in the **JSX** variant. This is materially worse than the analogous pre-existing missing `setText(undefined)`: the other shared-scanner consumers — `preProcess.ts` (line 338), `organizeImports.ts` (line 248), `completions.ts` (line 1898) — always call `setText` before scanning (so text self-heals) but do **not** set the language variant and assume it is `Standard`. A leaked JSX variant would silently mis-scan their input (e.g. treating `</` as `LessThanSlashToken`) until the next `createChildren` call resets it. **Fix:** wrap the body in `try { ... } finally { scanner.setText(undefined); scanner.setLanguageVariant(LanguageVariant.Standard); }`. Practical likelihood is low because `Debug.fail` is a "should never happen" path, but the asymmetry with the self-healing text makes it a genuine exception-safety gap this PR introduces.

---

### Verified correct / not issues (checked per your request)

- **`src/services/utilities.ts:1892`** (`LessThanToken → LessThanSlashToken`, `isInsideJsxElementOrAttribute`): correct. For `<div>|</div>`, `getTokenAtPosition` now returns the `</` (`LessThanSlashToken`) whose parent is `JsxClosingElement`. [Inference] One extremely narrow edge: a malformed closing tag with whitespace between `<` and `/` (e.g. `< /div>`) would leave a bare `LessThanToken` that the old check matched and the new one doesn't — malformed-input only, below reporting threshold.
- **`src/services/utilities.ts:1936-1937`** (`isInsideJsxElement`): correct and robust — `LessThanSlashToken` was **added** alongside the retained `SlashToken`, so both the self-closing `/` and the closing `</` are handled.
- **`src/services/completions.ts:1598, 3521, 5808`**: all three are genuine `JsxClosingElement` contexts; replacing `SlashToken` with `LessThanSlashToken` is correct given `getChildren` now emits `</`.
- **Completeness of the token audit:** every JSX-closing consumer of the re-scanned tokens was updated. The remaining `SlashToken` references are correctly left alone — `completions.ts:4834/4843` (opening/self-closing element `/`), `formatting/rules.ts:188-189/976` (self-closing), `classifier.ts:168/450` and `inferFromUsage.ts:795` (regex rescan / binary operator). `formatting.ts:737` (`SlashToken` under a `JsxClosingElement` container) is **not** in scope: the formatting layer uses its own dedicated `jsxScanner` (`formatting/formattingScanner.ts:26`, `LanguageVariant.JSX`), independent of `createChildren`.
- **`getChildren` no-arg path:** covered — `getChildren` (services.ts:462) defaults `sourceFile` to `getSourceFileOfNode(this)`, a real `SourceFile` carrying `languageVariant`, so JSX scanning applies even when called without an explicit argument. Minor internal inconsistency worth noting only: `createChildren` derives text from `sourceFile || node.getSourceFile()` but the variant solely from `sourceFile?.languageVariant ?? Standard`; harmless because the sole caller always passes a defined `sourceFile`.
- **Test-baseline line-ending change** (`syntacticClassificationsJsx1.ts` / `2.ts`, the "no-op looking" `c2` block): verified as a cleanup, not a defect. Those 4 lines were the only LF lines in otherwise all-CRLF files (`.gitattributes` uses `* -text`, so git preserves as committed); the change makes each file uniformly CRLF. The substantive baseline update (`c.punctuation("<"), c.punctuation("/")` → `c.punctuation("</")`) correctly reflects the new scanning.

### Minor note
- **Test coverage:** the behavioral `completions.ts` changes (closing-tag completion, `isValidTrigger`, and the self-closing "fix location" case in finding #1) are not exercised by any new/updated fourslash **completion** test — only syntactic-classification baselines were touched. Given finding #1, a completions regression test for both `</` closing-tag completion and the self-closing `<div /|>` position would be worthwhile.

---

### Summary
The core mechanism (setting the scanner's language variant from the source file in `createChildren`, and updating the closing-tag consumers from `SlashToken` to `LessThanSlashToken`) is sound and the closing-tag consumers were updated consistently. Three items warrant attention: **(1)** the change at `completions.ts:3511` was over-applied to a self-closing-element case, producing an unsatisfiable condition and dropping the original `SlashToken` handling — this should be reverted to `SlashToken`; **(2)** the new `SourceFileLike.languageVariant` field is public rather than `@internal` despite only internal use; and **(3)** the variant reset in `createChildren` is not exception-safe and can leak the JSX variant into other shared-scanner consumers that assume `Standard`. Items 1 and 3 are the ones I'd want addressed before merge; item 2 is a maintainer judgment call on public-API intent.
