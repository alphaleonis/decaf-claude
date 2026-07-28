# subagent agent-a07d075e5d163411d

## TypeScript/JavaScript Idiom Review — PR #61928 (`02672d281`)

Verified directly against `src/compiler/parser.ts` (`parseJsxOpeningOrSelfClosingElementOrOpeningFragment` at line 6191–6229, `parseJsxClosingElement`/`parseJsxClosingFragment` at 6337–6363) and a codebase-wide grep confirming `LessThanSlashToken` is produced at exactly two sites in the whole compiler, both attaching it as the opening token of `JsxClosingElement`/`JsxClosingFragment` — never `JsxSelfClosingElement`. Self-closing `/>` remains a standalone `SlashToken` under `parseExpected(SyntaxKind.SlashToken)` (parser.ts:6215) in both scanner variants, unaffected by this PR's fix.

```json
[
  {
    "file": "src/services/completions.ts",
    "line": 3511,
    "severity": "High",
    "category": "type-safety",
    "issue": "[TS_TYPES] In the \"Fix location\" switch, `case SyntaxKind.LessThanSlashToken: if (currentToken.parent.kind === SyntaxKind.JsxSelfClosingElement) location = currentToken;` is unreachable. `LessThanSlashToken` is only ever synthesized (by parser.ts's parseJsxClosingElement/parseJsxClosingFragment, and by createChildren's scanner which this PR just aligned to match) as the opening token of a JsxClosingElement or JsxClosingFragment — never a JsxSelfClosingElement, since self-closing `/>` remains a standalone SlashToken in both scanner variants (confirmed: parser.ts:6215 `parseExpected(SyntaxKind.SlashToken)` before `createJsxSelfClosingElement`). This occurrence was mechanically swapped from `case SyntaxKind.SlashToken` along with the other three sites in this PR, but unlike those (which correctly target the closing-tag `</`), this one guards the self-closing-tag slash and should not have been touched. The change silently turns a previously-live location-fixup for completions triggered at a self-closing tag's `/` into permanently dead code.",
    "fix": "Revert this case label to `case SyntaxKind.SlashToken:` (keep the inner `JsxSelfClosingElement` guard unchanged) so self-closing-tag completion location-fixup is restored; add a fourslash regression test for completions positioned at the trailing slash of a self-closing JSX element.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/services/services.ts",
    "line": 507,
    "severity": "Low",
    "category": "resource-management",
    "issue": "[TS_MUTATION] `createChildren` mutates the shared module-level `scanner` singleton (exported from utilities.ts:391, the only consumer of which in src/services is this function) via `scanner.setText(...)` and the newly-added `scanner.setLanguageVariant(languageVariant)`, resetting both only after `node.forEachChild(...)`/`addSyntheticNodes` complete, with no try/finally. `addSyntheticNodes` (services.ts:544) contains `Debug.fail(...)` on an unexpected Identifier in trivia, which throws; if that (or any other exception) fires mid-scan, the shared scanner is left holding the JSX variant and stale source text instead of `LanguageVariant.Standard`/`undefined`. Each subsequent legitimate `createChildren` call re-sets both fields at its own entry, so the leak self-heals on next call, limiting real-world exposure to a narrow reentrancy/inspection window.",
    "fix": "Wrap the scan body in try/finally so `scanner.setText(undefined); scanner.setLanguageVariant(LanguageVariant.Standard);` always executes, matching the exception-safety already implicitly assumed by relying on a shared singleton.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- `src/services/completions.ts:1598` (`getJsxClosingTagCompletion` findAncestor switch, `case SyntaxKind.LessThanSlashToken`) — correct. Traced the two ways this function's walk can reach a `SlashToken`/`LessThanSlashToken`: for a genuine closing tag, `LessThanSlashToken`'s parent is directly `JsxClosingElement`, so `return false` then hitting `case JsxClosingElement: return true` on the next hop is right. For a self-closing element's `/`, the walk would `default: return "quit"` either way (whether `SlashToken` is kept in the continue-list or not, since its parent `JsxSelfClosingElement` isn't in the true/continue set) — removing `SlashToken` here changes zero observable behavior, unlike the completions.ts:3511 case. No finding.
- `src/services/completions.ts:3521` (`switch(parent.kind) case JsxClosingElement: if (contextToken.kind === LessThanSlashToken)`) — correct and required; this is exactly the site whose old `SlashToken` check would have gone permanently dead once `createChildren` stopped splitting `</` into two tokens. No finding.
- `src/services/completions.ts` `isValidTrigger` case `"/"` (`contextToken.kind === LessThanSlashToken && isJsxClosingElement(contextToken.parent)`) — correct. Since `getTokenAtPosition`/`findPrecedingToken` are themselves built on `createChildren`'s scanner (confirmed: `scanner` is exported once from utilities.ts and consumed only by services.ts's `createChildren`), the token ending exactly at the just-typed `/` is now genuinely a single `LessThanSlashToken` under JSX-variant scanning, so the trigger check fires at the correct (and only) reachable position. No finding.
- `src/services/utilities.ts` `isInsideJsxElementOrAttribute` (`LessThanToken`→`LessThanSlashToken` at the `<div>|</div>` comment site) — correct; this occurrence only ever handled the closing-tag `<`+`/` pair (never self-closing), so the straight swap is right, no `SlashToken` retention needed here.
- `src/services/utilities.ts` `isInsideJsxElement` (adds `LessThanSlashToken`, keeps `SlashToken`) — correct and internally consistent, and notably *not* the same mistake as completions.ts item 2: this traversal legitimately needs to ascend through **both** kinds of token — `SlashToken` for self-closing `/>` (unchanged by the variant fix) and the new `LessThanSlashToken` for closing `</` (previously split into `LessThanToken`+`SlashToken`, both already in the ascend-list, so it "worked by accident" pre-fix; post-fix it needs the new combined kind added). This is the opposite of a latent inconsistency — the utilities.ts diff shows the author correctly distinguishing self-closing-slash from closing-tag-slash in this function, which makes the identical conflation in completions.ts:3511 (finding 1) look like an isolated oversight in an otherwise careful PR, not a systemic misunderstanding.
- `src/services/services.ts` `sourceFile?.languageVariant ?? LanguageVariant.Standard` — idiomatic, no coercion or nullish-check hazard.
- `src/compiler/types.ts` optional `languageVariant?: LanguageVariant` on `SourceFileLike` — a widening addition to a structural interface; every read site in the diff guards it with `?? LanguageVariant.Standard`, so no unsound narrowing or unchecked access. (Whether silently defaulting to `Standard` for `SourceFileLike` callers that forgot to populate it for JSX content is *desirable* is a design/API-contract question, out of this reviewer's scope.)

## Item #2 — explicit trace and confidence statement

Trace: `LessThanSlashToken` is produced at exactly two production sites in the entire compiler (grep-verified across `src/compiler/*.ts`): `parseJsxClosingElement` (parser.ts:6339, parent → `JsxClosingElement`) and `parseJsxClosingFragment` (parser.ts:6355, parent → `JsxClosingFragment`). There is no code path, including error recovery (the synthesized empty `JsxClosingElement` at parser.ts:6067 doesn't consume a real token at all), that attaches a `LessThanSlashToken` to a `JsxSelfClosingElement`. Self-closing `/>` is parsed via a separate, unconditional `parseExpected(SyntaxKind.SlashToken)` (parser.ts:6215) immediately before `factory.createJsxSelfClosingElement(...)` — untouched by JSX-variant tokenization in either the parser or `createChildren`. Therefore `currentToken.parent.kind === SyntaxKind.JsxSelfClosingElement` at completions.ts:3512 can never be true once the case label reads `LessThanSlashToken`; before this PR (label `SlashToken`) it could be true and clearly was meant to be — the original hunk (`git log -p -L`) shows this is a pure mechanical `SlashToken`→`LessThanSlashToken` substitution applied uniformly across four sites, three of which needed it and one (this one) did not.

Confidence: **100** that the branch is dead code — this is a closed-form structural fact, not an inference about runtime behavior. Confidence that this constitutes an observable completion regression (vs. code that was already effectively unreachable before the PR for unrelated reasons) is somewhat lower since I did not run a live repro, but I found no fourslash test (`verify.completions` combined with "SelfClosing") that would have exercised this path, which is consistent with why CI stayed green despite the regression.

## Probe Requests

- A fourslash completion test in a `.tsx` file with a self-closing JSX element and the cursor positioned at/near the trailing `/` of `<div /* marker */ />` (with an `IntrinsicElements` `div` that has required/optional attributes), asserting the expected attribute-completion list. This is the scenario `completions.ts:3511`'s dead branch was guarding; running it against current HEAD (`02672d281`) should reveal whether attribute completions at that position are now empty/wrong.
- Same test also run against the parent commit (`f3a6d3165`, pre-PR) to diff observed completion output and confirm the behavior actually changed rather than having been already broken.
