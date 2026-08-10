# subagent agent-a1157a636476f66e1

## Findings — PR #61928 (`02672d281`), git blame/history analysis

Repo was a depth-2 shallow clone; I deepened it (`git fetch --deepen=3000 origin f3a6d3165...`) to get ~3542 commits of history for `src/services/*.ts` before blaming.

### 1. (High confidence) `getCompletionData`'s "Fix location" switch drops the `SlashToken` case for `JsxSelfClosingElement`, making that branch dead code

**File:** `src/services/completions.ts:3511-3515`

```ts
case SyntaxKind.LessThanSlashToken:      // was: case SyntaxKind.SlashToken:
    if (currentToken.parent.kind === SyntaxKind.JsxSelfClosingElement) {
        location = currentToken;
    }
    break;
```

`LessThanSlashToken` is only ever produced when `<` is *immediately* followed by `/` (scanner.ts:2202-2207, unchanged by this PR: `languageVariant === LanguageVariant.JSX && charCodeUnchecked(pos+1) === slash`). A self-closing element's trailing slash (`<Foo />`, `<Foo/>`) is never adjacent to a `<` — there's always a tag name/attributes between them — so its trailing `/` remains a lone `SyntaxKind.SlashToken` both before *and after* this PR. Direct evidence from this same commit's own fourslash-baseline diff (`tests/cases/fourslash/syntacticClassificationsJsx1.ts`/`Jsx2.ts`):

```
-        c.punctuation("<"), c.punctuation("/"), c.jsxCloseTagName("div"), c.punctuation(">"), ...
+        c.punctuation("</"), c.jsxCloseTagName("div"), c.punctuation(">"), ...
     ...
        c.jsxSelfClosingTagName("element"),
        ...
           c.punctuation("/"), c.punctuation(">")   // <-- unchanged: still two separate tokens
```

Only the *closing-element* `</` merges; the self-closing element's `/` stays split. So the case at line 3511 can now never match — before the PR it fired whenever the cursor touched the self-closing slash and corrected `location`; after the PR it never fires.

Strong corroborating evidence from history: the exact same file, in `tryGetContainingJsxElement` (line 4833-4834, **not touched by this PR**), already handles this correctly by keeping *both* kinds side by side:

```ts
case SyntaxKind.GreaterThanToken:
case SyntaxKind.LessThanSlashToken:
case SyntaxKind.SlashToken:
    ...
    if (parent && (parent.kind === SyntaxKind.JsxSelfClosingElement || parent.kind === SyntaxKind.JsxOpeningElement)) {
```

`git show f3a6d3165:src/services/completions.ts` confirms `LessThanSlashToken` was already present there pre-PR alongside `SlashToken` — i.e. the established, correct pattern for `JsxSelfClosingElement`/`JsxOpeningElement` contexts in this very file is "add `LessThanSlashToken`, keep `SlashToken`," not "replace `SlashToken` with `LessThanSlashToken`." The PR applied the replace-pattern (correct for pure `JsxClosingElement` contexts, where `<`+`/` are grammatically always adjacent) to a `JsxSelfClosingElement` context where it is wrong. `src/services/utilities.ts`'s `isInsideJsxElement` change in the same PR does it the right (additive) way — `|| node.kind === SyntaxKind.LessThanSlashToken` added on top of the existing `SlashToken` check — which makes the completions.ts miss stand out as an inconsistent, overly-broad find/replace.

**Impact:** completion requests positioned at/around the self-closing `/` of a JSX tag (`<Foo /|>`) will no longer get `location` corrected to that slash token, changing/degrading completion behavior at that cursor position — a narrow but real regression with no fourslash test currently guarding it (none of the existing fourslash tests exercise `getJsxClosingTagCompletion`/self-closing-slash completion positioning).

### 2. (Medium confidence, new risk — no prior fix found in history for this exact class of bug) Shared global `scanner` singleton now carries JSX language-variant state with no exception safety

**File:** `src/services/services.ts:507-530` (new `languageVariant` capture/set at 507-509, reset at 529-530), singleton defined at `src/services/utilities.ts:391`.

`scanner` (`export const scanner: Scanner = createScanner(ScriptTarget.Latest, /*skipTrivia*/ true);`) is a **module-level singleton reused across the whole services layer** — confirmed by grepping all its call sites: `src/services/services.ts`, `src/services/completions.ts` (own inline use at line 1898-1900), `src/services/classifier.ts`, `src/services/organizeImports.ts`, `src/services/preProcess.ts` all import and mutate the *same* object. History check (`git log -S 'setLanguageVariant' -- src/services/`) shows **no prior code path ever called `setLanguageVariant` on this scanner** — every other consumer only ever calls `setText`/`resetTokenState`/`scan`, and none of them reset or care about language variant, because it was always implicitly `LanguageVariant.Standard` (the `createScanner` default).

This PR is the first to mutate that shared state (`scanner.setLanguageVariant(languageVariant)` at line 509) and only restores it (`scanner.setLanguageVariant(LanguageVariant.Standard)` at line 530) in the non-throwing path — there is no `try/finally`. That mirrors the pre-existing (and already fragile) `scanner.setText(undefined)` reset pattern, but with one crucial difference: leftover **text** is harmless because every other consumer of `scanner` calls `setText` again before scanning — but leftover **language variant** is *not* reset by any other consumer. If `createChildren` throws mid-traversal while processing a `.tsx` node — e.g. via the pre-existing `Debug.fail("Did not expect ... to have an Identifier in its trivia")` at `src/services/services.ts:544`, unchanged by this PR — the shared scanner is left in `LanguageVariant.JSX` until the *next* successful `createChildren` call (for any node, any file) happens to reset it back to `Standard` at its own end. Any `classifier.ts` / `organizeImports.ts` / `preProcess.ts` / `completions.ts` scan of an unrelated, non-JSX file that runs in that window would tokenize incorrectly (e.g. `x < /re/.test(y)` — a `<` immediately followed by `/` in ordinary comparison+regex code — would be mis-merged into `LessThanSlashToken` per `scanner.ts:2202-2207`).

I found no prior TypeScript bug/fix in history for exception-safety of this specific shared scanner's state (searched `-S 'finally'` and grep/blame commit messages for "scanner"+"leak/stale/corrupt/reset" — nothing), so this isn't a *regression of a documented fix*; it's a new failure mode introduced by adding un-guarded mutable shared state to a previously stateless-beyond-text singleton.

### Not flagged as bugs (verified consistent with history)
- `src/services/utilities.ts:1892` (`LessThanToken`→`LessThanSlashToken` for `JsxClosingElement`) and the three other `JsxClosingElement`-only substitutions in completions.ts (lines 1598, 3521, 5808) are correct: a JSX closing tag's `<` and `/` are grammatically always adjacent, so the merge is total and the pure substitution is safe there — unlike the self-closing case above.
- `src/compiler/types.ts`'s new optional `languageVariant?: LanguageVariant` on `SourceFileLike` — checked all real call sites of `.getChildren(sourceFile)`/`.getStart(sourceFile)` across `src/services/*.ts`; they all pass either the default (a real `SourceFile`, which always has `languageVariant` set from parsing) or the enclosing function's real `sourceFile`. The one non-`SourceFile` `SourceFileLike` implementation (`createSourceFileLike` in `src/services/sourcemaps.ts`, used for declaration-map source lookups) is never passed into `getChildren`, so the "silently falls back to `Standard`" gap for a hand-built `SourceFileLike` is theoretical, not exercised — I'm not reporting it as a live bug.
