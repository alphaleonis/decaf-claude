# subagent agent-a09f303e59f161f4a

## Sibling-Consistency Review — PR #61928 (Use jsx language variant for jsx file scanning in getChildren)

### Sibling census

For the `SlashToken` → `LessThanSlashToken` migration, the changeset's own three clean sites establish the convention: a JSX-closing-tag context (`JsxClosingElement`/`JsxClosingFragment`) pairs exclusively with `LessThanSlashToken`; a self-closing context (`JsxSelfClosingElement`) pairs exclusively with `SlashToken`. This is grounded in `src/compiler/parser.ts:6339` (`parseJsxClosingElement` → `parseExpected(SyntaxKind.LessThanSlashToken)`) and `:6355` (`parseJsxClosingFragment`, same) — `LessThanSlashToken` is never produced for any other parent. Confirmed clean sites: `src/services/completions.ts:1598` (closing-tag ancestor walk), `src/services/completions.ts:3520-3521` (`JsxClosingElement` ↔ `LessThanSlashToken`), `src/services/completions.ts:5808` (`isJsxClosingElement` ↔ `LessThanSlashToken`), `src/services/utilities.ts:1892` (same pairing). `src/services/utilities.ts:1936-1937` is a deliberate ADD (not REPLACE) inside a generic structural-token allow-list that also keeps `LessThanToken`/`GreaterThanToken`, justified because that walk-up needs to treat both self-closing and closing markers as pass-through tokens.

### Findings

```json
[
  {
    "file": "src/services/completions.ts",
    "line": 3511,
    "severity": "High",
    "category": "design",
    "issue": "[CONS_SYMMETRY] `case SyntaxKind.LessThanSlashToken:` at completions.ts:3511 is paired with `currentToken.parent.kind === SyntaxKind.JsxSelfClosingElement` (line 3512) — a pairing that can never be true, since `LessThanSlashToken` is only ever parented by `JsxClosingElement`/`JsxClosingFragment` (src/compiler/parser.ts:6339, :6355). The sibling case in the very same switch, `case SyntaxKind.GreaterThanToken:` at completions.ts:3505-3509, keeps its parent-kind check (`JsxElement`/`JsxOpeningElement`) reachable for that token kind, and the switch six lines below at completions.ts:3520-3521 shows the correct pairing (`case SyntaxKind.JsxClosingElement: if (contextToken.kind === SyntaxKind.LessThanSlashToken)`). This site renamed only the case label, not the paired body check, leaving the self-closing-tag 'Fix location' branch dead.",
    "fix": "Change the case label back to `SyntaxKind.SlashToken` (matching its `JsxSelfClosingElement` body check, which is unchanged and still correct for the self-closing slash) so the case label and the parent-kind check it guards refer to the same node.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/services/formatting/formatting.ts",
    "line": 737,
    "severity": "Medium",
    "category": "design",
    "issue": "[CONS_HELPER] `shouldAddDelta`'s `case SyntaxKind.SlashToken:` falls through into a `container.kind` switch that still lists `SyntaxKind.JsxClosingElement` (formatting.ts:737-742) as a container this token can appear under. A `JsxClosingElement`'s leading token is always `LessThanSlashToken`, never a bare `SlashToken` (src/compiler/parser.ts:6339). Every closing-tag site this PR did touch now pairs `JsxClosingElement` exclusively with `LessThanSlashToken` (src/services/utilities.ts:1892; src/services/completions.ts:3520-3521, :5808) — formatting.ts was left out of the sweep, so its `JsxClosingElement` branch inside this `SlashToken` case is unreachable and JSX closing-tag indentation delta is never actually suppressed via this path.",
    "fix": "Add `SyntaxKind.LessThanSlashToken` alongside `SyntaxKind.SlashToken`/`SyntaxKind.GreaterThanToken` in the outer switch (formatting.ts:737-738) so the `JsxClosingElement` container case in the inner switch becomes reachable again.",
    "confidence": 100,
    "pre_existing": true
  }
]
```

## Considered But Not Flagged

- **`tests/cases/fourslash/syntacticClassificationsJsx1.ts`/`2.ts` CRLF churn on the `const c2 = classification(...)` block**: examined at byte level — that block was anomalously LF-only while the rest of both files is CRLF (verified via `xxd`); the PR's incidental re-save normalized it to CRLF, i.e. it now *matches* the file's dominant convention rather than deviating from it. Not drift.
- **`src/services/utilities.ts:1936-1937` (`isInsideJsxElement` ADD of `LessThanSlashToken` alongside kept `SlashToken`)**: correctly an ADD, not a REPLACE — sibling entries `LessThanToken`/`GreaterThanToken` in the same allow-list are also kept as generic pass-through tokens for both opening/closing/self-closing shapes; no closing-vs-self-closing disambiguation happens in this function, so ADD is the right shape here.
- **`src/services/utilities.ts:1892` (`isInsideJsxElementOrAttribute`, single REPLACE)**: scoped to the exact `<div>|</div>` scenario per its own comment; no sibling case for self-closing exists in this function to compare against, so REPLACE (not ADD) is correct and not evidence of an incomplete sweep.
- **`src/services/completions.ts:4833-4834` (`tryGetContainingJsxElement`, fallthrough `case LessThanSlashToken: case SlashToken:`)**: this pre-existing (blame: `f3a6d3165`, prior commit) fallthrough combining both kinds into one body that only checks `JsxSelfClosingElement`/`JsxOpeningElement` parents looks like it could have the same "unreachable for `LessThanSlashToken`" issue as the completions.ts:3511 finding above — but it predates this PR entirely, is not touched by the diff, and fully tracing its downstream fallthrough behavior (`break` vs. return, `precedingToken` checks) needs more verification than this pass supports. Noted, not reported.
- **`src/services/services.ts:507-509, 529-530` (`languageVariant` set/reset around `scanner.setText`)**: matches the existing `scanner.setText(...)`/`scanner.setText(undefined)` set/reset pairing already present in the function — consistent, not flagged (as the task context itself already notes).
- **`src/compiler/types.ts` `SourceFileLike.languageVariant?: LanguageVariant`**: new optional property on an interface with several other `?`-optional members (`lineMap?`, `getPositionOfLineAndCharacter?`) — matches the interface's existing optionality convention.
- **`src/services/formatting/rules.ts:188-189, 976` and `formattingScanner.ts:173`, `classifier.ts:168,450`, `codefixes/inferFromUsage.ts:795`**: all genuinely unrelated `SlashToken` usages (self-closing-slash formatting rules, regex-vs-divide disambiguation, binary/unary operator inference) — not JSX-closing-tag contexts, correctly left untouched.
