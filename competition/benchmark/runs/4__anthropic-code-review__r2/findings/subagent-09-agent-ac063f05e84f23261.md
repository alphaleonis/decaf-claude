# subagent agent-ac063f05e84f23261

## PR Summary: Use jsx language variant for jsx file scanning in getChildren

**Title**: Use jsx language variant for jsx file scanning in getChildren

**Author**: Gabriela Araujo Britto (@gabritto)

**Purpose**: Fix JSX file scanning in Strada services by using the correct JSX language variant when reusing the global scanner in `getChildren()`. Previously, JSX/TSX files were scanned with the standard language variant instead of the JSX variant, causing incorrect tokenization (e.g., `</div>` was split into `<`, `/`, `div`, `>` instead of `</`, `div`, `>`). This caused test failures like `tsxCompletionOnClosingTagWithoutJSX1` in Corsa.

**Head commit SHA**: `da29c9991c881c0a3487a55ca8df6198fe2ac048`

---

## Code-Level Changes

**1. Type System (types.ts)**
- Added optional `languageVariant?: LanguageVariant;` property to `SourceFileLike` interface
- Allows source files to specify their language variant (JSX vs Standard)

**2. Scanner Configuration (services.ts - `createChildren` function)**
- Extracts `languageVariant` from the sourceFile (defaults to `LanguageVariant.Standard` if not provided)
- Calls `scanner.setLanguageVariant(languageVariant)` after `scanner.setText()` to configure the scanner with the correct variant before tokenizing
- Resets scanner back to `LanguageVariant.Standard` after scanning completes

**3. Token Kind Corrections (completions.ts)**
- Changed 4 locations where `SyntaxKind.SlashToken` was used to check for JSX closing tags to `SyntaxKind.LessThanSlashToken`
- Updates affect:
  - `getJsxClosingTagCompletion()` 
  - `getCompletionData()` (2 fixes)
  - `isValidTrigger()` trigger character logic
- When JSX variant is used, `</` is a single token (`LessThanSlashToken`), not two separate tokens

**4. Utility Updates (utilities.ts)**
- Changed token kind check in `isInsideJsxElementOrAttribute()` from `LessThanToken` to `LessThanSlashToken`
- Added `LessThanSlashToken` as additional condition in `isInsideJsxElement()` loop

**5. Test Baseline Updates (api/typescript.d.ts)**
- Updated TypeScript API reference to include the new `languageVariant?` property on `SourceFileLike`

---

## Files Changed

| File | Changes | Impact |
|------|---------|--------|
| src/compiler/types.ts | +1, -0 | Interface addition |
| src/services/completions.ts | +4, -4 | 4 token kind corrections |
| src/services/services.ts | +3, -1 | Scanner variant configuration logic |
| src/services/utilities.ts | +2, -1 | Token kind corrections |
| tests/baselines/reference/api/typescript.d.ts | +1, -0 | API reference update |
| tests/cases/fourslash/syntacticClassificationsJsx1.ts | +5, -5 | Closing tag tokenization expectations |
| tests/cases/fourslash/syntacticClassificationsJsx2.ts | +5, -5 | Closing tag tokenization expectations |

**Total: +21 additions, -16 deletions**

---

## Test Changes

Two test files (`syntacticClassificationsJsx1.ts` and `syntacticClassificationsJsx2.ts`) verify syntactic classifications for JSX:
- Tests now expect `</` to tokenize as a single `LessThanSlashToken` (via `c.punctuation("</")`) instead of two separate tokens
- This reflects correct JSX parsing when the JSX language variant is applied
- Tests cover both simple JSX (`<div>`) and namespaced JSX (`<div.name>`)
