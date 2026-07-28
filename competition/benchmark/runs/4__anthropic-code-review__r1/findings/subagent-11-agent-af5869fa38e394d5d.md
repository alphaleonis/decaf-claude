# subagent agent-af5869fa38e394d5d

## Findings: Prior/Current PR Review Comments Applicable to This Change

I checked git/GitHub history for the four changed files. All of them were last touched by this exact PR (#61928, merge commit `02672d281`); there is essentially no separate "prior PR" touching this code — but critically, **this PR's own subsequent history and its own review thread both surface directly applicable concerns**.

### 1. This exact change was later reverted in production due to a real crash (highest priority)

- **Source**: PR #62423 ["Revert PR 61928"](https://github.com/microsoft/TypeScript/pull/62423) (merged 2025-09-25, also cherry-picked to release-5.9), fixing issue [#62188 "Maxinum call stack size exceeded for 5.9.x"](https://github.com/microsoft/TypeScript/issues/62188).
- **Description**: Issue #62188 reported a `RangeError: Maximum call stack size exceeded` in 5.9.x (not present in 5.8.x) when running `eslint`. It was bisected to PR #61928 itself. Cross-referenced downstream breakage: [typescript-eslint/typescript-eslint#11455](https://github.com/typescript-eslint/typescript-eslint/issues/11455) and [eslint-stylistic/eslint-stylistic#915](https://github.com/eslint-stylistic/eslint-stylistic/issues/915).
- **Why it applies**: The change under review makes `createChildren`/`getChildren` scan JSX/TSX files with the JSX language variant, so a closing tag `</div>` now tokenizes as a single `LessThanSlashToken` instead of separate `<` + `/` tokens. jakebailey confirmed: *"the only reason we emitted the three tokens instead of two in this instance was because of a bug. And I suspect that the other parser for tsx mentioned in the other thread just emulated that behavior."* Downstream tools (typescript-eslint / eslint-stylistic, which walk/recurse over these tokens) broke on the new shape, causing stack overflows for real users. gabritto agreed reverting was fine ("the bug has existed for a long time"), and a post-process workaround was explored by an eslint-stylistic maintainer but the revert shipped anyway. **This means the diff under review, exactly as written, is known to cause a real-world regression severe enough to warrant a full revert** — this is the single most important prior-PR fact for anyone reviewing this diff today.

### 2. Formatter's `shouldAddDelta` — reviewer-flagged gap, appears unaddressed

- **Source**: PR #61928's own review — Daniel Rosenwasser, review state `DISMISSED`: *"There is a branch in the formatter for `SlashToken` in `shouldAddDelta` - I think that may need to be adjusted. Might indicate a lack of test for the indentation of a JSX closing tag."* (via `gh api repos/microsoft/TypeScript/pulls/61928/reviews`)
- **Description**: I verified `shouldAddDelta` in `src/services/formatting/formatting.ts:727-745` still only has:
  ```
  case SyntaxKind.SlashToken:
  case SyntaxKind.GreaterThanToken:
      switch (container.kind) {
          case SyntaxKind.JsxOpeningElement:
          case SyntaxKind.JsxClosingElement:
          case SyntaxKind.JsxSelfClosingElement:
              return false;
      }
  ```
  There is no `case SyntaxKind.LessThanSlashToken:` anywhere in `src/services/formatting/` (checked `formatting.ts`, `formattingScanner.ts`, `rules.ts` — zero hits).
- **Why it applies**: Because of this PR, the leading token of a `JsxClosingElement` (`</`) is now `LessThanSlashToken`, not `SlashToken`. That means the explicit "no indent delta" carve-out for JSX closing elements no longer fires for that token position — it silently falls through to default delta logic. Self-closing elements (`<div />`) are unaffected since `/>` still tokenizes as separate `SlashToken` + `GreaterThanToken`. The PR's own test changes (`syntacticClassificationsJsx1.ts`, `syntacticClassificationsJsx2.ts`) only cover *classification*, not formatting/indentation — confirming Daniel's suspicion of a missing indentation test. This looks like a genuine, still-open gap directly caused by the diff's token-kind change, raised by a maintainer on this very PR and never followed up on in the merged code.

### Items checked and already resolved (no action needed)

- Copilot bot inline comment on `src/services/utilities.ts:1894` (`LessThanSlashToken` check) — purely descriptive of the change itself, not a request.
- Daniel Rosenwasser's inline suggestion on `src/services/services.ts:507`: *"I would personally just declare `languageVariant` as optional in `SourceFileLike`."* — **adopted**: `src/compiler/types.ts:4291` declares `languageVariant?: LanguageVariant;` and `services.ts:507` uses `sourceFile?.languageVariant ?? LanguageVariant.Standard`.
- jakebailey's initial "is it worth changing?" comment — mild, superseded by his later approval; no open thread.

### Note on environment

The local checkout is shallow (2 commits only), so I used `gh api`/`gh pr view`/`gh issue view` against `microsoft/TypeScript` directly rather than local `git log`. I noticed another process in this shared working directory concurrently running `git fetch --unshallow` (a `.git/shallow.lock` was present); I did not touch it and used GitHub's API instead to avoid contention.
