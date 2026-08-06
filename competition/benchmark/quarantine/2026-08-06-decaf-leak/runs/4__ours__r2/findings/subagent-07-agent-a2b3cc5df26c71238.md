# subagent agent-a2b3cc5df26c71238

## Findings

```json
[
  {
    "file": "src/services/completions.ts",
    "line": 3511,
    "severity": "Medium",
    "category": "type-safety",
    "issue": "[TS_TYPES] Case label changed from SlashToken to LessThanSlashToken, but the guard `currentToken.parent.kind === SyntaxKind.JsxSelfClosingElement` can never be true for a LessThanSlashToken, making the whole case arm dead code and silently dropping the original self-closing-element 'Fix location' behavior.",
    "fix": "Verified in src/compiler/parser.ts: `parseJsxClosingElement`/`parseJsxClosingFragment` are the only producers of `LessThanSlashToken` (lines 6337-6356), and both build a `JsxClosingElement`/`JsxClosingFragment` node, never `JsxSelfClosingElement`. Self-closing elements consume a separate `SlashToken` before `>` in `parseJsxOpeningOrSelfClosingElementOrOpeningFragment` (line 6215) and that token's parent (via `addSyntheticNodes`/`createNode(token, pos, textPos, parent)` in src/services/services.ts:534-553) is the `JsxSelfClosingElement`. So `LessThanSlashToken` structurally can only ever have `JsxClosingElement`/`JsxClosingFragment` as parent — the `case SyntaxKind.LessThanSlashToken:` guard checking for `JsxSelfClosingElement` is unreachable. This case should have been left as `SyntaxKind.SlashToken` (self-closing `/` is unaffected by the JSX-variant fix, unlike the closing-tag `/` which merged into the new digraph token), restoring the original intent of refining `location` to the self-closing element's trailing slash token.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/services/services.ts",
    "line": 507,
    "severity": "Medium",
    "category": "type-safety",
    "issue": "[TS_TYPES] `languageVariant` is derived only from `sourceFile?.languageVariant ?? LanguageVariant.Standard`, unlike the source text on the next line which falls back to `node.getSourceFile()` when `sourceFile` is absent/lacks the field. Since `languageVariant` was added as an *optional* field on the loosely-typed `SourceFileLike` (src/compiler/types.ts:4291), any caller of the public `Node.getChildren(sourceFile: SourceFileLike)` API that passes a plain object satisfying `SourceFileLike` (rather than a real compiler `SourceFile`, which always has the field populated) for a JSX/TSX node gets silently scanned with `LanguageVariant.Standard` — reproducing the exact `</div>` mis-tokenization bug this PR set out to fix, but scoped to any external/lightweight `SourceFileLike` caller instead of the internal one that was fixed.",
    "fix": "Mirror the text-derivation fallback: `const languageVariant = sourceFile?.languageVariant ?? (sourceFile ? LanguageVariant.Standard : node.getSourceFile().languageVariant);` or simply always derive from `(sourceFile || node.getSourceFile())` for both text and languageVariant so the two never diverge.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/services/services.ts",
    "line": 529,
    "severity": "Low",
    "category": "resource-management",
    "issue": "[TS_MUTATION] `scanner.setLanguageVariant(LanguageVariant.Standard)` resets the module-level shared `scanner` singleton (exported from src/services/utilities.ts:391) after use, but it is not wrapped in try/finally. If `node.forEachChild(processNode, processNodes)` throws mid-traversal, the scanner is left with `LanguageVariant.JSX` set for any later reuse before the next `createChildren` call re-initializes it.",
    "fix": "Wrap the scan body in try/finally so `scanner.setText(undefined); scanner.setLanguageVariant(LanguageVariant.Standard);` always runs, restoring the shared scanner's state even on exception. Note this mirrors a pre-existing gap (the `scanner.setText(undefined)` reset on the line above was already not exception-safe before this PR); this change adds a second piece of state to the same unprotected reset rather than introducing a wholly new class of bug.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- `src/services/completions.ts:1598` (`getJsxClosingTagCompletion` ancestor allow-list) — `SlashToken` → `LessThanSlashToken` swap verified correct: `LessThanSlashToken`'s parent is always `JsxClosingElement`, and `findAncestor` walking from a leaf token through this allow-list up to `JsxClosingElement` remains sound. No regression.
- `src/services/completions.ts:3521` (`switch(parent.kind) case JsxClosingElement: if (contextToken.kind === LessThanSlashToken)`) — correct and reachable; `contextToken.parent === JsxClosingElement` and `contextToken.kind === LessThanSlashToken` co-occur exactly when the previous token is the closing tag's `</`. Distinct from the dead branch at line 3511 (different guard: `parent.kind` of the *containing* switch vs. `currentToken.parent.kind` in the "Fix location" switch).
- `src/services/completions.ts:5808` (`isValidTrigger` case `"/"`) — correctly scoped to `isJsxClosingElement(contextToken.parent)`; self-closing `/` was never a valid trigger character path here pre- or post-fix, so the `LessThanSlashToken` swap is a faithful match to the new tokenization with no behavior loss.
- `src/services/utilities.ts:1892` (`isInsideJsxElementOrAttribute`, `<div>|</div>` case) — `LessThanToken` → `LessThanSlashToken` swap is correct; pre-fix, `</div>`'s first synthesized token was a standalone `<` (`LessThanToken`) due to missing JSX variant; post-fix it's the digraph `LessThanSlashToken`. Parent is `JsxClosingElement` in both cases.
- `src/services/utilities.ts:1937` (`isInsideJsxElement` traversal allow-list) — `LessThanSlashToken` added while `SlashToken` retained; correct, since `SlashToken` is still needed for self-closing elements' trailing slash and `LessThanSlashToken` now needs separate handling for closing tags — these are two genuinely distinct tokens post-fix, not a duplicate/redundant addition.
- `src/compiler/types.ts:4291` (`languageVariant?: LanguageVariant` added to `SourceFileLike`) — additive optional field, does not itself introduce unsoundness (covered instead by the fallback-derivation finding above, at the one call site that consumes it).
- Reachability of the `sourceFile === undefined` branch through the public `Node.getChildren()` API — traced that `getChildren(sourceFile: SourceFileLike = getSourceFileOfNode(this))`'s default parameter and `createChildren`'s internal `node.getSourceFile()` fallback both resolve via the identical `getSourceFileOfNode` parent-walk on the same node, so for the *sole* internal caller of `createChildren` they can't diverge — ruled out as a live internal defect and re-scoped the finding to external/`SourceFileLike`-typed callers instead (see finding above).
- Scanner-state leak's real-world exploitability — the only other consumer of the shared `scanner` singleton that doesn't itself call `setLanguageVariant` (`src/services/completions.ts:1898`, scanning for `AsKeyword`/`Identifier` in a named-import clause) never scans JSX-sensitive characters, so a leaked JSX variant wouldn't currently produce an observable wrong token there — kept the try/finally finding at Low severity rather than escalating it.
