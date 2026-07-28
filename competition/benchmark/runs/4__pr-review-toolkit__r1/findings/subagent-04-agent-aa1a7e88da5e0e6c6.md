# subagent agent-aa1a7e88da5e0e6c6

# Type Design Review — `SourceFileLike.languageVariant` (microsoft/TypeScript PR #61928)

## Type: `SourceFileLike` (widened structural supertype of `SourceFile`)

**What the PR does.** Adds `languageVariant?: LanguageVariant` to `SourceFileLike` so the internal `createChildren` re-scan can pick the JSX vs. Standard tokenizer, fixing JSX close-tags (`</`) being mis-scanned as two `<` + `/` tokens. Source-side change at `src/compiler/types.ts:4291`; consumed at `src/services/services.ts:507-509`; emitted into the public API at `tests/baselines/reference/api/typescript.d.ts:5910`.

### Invariants Identified

- **True invariant (on `SourceFile`):** every real source file has exactly one language variant. It is a **required** field — `src/compiler/types.ts:4359` (`languageVariant: LanguageVariant;`), mirrored publicly at `typescript.d.ts:5927`.
- **Weakened invariant (on `SourceFileLike`):** "a variant *may* be present" — `languageVariant?` at `types.ts:4291`. The `?` makes "absent" a representable, legal state.
- **Silent-default rule:** absent variant ⇒ `LanguageVariant.Standard` (`services.ts:507`). "Missing" and "genuinely Standard" are collapsed into one value.
- **Shared-scanner reset invariant:** `createChildren` mutates the module-global scanner (`src/services/utilities.ts:391`) and must restore it to `Standard` on exit (`services.ts:530`) or leak variant state into unrelated callers. This is a hand-maintained postcondition, not an enforced one.

### Ratings

- **Encapsulation: 4/10**
  `SourceFileLike` is a bare structural bag with no constructor and no guard, so it cannot enforce anything — that part is pre-existing. What this PR adds is a *leak of an internal-only concern into the public surface*. The field exists solely to feed the `@internal` `createChildren`/scanner path; yet it is emitted without `@internal` (`typescript.d.ts:5910`) while both siblings — `lineMap` and `getPositionOfLineAndCharacter` — are `@internal` and correctly stripped (`types.ts:4287-4290`; note they are absent from the public baseline at 5908-5911). The property is inert through every *public* entry point that accepts a `SourceFileLike` (`getLineAndCharacterOfPosition`/`getPositionOfLineAndCharacter` at `typescript.d.ts:8493-8494`, `Node.getWidth` at 4314) — none of them tokenize — so it is public state that does nothing for public consumers yet must be supported forever.

- **Invariant Expression: 4/10**
  The type now *understates* reality. On a `SourceFile` the variant is total and required; the supertype declares it partial. `languageVariant?` tells every reader "this can legitimately be absent," which is the opposite of the domain truth. There is no expression of "Standard-as-fallback" vs. "Standard-as-real" — the model cannot distinguish them.

- **Invariant Usefulness: 5/10**
  Threading the variant is genuinely necessary — that is the bug fix. But encoding it as *optional with a silent Standard default* re-creates the exact footgun the PR set out to kill: any `SourceFileLike` that omits the field silently scans JSX as Standard. The useful invariant ("we know the variant") is undermined by making its absence cheap and quiet.

- **Invariant Enforcement: 3/10**
  Nothing checks presence. `?? LanguageVariant.Standard` (`services.ts:507`) swallows absence with no diagnostic. Worse, enforcement is *internally inconsistent* within the same two lines (see first Concern). No construction-time validation is possible on a structural interface, and none is added.

### Strengths

- Correctly scopes variant mutation and **restores the shared scanner** to `Standard` afterward (`services.ts:530`), avoiding cross-call state leakage into the module-global scanner (`utilities.ts:391`).
- Reuses the already-public `LanguageVariant` enum, which the public baseline emits as a plain (non-`const`) enum (`typescript.d.ts:7223`), so the reference introduces **no new type leak** — the only new public surface is the property itself.
- Co-locating the field on `SourceFileLike` is at least *consistent* with that type's stated purpose ("Subset of properties from SourceFile that are used in multiple utility functions", `types.ts:4283`), so the placement is defensible in principle.

### Concerns

1. **Latent bug — text and variant use asymmetric fallbacks (`src/services/services.ts:507-508`).** Text recovers from the node's own file when the arg is falsy:
   `scanner.setText((sourceFile || node.getSourceFile()).text)`
   but the variant does **not** — it only reads `sourceFile?.languageVariant ?? Standard`. So a `SourceFileLike` that carries `text` but omits `languageVariant` (fully legal per `types.ts:4291`, and the only *required* public member is `text`) will scan a JSX node as Standard **even though `node.getSourceFile().languageVariant` was available**. That is precisely the failure class this PR fixes, left reachable. In practice the public `getChildren(sourceFile?: SourceFile)` overload (`src/services/types.ts:52`) always passes a full `SourceFile`, and the internal overload's default (`getChildren(sourceFile = getSourceFileOfNode(this))`, `services.ts:462`) also yields a real `SourceFile` — so the common paths are safe. But the type deliberately admits the unsafe input via the `@internal` `SourceFileLike` overload (`services/types.ts:54`), and the code does not close it.

2. **`@internal` almost certainly intended, and omitted (`types.ts:4291` → `typescript.d.ts:5910`).** [Inference — expected from the surrounding code, not a stated fact:] the field serves only the internal scanner path; its two siblings are `@internal`; the `SourceFileLike`-typed `getChildren` overload that consumes it is `@internal` (`services/types.ts:53-54`). Every signal says this should have carried `/** @internal */`. As shipped it is a **permanent public API commitment** on `ts.SourceFileLike` that no public workflow needs.

3. **Consistency asymmetry (`types.ts:4287-4291`).** Three optional members now sit side by side; two are `@internal`, the new one is public. This is unwritten-convention drift within a single four-line interface body.

4. **Optional-with-silent-default is the wrong modeling for a total field.** Because `SourceFile.languageVariant` is required, widening to optional on the supertype is a pure loss of information with a silent recovery. A reader cannot tell whether Standard was chosen or defaulted-into.

### Recommended Improvements (ordered, low-risk first)

1. **Mark it `@internal`** (matches siblings, removes the forever-public commitment):
   ```ts
   /** @internal */
   languageVariant?: LanguageVariant;
   ```
   This also drops the added line from the public baseline (`typescript.d.ts:5910`). If any *public* consumer genuinely needs to influence variant selection, that is a separate, deliberate API decision — not a side effect of a scanner fix.

2. **Make the fallback symmetric with the text fallback** so a partial `SourceFileLike` still gets the node's real variant (`services.ts:507`):
   ```ts
   const resolved = sourceFile ?? node.getSourceFile();
   scanner.setText(resolved.text);
   scanner.setLanguageVariant(resolved.languageVariant ?? LanguageVariant.Standard);
   ```
   This closes Concern #1: `node.getSourceFile()` returns a full `SourceFile` whose `languageVariant` is required, so JSX no longer silently degrades when a bare `SourceFileLike` is supplied.

3. **Consider not widening the public type at all.** Since `createChildren`'s only caller (`getChildren`, `services.ts:462-464`) already guarantees a real `SourceFile` via its default parameter, the variant can be read from `node.getSourceFile().languageVariant` without adding any member to `SourceFileLike`. That fixes the bug with **zero** new API surface. Trade-off: it always calls `node.getSourceFile()` (a parent walk) even when a `SourceFileLike` was passed; option 2 avoids that when the arg already carries the variant. Either is preferable to a public optional field.

4. **Do not model it as a plain optional if it stays.** If the field must live on `SourceFileLike`, prefer a single documented, enforced fallback helper (e.g. a local `getLanguageVariant(sfl, node)`) so the "missing ⇒ Standard" decision exists in exactly one place rather than at each call site — today's `?? Standard` is already the second such literal near the reset at `services.ts:530`.

### Note on scope / verification confidence

- Findings #2/#3 rest on repository convention (siblings + the `@internal` overload) rather than a maintainer statement; I could not read PR discussion (commit body was empty). I label the "intended `@internal`" claim **[Inference]** — it is the expected reading of the surrounding code, not a guaranteed fact.
- Finding #1 is **[Verified]** against the code: the asymmetry at `services.ts:507-508` is real, and `SourceFileLike`'s only required public member being `text` (`types.ts:4285-4286`) makes the unsafe input constructible. Whether it is *reached* today depends on callers; I found no in-repo caller passing a `text`-only `SourceFileLike` to `getChildren`, so this is a latent/defensive gap rather than an active regression.
- A cleaner existing pattern for comparison: `src/services/organizeImports.ts:225` builds a *per-call* scanner and passes `sourceFile.languageVariant` at construction — no shared mutable state, no reset obligation, no optional field. That is the direction options 2-3 lean toward.

Relevant files (absolute paths):
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/4/src/compiler/types.ts` (interface: 4285-4292; required sibling: 4359; enum: 7677)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/4/src/services/services.ts` (consumer: 462-464, 497-532)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/4/src/services/types.ts` (public vs `@internal` overloads: 52-54, 60, 65-70)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/4/src/services/utilities.ts` (shared scanner: 391)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/4/tests/baselines/reference/api/typescript.d.ts` (public emission: 5908-5911; SourceFile required: 5927; enum: 7223)
