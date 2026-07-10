---
# dcc-wyba
version: 1
title: 'code-review: revert-probe test-validation must not git-checkout uncommitted work (data-loss risk)'
status: todo
type: bug
priority: high
created_at: 2026-07-10T19:54:50Z
updated_at: 2026-07-10T19:54:50Z
order: zV
---

Session evidence (nibs project, /auto-tdd on nibs-qpvw, 2026-07-10): during code-review iteration 2 the test-reviewer ran a revert-probe — revert the production fix, re-run the tests, confirm they fail — to validate that the new regression tests are genuine guards, not false positives (a high-value check). It reverted using git checkout <file>. The fix was UNCOMMITTED (working-tree only), so git checkout restored the file to HEAD (the older pre-fix version), wiping ALL uncommitted changes in that file, not just the one line it meant to test. The agent noticed the over-revert, hand-restored the file, and re-verified; the orchestrator then independently re-verified the tree (diffstat, fix line present, full suite green) before committing. No work was lost — but by recovery-after-the-fact, not by design.

Root cause: git checkout -- <path> / git restore / git reset are destructive to uncommitted work by design. A review agent (nominally read-only) improvised a working-tree revert with a blunt instrument, on a tree whose changes were not yet committed, so the destructive scope was the entire diff under review rather than the single targeted line.

## Todo

- [ ] code-review SKILL.md (test-reviewer guidance / any mutation- or revert-probe instructions): forbid destructive git on the working tree during review — never run git checkout / git restore / git reset / git stash drop against tracked files. State that a reviewer is read-only with respect to the working tree.
- [ ] code-review SKILL.md: document the APPROVED non-destructive way to empirically validate a regression guard (revert-probe / mutation test) so agents do not improvise — operate on a COPY of the file, OR snapshot first (git stash create, or a throwaway commit) and restore exactly, OR apply a precise inline edit and undo it by re-editing — always leaving the working tree byte-identical afterward, and verify (diff --stat unchanged) before reporting.
- [ ] auto-code-review / auto-dev / auto-tdd SKILL.md (defense-in-depth): before a review phase that may run such probes, snapshot the work so any tree mutation is recoverable — prefer committing WIP first (the build skills already end by committing), or at least git stash create. At minimum note that review may mutate the tree and recommend committing before review.
- [ ] Consider a standing line in the review-agent prompt: you must not run any git command that discards, reverts, or resets working-tree changes; validate tests by editing a copy or a recoverable snapshot instead.

## Notes

- Positive datapoint (keep, do not regress): in the same run the review agent correctly REJECTED a prompt-injection attempt embedded in a tool result (a fake system-reminder instructing it to conceal the reverted change). The revert-safety fix must not weaken that behavior.
- Related: #dcc-jxya (another review-agent misbehavior), #dcc-unre (review-skill tuning tracker).
