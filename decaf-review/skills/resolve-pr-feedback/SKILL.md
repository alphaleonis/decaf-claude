---
name: resolve-pr-feedback
description: Walk through unresolved PR review feedback and decide a resolution for each thread — fix, reply, decline with evidence, or escalate. Works with Azure DevOps and GitHub. Use "auto" for autonomous resolution; replies are drafted and approved before posting.
argument-hint: "[auto] [PR# | thread-URL] [--auto-post] [instructions]"
---

# Resolve PR Feedback

Bring every unresolved review thread on a PR to an honest resolution: implement the requested change, answer the question, or push back with evidence — then reply and update thread status.

**Posting etiquette is binding** — read and follow it:

@../../conventions/pr-etiquette.md

**Two modes:**
- **Interactive** (default): walk threads one at a time; the user picks each resolution.
- **Auto** (`auto`): plan all resolutions, confirm once, then resolve via parallel `pr-thread-resolver` subagents. Replies are still drafted and batch-approved before posting unless `--auto-post` is given.

## Argument Parsing

Parse `$ARGUMENTS`:

1. **Mode**: `auto` (autonomous) or omitted (interactive)
2. **Target**: a PR number (resolve all unresolved feedback on it), a thread/comment URL (targeted: just that thread), or omitted (the PR associated with the current branch)
3. **`--auto-post`**: post approved-by-policy replies without the batched draft approval (see etiquette)
4. **Instructions**: any remaining text (e.g., "only the threads from Anna", "skip the styling ones")

## Execution Steps

### Step 1: Identify PR and Platform

Detect the hosting platform from context (git remotes, available MCP tools, prior conversation):

- **Azure DevOps**: resolve the repository ID first (`repo_get_repo_by_name_or_id`), then find the PR — by number if given, otherwise the active PR whose source branch is the current branch (`repo_list_pull_requests_by_repo_or_project`).
- **GitHub**: `gh pr view` for the current branch, or the given number.

If no PR exists for the current branch, say so and stop. If a thread URL was given, extract the PR and thread identity from it (targeted mode — the queue is that single thread).

### Step 2: Fetch and Triage Threads

Fetch all threads with comments:

- **ADO**: `repo_list_pull_request_threads` + `repo_list_pull_request_thread_comments`. Thread status values: `active`, `pending`, `fixed`, `wontFix`, `byDesign`, `closed`.
- **GitHub**: `gh api` for review threads (GraphQL `reviewThreads` with `isResolved`) and `gh pr view --json reviews,comments` for review bodies and top-level comments.

Build the **actionable queue** — keep a thread when ALL hold:
1. It is unresolved (`active`/`pending` on ADO; `isResolved: false` on GitHub)
2. It is human feedback, not noise — drop silently (no announcement, no counting): platform system threads (vote changes, iteration pushes, policy/build bots), pure bot wrappers, and threads whose last substantive comment is from the PR author awaiting the reviewer (the ball is not in our court)
3. It anchors code that still exists, or is a general (non-anchored) comment

Apply any user instructions as a filter. If the queue is empty: report "no actionable feedback" and stop.

### Step 3: Resolve Threads

#### Interactive Mode — one thread at a time (MANDATORY STOP per thread)

For each thread:

**3a. Present it:**
```
## Thread N of M — [file:line | general] — by [reviewer]

> [comment chain, condensed to the substantive points]

**My read:** [what is being asked; whether it's valid against the current code; proposed resolution]
```

**3b. Ask** (AskUserQuestion, max 4 options — pick the 3 most fitting + the user can always use "Other"):
- "Fix" — implement the change (or the better variant if the suggested one is flawed)
- "Reply only" — no code change; answer/explain (present the draft)
- "Decline / Not addressing" — push back with evidence (present the draft)
- "Skip" — leave the thread untouched this session

**3c. Execute** the choice. Fixes follow the verify-first discipline: re-verify the feedback against current code before changing anything; surface to the user if verification contradicts the request. Draft the reply for whatever happened — drafts accumulate for Step 5.

#### Auto Mode

**3a. Plan.** For each queued thread, determine the likely resolution (fix / reply / decline / needs-human) from the comment and the current code. Present the plan table (thread, file, request summary, planned resolution) and confirm once via AskUserQuestion — same interaction shape as `resolve-code-review` auto. ⚠️ STOP AND WAIT.

**3b. Dispatch `decaf-review:pr-thread-resolver` subagents in parallel** — one per thread, with the thread's full context (platform, PR, comment chain, anchor with iteration/outdated info, diff context, test command).
- **File-conflict serialization**: threads touching the same file run sequentially (or one agent handles them in sequence); disjoint threads run in parallel, batched ≤4 at a time.
- Collect each agent's verdict, reply draft, files changed, and reason.

**Verdict vocabulary** (both modes): `fixed`, `fixed-differently`, `replied`, `not-addressing`, `declined`, `needs-human`. `needs-human` threads get a drafted reply describing the decision needed — they are never marked resolved.

### Step 4: Validate and Commit

Skip when no files changed.

1. **Validate once, combined**: run the project's test command (or build) on the full result of all fixes — not per-thread; cross-thread interactions are the point.
2. If validation fails and the failures touch files the resolvers changed: one diagnose-and-fix pass, re-validate; still red → revert the offending fixes, downgrade those threads to `needs-human` with the failure attached. Failures only in untouched files are pre-existing — note and proceed.
3. **Commit** the staged fixes with a message like `Address PR review feedback (!N)` listing the per-thread changes, and **push** to the PR's source branch. Follow the project's commit conventions.

### Step 5: Approve and Post

Per the etiquette convention — this is the only step that touches anything visible to others.

**5a. Present the posting batch** (skip straight to 5b if `--auto-post`):

```
## Ready to post — please review

| Thread | Verdict | Status change | Reply draft |
|--------|---------|---------------|-------------|
| file:line (reviewer) | fixed | → fixed/resolved | "..." |
| ... | declined | → wontFix | "..." |
| ... | needs-human | (stays open) | "..." |
```

Ask via AskUserQuestion: post all / adjust (free-form edits per thread) / post none. ⚠️ STOP AND WAIT.

**5b. Post the approved batch.** Append the signature (`— Claude`) to every reply, then per thread:

| Verdict | Reply | Thread status (ADO) | Thread status (GitHub) |
|---------|-------|---------------------|------------------------|
| `fixed` / `fixed-differently` | what changed, referencing the commit | `fixed` | reply + resolve |
| `replied` | the answer/explanation | `closed` (or leave `active` if the reviewer should confirm) | reply + resolve |
| `not-addressing` | the evidence | `wontFix` | reply, leave unresolved |
| `declined` | the concrete harm | `wontFix` | reply, leave unresolved |
| `needs-human` | the decision needed + options | leave `active` | reply, leave unresolved |

ADO: `repo_reply_to_comment` + `repo_update_pull_request_thread`. GitHub: reply and resolve via `gh api` (GraphQL mutations for review threads; `gh pr comment` for top-level comments, which have no resolve mechanism).

### Step 6: Verify and Summarize

1. **Re-fetch** the threads. The actionable queue should now be empty except `needs-human` items. If *new* actionable feedback appeared meanwhile: run one more cycle from Step 2 — at most **two** cycles total, then stop and surface the remainder as a recurring pattern needing the user.
2. **Summarize**, grouped by verdict — one line each describing what was done:

```
## PR Feedback Resolved — !N

Fixed (X): [thread — what changed]
Fixed differently (X): [thread — what changed and why the approach differs]
Replied (X): [thread — what was answered]
Not addressing (X): [thread — the evidence]
Declined (X): [thread — the harm cited]

Validation: [one line, or omitted when no code changed]
Posted: [N replies, M status changes | drafts not posted — user declined]

Needs your input (X):
1. [thread — the decision, the options, the agent's lean]
```

3. For `needs-human` items, offer once to create follow-up work items via the project's tracking system (same `deferSystem` detection as `resolve-code-review`).

## Notes

- Drafts are presented unsigned; the signature is appended only at posting time, exactly once.
- A thread the author already declined with reasoning is not "actionable" — do not relitigate it; it was dropped in triage.
- In targeted mode (thread URL), Steps 2–6 operate on the single thread; the posting batch is one row but still goes through approval.
- If the platform tools for posting are unavailable, complete the fixes and present the drafts as text for the user to post manually — never fail the session over posting.
