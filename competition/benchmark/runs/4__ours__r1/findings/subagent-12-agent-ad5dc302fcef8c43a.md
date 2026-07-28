# subagent agent-ad5dc302fcef8c43a

I have completed my analysis. Building the system model and verifying each surface against the code, here is my report.

## System Model (reference frame)

- **Shared mutable global scanner**: `export const scanner` (utilities.ts:391), a singleton created once (`skipTrivia=true`, `ScriptTarget.Latest`, default `Standard` variant). Mutated by `createChildren` (services.ts), `preProcessFile` (preProcess.ts:338/416), and completions.ts:1898. Only `createChildren` sets/clears the language variant; the other two consumers set text but **not** variant, so they inherit whatever variant was last left.
- **Scan→interpret contract**: `getChildren()` → `createChildren` synthesizes punctuation token nodes via the shared scanner; `getTokenAtPosition`/`findPrecedingToken` walk `getChildren`, so the token *kinds* completions.ts/utilities.ts branch on are produced by the variant `createChildren` selects. This is an implicit cross-module contract.
- **Token facts (verified against scanner.ts:2204-2212)**: in JSX variant `</` (not followed by `*`) → one `LessThanSlashToken` (parent `JsxClosingElement`); the standalone `/` in `<div />` → `SlashToken` (parent `JsxSelfClosingElement`) in **both** variants.
- **Public surface**: `SourceFileLike` gains `languageVariant?` (not `@internal`, so it ships in `typescript.d.ts`).

## Findings

```json
[
  {
    "file": "src/services/completions.ts",
    "line": 3511,
    "severity": "Medium",
    "category": "design",
    "issue": "[CROSS_CUTTING_DRIFT] The SlashToken->LessThanSlashToken rename was applied uniformly across all interpret sites, but this site's SlashToken referred to the self-closing-element '/', not a closing-tag '</'. Per the scanner, the '/' in `<div />` stays a SlashToken (parent JsxSelfClosingElement) in JSX variant; only `</` becomes LessThanSlashToken (parent JsxClosingElement). A LessThanSlashToken can never have parent JsxSelfClosingElement, so `case LessThanSlashToken: if (currentToken.parent.kind === JsxSelfClosingElement)` is now dead, silently dropping the pre-existing `location = currentToken` refinement for self-closing tags.",
    "fix": "This interpret site should remain `case SyntaxKind.SlashToken` because it keys off parent JsxSelfClosingElement, which is unaffected by the variant change. Distinguish 'SlashToken inside a closing tag' (which did become LessThanSlashToken and is handled at line 3520) from 'SlashToken inside a self-closing element' (unchanged) rather than mapping both uniformly.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/services/services.ts",
    "line": 509,
    "severity": "Medium",
    "category": "design",
    "issue": "[CONCURRENCY_DESIGN] createChildren sets the shared global scanner to JSX variant (509) and resets it to Standard (530) without a try/finally. If node.forEachChild/addSyntheticNodes throws between them (e.g. the Debug.fail at services.ts:544), the singleton scanner is left in JSX variant. Unlike the pre-existing setText leak — which every consumer overwrites via setText before use and is thus self-correcting — the variant leak is sticky: preProcessFile (preProcess.ts:338) and completions.ts:1898 call setText but never setLanguageVariant, so they inherit the leaked JSX variant, under which base scan() tokenizes '</' as LessThanSlashToken instead of LessThanToken+SlashToken.",
    "fix": "Bracket the shared-scanner mutation in try/finally so both setText(undefined) and setLanguageVariant(Standard) always run, matching how shared mutable state should be restored. Alternatively have the trivia/import consumers that rely on Standard set the variant explicitly so they are not order-dependent on the previous caller.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/compiler/types.ts",
    "line": 4291,
    "severity": "Low",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] SourceFileLike.languageVariant is optional and createChildren treats absent as Standard (`?? LanguageVariant.Standard`). Any SourceFileLike that is a hand-built shim over .tsx/.jsx text but omits languageVariant will be scanned as Standard by getChildren — silently reintroducing the exact bug this PR fixes. The getChildren default param (getSourceFileOfNode) covers the common path with a real SourceFile, so this is latent, but the contract 'you must set languageVariant or JSX tokenizes wrong' is implicit and easy to miss. The field is also not marked @internal (unlike its sibling optional members lineMap/getPositionOfLineAndCharacter), so it widens the shipped public typescript.d.ts surface.",
    "fix": "Document the absent==Standard contract at the interface, or have createChildren fall back to node.getSourceFile().languageVariant (parallel to how it already falls back to node.getSourceFile().text) so a shim's missing variant defers to the underlying SourceFile rather than silently defaulting to Standard. Confirm the public exposure (drop @internal omission) is intended.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`getChildren()` public token-stream change**: For JSX files, `Node.getChildren()` now returns a single `LessThanSlashToken` where it previously returned `LessThanToken`+`SlashToken`. This is a behavioral change to a public API's output that could affect downstream AST consumers (linters, ts-morph-style tools). Not flagged as a defect — it is the intended correctness fix (the old output was wrong); noted only as an expected-compat consideration.
- **Reentrancy of the scanner walk**: `processNode`/`processNodes`/`createSyntaxList` re-enter the shared scanner via `addSyntheticNodes`, but only call `resetTokenState`/`scan` — never `setText`/`setLanguageVariant` — and `forEachChild` does not recurse into `getChildren`. Combined with JS single-threading, there is no interleaving that corrupts the variant within a single `createChildren` call. Sound.
- **The other three updated interpret sites** (completions.ts:1598 walk-up set, 3521 JsxClosingElement, 5808 isValidTrigger; utilities.ts:1892 and 1937): each keys off `JsxClosingElement`/closing-tag context, so `SlashToken`/`LessThanToken` → `LessThanSlashToken` is correct there. utilities.ts:1937 correctly *adds* `LessThanSlashToken` while keeping `SlashToken` (self-closing) and `LessThanToken` (opening). completions.ts:4367 checks parent kind only, robust to the tokenization change. Verified consistent.
- **classifier.ts / formatting**: use their own scanners created with the correct `sourceFile.languageVariant` and do not consume `createChildren`'s synthesized tokens; unaffected.
- **Backward compat of the optional interface widening itself**: adding an optional property to `SourceFileLike` does not break existing implementers or readers. Sound (the concern is the silent-default semantics, captured in finding 3, not the widening).

### Probe Requests
Optional (I verified the finding-1 deadness statically from scanner.ts + the stated token facts; no probe strictly required):
1. `grep -rl "JsxSelfClosingElement" tests/cases/fourslash | xargs grep -l "completion" ` then run those fourslash cases against a self-closing `<div /|>` completion position, to demonstrate whether the lost `location` refinement at completions.ts:3511-3514 has observable coverage (I found none in the two tests this PR touched, which both concern the `</` closing-tag classification only).
