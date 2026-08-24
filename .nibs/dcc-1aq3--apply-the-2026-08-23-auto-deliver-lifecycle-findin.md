---
# dcc-1aq3
version: 1
title: Apply the 2026-08-23 auto-deliver lifecycle findings (F1-F6)
status: completed
type: feature
priority: high
created_at: 2026-08-24T07:08:53Z
updated_at: 2026-08-24T07:16:04Z
order: zzzzzV
---

Apply the six findings from the auto-deliver field report (`/mnt/d/2026-08-23-subagent-lifecycle-and-loop-findings.md`, from the nibs-gfsb run in alphaleonis/nibs), amended per the 2026-08-24 assessment: F1 uses the mode-aware dispatch remedy (task vs teammate mode, per the verified no-name dispatch rule in code-review dcc-8yio), NOT the report's blanket always-SendMessage line.

Delivered on `main` first, then merged to `tuning` (target files are identical on both branches).

- [x] F1 — new `conventions/subagent-briefs.md` (dispatch-mode table, delivery clause for named teams, tripwire) + symlinks in decaf-build/decaf-quality + references from batch-dev fan-outs, auto-code-review Step 2, auto-deliver focused fixes
- [x] F2 — batch-dev Phase 6a: implementation agent stages, conductor commits; Failure handling: a dispatched agent cannot be reliably redirected (verify with git, commit message is not evidence of which brief it followed); auto-deliver Invariant 3 extended to commits
- [x] F3 — auto-code-review Step 5.4: fourth escalation trigger for documentation surfaces consumed as command references
- [x] F4 — auto-deliver setup checks `git check-ignore .decaf`; artifact-layout durability claim made conditional
- [x] F5 — state.json schema gains `scope`/`review_spec`/`note`; SELECT scope-reconciliation rule; setup notes the argument may name a plan root or a single phase
- [x] F6 — auto-deliver VERIFY attempts an execution before honoring `[manual]`; acceptance-criteria convention states the tag is a testable claim

## Summary

**Completed 2026-08-24** — All six findings from the 2026-08-23 auto-deliver field report applied on main (six commits, a94f98b..4547c73). F1 was implemented mode-aware per the assessment — new conventions/subagent-briefs.md (task vs teammate dispatch, delivery clause for named teammates, spawn-ack tripwire, redirection caveat) wired into batch-dev, auto-code-review, and auto-deliver — instead of the report's blanket always-SendMessage line, which loses reports on the task path. F2: series-lane workers stage while the conductor commits; worktree lanes keep their commits with the trade-off stated; redirection rule added to Failure handling and auto-deliver Invariant 3. F3: fourth escalation trigger for doc surfaces consumed as command references (bounded to command/grammar surfaces). F4: setup probes git check-ignore on .decaf/ and the durability claim is conditional. F5: state.json documents scope/review_spec/note; SELECT reconciles next-ready against scope; the argument may name a plan root or a single phase. F6: VERIFY attempts a settling execution before honoring [manual]; the convention states the tag as a testable claim. Deviation from the report: the optional note in code-review's own guidance ("review doc surfaces as claims verified by execution") was not added — that skill is a benchmark-tuned surface and the trigger alone covers the finding.
