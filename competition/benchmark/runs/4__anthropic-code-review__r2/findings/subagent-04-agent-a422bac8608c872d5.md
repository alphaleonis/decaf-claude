# subagent agent-a422bac8608c872d5

Based on my verification using `gh`, I have confirmed this issue is absolutely real and not a false positive:

**Evidence gathered:**

1. **PR #61928 explicitly changes token shape**: The PR description states `</div>` changed from being scanned as three tokens (`<`, `/`, `>`) to two tokens (`</`, `>`).

2. **jakebailey's API-consumer concern during review**: Found comment: "Yeah, I was just thinking about API consumers using getChildren getting unexpected tokens, though those tokens would have surely been wrong."

3. **PR was merged**: Confirmed merged on 2025-06-25.

4. **Downstream crashes confirmed**: 
   - typescript-eslint issue #11455 reports: "RangeError: Maximum call stack size exceeded" with JSX fragments in TypeScript 5.9
   - The issue clearly states: "In TypeScript 5.8, </> returns three tokens: <, /, and >, but in TypeScript 5.9, </> returns two tokens: </ and >."
   - This broke the `@stylistic/indent` rule in ESLint

5. **Revert PR #62423 confirms breakage severity**:
   - Title: "Revert PR 61928"
   - Body: "Fixes #62188" and states "not sure if it's worth the crashing it seems to be causing downstream"
   - References typescript-eslint#11455 and eslint-stylistic#915
   - Merged 2025-09-25 (3 months after original merge)

**Conclusion**: This is a confirmed, real, high-impact breaking change to a public API (`getChildren()`) that caused downstream crashes in widely-used tools like `@typescript-eslint/parser` and ESLint. The issue occurs frequently in practice (any JSX closing tag or fragment triggers it). jakebailey explicitly raised this concern during review, and the impact was severe enough to warrant a full revert.

SCORE: 100
