# subagent agent-aec0aa3a41438fd78

## Architectural Analysis

### Design Assessment

This is a small, targeted correctness fix: `createChildren()` now scans JSX/TSX source in the JSX language variant so that `getChildren()` reconstructs `</`-style closing tags as a single `LessThanSlashToken` (matching the parser's real tree) rather than the split `<` + `/` tokens the Standard variant produced. The token-kind updates in `completions.ts`/`utilities.ts` correctly follow that change and actually *reduce* an existing skew between the parser tree and `getChildren()`. The two concerns worth surfacing are the shape of the new public-API property and the shared mutable scanner state.

### Findings

#### High

- **[api-design]** New `languageVariant?: LanguageVariant` on `SourceFileLike` is not marked `@internal`, unlike its sibling optional members — `src/compiler/types.ts:4291`
  - Why it matters: The other two optional members of this interface (`lineMap`, `getPositionOfLineAndCharacter`) both carry `/** @internal */`; only `readonly text` is public. The new property omits the tag, so it leaks into the published `typescript.d.ts` (confirmed at `tests/baselines/reference/api/typescript.d.ts:5910`), permanently widening TypeScript's public API contract and pulling `LanguageVariant` into the public `SourceFileLike` surface. The property's only consumer is the internal `createChildren()`; `@internal` controls only d.ts emission, not internal compilation, so marking it internal would not affect the fix. This reads as an accidental omission rather than a deliberate public-API decision. Adding an optional property is backward-compatible for existing implementers, but once published it is subject to API-stability guarantees and cannot be cheaply changed or removed.
  - Recommendation: Add `/** @internal */` above `languageVariant?: LanguageVariant`, matching the two sibling members, then regenerate the API baseline. Alternative considered: keeping it public if external `SourceFileLike` implementers legitimately need to influence child scanning — rejected because no public code path reads it and the fix works identically when internal.
  - Confidence: 88/100

#### Medium

- **[coupling]** Shared module-level `scanner` singleton has its language variant mutated globally and reset only on the happy path — `src/services/services.ts:509,530`
  - Why it matters: `scanner` is a process-wide singleton (`src/services/utilities.ts:391`, defaulting to `LanguageVariant.Standard`) shared by at least three modules. `completions.ts:1898` and `preProcess.ts:338` call `scanner.setText(...)`/`scan()` without ever setting a variant, i.e. they implicitly depend on the singleton being in Standard. `createChildren()` now sets the variant on entry and resets it (`setText(undefined)` + `setLanguageVariant(Standard)`) only after `node.forEachChild(...)` returns normally, with no `try/finally`. If scanning throws mid-function (e.g. a `Debug` assertion), the singleton is left in JSX variant and silently corrupts subsequent token classification in those other consumers until the next `createChildren` call self-heals it. This extends a pre-existing fragility — `setText(undefined)` already had the same happy-path-only reset — so the change widens an existing debt rather than introducing a new class. The reset *target* (Standard) is correct: it restores the singleton's construction-time baseline that the other consumers assume, so save/restore-previous is not needed.
  - Recommendation: Wrap the body in `try { ... } finally { scanner.setText(undefined); scanner.setLanguageVariant(LanguageVariant.Standard); }` so both pieces of shared state are restored on all exit paths. Alternative considered: creating a per-call scanner from the source file (the pattern used in `src/compiler/utilities.ts:2459` and Corsa, per the PR narrative) — cleaner and eliminates the shared-state coupling entirely, but a larger change than this fix intends; the `finally` is the minimal step.
  - Confidence: 78/100

### Positive Observations

- The token-kind updates are consistent with the fix: `getChildren()` now emits `LessThanSlashToken` for JSX closing tags, aligning it with the parser's real tree (`src/compiler/parser.ts:6339,6355` already use `parseExpected(LessThanSlashToken)`), so the change removes a parser-vs-`getChildren` skew rather than adding one.
- The remaining `SlashToken`/`LessThanToken` references I checked are legitimately unrelated to closing tags (self-closing `/>` in `completions.ts:4834`/`formatting/rules.ts:188`, opening `<` in `utilities.ts:1875-1918`, regex rescanning in `classifier.ts`), so I found no concrete stale consumer left behind. The affected classification baselines were updated in the same PR.

### Recommendations

1. Mark `languageVariant?` as `@internal` and regenerate the API baseline unless a public `SourceFileLike` consumer genuinely needs it (High).
2. Add a `try/finally` around the mutate/reset of the shared `scanner` in `createChildren()` to keep the singleton's variant and text from leaking across the services modules that share it (Medium).

```json-findings
[{"severity":"High","confidence":88,"category":"other","file":"src/compiler/types.ts","line":4291,"finding":"New optional member `languageVariant?: LanguageVariant` on the public `SourceFileLike` interface omits the `/** @internal */` tag carried by its two sibling optional members (`lineMap`, `getPositionOfLineAndCharacter`), so it leaks into the published typescript.d.ts (tests/baselines/reference/api/typescript.d.ts:5910) and permanently widens the public API surface. Its only consumer is the internal createChildren(); @internal affects only d.ts emission, not the fix.","remediation":"Add `/** @internal */` above `languageVariant?: LanguageVariant` to match the sibling members and regenerate the API baseline, unless an external SourceFileLike implementer genuinely needs to set it.","source":"architecture-reviewer"},{"severity":"Medium","confidence":78,"category":"architecture-coupling","file":"src/services/services.ts","line":509,"finding":"createChildren() mutates the process-wide shared `scanner` singleton (src/services/utilities.ts:391, default Standard) via setLanguageVariant, but resets it only after node.forEachChild returns normally with no try/finally. If scanning throws, the singleton is left in JSX variant and silently corrupts other consumers that read it without setting a variant (completions.ts:1898, preProcess.ts:338). Extends the pre-existing happy-path-only reset of setText(undefined).","remediation":"Wrap the scan body in try/finally so scanner.setText(undefined) and scanner.setLanguageVariant(LanguageVariant.Standard) run on all exit paths; longer term prefer a per-source-file scanner as done in src/compiler/utilities.ts:2459.","source":"architecture-reviewer"}]
```
