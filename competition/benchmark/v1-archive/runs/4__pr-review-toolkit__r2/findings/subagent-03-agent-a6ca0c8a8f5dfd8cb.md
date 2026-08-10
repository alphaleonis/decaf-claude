# subagent agent-a6ca0c8a8f5dfd8cb

I have completed my audit. Here are my complete findings.

---

## Error-Handling / Silent-Failure Audit — PR #61928 "Use jsx language variant for jsx file scanning in getChildren"

### Setup facts established (load-bearing for the findings)

- The `scanner` used in `createChildren` is a **module-level singleton** exported at `src/services/utilities.ts:391` (`export const scanner = createScanner(...)`). It lives for the entire lifetime of the language service and is shared across requests.
- Other consumers of this same shared scanner: `src/services/completions.ts:1898-1900` and `src/services/preProcess.ts:39+`. **Neither sets `languageVariant`** — both implicitly rely on it being `LanguageVariant.Standard`.
- `grep` confirms `setLanguageVariant` is called in **exactly two places in all of services** — both inside `createChildren` (`services.ts:509` and `:530`). No other consumer ever resets it. So whatever variant `createChildren` leaves behind is what the next `completions`/`preProcess` scan inherits.
- `Debug.fail` (`src/compiler/debug.ts:196`) genuinely `throw`s (returns `never`). It is reachable from inside the set/reset window via `addSyntheticNodes` at `services.ts:544`.
- Scanner behavior (`src/compiler/scanner.ts:2205-2212`): `LessThanSlashToken` is produced **only** when `languageVariant === JSX`; in Standard variant `</` becomes `LessThanToken` + `SlashToken`. `LanguageVariant`: `Standard = 0`, `JSX = 1` (`types.ts:7677`).
- Token/parent invariants from the parser: self-closing `<div />` → `/` is a **`SlashToken`** whose parent is **`JsxSelfClosingElement`** (`parser.ts:6215`); closing `</div>` / `</>` → `</` is a **`LessThanSlashToken`** whose parent is **`JsxClosingElement`/`JsxClosingFragment`** (`parser.ts:6339`, `:6355`). The token kinds inspected in completions come from `getTokenAtPosition` → `getChildren` → `createChildren` (`utilities.ts:1580`), so they reflect `createChildren`'s scanning.

---

### Finding 1 — CRITICAL: shared-scanner state leak on throw (unguarded set/reset, no try/finally)

**Location:** `src/services/services.ts:507-531` (set at 509, reset at 529-530; throw path at `services.ts:544` via `addSyntheticNodes`).

**Issue:** `createChildren` sets `scanner.setLanguageVariant(languageVariant)` at line 509, runs `node.forEachChild(processNode, processNodes)` (527) and `addSyntheticNodes(...)` (528), then resets to `Standard` at 530 — all in straight-line code with **no `try/finally`**. `addSyntheticNodes` can throw: `Debug.fail(...)` at `services.ts:544` fires on an unexpected `Identifier` in trivia and is a real `throw`. `forEachChild` callbacks route through `addSyntheticNodes` as well.

**Hidden errors that leave the scanner dirty:** any `Debug.fail` assertion in `addSyntheticNodes`; any exception thrown from a `forEachChild` visitor or from `createSyntaxList`/`createNode`; an out-of-memory or stack-overflow mid-scan. On any of these the function exits via exception and **lines 529-530 never run**.

**Concrete failure scenario:** `createChildren` is invoked for a JSX source file → line 509 sets the shared scanner to `JSX`. `addSyntheticNodes` hits the `Debug.fail` path and throws. The exception propagates out; the scanner singleton is now stuck in `JSX` variant. Because **no other consumer resets the variant** (confirmed by grep), the next call to `completions.ts:1900` (`scanner.scan()` in the `import { X as Y }` check) or the next `preProcess.ts` scan runs in `JSX` variant instead of `Standard`. Any `</` in that later text would then tokenize as `LessThanSlashToken` instead of `LessThanToken`+`SlashToken`, silently mis-scanning unrelated input. The corruption persists across language-service requests until a later `createChildren` happens to overwrite the variant. This is exactly the silent, hard-to-reproduce, "why did an unrelated file suddenly mis-tokenize once" class of bug.

**Was this a pre-existing property?** Partly. The prior `scanner.setText(undefined)` at line 529 was *also* outside any `try/finally`, so leftover text already leaked on throw. But that leak was **benign**: every consumer calls `scanner.setText(...)` before scanning, so stale text is always overwritten. The PR changes the blast radius: leftover **`languageVariant` is *not* overwritten by any other consumer**, turning a previously-harmless unguarded reset into a consequential state leak. The PR introduces new mutable global state without the guard its new invariant requires.

**Recommendation:** Wrap the mutate-scan-restore in `try/finally` so both resets always run:

```ts
const languageVariant = sourceFile?.languageVariant ?? LanguageVariant.Standard;
scanner.setText((sourceFile || node.getSourceFile()).text);
scanner.setLanguageVariant(languageVariant);
try {
    let pos = node.pos;
    // ... processNode / processNodes / forEachChild / addSyntheticNodes ...
    addSyntheticNodes(children, pos, node.end, node);
} finally {
    scanner.setText(undefined);
    scanner.setLanguageVariant(LanguageVariant.Standard);
}
return children;
```

(Fold the existing `setText(undefined)` into the same `finally` while you're there — it closes the pre-existing latent leak too.)

---

### Finding 2 — HIGH: `SlashToken` → `LessThanSlashToken` change makes a self-closing-element branch unsatisfiable (silent stop-matching)

**Location:** `src/services/completions.ts:3511-3515`

```ts
case SyntaxKind.LessThanSlashToken:
    if (currentToken.parent.kind === SyntaxKind.JsxSelfClosingElement) {
        location = currentToken;
    }
    break;
```

**Issue:** This case was mechanically switched from `SyntaxKind.SlashToken` to `SyntaxKind.LessThanSlashToken`, but its body still tests `currentToken.parent.kind === JsxSelfClosingElement`. That combination is **impossible**. Per the parser, a `JsxSelfClosingElement`'s slash (`<div />`) is a plain **`SlashToken`** (`parser.ts:6215`), and re-scanning `<div />` in either variant yields `SlashToken` for that `/` because the `LessThanSlashToken` rule requires the `<` to be immediately before the `/` (`scanner.ts:2205`). A `LessThanSlashToken` is only ever produced for `</`, whose parent is `JsxClosingElement`/`JsxClosingFragment` — **never** `JsxSelfClosingElement`. The predicate can therefore never be true; the branch is dead.

**Hidden error / user impact:** This is a silent behavior removal, not a thrown error — the worst kind for debugging. Before the PR, when the cursor sat at the slash of a self-closing tag (`<div /|>` / the incomplete `<div /|`), `currentToken` was a `SlashToken` with a `JsxSelfClosingElement` parent, the branch fired, and `location = currentToken` corrected the completion anchor. After the PR that fix-up **silently never happens** for self-closing elements. Users get subtly wrong or missing JSX completions at the self-closing slash, with no log, no assertion, and nothing to indicate a regression. It is not covered by any test in this PR (the only test changes are two `syntacticClassificationsJsx` classification baselines, unrelated to this path).

**Recommendation:** This case should **not** have been switched. Restore the `SlashToken` label (the self-closing slash is genuinely a `SlashToken`, unaffected by the variant fix):

```ts
case SyntaxKind.SlashToken:
    if (currentToken.parent.kind === SyntaxKind.JsxSelfClosingElement) {
        location = currentToken;
    }
    break;
```

Add a completions fourslash test for the cursor at the self-closing slash (`<div /*here*/ />`) so the regression can't recur silently.

---

### Finding 3 — MEDIUM: fallback `?? LanguageVariant.Standard` silently mis-scans, and is inconsistent with the `text` fallback on the adjacent line

**Location:** `src/services/services.ts:507-508`

```ts
const languageVariant = sourceFile?.languageVariant ?? LanguageVariant.Standard;
scanner.setText((sourceFile || node.getSourceFile()).text);
```

**Issue:** `SourceFileLike.languageVariant` is **optional** (`types.ts:4291`), so `sourceFile` may carry `text` but not `languageVariant`. Note the asymmetry on these two adjacent lines: for **text**, the code falls back to the node's real source file (`sourceFile || node.getSourceFile()).text`); for **languageVariant**, it does **not** — it jumps straight to `Standard` and never consults `node.getSourceFile().languageVariant`. So a caller that passes a synthetic `SourceFileLike` (text present, `languageVariant` absent) for a node that actually belongs to a **JSX** file would get JSX **text** scanned with **Standard** variant — silently reintroducing the exact `</`-mis-tokenization bug this PR exists to fix, with no error surfaced.

**Current reachability (why MEDIUM, not HIGH):** I traced the synthetic-`SourceFileLike` constructor `createSourceFileLike` (`sourcemaps.ts:231`) — it omits `languageVariant`, but its instances are only used for `getLineAndCharacterOfPosition`, never passed to `getChildren`/`createChildren`. The default arg of `getChildren` is `getSourceFileOfNode(this)` (`services.ts:462`), a real `SourceFile` that always has `languageVariant`. So **no currently-active path** hits the unsafe fallback with a JSX file. The defect is latent: the correctness of the whole fix silently depends on every caller passing a `languageVariant`-bearing object, and nothing — type system or runtime — enforces it. The moment someone routes a variant-less `SourceFileLike` through `getChildren`, JSX files mis-scan with zero diagnostics.

**Recommendation:** Make the variant fallback mirror the text fallback so it degrades to the *real* file's variant before defaulting to Standard, closing the silent-mis-scan gap:

```ts
const languageVariant = sourceFile?.languageVariant
    ?? node.getSourceFile().languageVariant
    ?? LanguageVariant.Standard;
```

(`node.getSourceFile()` is already the text fallback source on the next line, so this is consistent and cheap.) Alternatively, since `getChildren`'s default arg already yields a real `SourceFile`, document/assert that any `SourceFileLike` passed to `getChildren` is expected to carry `languageVariant`.

---

### Categories that are CLEAN

- **The other `SlashToken`/`LessThanToken` → `LessThanSlashToken` changes are correct and coordinated with the variant fix — no silent stop-matching:**
  - `completions.ts:1598` (walk-up to `JsxClosingElement`) — correct; `</` is now `LessThanSlashToken`.
  - `completions.ts:3521` (`parent.kind === JsxClosingElement`, `contextToken.kind === LessThanSlashToken`) — correct.
  - `completions.ts:5808` (`isJsxClosingElement(contextToken.parent)`) — correct.
  - `utilities.ts:1889` (`LessThanToken` → `LessThanSlashToken` for the `<div>|</div>` closing-element case) — correct; the closing tag's leading `<` is now absorbed into `LessThanSlashToken`.
  - `utilities.ts:1934-1935` — **additive**: it keeps `SlashToken` (for the self-closing `/>`) and *adds* `LessThanSlashToken` (for `</`). Because it does not remove `SlashToken`, no previously-matching case is silently dropped. Correct and complete.
- **No empty catch blocks, swallowed exceptions, or logging-and-continue patterns** are introduced by this diff. The diff contains no `try/catch` at all — the error-handling concern here is exclusively the *missing* `try/finally` in Finding 1, not a misused one.

---

### Overall summary

The diff is small but touches shared mutable global state and a family of token-kind predicates, and it lands **three error-handling defects, none of which surfaces an error to anyone**:

1. **CRITICAL (`services.ts:507-531`)** — the new `setLanguageVariant`/reset pair is not guarded by `try/finally`, and a reachable `Debug.fail` (`services.ts:544`) can throw between them. Because this PR made the leaked state (`languageVariant`) something no other scanner consumer resets, a throw leaves the process-wide shared scanner stuck in `JSX` variant, silently corrupting later unrelated `completions`/`preProcess` scans until a subsequent `createChildren` masks it. Fix: `try/finally`.
2. **HIGH (`completions.ts:3511-3515`)** — the blanket `SlashToken → LessThanSlashToken` rename hit a case whose body checks `JsxSelfClosingElement`, making it a permanently-false branch. The self-closing-slash completion `location` fix-up silently stops working, untested. Fix: revert this one case to `SlashToken`.
3. **MEDIUM (`services.ts:507`)** — the `?? LanguageVariant.Standard` fallback silently mis-scans a JSX file if a `languageVariant`-less `SourceFileLike` ever reaches it, and is inconsistent with the `text` fallback on the very next line. Not reachable today, but the fix's correctness rests on an unenforced caller invariant. Fix: fall back to `node.getSourceFile().languageVariant` before `Standard`.

The remaining token-kind changes (`completions.ts:1598/3521/5808`, `utilities.ts:1889/1934`) are correct and consistent with the parser's token/parent invariants. The single highest-value action is adding the `try/finally` (Finding 1); the self-closing regression (Finding 2) is the most likely to reach users as a subtle "completions got worse in JSX" report with nothing in any log to explain it.

Relevant files: `/home/decaf/code/decaf-claude/competition/benchmark/repos/4/src/services/services.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/4/src/services/completions.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/4/src/services/utilities.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/4/src/compiler/scanner.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/4/src/compiler/parser.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/4/src/services/preProcess.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/4/src/services/sourcemaps.ts`.
