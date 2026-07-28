# subagent agent-a794717b025a5dc43

## Verdict: CONFIRMED

### Evidence trail

**1. Shared scanner singleton, confirmed.**
`src/services/utilities.ts:391`: `export const scanner: Scanner = createScanner(ScriptTarget.Latest, /*skipTrivia*/ true);` — one module-level instance imported by `services.ts`, `preProcess.ts`, `completions.ts`, `classifier.ts`, `organizeImports.ts`.

**2. No try/finally around the set/reset in `createChildren`, confirmed.**
`src/services/services.ts:497-532` (`createChildren`) sets `scanner.setText(...)` / `scanner.setLanguageVariant(languageVariant)` at 508-509, walks the tree via `node.forEachChild(processNode, processNodes)` at 527 and `addSyntheticNodes` at 528, then resets both at 529-530 — straight-line code, no try/finally.

**3. `Debug.fail` throws unconditionally, confirmed.**
`src/compiler/debug.ts:196-204`: `export function fail(...): never { ...; throw e; }` — not gated by an assertion-level check (unlike `Debug.assert`), so it fires in every build. It's reached from `addSyntheticNodes` at `services.ts:544` when an `Identifier` token appears in trivia and `hasTabstop(parent)` is false — a known, if narrow, invariant-violation crash pattern in the language service (malformed/reused node trees), not purely theoretical.

**4. `setText` does not reset `languageVariant`, confirmed.**
`src/compiler/scanner.ts:3993-3997` (`setText`) only touches `text`/`end`/token position via `resetTokenState`; `languageVariant` is a separate closure variable only mutated by `setLanguageVariant` (line 4007-4009). `resetTokenState` (4019-4027) doesn't touch it either.

**5. The "not self-healing" distinction holds — verified directly.**
Grepped every `scanner.setLanguageVariant` call in the repo: only two exist on this shared scanner, both inside the function under review (`services.ts:509` and `:530`). `preProcess.ts:338`, `completions.ts:1898`, `classifier.ts:123`, `organizeImports.ts:248` all call `scanner.setText(...)` but **never** `scanner.setLanguageVariant(...)`. (The other two `setLanguageVariant` call sites in the codebase — `parser.ts:1775` and `checker.ts:33079` — operate on their *own* independent `createScanner(...)` instances, confirmed via `grep createScanner` in those files, so they're irrelevant to this shared singleton.)

**6. Attribution confirmed as newly introduced, not pre-existing.** `git show 02672d281 -- src/services/services.ts` shows both `scanner.setLanguageVariant(...)` lines are net-new additions in this exact commit (#61928). Before this PR, nothing ever called `setLanguageVariant` on this shared scanner, so its variant was permanently `LanguageVariant.Standard` (the `createScanner` default, `scanner.ts:1025`) for the service's entire lifetime. This directly refutes quick-reviewer's dismissal: the pre-existing `setText` leak is self-healing because *every* consumer must call `setText` before scanning (a hard requirement to scan anything), but `setLanguageVariant` was never part of that contract for any consumer except this new code — so there's no equivalent "everyone resets it anyway" safety net.

**7. Consequence confirmed real, not hypothetical.** The same commit changes `completions.ts` logic to distinguish `SyntaxKind.LessThanSlashToken` (JSX variant) from `SyntaxKind.SlashToken`+`SyntaxKind.LessThanToken` (Standard variant) — i.e., the variant genuinely changes how `</` tokenizes, exactly as the finding claims, and `completions.ts`, `classifier.ts`, and `preProcess.ts` all scan raw source text with this shared scanner without ever re-asserting Standard variant.

### Severity calibration

I'd land on **Medium**, not High: the trigger (`Debug.fail` on an already-invariant-violated tree) requires a pre-existing tree malformation that's itself rare, and the leak self-heals on the very next `createChildren` call (which sets the variant unconditionally from that call's own `sourceFile` at the top, not conditionally) — and `getChildren`/`createChildren` is invoked pervasively throughout the language service, so the exposure window is often short in practice. But it's a real, newly-introduced, uncontained global-mutable-state hazard with a demonstrable (if narrow) trigger and a demonstrable (if transient) blast radius across unrelated shared-scanner consumers — not a mere style nit, and not equivalent to the pre-existing self-healing `setText` pattern as quick-reviewer claimed. Low/dismiss is not warranted; the "quick-reviewer" verdict is refuted by evidence, not just disagreement.

```json
{
  "finding": "the shared-scanner language-variant leak in createChildren",
  "verdict": "confirmed",
  "reason": "Verified directly: scanner is a shared singleton (utilities.ts:391); createChildren (services.ts:497-532) sets/resets setText+setLanguageVariant with no try/finally; Debug.fail (debug.ts:196-204) throws unconditionally and is reachable from addSyntheticNodes (services.ts:544); and critically, grepping every setLanguageVariant call on this scanner shows only createChildren's two calls exist — preProcess.ts:338, completions.ts:1898, classifier.ts:123, organizeImports.ts:248 call setText but never setLanguageVariant, so unlike the pre-existing self-healing setText pattern, nothing else resets a leaked JSX variant. git show on commit 02672d281 confirms both setLanguageVariant calls are net-new in this PR (pre-PR the scanner's variant was permanently Standard), refuting quick-reviewer's 'same as pre-existing pattern' dismissal.",
  "corrections": {
    "line": 507
  }
}
```

Suggested calibrated severity for the orchestrator: **Medium** (real, newly-introduced, correctly attributed defect; narrow but non-theoretical trigger; transient but real cross-consumer blast radius; self-heals on the next `createChildren` call rather than persisting indefinitely).
