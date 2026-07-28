# subagent agent-af28592e88bfde118

Excellent. I have verified the claim through GitHub records:

**Verification Results:**

1. **PR #62423 Status:**
   - Title: "Revert PR 61928"
   - Body: Explicitly states "This reverts #61928" and "Fixes #62188"
   - State: **MERGED** (merged at 2025-09-25T17:22:27Z)
   - The PR author wrote: "I'm not sure if it's worth the crashing it seems to be causing downstream"
   - References both downstream failures: typescript-eslint issue #11455 and eslint-stylistic issue #915

2. **Issue #62188 Status:**
   - Title: "Maximum call stack size exceeded for 5.9.x"
   - Body: Reports "RangeError: Maximum call stack size exceeded for 5.9.x" with a clear regression between 5.8.x (working) and 5.9.x (broken)
   - State: **CLOSED**

**Confirmed Facts:**
- PR #62423 is a direct revert of PR #61928 ✓
- PR #62423 is merged ✓
- Issue #62188 is explicitly about a stack overflow (`RangeError: Maximum call stack size exceeded`) occurring in 5.9.x ✓
- The causal link is confirmed: the revert PR explicitly references issue #62188 and the downstream projects affected ✓
- Real-world impact is confirmed: downstream projects (typescript-eslint, eslint-stylistic) experienced failures ✓

The evidence directly confirms this is a real issue that occurred in practice (affecting real users on TypeScript 5.9.x). The token-shape change from PR #61928 broke consumers that walk token streams, causing stack overflows. The regression was severe enough to warrant a full revert of the original changes.

SCORE: 100
