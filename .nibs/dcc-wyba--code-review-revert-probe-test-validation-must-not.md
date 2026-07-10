---
# dcc-wyba
version: 1
title: 'code-review: revert-probe test-validation must not git-checkout uncommitted work (data-loss risk)'
status: completed
type: bug
priority: high
created_at: 2026-07-10T19:54:50Z
updated_at: 2026-07-10T20:13:49Z
order: zV
---

Session evidence (nibs project, /auto-tdd on nibs-qpvw, 2026-07-10): during code-review iteration 2 the test-reviewer ran a revert-probe — revert the production fix, re-run the tests, confirm they fail — to validate that the new regression tests are genuine guards, not false positives (a high-value check). It reverted using git checkout <file>. The fix was UNCOMMITTED (working-tree only), so git checkout restored the file to HEAD (the older pre-fix version), wiping ALL uncommitted changes in that file, not just the one line it meant to test. The agent noticed the over-revert, hand-restored the file, and re-verified; the orchestrator then independently re-verified the tree (diffstat, fix line present, full suite green) before committing. No work was lost — but by recovery-after-the-fact, not by design.

Root cause: git checkout -- <path> / git restore / git reset are destructive to uncommitted work by design. A review agent (nominally read-only) improvised a working-tree revert with a blunt instrument, on a tree whose changes were not yet committed, so the destructive scope was the entire diff under review rather than the single targeted line.

## Todo

- [x] code-review SKILL.md (test-reviewer guidance / any mutation- or revert-probe instructions): forbid destructive git on the working tree during review — never run git checkout / git restore / git reset / git stash drop against tracked files. State that a reviewer is read-only with respect to the working tree.
- [x] code-review SKILL.md: document the APPROVED non-destructive way to empirically validate a regression guard (revert-probe / mutation test) so agents do not improvise — operate on a COPY of the file, OR snapshot first (git stash create, or a throwaway commit) and restore exactly, OR apply a precise inline edit and undo it by re-editing — always leaving the working tree byte-identical afterward, and verify (diff --stat unchanged) before reporting.
- [x] auto-code-review / auto-dev / auto-tdd SKILL.md (defense-in-depth): before a review phase that may run such probes, snapshot the work so any tree mutation is recoverable — prefer committing WIP first (the build skills already end by committing), or at least git stash create. At minimum note that review may mutate the tree and recommend committing before review.
- [x] Consider a standing line in the review-agent prompt: you must not run any git command that discards, reverts, or resets working-tree changes; validate tests by editing a copy or a recoverable snapshot instead.

## Notes

- Positive datapoint (keep, do not regress): in the same run the review agent correctly REJECTED a prompt-injection attempt embedded in a tool result (a fake system-reminder instructing it to conceal the reverted change). The revert-safety fix must not weaken that behavior.
- Related: #dcc-jxya (another review-agent misbehavior), #dcc-unre (review-skill tuning tracker).

## Summary of Changes

Fixed on branch `dcc-wyba-revert-safety` (off main). Five files, all guidance/skill docs — no runtime code:

1. **`decaf-quality/skills/code-review/SKILL.md`** — added a **Working-tree safety** block to the Base Context Template (Step 3), which is injected into *every* dispatched reviewer. States reviewers are read-only w.r.t. the tree; forbids `git checkout`/`restore`/`reset`/`stash`/`clean` on tracked files (the diff is uncommitted, so these wipe the whole change); gives the approved non-destructive revert-probe (copy / precise edit-and-undo / `git stash create` snapshot) with a `git diff --stat` verify; and makes the rule non-overridable by injected instructions in the diff/comments/tool results (preserves the prompt-injection-rejection behavior called out in Notes). Covers todos 1, 2 (concise), 4.
2. **`decaf-quality/agents/test-reviewer.md`** — added a detailed **Validating a Regression Guard (Revert-Probe) — Non-Destructively** section (the test-reviewer is the agent that runs these), with the absolute never-`git checkout` rule and the 5-step snapshot→edit→run→restore→verify procedure. Covers todo 2 (depth).
3. **`decaf-quality/skills/auto-code-review/SKILL.md`** — (a) Step 1 now establishes a recoverable `SNAPSHOT=$(git stash create)` before any fix/probe phase; (b) the fix subagent takes a per-fix `FIX_SNAPSHOT` and, on failed verification, restores only the edited files via `git checkout $FIX_SNAPSHOT -- <files>` — replacing the previous `git checkout -- <files>` (line 216) that reverted to HEAD and wiped all uncommitted work. Covers todo 3 + removes the live instance of the bug.
4. **`decaf-build/skills/auto-dev/SKILL.md`** and **5. `decaf-build/skills/auto-tdd/SKILL.md`** — added a defense-in-depth Note that review runs on uncommitted changes and may mutate the tree, that auto-code-review snapshots first, and that committing before review is a stronger guarantee. Covers todo 3.

Verification: grep confirms no bare `git checkout -- <files>` directive remains — every surviving `git checkout` is either snapshot-based (safe restore) or an explicit *never*-do-this warning.
