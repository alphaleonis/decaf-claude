---
# dcc-ho2w
version: 1
title: 'Benchmark v2: deny reviewers post-hoc PR context'
status: in-progress
type: milestone
priority: critical
created_at: 2026-08-10T12:32:37Z
updated_at: 2026-08-10T19:55:42Z
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
  RESOLVED which subjects are unsafe: see "Model cutoffs and subject vintage" below — 6 of 10 predate
  the binding Jan 2026 cutoff, including subject 9. Open question is now what to DO about it
  (options listed in that section), and at what cadence the corpus gets refreshed.
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

## Model cutoffs and subject vintage (2026-08-10)
Source: https://platform.claude.com/docs/en/about-claude/models/overview — the page carries TWO
cutoffs per model and they differ. For contamination the **training data cutoff** is the relevant
one: memorization only requires the data to be in training at all.

| Model | Reliable knowledge cutoff | Training data cutoff |
|---|---|---|
| Claude Opus 5 | May 2026 | May 2026 |
| Claude Sonnet 5 | Jan 2026 | Jan 2026 |
| Claude Fable 5 | Jan 2026 | Jan 2026 |
| Claude Opus 4.8 | Jan 2026 | Jan 2026 |
| Claude Opus 4.7 | Jan 2026 | Jan 2026 |
| Claude Sonnet 4.6 | Aug 2025 | Jan 2026 |
| Claude Opus 4.6 | May 2025 | Aug 2025 |
| Claude Haiku 4.5 | Feb 2025 | Jul 2025 |

(Opus 3 — Aug 2023 — is not on the page; it is retired.)

Models in play: `BENCH_MODEL=claude-opus-4-8` (training Jan 2026) is the session model for every
cell. `anthropic-code-review` hard-pins Sonnet and Haiku regardless of `BENCH_MODEL`; decaf's
`models=low` puts reviewers on haiku, `models=high` on opus/sonnet. So the **binding cutoff for
most cells is Jan 2026**.

## Subject merge dates vs the Jan 2026 cutoff

Dates are the merge commit's committer date from each `repos/<id>` checkout.

| Subject | Repo | PR | Merged | vs Jan 2026 |
|---|---|---|---|---|
| 1 | dotnet/efcore | 32770 | 2024-01-27 | IN TRAINING |
| 7 | prometheus/prometheus | 13777 | 2024-03-15 | IN TRAINING |
| 4 | microsoft/TypeScript | 61928 | 2025-06-25 | IN TRAINING |
| 9 | kubernetes/kubernetes | 130837 | 2025-07-11 | IN TRAINING |
| 8 | kubernetes/kubernetes | 129768 | 2025-09-08 | IN TRAINING |
| 10 | BurntSushi/ripgrep | 3185 | 2025-10-14 | IN TRAINING |
| 3 | dotnet/runtime | 127146 | 2026-04-21 | after cutoff |
| 5 | microsoft/vscode | 308517 | 2026-04-08 | after cutoff |
| 6 | microsoft/vscode | 320685 | 2026-06-11 | after cutoff |
| 2 | dotnet/aspnetcore | 67075 | 2026-07-09 | after cutoff |

**Six of ten subjects predate the binding cutoff**, including subject 9 — whose revert (#132958)
and take-2 (#133059) also landed in 2025. Every *catch* on those six now has a second
unfalsifiable explanation alongside the `gh` lookup. A *miss* is still sound evidence (memorization
cannot cause a miss), so `ours-bugs` 0/2 on subject 9 survives this.

Only subjects 2, 3, 5, 6 are vintage-safe for a Jan-2026-cutoff model. Note only ONE of them
(subject 5) is in the current 3-subject variant comparison.

**The judge is contaminated too.** This session graded subject 9 on `claude-opus-5[1m]` — training
cutoff May 2026, so the judge may know the revert as well. The frozen answer key is
human-confirmed, which limits the damage, but blind grading does not neutralize memorization.

## Implications to decide

- Vintage-safe subjects are a *decreasing* resource: every model release moves the cutoff forward
  and retires more of the corpus. The subject set needs a refresh cadence, not a one-time fix.
- The cutoff is per model, not per benchmark: pinning Haiku (Jul 2025) and Opus 4.8 (Jan 2026) in
  the same run means the same subject is in-training for one reviewer and not the other.
- Options: (a) restrict the corpus to post-cutoff PRs and accept a smaller/rolling set;
  (b) keep old subjects but report them separately as "possibly memorized"; (c) accept it and
  document, since the `gh` fix removes the *verifiable* leak and memorization is unfalsifiable
  either way.

## v2 methodology draft + subject-9 prototype (2026-08-10)
Draft written to `competition/benchmark/METHODOLOGY-v2.md`. Key changes from the design discussion:

**Force-pushed commits ARE recoverable** — corrects an earlier claim in this nib's discussion.
GitHub records every force-push as `HeadRefForcePushedEvent` with before/after oids and keeps those
commits fetchable. Verified: subject 9's as-opened head `be7da1315a3c` (force-pushed away 2025-03-15,
15 months ago) fetches cleanly and diffs to 11 files / +342-426 against merge-base `18e5a4d585f6`.
So reviewing the PR *as reviewed by humans* is feasible today, with no waiting.

**The unit is a review CHECKPOINT, not "as opened"** — a (head SHA, threads written against it) pair.
Subject 9 has 113 force-pushes over 4 months; its first thread postdates its first force-push by 3
hours, and several threads name files absent from the as-opened diff. Low force-push count should be
a subject-selection criterion.

**Subject 9 fails the Track-2 presence check, and the finding matters:**

| | as opened | as merged |
|---|---|---|
| `NewNodeManager` | returns `*NodeManager`, no error path | returns an error — the fatal path |
| exit pattern | 2x `klog.FlushAndExit` (correct) | 3x plain `klog.Flush()` (the h1 defect) |
| node.go | 92 lines | 190 lines |

Both the primary escaped bug AND h1 were introduced DURING review. Consequence: the two tracks can
need different checkpoints of the same subject, i.e. two review runs, not one.

**Thread inventory for Track 1 (subject 9):** 46 threads, 35 resolved / 11 unresolved, 0 bot-authored,
44 of 46 by danwinship, spanning 2025-03-15 to 2025-07-15 across 11 files.

**Time-boxing replaces blanket denial.** Four tiers: git ancestry is free and safe (needs --depth 500,
not 2); `gh` gets a PATH shim that refuses targets newer than the checkpoint and denies api/graphql/
search; WebFetch/WebSearch are disallowed (harness built-ins, not shimmable) and replaced by a
`docs-at` script pinning fetches to the Wayback snapshot at the checkpoint date; everything is logged
and post-run audited, with tripped cells quarantined rather than scored.

The in-loop LLM approval gate was considered and rejected as the primary control — latency and cost
per call, and an LLM cannot reliably date a page that carries no date. It belongs in the post-run
audit instead, where it blocks nothing and reviews evidence rather than guessing.

## Subject-9 checkpoint trace (2026-08-10)
Correction: subject 9 has **13 force-pushes, not 113** — the 113 figure was total timeline items,
not force-pushes. Earlier notes in this nib and the first draft of METHODOLOGY-v2.md were wrong.

Walked all 13 heads reading `pkg/proxy/node.go` at each (via
`repos/O/R/contents/PATH?ref=SHA` — one API call per head, no tree fetches):

| Push | Date | Head | node.go | NewNodeManager | Exit path |
|---|---|---|---|---|---|
| #0 opened | 2025-03-15 | be7da1315a3c | 91 | no error return | 2x FlushAndExit |
| #1 | 2025-03-15 | a0c5cb55f9c9 | 91 | no error return | 2x FlushAndExit |
| **#2** | **2025-03-18** | **2ccd845497ee** | **167** | **returns error** | **3x Flush()** |
| #3-#8 | to 2025-06-08 | ... | ~190 | returns error | 3x Flush() |
| #9 | 2025-06-22 | 7841a3e74d14 | 235 | returns error | 2x FlushAndExit + 2x Flush() |
| #10 | 2025-06-23 | 26a42d63228d | 190 | returns error | 3x Flush() |
| #13 merged | 2025-07-11 | 46e2c22fd766 | 189 | returns error | 3x Flush() |

Both defects entered in ONE push, 3 days after opening, and survived 11 more pushes over 4 months.
Push #9 briefly restored FlushAndExit (the h1 fix) and #10 reverted it the next day.

**Merge base is per-checkpoint.** Comparing a later head to the as-opened base inflates push #3 from
18 files to 240 files / +12663-5081, because the branch absorbed master in between. Compute
`compare/<target>...<head>` -> `merge_base_commit` for each checkpoint.

| Checkpoint | Base | Diff |
|---|---|---|
| #0 as-opened | 18e5a4d585f6 | 11 files, +342/-426 |
| #2 | 8559194e118f | 18 files, +745/-727 |
| merged | merge^1 | 18 files, +757/-803 |

**Recommended checkpoint for subject 9: push #2 (2ccd845497ee).** Defect present; diff is full-size
and realistic (745 vs 757 lines at merge); 29 of 46 threads (10 unresolved) are still ahead and
admissible, plus the escaped bug and h1 from post-merge -> ~31 candidate key entries vs 2 at the
merged head.

This resolves the earlier open question about needing two review runs for split-defect subjects:
ONE run at the earliest head containing the defect serves both purposes.

## Proof of concept complete (2026-08-10)
Three subjects taken through the section 4 procedure end to end. Artifacts under
`competition/benchmark/v2/` (fixtures, keys, airtight checkouts).

**Verdict on the checkpoint idea: it changed the answer in 1 of 3 subjects**, and there only because
the merged head turned out unscorable. Review did something different to the defect in each case —
INTRODUCED it (9), REMOVED it (11), TRANSFORMED it (2) — so there is no default checkpoint, but
neither is the machinery load-bearing. Demote it from v2's centrepiece to an occasional tool.

**What actually earned its keep:** the leak-proofing (section 5) and the key-building discipline
(section 4 step 6), which caught two invalid v1 ground truths before either cost a review cell. See
[[dcc-5xad]] for the audit of the remaining 9.

Procedure bugs found by executing it, all fixed in the doc:
1. `fetch --depth 1` of the merge base after a deep fetch re-shallows the repo (129013 commits -> 7)
2. Mechanical pre-filters rejected 0 of 46 threads on subject 9; the must_flag triage does the work
3. Force-pushes do not enumerate all heads — ordinary pushes leave gaps in the chain
4. A full-revert "fix" gives no line-level localization; the locus must come from the discussion

Next: prove the pipeline end to end on subject 2 (vintage-safe, clean 2-entry key) with gh and
WebFetch denied outright. Build the section 5 shim and `docs-at` only once the plumbing is shown to
produce a sensible verdict.

## Current Focus

Completed dcc-ixyy: Full 12-cell grid built. Fixtures and thread sets in `v2/pooled/`; checkouts gitignored and rebuilt
from pinned SHAs by `v2/build_pooled_repo.sh`.

**120 admitted review threads across 12 subjects**, against the anchor's 12 key entries across 7 — the
tenfold jump in miss-detector signal that justified the instrument. Nine repos, max two each, five
languages that fell out rather than being selected for.

The checkpoint rule needed measuring, not assuming: threads disperse across **4 to 15 commits** per PR,
the most-commented commit holding only ~42%. So the checkpoint is the commit the earliest review
comment targeted — the state at which human review began — with admission applied per thread (file in
the checkpoint diff, line in a changed hunk). That recovers 120 where a modal-commit rule gives ~92.

Verified rather than asserted: merge-base correctness per subject (every checkpoint diff touches dirs
the PR touches — the failure mode that once turned 18 files into 240); diff-size sanity, where two
outliers were investigated and `grafana#117615`'s 3.14x proved to be genuine branch shrinkage, its
checkpoint holding test scaffolding reviewers later consolidated; and Step 8 on all 12.

Two silent failures caught and fixed in tooling: `find_candidates.sh` reported "0 candidates" for two
repos that have ~100, from transient GraphQL errors swallowed by `2>/dev/null`; and
`build_pooled_repo.sh` aborted before printing its report because `grep` exits 1 on no match under
`set -e`. Both now fail loudly.

Carried forward: two small-diff cells admit fewer than 5 threads (2 and 3). They stay usable for
pooled adjudication, which does not depend on threads, but their thread-recall axis is thin. Small
PRs with dense review are the scarcest combination in the corpus — 13 of 547 candidates.
