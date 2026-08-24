---
# dcc-1aq3
version: 1
title: Apply the 2026-08-23 auto-deliver lifecycle findings (F1-F6)
status: in-progress
type: feature
priority: high
created_at: 2026-08-24T07:08:53Z
updated_at: 2026-08-24T07:12:08Z
order: zzzzzV
---

Apply the six findings from the auto-deliver field report (`/mnt/d/2026-08-23-subagent-lifecycle-and-loop-findings.md`, from the nibs-gfsb run in alphaleonis/nibs), amended per the 2026-08-24 assessment: F1 uses the mode-aware dispatch remedy (task vs teammate mode, per the verified no-name dispatch rule in code-review dcc-8yio), NOT the report's blanket always-SendMessage line.

Delivered on `main` first, then merged to `tuning` (target files are identical on both branches).

- [x] F1 — new `conventions/subagent-briefs.md` (dispatch-mode table, delivery clause for named teams, tripwire) + symlinks in decaf-build/decaf-quality + references from batch-dev fan-outs, auto-code-review Step 2, auto-deliver focused fixes
- [ ] F2 — batch-dev Phase 6a: implementation agent stages, conductor commits; Failure handling: a dispatched agent cannot be reliably redirected (verify with git, commit message is not evidence of which brief it followed); auto-deliver Invariant 3 extended to commits
- [ ] F3 — auto-code-review Step 5.4: fourth escalation trigger for documentation surfaces consumed as command references
- [ ] F4 — auto-deliver setup checks `git check-ignore .decaf`; artifact-layout durability claim made conditional
- [ ] F5 — state.json schema gains `scope`/`review_spec`/`note`; SELECT scope-reconciliation rule; setup notes the argument may name a plan root or a single phase
- [ ] F6 — auto-deliver VERIFY attempts an execution before honoring `[manual]`; acceptance-criteria convention states the tag is a testable claim
