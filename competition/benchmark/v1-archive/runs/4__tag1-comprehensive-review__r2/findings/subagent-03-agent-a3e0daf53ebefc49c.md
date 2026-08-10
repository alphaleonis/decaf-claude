# subagent agent-a3e0daf53ebefc49c

## Type design review: `SourceFileLike.languageVariant` (src/compiler/types.ts:4291)

**What changed.** `src/compiler/types.ts:4285-4292` (`SourceFileLike`) gained `languageVariant?: LanguageVariant;` directly below two `@internal`-tagged siblings (`lineMap?`, `getPositionOfLineAndCharacter?`, lines 4288-4290). The new field carries **no** `@internal` tag. `SourceFile.languageVariant` (line 4359) remains mandatory, non-optional, non-readonly. The field's only production consumer is `src/services/services.ts:507`: `const languageVariant = sourceFile?.languageVariant ?? LanguageVariant.Standard;`, feeding `scanner.setLanguageVariant` inside the internal `createChildren` helper — a fix for JSX closing-tag (`</`) tokenization in `getChildren()`.

**Encapsulation (4/10).** `SourceFileLike` is an intentionally duck-typed "subset of `SourceFile`" bag (per its own doc comment) with no behavior — consistent with the rest of the file, so a plain optional field isn't itself a violation of that pattern. What *is* a genuine encapsulation failure is that an implementation detail needed by exactly one internal function (`createChildren`) was placed on a structural interface without the `@internal` tag its neighbors carry, and it consequently leaked into the shipped public `.d.ts` (`tests/baselines/reference/api/typescript.d.ts`, confirmed via `git diff`). Nothing about this member's design signals "public API decision" — it reads exactly like an oversight, not an encapsulation boundary that was deliberately opened.

**Invariant expression (5/10).** Optional-on-`SourceFileLike` vs. mandatory-on-`SourceFile` mirrors the existing pattern for `lineMap`/`getPositionOfLineAndCharacter`/`getLineAndCharacterOfPosition` (the latter added via module augmentation in `src/services/types.ts:180`, also public, also no way to tell from the type alone what "absent" means). So this isn't a new problem introduced by this PR, but the PR does nothing to improve it: nothing in the type signals that "absent" silently means `LanguageVariant.Standard` to the one caller that reads it (`services.ts:507`) and means "not applicable" to every other consumer of `SourceFileLike` that ignores the field entirely. Two sources of truth exist by construction (`SourceFile.languageVariant`, always correct; ad hoc `SourceFileLike` literals, which may or may not set it) and the type gives no hint which one you're holding.

**Usefulness (4/10).** `LanguageVariant` is the correct type (matches `SourceFile.languageVariant` and `Scanner.setLanguageVariant`'s parameter) — no complaint there. But as a *public* member it has no known external consumer and no stated use case beyond the one internal call site; it commits the public API to a member whose contract ("optional, defaults to Standard somewhere, but only if the caller happens to be `createChildren`") isn't something a plugin author or `SourceFileLike`-implementing consumer can reason about from the declaration alone.

**Enforcement (3/10).** There is no runtime or compile-time mechanism keeping `SourceFileLike.languageVariant` consistent with the source file's actual syntax. Concretely, two existing `SourceFileLike`-literal producers never set it: `src/services/textChanges.ts:1339-1344` (`getFormattedTextOfNode`'s synthetic `file`) and `src/services/sourcemaps.ts:231-238` (`createSourceFileLike`). Both currently happen to be non-JSX-scanning contexts, so today's behavior is fine, but the type system will not stop a future caller from passing a hand-built `SourceFileLike` for JSX content into `getChildren()`/`createChildren` without setting `languageVariant` — it will silently default to `Standard` and mis-tokenize `</` as separate `LessThanToken`+`SlashToken` rather than `LessThanSlashToken`, exactly the class of bug this PR fixed for the `SourceFile` case, now reintroduced as a latent trap for `SourceFileLike` literals.

**Strengths.** Correct type choice; the actual bug fix (JSX-aware scanning in `getChildren`) is sound and the `?? LanguageVariant.Standard` default is a reasonable degrade-gracefully choice for the cases that do exist today.

**Concerns (highest first).**
1. Missing `@internal` tag causes an implementation-detail field to leak into the shipped public API surface (`tests/baselines/reference/api/typescript.d.ts`), immediately adjacent to two members that were deliberately marked `@internal`. This is the strongest signal of an oversight rather than an intentional public-contract decision — TypeScript's own public-API baseline is exactly the guard meant to catch this, and it recorded the leak instead of blocking it.
2. No enforcement ties ad hoc `SourceFileLike` literals to the real language variant; a future consumer can silently get wrong JSX tokenization with no compiler error.

**Recommended improvements (low cost, no behavior change intended).**
- Add `/** @internal */` above `languageVariant?: LanguageVariant;` at `src/compiler/types.ts:4291`, matching its siblings, and regenerate `tests/baselines/reference/api/typescript.d.ts` to drop it from the public surface — unless a maintainer confirms external consumers (e.g., language-service plugin authors implementing `SourceFileLike`) genuinely need to set this, in which case it should be documented as an intentional public addition, not a silent one.
- No change needed to optionality or readonly-ness — matches established sibling-field conventions in this file and isn't worth the churn.

```json-findings
[
  {
    "severity": "high",
    "confidence": 75,
    "agent": "type-design-analyzer",
    "category": "architecture-coupling",
    "file": "src/compiler/types.ts",
    "line": 4291,
    "finding": "`languageVariant?: LanguageVariant;` was added to the public `SourceFileLike` interface without an `@internal` tag, while its immediate neighbors `lineMap?` (4288) and `getPositionOfLineAndCharacter?` (4290) are both `@internal`. The field consequently leaked into the shipped public API baseline (tests/baselines/reference/api/typescript.d.ts), yet its only production consumer is the internal helper `createChildren` in src/services/services.ts:507. This looks like an accidental promotion of an internal implementation detail to a permanent public contract rather than a deliberate API decision.",
    "remediation": "Tag the field `/** @internal */` to match its siblings and regenerate the public API baseline, unless a maintainer explicitly confirms external `SourceFileLike` implementers (e.g., language-service plugins) are meant to set/read this member."
  },
  {
    "severity": "medium",
    "confidence": 55,
    "agent": "type-design-analyzer",
    "category": "edge-case",
    "file": "src/services/services.ts",
    "line": 507,
    "finding": "`sourceFile?.languageVariant ?? LanguageVariant.Standard` silently defaults to Standard whenever a `SourceFileLike` doesn't set the (optional) field. Existing `SourceFileLike` object-literal producers never set it — src/services/textChanges.ts:1339-1344 and src/services/sourcemaps.ts:231-238 — so any future caller that feeds actual JSX text through one of these ad hoc literals into `createChildren`/`getChildren` will get the pre-fix, mis-tokenized `</` behavior (separate LessThanToken+SlashToken instead of LessThanSlashToken) with no compiler or runtime signal that the variant was unset.",
    "remediation": "Either require callers of `createChildren` to pass a concrete `LanguageVariant` (no silent default), or add a comment at the `SourceFileLike` declaration site documenting that omitting `languageVariant` is only safe for non-JSX-scanning use sites."
  }
]
```
