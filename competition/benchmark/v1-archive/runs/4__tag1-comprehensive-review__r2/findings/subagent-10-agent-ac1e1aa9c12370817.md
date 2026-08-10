# subagent agent-ac1e1aa9c12370817

I have enough evidence. Here is my architectural assessment.

## Architectural Analysis

### Design Assessment

The functional fix is correct and minimal: JSX files must be scanned in the JSX language variant so `</` tokenizes as a single `LessThanSlashToken`, and `createChildren` now sources the variant from the file. However, the implementation introduces the first-ever mutation of a shared module-global scanner's language variant, breaking a previously-invariant "always Standard" assumption that four other service modules silently depend on, and it restores that invariant only on the happy path. Separately, the new field lands in the public `ts` API surface, inconsistent with its `@internal` siblings.

### Findings

#### High

- **[Coupling / Robustness]** `createChildren` sets the shared global scanner to the file's variant and resets it to `Standard` only on the normal return path — not exception-safe — src/services/services.ts:509
  - Evidence: `scanner` is a single module-global (`/** @internal */ export const scanner` at src/services/utilities.ts:391), created with the default `LanguageVariant.Standard` (src/compiler/scanner.ts:1025). It is shared by `organizeImports.ts`, `preProcess.ts`, `completions.ts`, `classifier.ts`, and `services.ts`. Before this PR, the *only* `setLanguageVariant` calls in all of `src/services` are the two this PR adds — meaning every other consumer relies on the scanner being in `Standard` variant without ever setting it. `createChildren` sets JSX at line 509, does work via `node.forEachChild(...)` → `addSyntheticNodes`, then resets to `Standard` at line 530. `addSyntheticNodes` contains a reachable `Debug.fail(...)` (services.ts:544) and `scanner.scan()`, either of which can throw between the set and the reset.
  - Why it matters: The language service is long-lived and catches per-request exceptions to keep serving. If `createChildren` throws after line 509, the shared scanner is left in JSX variant, and the *next* unrelated caller (classifier, organizeImports, preProcess, completions) scans with the wrong variant — producing silent mis-tokenization (`</` handling differs between variants) rather than a loud crash. This is strictly worse than the pre-existing `setText(undefined)` reset, whose failure mode is an obvious crash on next use. The PR converts a held invariant into fragile temporal coupling on shared mutable state.
  - Recommendation: Wrap the body in `try { ... } finally { scanner.setText(undefined); scanner.setLanguageVariant(LanguageVariant.Standard); }` so the reset always runs. (Rejected alternative: a function-local scanner would be fully isolated, but that departs from the module's established shared-scanner convention and adds per-call allocation on a hot path; try/finally preserves the convention while closing the gap.)
  - Confidence: 80/100

#### Medium

- **[Public API / Evolution]** New `languageVariant?: LanguageVariant` on `SourceFileLike` is exported into the public `ts` namespace, unlike its `@internal` siblings — src/compiler/types.ts:4291
  - Evidence: The two adjacent fields in `SourceFileLike` (`lineMap`, `getPositionOfLineAndCharacter`) both carry `/** @internal */`; the new field does not, so it surfaces in the public baseline (tests/baselines/reference/api/typescript.d.ts:5910). The field's only consumer is the internal `createChildren`. `SourceFileLike` is a genuine public parameter type (`getPositionOfLineAndCharacter`, `getLineAndCharacterOfPosition`, `getWidth`), but those functions read `lineMap`, not the variant, so no public caller benefits from setting it.
  - Why it matters: TypeScript treats its exported API as near-immutable; every public field becomes a permanent maintenance obligation. The addition is backward-compatible (optional), so this is not a breaking change — but it widens the contract with no public consumer. Strongest counter-argument: the concrete `SourceFile` already exposes `languageVariant` publicly, so mirroring it on `SourceFileLike` is arguably consistent; however, an internal utility can read it via an `@internal` field exactly as the two siblings do, so public exposure is not required.
  - Recommendation: Mark the field `/** @internal */` to match the sibling fields and the internal-only consumer, keeping the field out of the public baseline.
  - Confidence: 78/100

### Positive Observations

- The core fix is coherent and consistent across the module: the same `SlashToken` → `LessThanSlashToken` correction is applied uniformly in `completions.ts` and `utilities.ts` where JSX closing-tag tokens are matched, so the variant change and the downstream token expectations stay in sync.
- Adding `scanner.setLanguageVariant(Standard)` alongside the pre-existing `scanner.setText(undefined)` reset correctly mirrors the module's existing cleanup convention on the happy path.
- Sourcing the variant from the `SourceFile` (which already carries `languageVariant`) rather than inventing a new per-file signal is the right model — it reuses the compiler's existing per-file variant representation.

### Recommendations

1. Make the shared-scanner variant reset exception-safe (try/finally) so a throw in `addSyntheticNodes` cannot leak JSX variant into subsequent unrelated scans in the long-lived language service.
2. Mark `SourceFileLike.languageVariant` as `/** @internal */` unless a public consumer is actually intended, keeping it consistent with the interface's other internal fields and off the permanent public contract.

```json-findings
[{"severity":"High","confidence":80,"agent":"architecture-reviewer","category":"architecture-coupling","file":"src/services/services.ts","line":509,"finding":"createChildren mutates the shared module-global scanner's language variant (first such mutation in all of src/services) and restores it to Standard only on the normal return path. A reachable throw (Debug.fail / scanner.scan in addSyntheticNodes) between set and reset leaves the shared scanner in JSX variant; because organizeImports/preProcess/completions/classifier all reuse this scanner and rely on it being Standard without ever setting it, a subsequent unrelated request in the long-lived language service scans with the wrong variant, causing silent mis-tokenization rather than a loud failure.","remediation":"Wrap the body in try/finally so scanner.setText(undefined) and scanner.setLanguageVariant(LanguageVariant.Standard) always run even on exception."},{"severity":"Medium","confidence":78,"agent":"architecture-reviewer","category":"architecture-coupling","file":"src/compiler/types.ts","line":4291,"finding":"New languageVariant?: LanguageVariant added to SourceFileLike lacks the /** @internal */ marker its two sibling fields carry, so it surfaces in the public ts API baseline (typescript.d.ts). The field's only consumer is the internal createChildren, and no public consumer of SourceFileLike (getPositionOfLineAndCharacter/getLineAndCharacterOfPosition/getWidth) needs it, so this permanently widens the exported public contract without benefit.","remediation":"Add /** @internal */ to the field to match the sibling fields and the internal-only consumer, keeping it out of the public API baseline."}]
```
