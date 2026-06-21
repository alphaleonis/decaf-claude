# PR Posting Etiquette

Rules for anything decaf-quality writes where other people will read it: PR comments and replies, thread status changes, votes, review submissions. These rules bind every skill and agent in this plugin.

## When posting is allowed

| Skill | Policy |
|-------|--------|
| `code-review` | **Never posts.** The review is a local report only. Posting findings to the PR happens only when the user explicitly requests it in that invocation — and then under the rules below. |
| `resolve-pr-feedback` | **Drafts first.** All replies and status changes are drafted and presented to the user for one batched approval before anything is posted. The `--auto-post` argument opts into posting without the approval step. |
| Agents (`pr-thread-resolver`, reviewers) | **Never post.** Agents return draft text; only the orchestrating skill posts, under the policies above. |

## Rules for posted content

1. **Sign agent-authored content.** Every comment or reply authored by the agent ends with the signature line `— Claude`, so recipients know they are reading agent output, not the PR author's own words. Posting through a user's identity without the marker misrepresents authorship.
2. **No performative agreement.** Replies state what was done or why not — "Fixed in <commit>", "Not changing this: <evidence>" — never "Great catch!" or "You're absolutely right!".
3. **Quote or reference the comment being answered** when a thread has multiple open points, so the reply is unambiguous.
4. **Never @-mention people to summon them.** Mentioning a person creates a notification obligation; that's the user's call, not the agent's.
5. **Status changes ride with the approved batch.** Marking a thread fixed/wontFix/resolved is a visible workflow action — it goes through the same approval as reply text (or `--auto-post`).
6. **Declines are explained.** A thread resolved as won't-fix or by-design always carries a reply with the concrete reasoning — never a silent status flip.
7. **Posted means published.** Treat anything posted as permanent (notifications fire immediately, even if later edited or deleted) — draft accordingly.
