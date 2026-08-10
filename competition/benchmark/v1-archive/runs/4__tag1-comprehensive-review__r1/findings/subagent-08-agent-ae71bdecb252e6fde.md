# subagent agent-ae71bdecb252e6fde

## Summary

Fixes JSX/TSX tokenization in `createChildren()`: the shared scanner used for splitting a node into child tokens was reused via `scanner.setText()` without also setting its language variant, so `</div>` in a `.tsx` file was scanned as four standard-variant tokens (`<`, `/`, `div`, `>`) instead of three JSX-variant tokens (`</`, `div`, `>`). This broke tests like the JSX closing-tag completion scenario in Corsa. The fix threads the source file's `languageVariant` through to the scanner in `createChildren`, resets it to `Standard` afterward (since the scanner is shared/global), and updates the completions and utilities code that inspected `SlashToken`/`LessThanToken` to instead match the new `LessThanSlashToken` produced under the JSX variant.

**Type:** bugfix
**Effort:** 2/5 — Small, contained diff (+21/-16 across 7 files) that is mechanical once the root cause is understood, but touches scanner state management and adds a field to the public `SourceFileLike` interface, so it warrants a careful read despite the low line count.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| src/services/services.ts | Modified | `createChildren()` now sets the shared scanner's language variant from `sourceFile.languageVariant` (defaulting to `Standard`) before scanning, and resets it to `Standard` after, so JSX/TSX files scan `</` as a single `LessThanSlashToken` |
| src/services/completions.ts | Modified | Updates 4 call sites (JSX closing-tag completion detection, self-closing element check, closing-element context check, trigger-char validation) from `SyntaxKind.SlashToken` to `SyntaxKind.LessThanSlashToken` to match the corrected tokenization |
| src/services/utilities.ts | Modified | `isInsideJsxElementOrAttribute` now checks `LessThanSlashToken` (was `LessThanToken`); `isInsideJsxElement`'s ancestor walk-up adds `LessThanSlashToken` alongside the existing `SlashToken` check |
| src/compiler/types.ts | Modified | Adds optional `languageVariant?: LanguageVariant` field to the `SourceFileLike` interface |
| tests/baselines/reference/api/typescript.d.ts | Modified | Regenerated public API baseline reflecting the new `SourceFileLike.languageVariant` field |
| tests/cases/fourslash/syntacticClassificationsJsx1.ts | Modified | Updates expected syntactic classification tokens: `<`, `/` (two separate punctuation tokens) collapse into a single `</` token |
| tests/cases/fourslash/syntacticClassificationsJsx2.ts | Modified | Same token-collapsing update as Jsx1, for the dotted close-tag-name variant (`div.name`) |

## Related Issues & PRs

<!-- issue-linker output will be merged here — the orchestrator replaces this placeholder -->
