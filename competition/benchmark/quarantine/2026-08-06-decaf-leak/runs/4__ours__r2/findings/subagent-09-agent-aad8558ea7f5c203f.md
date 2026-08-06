# subagent agent-aad8558ea7f5c203f

## Findings

I traced every `.getChildren(x)/.getFirstToken(x)/.getLastToken(x)` call with an explicit `SourceFileLike` argument, and found **one confirmed synthetic `SourceFileLike` that reaches these calls without `languageVariant`**, forming a real bug chain:

**Root construction — `src/services/textChanges.ts:1339-1344`** (inside `getFormattedTextOfNode`):
```ts
const file: SourceFileLike = {
    text,
    getLineAndCharacterOfPosition(pos) {
        return getLineAndCharacterOfPosition(this, pos);
    },
};
const changes = formatting.formatNodeGivenIndentation(node, file, targetSourceFile.languageVariant, initialIndentation, delta, ...);
```
This synthetic object has only `text` and `getLineAndCharacterOfPosition` — **no `languageVariant`, no `lineMap`**. Note `targetSourceFile.languageVariant` is passed as a *separate* explicit parameter, giving the false impression the variant is handled.

**Propagation:**
- `formatNodeGivenIndentation` (`src/services/formatting/formatting.ts:437-450`) only uses the explicit `languageVariant` param for the raw token scanner (`getFormattingScanner(sourceFileLike.text, languageVariant, ...)`), but passes `sourceFileLike` itself (still missing `languageVariant`) down into `formatSpanWorker`.
- `formatSpanWorker` builds `new FormattingContext(sourceFile, ...)` (`formattingContext.ts:35`) storing that same synthetic object as `context.sourceFile`.
- **`src/services/formatting/rules.ts:921`**: `context.nextTokenParent.getFirstToken(context.sourceFile)` (inside `isSemicolonDeletionContext`) calls `getFirstToken` on a real `Node` using this synthetic, `languageVariant`-less `sourceFile`.
- That flows into `createChildren` (`src/services/services.ts:507`), which does `sourceFile?.languageVariant ?? LanguageVariant.Standard` — since the synthetic object has no `languageVariant`, it **always falls back to `Standard`**, ignoring the correct variant that was already known and passed separately.

**Impact**: `getFormattedTextOfNode`/`computeNewText` in `textChanges.ts` format arbitrary inserted/replaced nodes for any `ChangeTracker` edit, including in `.tsx` files (JSX-producing codefixes/refactors). If the printed node text contains JSX, the re-scan in `createChildren` mis-tokenizes it as Standard, risking wrong formatting decisions or the `Debug.fail("Did not expect ... to have an Identifier in its trivia")` crash in `addSyntheticNodes`.

Other candidates checked (`classifier.ts:1222`, `smartIndenter.ts:536/758`, `sourcemaps.ts:231` `createSourceFileLike`) all use real parsed `SourceFile`s or aren't JSX-relevant — not matches.
