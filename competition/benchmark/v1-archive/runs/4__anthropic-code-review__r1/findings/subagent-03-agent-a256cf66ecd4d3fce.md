# subagent agent-a256cf66ecd4d3fce

## Summary

**What:** PR #61928 fixes JSX language variant handling in TypeScript's service layer (`Strada`). When rescanning JSX/TSX files to build child node trees, the service was using the standard language variant instead of the JSX variant, causing tokens like `</div>` to be split into separate tokens (`<`, `/`, `div`, `>`) instead of recognized as the proper closing tag syntax (`</`, `div`, `>`). This broke completions tests like `tsxCompletionOnClosingTagWithoutJSX1`.

**Why:** Corsa (the new compiler service) creates scanners with the correct language variant automatically. Strada reuses a global scanner for efficiency but wasn't propagating the source file's language variant, causing divergent behavior between the two systems.

---

## Files Changed

1. **src/compiler/types.ts** — Added optional `languageVariant?: LanguageVariant;` field to `SourceFileLike` interface
2. **src/services/services.ts** — Modified `createChildren()` to read the language variant from `sourceFile` and set it on the scanner before scanning
3. **src/services/completions.ts** — Updated 4 code paths to use `SyntaxKind.LessThanSlashToken` instead of `SyntaxKind.SlashToken` for JSX closing tags
4. **src/services/utilities.ts** — Fixed `isInsideJsxElementOrAttribute()` to check `LessThanSlashToken` and added `LessThanSlashToken` to the traversal condition in `isInsideJsxElement()`
5. **tests/baselines/reference/api/typescript.d.ts** — Updated public API type definitions to include the new `languageVariant` field
6. **tests/cases/fourslash/syntacticClassificationsJsx1.ts** — Updated expected classification for JSX closing tags (`<` + `/` → `</`)
7. **tests/cases/fourslash/syntacticClassificationsJsx2.ts** — Updated expected classification for JSX closing tags

---

## Notable Context

- **Author:** Gabriela Araujo Britto (@gabritto)
- **Motivation:** Aligning Strada service behavior with Corsa to prevent test failures and ensure consistent JSX/TSX token classification across the compiler pipeline
- **Linked to:** Internal Corsa/Strada service alignment work (not explicitly linked to a GitHub issue in the PR body)
