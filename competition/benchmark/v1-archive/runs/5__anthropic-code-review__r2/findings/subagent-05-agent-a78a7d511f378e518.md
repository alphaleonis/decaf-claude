# subagent agent-a78a7d511f378e518

Perfect! I found the key evidence. The Copilot PR review on the revert PR explains the reason. Let me verify the timeline and summary.

Based on my verification using gh:

**Confirmed Evidence:**

1. **PR #308517** exists and adds:
   - `SSE_FIRST_CHUNK_TIMEOUT_MS = 120000` (2 min)
   - `SSE_IDLE_TIMEOUT_MS = 60000` (1 min)
   - `withStreamIdleTimeout()` function that calls `stream.destroy()` when timeout fires
   - Applies this to SSE streams in Anthropic Messages API and OpenAI Responses API

2. **PR #308779** ("Revert 'Support timing out hung streams (#308517)'") was:
   - Created: 2026-04-09 (the day after #308517 was merged on 2026-04-08)
   - Merged by lramos15 (the same author as the original PR)
   - Approved by TylerLeonhardt within hours

3. **Copilot's review comment on the revert** states:
   - "Reverts the Copilot networking change that added idle/first-chunk timeouts around SSE streaming reads"
   - "to address the reported **length-limit/no-output failure**"

**What I Cannot Verify:**
The specific claim that "Claude models buffer large tool arguments" is not documented in the accessible GitHub records. The revert references fixing "length-limit/no-output failure" (issue #308627), but the exact technical mechanism causing the false timeouts is not explicitly stated in the records.

**Score: 75**

The PR was reverted within hours of merge by its own author, addressing a reported failure mode where timeouts were destroying valid streams. This strongly indicates a real, serious issue in practice. However, the specific technical explanation (Claude tool argument buffering) cannot be verified from the GitHub records — only that *some* legitimate use case was being incorrectly terminated by the 60-second watchdog.
