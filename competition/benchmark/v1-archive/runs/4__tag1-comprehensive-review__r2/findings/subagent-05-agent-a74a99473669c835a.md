# subagent agent-a74a99473669c835a

## Summary

Fixes a scanner bug where `createChildren()` in `services.ts` reused the shared global scanner via `setText()` without setting the JSX language variant, causing JSX/TSX files to be scanned with the standard variant (e.g. `</div>` tokenized as `<`, `/`, `div`, `>` instead of `</`, `div`, `>`). This broke completions logic (e.g. JSX closing-tag completions) and is corrected by threading `languageVariant` through `SourceFileLike`, resetting the scanner's variant explicitly around `createChildren`, and updating completions/utilities code to check the resulting `LessThanSlashToken` instead of a separate `SlashToken`.

**Type:** bugfix
**Effort:** 2/5 — small, contained diff (+21/-16 across 7 files) but touches core scanner state handling and several call sites consistently; low line count keeps it out of medium territory.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| src/services/services.ts | Modified | `createChildren` now derives `languageVariant` from the source file, calls `scanner.setLanguageVariant()` before scanning and resets it to `Standard` afterward |
| src/services/completions.ts | Modified | Four sites switched from checking `SyntaxKind.SlashToken` to `SyntaxKind.LessThanSlashToken` for JSX closing-tag/self-closing-element completion logic, matching the corrected token stream |
| src/services/utilities.ts | Modified | `isInsideJsxElementOrAttribute` changed from `LessThanToken` + parent-is-`JsxClosingElement` check to `LessThanSlashToken`; `isInsideJsxElement` gains a `LessThanSlashToken` case alongside the existing `SlashToken` case |
| src/compiler/types.ts | Modified | Adds optional `languageVariant?: LanguageVariant` to the internal `SourceFileLike` interface |
| tests/baselines/reference/api/typescript.d.ts | Modified | Generated API baseline updated to reflect the new public `languageVariant` field on `SourceFileLike` |
| tests/cases/fourslash/syntacticClassificationsJsx1.ts | Modified | Expected classification updated from separate `<`/`/` punctuation tokens to a single `</` token for JSX closing tags; trailing block normalized to CRLF |
| tests/cases/fourslash/syntacticClassificationsJsx2.ts | Modified | Same closing-tag token expectation update and CRLF normalization as Jsx1 |

## Related Issues & PRs

<!-- issue-linker output will be merged here — the orchestrator replaces this placeholder -->
