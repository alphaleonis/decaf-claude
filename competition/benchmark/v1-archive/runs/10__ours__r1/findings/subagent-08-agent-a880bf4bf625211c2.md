# subagent agent-a880bf4bf625211c2

```json
{
  "finding": "#1",
  "verdict": "confirmed",
  "reason": "Verified in crates/searcher/src/searcher/core.rs: the comment added by commit d4b77a8 (lines 190-197) explains only the cost-skip and the context-separator rationale, never mentioning after_context_left or why after-context lines don't need backward preservation. roll() (lines 209-210) resets last_line_counted/last_line_visited but not after_context_left. after_context_left is set to config.after_context in sink_matched (line 551) and decremented forward in sink_after_context/after_context_by_line (lines 300, 304, 612), confirming after-context state persists across roll() and is tracked forward independently of preceding()'s backward scan — exactly the undocumented invariant the finding describes. The failure scenario (a maintainer 'restoring' max_context() for symmetry, with tests still passing) is plausible since output correctness doesn't depend on this invariant, only performance does.",
  "corrections": null
}
```
