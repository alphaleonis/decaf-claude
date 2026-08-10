# subagent agent-a8c5d862c534d77f3

I have verified the token semantics and shared-state coupling directly against the scanner, parser, and other consumers. Key confirmations:
- scanner.ts:2204-2212 — `</` scans as `LessThanSlashToken` only when `languageVariant === JSX`; otherwise `LessThanToken` (+ separate `SlashToken`).
- parser.ts:6215 — the self-closing `/` in `<div />` is a standalone `SlashToken` (parent `JsxSelfClosingElement`) in both variants; `LessThanSlashToken`'s parent is only ever `JsxClosingElement`.
- utilities.ts:391 — the `scanner` is a single exported mutable singleton; preProcess.ts:11,338 uses that same global and never sets its variant (relies on Standard).
- Sibling comment precedent exists (parser.ts:6208-6211; preProcess.ts:18) — the codebase does document non-obvious scanner-state decisions.

Here is my report.

---

## VERDICT: NEEDS_CHANGES

## Project Standards Applied
No project documentation governing knowledge/comment conventions was found for the TypeScript repo under review (the CLAUDE.md files in scope belong to the surrounding decaf-claude tooling, not to microsoft/TypeScript). Applying RULE 0 and RULE 2 only. Where relevant I cite the TypeScript codebase's own established convention of commenting non-obvious scanner-variant behavior (parser.ts:6208-6211; preProcess.ts:18) as a sibling precedent, not as a formal standard.

## Findings

### [ASSUMPTION_UNVALIDATED SHOULD]: Reset-to-Standard silently guards a shared global scanner used by other features
- **RULE**: 0 (knowledge preservation)
- **Location**: `src/services/services.ts:530` (`scanner.setLanguageVariant(LanguageVariant.Standard)`)
- **Issue**: `scanner` is the single exported mutable singleton at `src/services/utilities.ts:391`, created with the default (Standard) variant and shared across features. `preProcess.ts` imports that same global (`preProcess.ts:11`), calls `scanner.setText(...)` (`preProcess.ts:338`) and scans, but never sets a language variant — it relies on the scanner already being in Standard. The new reset at line 530 is the *only* thing restoring that invariant after `createChildren` switches the scanner to JSX. Nothing at the reset site records why it exists or what depends on it.
- **Failure Mode / Rationale**: Open question — "what happens to `preProcessFile` if the global scanner is left in the JSX variant?" Answer: it scans `</` as one `LessThanSlashToken` instead of `LessThanToken`+`SlashToken`, silently misreading import/export trivia. A maintainer who reads `setLanguageVariant(Standard)` with no comment can reasonably conclude it is redundant (createChildren re-sets the variant on its next entry at line 509 anyway) and delete it, or fail to realize the set/reset pair must survive an exception thrown by the intervening `forEachChild`/`scan` (it is not in try/finally). Either way another feature's scanning is silently corrupted, and the "why" — cross-feature shared state — is not recoverable from this file. The TS codebase already documents comparable scanner-state assumptions (preProcess.ts:18), so a comment here is in-convention.
- **Suggested Fix**: Add a comment at line 530, e.g. `// scanner is a shared singleton (utilities.ts) also used by preProcessFile with the Standard variant; restore it so we don't leak the JSX variant into other consumers.` Consider wrapping the set/scan/reset in try/finally so an exception cannot leave the shared scanner in the JSX variant (the robustness aspect is for a correctness reviewer; the rationale comment is the knowledge fix).
- **Confidence**: 75
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: YES.

### [ASSUMPTION_UNVALIDATED SHOULD]: New `languageVariant?` on `SourceFileLike` has no contract doc for who populates it or the absent-means-Standard default
- **RULE**: 0 (knowledge preservation)
- **Location**: `src/compiler/types.ts:4291` (`languageVariant?: LanguageVariant;` on `SourceFileLike`)
- **Issue**: `SourceFileLike` is the deliberately-minimal "subset of properties used in multiple utility functions" interface (see its own doc at types.ts:4282-4284) with multiple implementers, and this field also surfaces in the public `typescript.d.ts` baseline. The consuming code at `services.ts:507` reads `sourceFile?.languageVariant ?? LanguageVariant.Standard` — so an absent value silently means Standard. The field carries no doc comment stating that implementers scanning JSX/TSX must populate it, nor that omission degrades to Standard. Unlike its neighbors it is also not marked `@internal`, yet gains no public-API documentation.
- **Failure Mode / Rationale**: Open question — "what does an implementer of `SourceFileLike` who forgets to set `languageVariant` for a JSX file get?" Answer: Standard-variant scanning in `createChildren` — i.e. the exact defect this PR fixes, silently reintroduced, with no signal at the interface that the field was load-bearing. The default-Standard contract lives only in a `??` expression in another file; an implementer reading the interface cannot infer it. This is contract knowledge that belongs where implementers look — at the interface — not in a commit message.
- **Suggested Fix**: Add a doc comment on the field, e.g. `/** Language variant used when re-scanning this file's tokens (e.g. in getChildren). Implementers backing JSX/TSX content must set this to LanguageVariant.JSX; when omitted, scanning defaults to LanguageVariant.Standard. */`. If public exposure in `typescript.d.ts` is unintended, decide `@internal` explicitly (that API-surface call is design-reviewer's; the doc/contract is the knowledge fix).
- **Confidence**: 75
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: YES.

### [IK_TRANSFER_FAILURE SHOULD]: `SlashToken`→`LessThanSlashToken` checks silently depend on `createChildren`'s variant switch, with nothing anchoring the coupling
- **RULE**: 0 (knowledge preservation)
- **Location**: `src/services/completions.ts:1598, 3511, 3521, 5808`; `src/services/utilities.ts:1892, 1937`
- **Issue**: These token-kind checks only match because `createChildren` (services.ts:509) now scans JSX files with the JSX variant, which makes `</` a single `LessThanSlashToken` (verified: scanner.ts:2204-2212). None of the six edited sites carries a comment tying the token kind to the variant switch in `services.ts`; conversely, `services.ts` carries nothing pointing forward to the consumers that depend on it. The dependency is entirely non-local and invisible in both directions.
- **Failure Mode / Rationale**: Open question — "what would a maintainer who reverts or 'simplifies' the variant switch in `createChildren` misunderstand?" Answer: they would not see that JSX closing-tag completion and `isInsideJsxElement*` rely on JSX-variant tokenization; `</` would revert to `LessThanToken`+`SlashToken`, the `LessThanSlashToken` branches would never fire, and JSX closing-tag completion would silently stop working. The updated fourslash tests are `syntacticClassificationsJsx1/2` — they anchor the `getChildren` classification path, not these completion branches, so the coupling is under-guarded. The token semantics are domain knowledge, but the specific coupling to `createChildren` is not; the TS codebase documents analogous variant-dependent scanning inline (parser.ts:6208-6211), so an anchoring comment is in-convention.
- **Suggested Fix**: Add a one-line comment at the reset site in `services.ts` (or beside the variant `setLanguageVariant` at line 509) noting that JSX-variant scanning is what produces `LessThanSlashToken` for `</`, which downstream completion/utility checks (getJsxClosingTagCompletion, isValidTrigger, isInsideJsxElementOrAttribute) rely on; and add a brief comment at one representative consumer (e.g. completions.ts:1598) noting the token is `LessThanSlashToken` because JSX files are scanned with the JSX variant in `getChildren`/`createChildren`.
- **Confidence**: 75
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: YES.

### [DEAD_CODE COULD]: "Fix location" case keys on `LessThanSlashToken` but guards on `JsxSelfClosingElement`, an unsatisfiable combination that reads as false context
- **RULE**: 2 (structural — comprehension risk)
- **Location**: `src/services/completions.ts:3511-3515`
- **Issue**: The case label was changed `SlashToken`→`LessThanSlashToken`, but the inner guard still checks `currentToken.parent.kind === SyntaxKind.JsxSelfClosingElement`. A `LessThanSlashToken` (the `</` of a closing tag) always has parent `JsxClosingElement`; a self-closing element's `/` is a standalone `SlashToken` with parent `JsxSelfClosingElement` (verified: scanner.ts:2204-2210 and parser.ts:6215). So this branch's body can never execute.
- **Failure Mode / Rationale**: Open question — "what will a future maintainer conclude when they read a `case LessThanSlashToken` that only acts when the parent is a `JsxSelfClosingElement`?" Answer: they cannot tell whether the self-closing-`/` handling that used to live here was intentionally dropped, is a latent bug, or is deliberately dead — the contradictory label/guard encodes an unresolvable ambiguity and misleads a reader about what the completion path actually does. (Whether this is a behavior regression is a correctness question owned by quick-reviewer / typescript-reviewer; I flag only the comprehension risk.)
- **Suggested Fix**: Resolve the contradiction so intent is legible: if self-closing-`/` handling is still required, keep a `case SyntaxKind.SlashToken:` for that path; if it is intentionally gone, remove the now-unreachable guard/branch. Either way the resulting code should not pair `LessThanSlashToken` with a `JsxSelfClosingElement` parent check.
- **Confidence**: 75
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: NO — needs a correctness call on whether the self-closing path is still wanted; that judgment is out of my scope and flagged for the correctness reviewers. The comprehension defect itself is concrete.

## Reasoning
Applied RULE 0. Found an undocumented shared-global-scanner invariant (reset guards preProcess), an undocumented public-interface field contract (absent=Standard), and an unanchored non-local coupling between the variant switch and the token checks; plus one contradictory (dead) case. Verdict: NEEDS_CHANGES — SHOULD-level knowledge gaps, no MUST.

## Considered But Not Flagged
- **"Why change to the batch/JSX-variant approach" as a code comment**: The rationale for the change itself lives in the PR/commit; not flagged (not-recorded-elsewhere gate). Only the forward-relevant invariants are flagged.
- **`utilities.ts:1892` (`LessThanToken`→`LessThanSlashToken`) and `1937` (adds `LessThanSlashToken`, keeps `SlashToken`)**: These are covered by the coupling finding; not separately flagged. The `isInsideJsxElement` change keeping both `SlashToken` and `LessThanSlashToken` is internally consistent (self-closing `/` still tokenizes as `SlashToken`), so no additional comprehension risk beyond the coupling.
- **`getChildren` default param `getSourceFileOfNode(this)` (services.ts:462)**: real SourceFiles carry `languageVariant`, so the common path is safe; the risk is only for custom `SourceFileLike` implementers, which is captured by the interface-contract finding.
- **try/finally robustness of the scanner set/reset**: the exception-safety bug is out of scope (quick-reviewer); referenced only as the failure mode enabled by the missing rationale in finding 1.

## Probe Requests
Read-only; optional deeper verification. I did not run these (they scan the test corpus for coverage, not required to substantiate the findings above):
- `rg -l "verify.completions|closeTag|</" tests/cases/fourslash | rg -i jsx` — to confirm whether any fourslash completion test exercises the `LessThanSlashToken` closing-tag branches in completions.ts (assess how under-guarded the coupling in finding 3 is).
- `rg -n "getChildren|createChildren" src/services --glob '!**/*.d.ts'` — to enumerate all callers that reach the shared scanner via `getChildren`, confirming no other consumer sets a variant it fails to reset.
