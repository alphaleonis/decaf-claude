# subagent agent-a30d649be2a5336bb

This diff is a TypeScript compiler/language-service internal change. I examined all four source files:

- `src/compiler/types.ts`: adds an optional `languageVariant?` field to the `SourceFileLike` interface.
- `src/services/services.ts`: sets the scanner's language variant in `createChildren()` and resets it to `Standard` afterward.
- `src/services/completions.ts` and `src/services/utilities.ts`: swap token-kind checks from `SlashToken`/`LessThanToken` to `LessThanSlashToken`.

There is no network, filesystem, auth, deserialization, credential, crypto, command-execution, or user-input trust boundary in these changes. All data flows are internal AST/scanner token handling. No secrets, no injection surface, no dependency changes, no prompt-injection content. The only non-functional risk I considered — the scanner being left in JSX mode if an exception occurred between `setLanguageVariant` and the reset — is a state-consistency/correctness concern within a single-threaded compiler pass, not a security vulnerability, and is out of scope for this review.

No security-relevant exposure found at Medium or higher.

NONE
