---
# dcc-ho2w
version: 1
title: 'Benchmark v2: deny reviewers post-hoc PR context'
status: draft
type: epic
priority: critical
created_at: 2026-08-10T12:32:37Z
updated_at: 2026-08-10T12:32:37Z
order: zzzzV
---

**DRAFT — design under discussion, not ready to execute.**

## Problem

Reviewers can see the current state of the PR: review threads, their resolutions, merge status, and
the subsequent revert / take-2 PRs. All of it is post-hoc, and the answer keys are *built* from it.
A tool that reads it is reading the answer key, not reviewing code.

Measured on subject 9 (see [[dcc-2cxq]]):

- `anthropic-code-review` — every finder of the primary bug in BOTH repeats cites the revert
  (#132958) or take-2 (#133059). Its 2/2 bug-catch is substantially lookup, not review.
- decaf presets — consolidated reports name the human reviewers (`nojnhuh`, `danwinship`) 12x in
  `ours` r1, 6x in `ours-review` r1, 2x in `ours-audit` r1. `prior-feedback-reviewer` reads PR
  threads by design; on a merged subject those threads contain h1 and h2 verbatim.
- `pr-review-toolkit` r2 — found h2 with NO thread references; that catch appears genuinely earned.

Only `superpowers` is structurally blind to the PR (`local_diff=true`). Every other tool has the
same access, so this is not one tool's problem.

**Consequence: the bug-catch and human-issue columns do not currently measure what they claim for
any PR-mode tool.** Re-grading cannot fix it — a reviewer that reads a thread and silently restates
its conclusion is indistinguishable from one that reasoned it out. Only re-running under denied
context fixes it.

## What is already safe

Git ancestry is the time boundary. `repos/9` has no refs and 3 reachable commits, all ancestors of
the merge; the revert is a descendant and is simply absent. No reconstruction is needed — checking
out the merge SHA already gives the point-in-time repo.

The shallow `--depth 2` fetch is likely part of the cause: with no local history to explore, tools
go to the network, and the network answers with the future.

## Proposed design

1. **Deepen history, drop the remote.** Fetch `--depth 500` (or `--shallow-since`) from the merge
   SHA; ancestry guarantees nothing later appears at any depth. Then `git remote remove origin` so
   no later fetch can pull newer state. This ENABLES the archaeology we want (git log/blame/show of
   deleted code) while excluding the future.
2. **Shim `gh`** early on PATH: exit non-zero with "PR metadata unavailable — review from the local
   diff", and log every attempted call. The log is a validity metric.
3. **Disallow `WebFetch` / `WebSearch`** for the cell.
4. **Sanitized PR context file** — title and body only, snapshotted at init. Scan bodies once: a PR
   description can itself reference a later fix.
5. **Rewrite invocations** off `{PR}` / `{REPO}` to the local range + context file.
6. **Record gh-attempts in `meta.json`** alongside model and effort.

## Reclassify human_issues

The merged head already contains the fixes for resolved threads — subject 9's key notes 44 of 46
threads were "RESOLVED and folded into the merged diff (so nothing remains for a reviewer of the
final diff to catch)". The surviving h1/h2 are exactly the UNRESOLVED ones, and h1 was raised
post-merge.

So `TP-human` does not measure "did the reviewer match a human" — its population is "issues humans
found and did NOT fix". Since both are unresolved they are present in the merged code and
discoverable from code alone: they are **secondary escaped defects**, not human issues. Reclassify
them as such. This makes the metric coherent AND removes any incentive to read threads.

`TP-primary` was always sound: the escaped bug is by definition not fixed in the merged head.

Rejected alternative: review the first-pushed diff so all 46 threads become catchable. Needs a
second answer key per subject, the pre-review head is usually destroyed by force-pushes, and it
measures what the humans demonstrably already caught.

## Answer keys survive

The keys are built from post-hoc information, which is legitimate: the JUDGE may see the revert, the
REVIEWER may not. Frozen keys, review diffs, and the grading methodology all carry forward. Only the
runs are invalidated.

## Open questions — TO DISCUSS

- **Prior-PR discussion is clipped.** Ancestry gives prior PRs' code and merge messages offline, but
  not their GitHub conversation. Accept, or find a way to snapshot pre-dated discussion too?
- **Training-data contamination** is unfalsifiable — a model may have memorized a PR and its revert.
  "After the model cutoff" is not one date (`anthropic-code-review` hard-pins Sonnet and Haiku, which
  may differ from Opus). Implies the subject set is a ROLLING asset needing periodic refresh. Which
  of the current 12 subjects are already unsafe? Unknown.
- Does denying PR access change what PR-native tools are, such that we measure a different tool?
- Do we keep `superpowers` comparable, given it was always local-diff-only?

## Acceptance (provisional)

- [ ] Design agreed (this nib leaves draft)
- [ ] Harness changes implemented (items 1-6)
- [ ] `human_issues` reclassified across all answer keys
- [ ] LEAK AUDIT GATE: run 2-3 cells, then grep bundles for revert PR numbers, reviewer names, and
      thread language, and inspect the gh-attempt log. Full re-run is NOT authorized until this passes
- [ ] Subject-vintage policy vs model cutoffs decided (may force subject replacement)
- [ ] Full re-run (dependent item — separate decision from building the harness)
