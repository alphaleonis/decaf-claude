# TODO

## Nibs status not updated when work is delegated to subagents

**Observed**: During Phase 4 of erinra web UI, auto-tdd ran all implementation via a subagent. The 3 nibs under Phase 4 (erin-dmwp, erin-jsj2, erin-tyj1) were never moved to in-progress or completed.

**Root cause**: Two gaps combined:
1. The main context didn't update nibs before/after launching the subagent — got caught up in the skill workflow and forgot about nib tracking.
2. The auto-tdd skill has no awareness of work items. The TDD subagent gets a fresh context with a focused prompt and doesn't know nibs exist.

**Proposed fixes**:

- **Nibs prime** (preferred): Add guidance like "When delegating work to subagents via skills (auto-tdd, auto-dev, etc.), update nib status to in-progress BEFORE launching and to completed AFTER — the subagent won't do this for you." This keeps the responsibility in the project-specific tracking hook rather than making generic skills project-aware.

- **Skills** (alternative): Add a step to auto-tdd/auto-dev that says "check if work items exist for this work and update their status." Downside: makes generic skills project-specific.

The first option is better — nibs prime owns the tracking behavior, skills stay generic.
