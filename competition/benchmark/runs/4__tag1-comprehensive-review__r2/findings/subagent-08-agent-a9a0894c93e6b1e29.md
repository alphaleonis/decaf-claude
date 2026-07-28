# subagent agent-a9a0894c93e6b1e29

Verified all three candidates against the code (not just the diff).

**Candidate 1 — `utilities.ts:1891-1892`, comment `// <div>|</div>`.** Still accurate. Confirmed via `src/compiler/scanner.ts:2204-2212` that `LessThanSlashToken` is only produced by the main scanner when `languageVariant === LanguageVariant.JSX` (Standard variant scans `<` and `/` as two separate tokens). `JsxClosingElement` (types.ts:3294-3298) stores only `tagName` as a real AST field — the leading `</` is not a stored node, so it's synthesized on demand by `createChildren`/`addSyntheticNodes` using the shared scanner. The comment shows the cursor sitting between the opening tag's end and the closing tag's start; that scenario is exactly what the `LessThanSlashToken`+`JsxClosingElement` check now matches (previously a dead/buggy check against `LessThanToken`, since the synthesized closing-gap token was never actually a bare `LessThanToken` once the language-variant fix in this PR is applied). The comment does not reference a token kind, so the kind change doesn't invalidate it. No comment rot here.

**Candidate 2 — `services.ts:497-532`, `createChildren`.** Genuine gap, confirmed non-obvious. `scanner` (services.ts:281 import) is the single module-level singleton declared `var scanner = createScanner(...)` in `src/compiler/parser.ts:1444`, shared across the whole process. It's also used directly, without setting language variant, by `src/services/completions.ts:1898-1900` and `src/services/preProcess.ts` (e.g. line 338 `scanner.setText(sourceText)` with no `setLanguageVariant` call). The parser itself is safe because `initializeState` (parser.ts:1772-1775) always explicitly resets both text and language variant before use — but these two other call sites are not, and implicitly rely on the scanner being in `Standard` variant. If `createChildren` didn't reset the variant back to `Standard` at line 530, a JSX file processed via `getChildren()` could leave the shared scanner in JSX mode, and a subsequent unrelated call in `completions.ts` or `preProcess.ts` could silently mis-tokenize (e.g., treat `</` as one token vs. two) with no visible connection between cause and effect. This is exactly the class of "spooky action at a distance via shared mutable state" that invites a future contributor to delete the reset as apparently-redundant cleanup.

**Candidate 3 — `types.ts:4291`, `languageVariant?: LanguageVariant;` on `SourceFileLike`.** Not an issue. `SourceFile.languageVariant` itself (types.ts:4359) is a public, non-`@internal` field, and the sibling `text` field on `SourceFileLike` (line 4286) is likewise untagged/undocumented — the pattern in this interface is that `@internal`-tagged members mirror internal-only `SourceFile` members (`lineMap`, and the service-only `getPositionOfLineAndCharacter` hook), while members mirroring genuinely public `SourceFile` fields stay untagged. Confirmed via the regenerated public baseline `tests/baselines/reference/api/typescript.d.ts:5908-5911`, which already shows `languageVariant?: LanguageVariant;` as public API (the `@internal` members were correctly stripped). This is deliberate public exposure, not an oversight, and not a comment-accuracy problem.

```json-findings
[
  {
    "severity": "medium",
    "confidence": 80,
    "agent": "comment-analyzer",
    "category": "docs",
    "file": "src/services/services.ts",
    "line": 507,
    "finding": "createChildren() sets scanner.setLanguageVariant(languageVariant) at line 509 and resets it to LanguageVariant.Standard at line 530, with no comment explaining why. `scanner` is a module-level singleton (declared `var scanner = createScanner(...)` in src/compiler/parser.ts:1444, exported and reused across services.ts, completions.ts, preProcess.ts). completions.ts:1898-1900 and preProcess.ts (e.g. line 338) call scanner.setText(...)/scanner.scan() directly without ever calling setLanguageVariant themselves, implicitly assuming the scanner is left in Standard variant. The reset at line 530 is therefore load-bearing cross-module cleanup, not local tidiness — omitting it (or a future edit removing it as apparently dead code) would silently corrupt tokenization in unrelated call sites the next time a JSX file's children are computed.",
    "remediation": "Add a short comment above the setLanguageVariant call (or above the reset at line 530) noting that `scanner` is a shared/global instance also used directly by completions.ts and preProcess.ts, which do not set language variant themselves, so it must be restored to Standard before returning."
  }
]
```
