# subagent agent-a62877d94d160b6d5

I now have a complete picture. Let me write up my findings.

---

## Type: `SourceFileLike` (adding `languageVariant?: LanguageVariant`)

Analysis of the type change in `src/compiler/types.ts:4291` and its ripple through `getChildren`/`createChildren`.

### How the pieces fit (verified)

- `SourceFileLike` (`src/compiler/types.ts:4285-4292`) is documented as "Subset of properties from SourceFile that are used in multiple utility functions." Its members before this PR: required `text`, and two `@internal` optional members (`lineMap?`, `getPositionOfLineAndCharacter?`). This PR adds `languageVariant?: LanguageVariant` — the only optional member *without* `@internal`.
- The full `SourceFile` already has a **required** `languageVariant: LanguageVariant` (`src/compiler/types.ts:4359`); the concrete `SourceFileObject` class declares it `public languageVariant!: LanguageVariant` (`src/services/services.ts:1102`). A required field trivially satisfies the new optional one, so there is **no widening/narrowing type error** — a real `SourceFile` remains structurally assignable to `SourceFileLike`.
- The consuming code is `createChildren` (`src/services/services.ts:497-532`), reached only from the public `Node.getChildren` (`src/services/services.ts:462-464`), whose default argument is `getSourceFileOfNode(this)` — a *real* `SourceFile`. The scanner it drives is the shared module-level singleton `export const scanner` (`src/services/utilities.ts:391`), which is why the PR both sets the variant (`:509`) and resets it to `Standard` afterward (`:530`) to avoid leaking JSX state.
- The bug being fixed: in JSX mode the scanner emits a single `LessThanSlashToken` for `</`; in Standard mode it emits `LessThanToken` + `SlashToken` (`src/compiler/scanner.ts:2205`). `createChildren` re-scans through `SourceFileLike`, which previously carried no variant, so JSX files were mis-tokenized. The rest of the diff (completions.ts, utilities.ts, baselines) just updates token-kind checks to the now-correct `LessThanSlashToken`.
- Established convention elsewhere: every other scanning site constructs its scanner with the variant taken directly from a real `SourceFile` — `createScanner(sourceFile.languageVersion, /*skipTrivia*/ true, sourceFile.languageVariant, …)` (`src/compiler/utilities.ts:2459, 2467, 2543`; `src/services/organizeImports.ts:225`). `createChildren` was the outlier because it operates on `SourceFileLike`, which lacked the field.

### Invariants Identified

1. **`text` is the file's source text** (pre-existing, required).
2. **Intended new invariant**: `languageVariant` describes how `text` must be tokenized, and for a JSX file it *must* be `JSX` or the token stream is wrong. The code encodes only a weaker rule: *absent ⇒ treat as `Standard`* (`src/services/services.ts:507`).
3. **Consistency invariant (unstated, unenforced)**: `languageVariant` and `text` must describe the same file. Nothing prevents a `SourceFileLike` with JSX `text` but no/`Standard` variant.
4. For a real `SourceFile`, the variant is always present and authoritative; the optional-ness only matters for the lightweight implementers.

### Lightweight implementers (the reason optionality was chosen)

Two hand-built `SourceFileLike` objects exist and **neither sets `languageVariant`**, so both silently resolve to `Standard`:
- `createSourceFileLike` in `src/services/sourcemaps.ts:231-239` (sourcemap position mapping — never reaches `getChildren`, so harmless today).
- The inline `file: SourceFileLike` in `src/services/textChanges.ts:1339-1345` — notably this code already has the correct variant at hand and passes it *separately* as an explicit parameter to `formatNodeGivenIndentation(node, file, targetSourceFile.languageVariant, …)` (`:1345`). That is a telling precedent: when the variant genuinely mattered, the existing code threaded it as a parameter rather than relying on the file-like object.

### Ratings

- **Encapsulation**: 4/10
  `SourceFileLike` is by design an open structural DTO — a property bag with no invariant protection — so encapsulation is inherently low and this change neither helps nor fundamentally hurts that. The specific negative: the new member is **public** while its structurally-identical siblings (`lineMap?`, `getPositionOfLineAndCharacter?`) are `@internal` (`src/compiler/types.ts:4287-4290`). The field exists solely to feed the internal scanner, yet it was added to the public contract. That is an encapsulation/consistency regression relative to the interface's own convention.

- **Invariant Expression**: 3/10
  The optional type expresses "maybe I know my variant; if not, assume Standard," which **conflates "unknown" with "Standard."** That is precisely the failure mode the PR is fixing (JSX mis-scanned as Standard). The type gives no compile-time signal to a JSX-producing implementer that omitting the field silently corrupts tokenization. The real invariant — "the variant must match the text" — is not expressible with an optional field defaulting to one of the two meaningful values.

- **Invariant Usefulness**: 6/10
  The datum itself is genuinely useful and the fix is real: it aligns `createChildren` with every other scanning site and repairs JSX token classification/completions. Net positive. It is docked because the *optional-with-silent-default* framing delivers the benefit only to the path (real `SourceFile`) that already had the data, while doing nothing to guarantee correctness for the lightweight path that motivated the optionality in the first place.

- **Invariant Enforcement**: 2/10
  Nothing enforces it. No construction-time validation (structural interface, no constructor); both lightweight constructors omit the field and get `Standard` for free; every consumer must remember `?? LanguageVariant.Standard`. Worse, `createChildren` is **asymmetric**: `text` falls back to `node.getSourceFile().text` when `sourceFile` is undefined (`:508`), but the variant does **not** fall back to `node.getSourceFile().languageVariant` — it falls straight to `Standard` (`:507`). The `sourceFile: SourceFileLike | undefined` signature permits `undefined`; on that path a JSX file would take its text from the real source file but its variant from the bare `Standard` default — reintroducing the exact mis-scan class on the undefined branch. It is latent today only because the sole caller (`getChildren`) defaults the argument to a real `SourceFile`.

### Strengths

- Correctly fixes a real tokenization bug and does so in line with the codebase's established `createScanner(..., sourceFile.languageVariant)` pattern.
- Places the datum on the object that represents the file (good cohesion) rather than adding a variant parameter to the public `getChildren` signature — that keeps the public method signature stable.
- Optionality is defensible on backward-compatibility grounds and is consistent with the interface's existing "optional capability" members (`lineMap?`, `getPositionOfLineAndCharacter?`).
- Properly resets the shared singleton scanner's variant afterward (`:530`), avoiding cross-call state leakage.

### Concerns

1. **Silent-default trap (primary).** `sourceFile?.languageVariant ?? LanguageVariant.Standard` (`src/services/services.ts:507`) treats "absent" as "Standard." A future JSX-producing `SourceFileLike` that forgets the field is mis-scanned with zero compile-time or runtime signal — the same bug this PR fixes.
2. **Asymmetric fallback (latent bug).** For `undefined` `sourceFile`, `text` comes from `node.getSourceFile()` but the variant does not (`:507-508`). The variant should be derived from the *same* source the text is.
3. **Public API commitment.** Added without `@internal` (confirmed by the `tests/baselines/reference/api/typescript.d.ts` change), so it becomes a permanent public member. `LanguageVariant` is already public, so the type is API-consistent, but the *member* is an internal scanning detail whose `@internal` siblings set the opposite precedent. A public optional member is a forward commitment (external implementers may start reading/writing it; removing or tightening it later is breaking).
4. **Two sources of truth (mild).** The full `SourceFile.languageVariant` (required, authoritative) and `SourceFileLike.languageVariant` (optional, defaultable) now coexist. No *type* hazard (required satisfies optional), but a semantic one: consumers holding a `SourceFileLike` cannot distinguish "Standard" from "unknown, assumed Standard."

### Recommended Improvements (in priority order, all low-cost)

1. **Mark it `@internal`.** `/** @internal */ languageVariant?: LanguageVariant;` — matches the sibling members (`src/compiler/types.ts:4287-4290`), keeps the field usable on every internal path, preserves structural compatibility with the real `SourceFile` (checked against internal types at build time), and avoids a permanent public-API commitment for what is an internal scanning detail. This is the single highest-value, lowest-risk change.
2. **Fix the asymmetric fallback.** Derive the variant from the same object the text comes from: compute it as `(sourceFile ?? node.getSourceFile()).languageVariant ?? LanguageVariant.Standard` (mirroring the `text` line at `:508`). This closes the `undefined`-path hole so text and variant always describe the same file.
3. **Prefer required over optional *if* API churn is acceptable.** Making `languageVariant: LanguageVariant` required would force each of the two lightweight constructors (`sourcemaps.ts:231`, `textChanges.ts:1339`) to state `LanguageVariant.Standard` explicitly, converting a silent default into a conscious decision and eliminating every `?? Standard` at the consumer. This is the strongest invariant expression but is a larger change and a breaking one for any external `SourceFileLike` implementer, so it is secondary to (1) and (2).
4. **Threading as a parameter is not recommended here.** Although `textChanges.ts:1345` sets that precedent for formatting, `getChildren`'s variant genuinely belongs to the file, and adding a parameter to the public `Node.getChildren` signature would be higher blast-radius than the property. Keep it on the object.

### Overall Verdict

**The change is correct and fixes a real bug, but the type design is the weakest defensible option.** Attaching the variant to `SourceFileLike` is the right *location* (cohesive, keeps the public `getChildren` signature stable), and optionality is a reasonable backward-compat concession. However, the **optional-with-silent-`Standard`-default encoding re-creates the very "JSX-scanned-as-Standard" failure class the PR set out to eliminate** — it merely relocates it from the real-`SourceFile` path (now fixed) to any lightweight or `undefined` path (still latent, shielded only by the current single caller). Two small, non-breaking edits would materially improve it: **mark the member `@internal`** (API hygiene + consistency with its siblings) and **make `createChildren` take the variant from the same object as the text** (close the asymmetric-fallback hole). Aggregate: **encapsulation 4, expression 3, usefulness 6, enforcement 2** — a useful fix riding on an under-specified invariant.

Key references: `src/compiler/types.ts:4285-4292` (interface), `:4359` (required twin), `:7677` (public `LanguageVariant`); `src/services/services.ts:462-464` (`getChildren`), `:497-532` (`createChildren`), `:507-508` (silent default + asymmetry), `:530` (scanner reset), `:1102` (concrete required field); lightweight implementers `src/services/sourcemaps.ts:231-239` and `src/services/textChanges.ts:1339-1345`; established pattern `src/compiler/utilities.ts:2459`; public-API baseline `tests/baselines/reference/api/typescript.d.ts` (adds `languageVariant?: LanguageVariant` to public `interface SourceFileLike`).
