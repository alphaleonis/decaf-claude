# subagent agent-a1b71b0604fe0fa1a

I have what I need. The global shared `scanner` (utilities.ts:391) is `createScanner(ScriptTarget.Latest, true)` — construction default variant is Standard (scanner.ts:1025). It's imported and mutated by three modules (services.ts, completions.ts, preProcess.ts), and both preProcess.ts (line 338) and completions.ts (line 1898) drive it without ever setting a variant — they implicitly assume Standard. This PR is the first code to mutate that variant. And I confirmed concern (c): `LessThanSlashToken`'s guard checks `JsxSelfClosingElement`, which per the AST invariant is unsatisfiable.

## VERDICT: NEEDS_CHANGES

## Project Standards Applied
Project documentation found (`CONTRIBUTING.md`, `.github/copilot-instructions.md`). Neither defines a standard governing inline decision-logging, dead-branch policy, or shared-scanner-state conventions that bears on these findings. Applying RULE 0 and RULE 2 only.

## Findings

### [LLM_COMPREHENSION_RISK SHOULD]: `case LessThanSlashToken` guards on a parent kind it can never have
- **RULE**: 0 (knowledge preservation); overlaps RULE 2 DEAD_CODE
- **Location**: `src/services/completions.ts:3511-3515` (getCompletionData "Fix location" switch)
- **Issue**: The mechanical rename `SlashToken` → `LessThanSlashToken` left the branch body untouched:
  ```ts
  case SyntaxKind.LessThanSlashToken:
      if (currentToken.parent.kind === SyntaxKind.JsxSelfClosingElement) {
          location = currentToken;
      }
      break;
  ```
  Per the stated AST invariant, `LessThanSlashToken` (`</`) only ever parents to `JsxClosingElement`; a `JsxSelfClosingElement` (`<div />`) contains a `SlashToken`, never a `LessThanSlashToken`. So the guard is unsatisfiable and the body is unreachable. The pre-rename code (`case SlashToken` + `JsxSelfClosingElement`) was satisfiable and targeted the `/` of a self-closing element — that intent is now neither expressed nor achievable in the code.
- **Failure Mode / Rationale**: A future maintainer reading this branch faces a self-contradiction with no in-code resolution and cannot tell which of three things is true: (1) intentional dead code left for symmetry, (2) a bug where the guard should be `JsxClosingElement`, or (3) a silently dropped self-closing-element location-fix (the `/` in `<div />` is still a `SlashToken`, and no arm of this switch matches it anymore). Each reading leads to a different, possibly behavior-changing edit. The "why it looks like this" knowledge is not recoverable from the code. (Dual-path note: forward reasoning reaches a wrong future edit / possible completion regression; backward reasoning traces that to this contradictory-but-unexplained branch. Paths do not both terminate in an unrecoverable consequence — original intent survives in history — so SHOULD, not MUST.)
- **Suggested Fix**: Resolve the contradiction and record the decision in one line. If self-closing location-fixing is still intended, key this arm on `SyntaxKind.SlashToken` (the `/` of `<div />`), not `LessThanSlashToken`. If it is not intended, delete the unreachable arm and add a comment stating that closing-tag `</` location is handled by the `JsxClosingElement` case below (lines 3520-3525). Do not leave a `LessThanSlashToken`/`JsxSelfClosingElement` pairing that can never fire.
- **Confidence**: 75
- **Pre-existing**: no — the contradiction was introduced by this changeset's rename; the prior `SlashToken`/`JsxSelfClosingElement` pairing was satisfiable
- **Actionability Check**:
  - Fix specifies exact change: YES
  - Fix requires no additional decisions: NO (author must confirm whether self-closing behavior was intended) — this is inherent; the fix names both concrete branches and asks for the one decision only the author can settle. See Probe Requests.

### [ASSUMPTION_UNVALIDATED COULD]: Undocumented "reset shared scanner to Standard" invariant that a future edit will read as redundant
- **RULE**: 0 (knowledge preservation)
- **Location**: `src/services/services.ts:530` (`scanner.setLanguageVariant(LanguageVariant.Standard)` in createChildren)
- **Issue**: `scanner` is a module-shared mutable singleton (defined `createScanner(ScriptTarget.Latest, true)` at `utilities.ts:391`, default variant Standard) imported by `services.ts`, `completions.ts`, and `preProcess.ts`. This PR is the first code to ever mutate its language variant. `preProcess.ts:338` and `completions.ts:1898` drive the same scanner (`setText`/`resetTokenState`/`scan`) without ever setting a variant — they silently assume Standard. The reset at line 530 is what upholds that assumption after a JSX/TSX file is scanned; the hard-coded `Standard` is load-bearing precisely because it matches the construction default those other consumers rely on. None of this is stated at the reset site.
- **Failure Mode / Rationale**: A maintainer noticing that `createChildren` sets the variant on every entry (line 509) could conclude the reset is redundant and delete it. That would leave the shared scanner in JSX variant after any `getChildren()`/`getTokenAtPosition` call on a JSX file, so the next `preProcess`/`completions` scan runs in JSX mode and silently mis-tokenizes (the exact class of bug this PR fixes, now inverted onto other consumers). The coupling is cross-file and not obvious from the reset line alone.
- **Suggested Fix**: Add a one-line comment at line 530, e.g. `// Restore the shared scanner's default (Standard) variant — other consumers (preProcess.ts, completions.ts) drive this singleton without setting a variant and assume Standard.` This is not redundant with the entry-side `setLanguageVariant` at line 509.
- **Confidence**: 75
- **Pre-existing**: no — the mutation and its cleanup are introduced by this changeset
- **Actionability Check**:
  - Fix specifies exact change: YES
  - Fix requires no additional decisions: YES

## Reasoning
Applied RULE 0 + RULE 2. Found a rename-induced contradictory branch whose intent is unrecoverable from code (comprehension trap, possible dropped self-closing behavior) and an undocumented shared-scanner reset invariant a future edit will misread as redundant. Verdict NEEDS_CHANGES: one SHOULD present.

## Considered But Not Flagged
- **Coupling between `createChildren` scan output and downstream token-kind expectations (concern b)**: Real but diffuse and architectural — the re-scanner's contract is "reproduce the parser's tokens," and every `getTokenAtPosition`-based service depends on it. It is not fixable by a single local comment, and the `setLanguageVariant(sourceFile?.languageVariant ?? Standard)` line already telegraphs intent ("scan in the file's own variant"). Fails the actionability bar for a discrete finding; noted here for context. That this coupling silently mis-scanned JSX for a long time is itself evidence the contract is under-documented, but the remedy is design-level, out of my scope.
- **`languageVariant?: LanguageVariant` added to `SourceFileLike` (types.ts / typescript.d.ts)**: Optional property with a self-descriptive name and type; a full `SourceFile` already carries `languageVariant`. Intent inferable from the name and the consuming code — fails the inferability gate. No decision lost.
- **Reset value `LanguageVariant.Standard` correctness**: Verified it equals the shared scanner's construction default (createScanner default at scanner.ts:1025; global scanner at utilities.ts:391 passes no variant). The assumption "Standard is the module-wide default" is true and verifiable from code — captured only as the durable-relevance risk in finding #2, not as a separate correctness claim.
- **Test baseline churn (`syntacticClassificationsJsx1/2.ts` `c2` whitespace)**: Cosmetic; no knowledge at risk.

### Probe Requests
Nominated (do not run without operator): to confirm whether finding #1 is dead-but-harmless vs a latent completion regression, add/run a fourslash completion test with the cursor at the `/` of a self-closing element (`var x = <div /**/ />`) on a `.tsx` file, and compare completion `location`/results against the pre-PR commit. If completions differ, the self-closing location-fix was lost and finding #1 escalates from comprehension debt to a behavior regression (route to quick-reviewer / typescript-reviewer for the bug classification).
