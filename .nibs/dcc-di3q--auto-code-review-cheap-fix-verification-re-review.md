---
# dcc-di3q
version: 1
title: 'auto-code-review: cheap fix-verification re-review rung'
status: draft
type: task
created_at: 2026-08-29T18:46:50Z
updated_at: 2026-08-29T18:46:50Z
order: zzzzzs
---

Idea from superpowers subagent-driven-development (6.3.0, `re-review-prompt.md`): a re-review rung cheaper than `bugs`-scoped-to-modified-files — a single read-only agent that only (1) verdicts each fixed finding ADDRESSED / NOT ADDRESSED with file:line evidence and (2) inspects the fix diff for new breakage; forbidden to spawn subagents, runs on a cheap model. With such a rung, the Step 5 gate could afford to default toward re-reviewing marginal rounds instead of skipping them.

Open questions: how it composes with the screen/validation funnel (its verdicts are not wave findings), and whether it replaces the iteration>=3 `bugs roster=3` rung or sits below it.
