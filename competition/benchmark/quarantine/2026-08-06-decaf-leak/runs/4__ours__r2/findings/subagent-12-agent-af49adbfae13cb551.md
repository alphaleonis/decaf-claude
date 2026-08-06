# subagent agent-af49adbfae13cb551

I have enough to build the system model and evaluate the design. Let me record my findings.

## System Model

**Boundary/shared-state**: `scanner` is a module-level singleton (`utilities.ts:391`, `createScanner(ScriptTarget.Latest, /*skipTrivia*/ true)` — defaults to `LanguageVariant.Standard`). It is imported and used by three service modules that share the one instance: `services.ts` (`createChildren`), `completions.ts` (`:1898` `setText`/`resetTokenState`/`scan`), and `preProcess.ts` (`:338`). `classifier.ts` and `organizeImports.ts` create their own local scanners and are unaffected.

**Contract**: `Node.getChildren(sourceFile?)` is public. `createChildren` re-scans source text to synthesize trivia/punctuation token nodes. Before this PR the shared scanner's variant was never mutated by `createChildren`, so it was permanently `Standard`.

**Data flow**: `getChildren(sourceFile = getSourceFileOfNode(this))` → `createChildren(node, sourceFile)`. `node.getSourceFile()` is itself `getSourceFileOfNode(this)` — the same function — so the text fallback and the default param resolve identically. `SourceFileLike` can also be an incomplete object (e.g. `textChanges.ts:1339` constructs one with `text` + `getLineAndCharacterOfPosition` but **no** `languageVariant`).

**Scanner API note**: `scanner.ts` exposes `setLanguageVariant` but **no** `getLanguageVariant` getter (verified) — so "save/restore prior variant" is not directly available.

## Findings

```json
[
  {
    "file": "src/services/services.ts",
    "line": 530,
    "severity": "High",
    "category": "design",
    "issue": "[CONCURRENCY_DESIGN] The shared `scanner` singleton's language variant is set to JSX at line 509 and reset to Standard at line 530 outside any try/finally. If `node.forEachChild(...)` or `addSyntheticNodes` throws (e.g. the `Debug.fail` at line 544), both resets are skipped and the process-wide shared scanner is left in JSX variant. Unlike the pre-existing text mutation (every consumer — completions.ts:1898, preProcess.ts:338 — calls `setText` before scanning and thus self-heals a leaked text), no consumer calls `setLanguageVariant`; they all assumed the scanner was permanently Standard. This PR breaks that invariant, so a leaked JSX variant persists across language-service requests and can mis-tokenize subsequent unrelated scans in completions/preProcess.",
    "fix": "Wrap the scan in try/finally so the variant (and text) reset always runs. Alternatively, have shared-scanner consumers set the variant they expect. The asymmetry — text is defensively re-set by every consumer but variant is not — is the core gap.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/services/services.ts",
    "line": 507,
    "severity": "Medium",
    "category": "design",
    "issue": "[DATA_MODEL] The scan text is derived from `sourceFile || node.getSourceFile()` but the language variant is derived only from `sourceFile?.languageVariant`. These two sources can diverge: a caller may pass an incomplete `SourceFileLike` that carries `text` but not `languageVariant` (e.g. the literal constructed at textChanges.ts:1339 has no languageVariant), or the fallback path uses `node.getSourceFile()` for text while the variant silently defaults to Standard. In those cases JSX/TSX content is scanned with the Standard variant — reintroducing exactly the `</div>` mis-tokenization this PR set out to fix. The authoritative variant on `node.getSourceFile().languageVariant` is available but never consulted.",
    "fix": "Derive the variant from the same resolved source used for text, with the node's real source file as the fallback, e.g. `const sf = sourceFile ?? node.getSourceFile(); scanner.setText(sf.text); scanner.setLanguageVariant((sourceFile?.languageVariant ?? node.getSourceFile().languageVariant) ?? LanguageVariant.Standard);` so text and variant stay consistent even for incomplete SourceFileLike implementers.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/services/services.ts",
    "line": 530,
    "severity": "Low",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] The reset restores a hard-coded `LanguageVariant.Standard` rather than the scanner's prior variant. This is correct only because of the unstated invariant that the shared scanner is always Standard outside `createChildren` (no current consumer sets it otherwise). It couples createChildren's correctness to that global assumption: if a future consumer ever leaves the shared scanner in a non-Standard variant, an unrelated `getChildren` call would silently clobber it. The Scanner API also exposes no `getLanguageVariant` getter, so a robust save/restore is not currently expressible — which itself signals the shared-mutable-scanner pattern is fragile for per-call variant state.",
    "fix": "Prefer restoring the prior variant (would require adding a `getLanguageVariant` getter) over hard-coding Standard, or document the 'shared scanner is always Standard' invariant at the singleton declaration so future consumers don't depend on reading it back.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/compiler/types.ts",
    "line": 4291,
    "severity": "Low",
    "category": "design",
    "issue": "[API_CONTRACT] `languageVariant?: LanguageVariant` was added to `SourceFileLike` without an `@internal` annotation, unlike its two immediately-preceding sibling members (`lineMap`, `getPositionOfLineAndCharacter`) which are `@internal`. It therefore surfaces in the public `typescript.d.ts` baseline and permanently grows the minimal public `SourceFileLike` contract (the doc comment describes it as a 'subset of properties'). Its only consumer, `createChildren`, is internal. Public exposure may be intentional (so external callers passing a custom SourceFileLike to `node.getChildren()` can opt into correct JSX scanning), but once public it cannot be removed without a breaking change, and the visibility divergence from its siblings is worth confirming.",
    "fix": "Confirm the intent. If external implementers are meant to supply the variant, keep it public and document why; if it exists solely for internal createChildren use, mark it `/** @internal */` to match its siblings and keep the public surface minimal.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Coordinated `SlashToken`/`LessThanToken` → `LessThanSlashToken` update (completions.ts, utilities.ts, test baselines)** — Sound and consistent. With the JSX variant now correctly applied, the re-scan produces `</` as a single `LessThanSlashToken`, matching what the *parser* already emits for `JsxClosingElement`. This PR makes `getChildren`'s re-scan consistent with the parser's tokenization (a cross-cutting consistency *fix*). I checked the remaining `SlashToken`/`LessThanToken` sites near JSX contexts (completions.ts:4834/4843 self-closing `/>`, utilities.ts:1875/1880/1918 and completions.ts:3154 opening-tag `<`); those are opening/self-closing contexts where the tokenization is unchanged (JSX only merges `</`, not `/>` or a lone `<`), so leaving them as `SlashToken`/`LessThanToken` is correct. No missed closing-tag consumer found.

- **Public token-stream behavior change of `Node.getChildren()` for JSX/TSX** — External API consumers that walked the old `<`,`/`,`div`,`>` sequence for `</div>` now get `</`,`div`,`>`. This is an observable public-API behavior change, but it is a correctness fix aligning the re-scan with the parser/AST, so I treat the direction as intended and sound rather than a regression.

- **Text-leak on exception via the same non-finally block** — Pre-existing (`scanner.setText(undefined)` was already outside any try/finally before this PR) and self-healing (every shared-scanner consumer calls `setText` before scanning). Only the *variant* dimension is newly leak-prone and not self-healed; captured in finding 1.

- **Re-entrancy within `createChildren`** — `forEachChild` callbacks only push nodes; they do not call `getChildren`, so there is no direct recursion into the shared scanner within a single `createChildren` invocation. Not a concern.

### Probe Requests (optional, to strengthen finding 2 reachability)
- Trace whether `formatting.formatNodeGivenIndentation` (reached from `textChanges.ts:1339`, which passes a `SourceFileLike` literal lacking `languageVariant`) ever calls `node.getChildren(file)` with that variant-less object on a TSX target — a `grep`/call-graph trace from `formatNodeGivenIndentation` to any `getChildren(`/`getChildAt(`/`getFirstToken(` on the passed `sourceFile`. If it does, finding 2 is a confirmed live path rather than a latent one.
