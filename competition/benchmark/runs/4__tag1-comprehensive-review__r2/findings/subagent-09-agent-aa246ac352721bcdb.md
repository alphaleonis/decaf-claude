# subagent agent-aa246ac352721bcdb

## Findings

Confirmed via diff (`git diff f3a6d3165f...HEAD -- src/services/services.ts`) and cross-file grep across `src/services/` and `src/compiler/`.

`createChildren()` (`src/services/services.ts:497-532`) has no `try/finally`. Between `scanner.setLanguageVariant(languageVariant)` (line 509) and the reset `scanner.setLanguageVariant(LanguageVariant.Standard)` (line 530), it calls `node.forEachChild(processNode, processNodes)` (line 527), whose callbacks call `addSyntheticNodes` (line 512/517). `addSyntheticNodes` (line 534-553) contains an unconditional `Debug.fail(...)` (line 544) when it scans an unexpected `Identifier` token in trivia that isn't a snippet tabstop. `Debug.fail` (`src/compiler/debug.ts:196-204`) is not gated by `shouldAssertFunction`'s no-op mechanism (that only applies to `assertionCache`-registered functions like `Debug.assert*`) — it unconditionally does `throw e`, in every build. So the "does forEachChild realistically throw" question resolves to: yes, a live, production-reachable throw exists inside the critical section, triggered whenever the traversed subtree has trivia the scanner classifies as an `Identifier` without a matching snippet-tabstop marker — a real internal-consistency check, not a hypothetical.

The `scanner` here (`src/services/services.ts:281` import) is the module-level singleton `export const scanner = createScanner(ScriptTarget.Latest, /*skipTrivia*/ true)` defined at `src/services/utilities.ts:391` — constructed with the default `languageVariant = LanguageVariant.Standard` (`src/compiler/scanner.ts:1025`). It is shared across `services.ts`, `classifier.ts`, `completions.ts`, `formatting.ts`/`formattingScanner.ts`, `organizeImports.ts`, and `preProcess.ts`. A grep for `setLanguageVariant` across `src/services/` and `src/compiler/` shows `services.ts:509` and `:530` are the **only** two call sites that ever mutate this particular instance's language variant — this PR is the first code to touch it at all. Three other consumers of the same shared scanner call `scanner.setText(...)` directly without ever calling `setLanguageVariant`, implicitly relying on it staying `Standard`:
- `classifier.ts:123` (`scanner.setText(text)` — lexical classification, used for editor syntax highlighting)
- `completions.ts:1898` (`scanner.setText(sourceFile.text)` — import-completion `as`-keyword lookahead)
- `preProcess.ts:338` (`scanner.setText(sourceText)` — triple-slash/import reference preprocessing)

If `createChildren` throws mid-traversal on a `.tsx`/JSX-variant `sourceFile`, the shared scanner is left permanently in JSX variant. None of those three call sites will ever detect or fix this — they'll silently mis-tokenize (JSX-specific `<`/`>`/text scanning rules) whatever unrelated `.ts` file is processed next, with zero error surfaced.

This is not just theoretical for a live process: `src/server/session.ts:3919`'s `onMessage` has a top-level `catch (err)` that logs the error and continues serving requests — tsserver does not crash or reset state on a `Debug.fail`. So a single malformed/edge-case `getChildren()` call (a core primitive invoked pervasively by IDE features) would leave the corrupted shared scanner in place for the remainder of the server session, silently degrading unrelated files' classification/completion/import-preprocessing results.

This differs materially from the pre-existing `scanner.setText(undefined)` non-finally pattern noted in the task: every downstream consumer of the shared scanner already calls `setText(...)` itself before scanning (self-correcting on next use), whereas 3 of them never call `setLanguageVariant`, so a leaked variant is not self-healing for them. [Inference: no historical bug report for this exact throw path was located; the exception path and blast radius are confirmed by static reading, but real-world firing frequency is not independently verified.]

```json-findings
[
  {
    "severity": "HIGH",
    "confidence": 70,
    "agent": "silent-failure-hunter",
    "category": "edge-case",
    "file": "src/services/services.ts",
    "line": 509,
    "finding": "createChildren() sets the shared module-global scanner (src/services/utilities.ts:391, also used by classifier.ts, completions.ts, formattingScanner.ts, organizeImports.ts, preProcess.ts) to a JSX language variant with no try/finally. If node.forEachChild(processNode, processNodes) at line 527 throws — which it can, via addSyntheticNodes' unconditional Debug.fail() at line 544 for an unexpected Identifier token in trivia (debug.ts:196-204, not gated by any assertion-level no-op) — the reset at line 530 (scanner.setLanguageVariant(LanguageVariant.Standard)) never runs. This is the first code in the codebase to ever mutate this shared instance's language variant (confirmed via grep: services.ts:509/530 are the only setLanguageVariant call sites touching it). Three other consumers of the same singleton (classifier.ts:123, completions.ts:1898, preProcess.ts:338) call scanner.setText(...) without ever calling setLanguageVariant themselves, implicitly relying on it staying Standard — so a leaked JSX variant silently persists into their unrelated scans. src/server/session.ts:3919's top-level catch in onMessage logs the error and keeps the session alive rather than resetting process state, so a single Debug Failure while processing one (likely .tsx) file's getChildren() request leaves classifier/completions/preProcess mis-tokenizing subsequent unrelated .ts files for the rest of the session, with no log or user-visible indication of the corruption itself.",
    "hiddenErrors": "Any exception thrown by node.forEachChild's callbacks (addSyntheticNodes' Debug.fail, or any future change to processNode/processNodes/hasTabstop) is swallowed by the *absence* of a catch at this scope and propagates up uncaught, but the state-leak side effect (JSX variant left set) is never logged anywhere, so the resulting misbehavior in a completely different file/request is undiagnosable from logs alone.",
    "userImpact": "A single crashing getChildren() call on one file (e.g. a .tsx file hitting the Debug.fail edge case) can cause silently wrong syntax classification, import-name completion insert-text, or triple-slash/import preprocessing results in subsequent, unrelated files for the remainder of the tsserver session — no error, no log entry pointing at the cause.",
    "recommendation": "Wrap the scanner-mutating body of createChildren in try/finally, restoring both scanner.setText(undefined) and scanner.setLanguageVariant(LanguageVariant.Standard) in the finally block, so the shared singleton's invariant (Standard-by-default, correct text) holds regardless of exceptions from forEachChild/addSyntheticNodes.",
    "example": "scanner.setText((sourceFile || node.getSourceFile()).text);\nscanner.setLanguageVariant(languageVariant);\ntry {\n    ... (jsDoc pass, node.forEachChild(processNode, processNodes), addSyntheticNodes) ...\n} finally {\n    scanner.setText(undefined);\n    scanner.setLanguageVariant(LanguageVariant.Standard);\n}\nreturn children;"
  }
]
```
