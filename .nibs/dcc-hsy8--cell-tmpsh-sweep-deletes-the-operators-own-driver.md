---
# dcc-hsy8
version: 1
title: cell_tmp.sh sweep deletes the operator's own driver logs in /tmp
status: completed
type: bug
created_at: 2026-08-20T12:48:55Z
updated_at: 2026-08-20T19:48:36Z
parent: dcc-ho2w
order: zzk
---

`cell_tmp.sh`'s post-cell sweep removes any top-level `/tmp` path created during a cell group and
absent from the quiescent baseline. That correctly catches junk a review tool leaves behind, but it
also catches **the operator's own driver log**, because `run_pilot.sh` is normally launched as
`... > /tmp/bench-run.log` — the pattern the `bench-run` skill documents verbatim.

Observed 2026-08-20 during [[dcc-fm7x]]: the `superpowers` r2 sweep recorded

```
removed  /tmp/bench-audit.log  0  created during the group (absent from quiescent baseline)
```

deleting the log of a *different, concurrently queued* driver. The four earlier logs survived only
because each predated its own group's baseline.

## Why this matters more than it looks

The log vanishes while the run continues, so `cat /tmp/bench-audit.log` returns "No such file or
directory" for a cell that is running perfectly. A `tail -f` started earlier keeps streaming the
deleted inode, so monitoring and filesystem disagree. That is the harness's recurring
indistinguishable-failure shape arriving through a new door: **a missing log is not evidence of a
missing run**, and the obvious reading of the evidence is the wrong one.

No data was lost this time — `meter.json`, `isolation.txt` and the `runs/*.tsv` row are the
authoritative records and none live in `/tmp`.

## Fix candidates

- Have `run_pilot.sh` default its own log to `v2/runs/` (gitignored) rather than the operator
  choosing a `/tmp` path, and update the `bench-run` skill's documented invocation.
- Or exclude the live drivers' own stdout targets from the sweep via the live-cell registry.
- Or narrow the sweep to paths the *cell* created, which is what it is actually for.

## Acceptance

- [ ] A driver log survives a concurrent cell group's sweep
- [ ] The `bench-run` skill no longer documents an invocation whose log the harness deletes
- [ ] `tmp-cleanup.tsv` distinguishes "cell junk" from "not ours" if the sweep keeps its current reach

## Related gap: the last cell's `.decaf/` report survives into the grading stage

`run_cell_v2.sh`'s `reset_repo()` cleans the checkout *before* each cell, so the report written by the
**final** cell of a matrix is never cleaned — it sits in the working tree indefinitely.

Observed 2026-08-20 on PostHog-posthog-55149 ([[dcc-fm7x]]): the `ours-audit` r1 report
(`.decaf/code-reviews/CODE_REVIEW_*.md`, 90,902 bytes — one tool's complete finding set) was still in
the checkout when the two blind graders ran there. Pass 1 noticed it and disclosed that it did not
open it; pass 2 never saw it.

Verified after the fact by grepping both grader transcripts: `CODE_REVIEW` and `code-reviews` appear
**zero** times in each, so neither read or listed it. The blind held **by luck and by one grader's
discretion, not by a control.**

There is no grader-side equivalent of `verify_cell_isolation.sh`. A grader that had read that file
would have graded one arm's claims with that arm's own reasoning in front of it, and nothing in the
pipeline would have recorded it.

Additional acceptance:

- [ ] The checkout is reset after the LAST cell of a matrix, not only before each cell
- [ ] The grading stage refuses to start on a dirty subject checkout, or resets it first
- [ ] A grader-transcript isolation check exists, analogous to `verify_cell_isolation.sh`, asserting no
      grading session referenced a tool report, `clusters.json`, `findings.json`, `extract/`, or `runs/`

## The grader/annotator forbidden list is enumerated by hand, and it was incomplete

During [[dcc-hw48]]'s annotation pass on grafana-grafana-117615 (2026-08-20) the agent disclosed
reading `pooled/<subject>/THREAD-AXIS-NOTE.md`, which states that no tool matched either of that
subject's two human threads. The file was not on the forbidden list I wrote — the list names
`analysis.json`, `clusters.json`, `findings.json`, `extract/`, `metrics.json`, `grading/verdicts-*`,
`grading/calibration*` and `runs/`, and misses every prose write-up that quotes those artifacts.

That is a real leak channel for exactly the circular reasoning the pass exists to avoid: the agent was
deciding whether those two threads are matchable, and it had seen that no tool matched them.

Both verdicts were re-verified independently afterwards and hold on checkpoint code alone —
`unquoteIdentifier` occurs 0 times under `public/app/features/expressions/`, and `default_table`
0 times — so nothing had to be re-run. The control held by luck and by the agent's disclosure.

`analysis/` is full of the same hazard: `THREAD-AXIS.md`, `PILOT-RESULTS.md`, `OURS-BUGS-VS-SUPERPOWERS.md`,
`SINGLE-SEAT-FINDINGS.md` and the per-subject notes all quote per-arm coverage.

Additional acceptance:

- [ ] The blind-work forbidden list is derived, not hand-written: deny by DEFAULT and allow only the
      subject's `repo/`, the named worksheets, and `fixture.json`
- [ ] Any `*.md` under `pooled/` or `analysis/` is off-limits to graders and annotators
- [ ] The grader-transcript isolation check greps for those paths too, not only the JSON artifacts

## Summary

**Completed 2026-08-20** — Three fixes, one per failure the nib describes.

**The driver log.** `cell_tmp.sh`'s PROTECT pattern now covers `bench-*`, the documented invocation
in the `bench-run` skill writes to `v2/runs/driver-<ts>.log` instead of `/tmp`, and the sweep's
manifest distinguishes three reasons for keeping a path — protected pattern, present before the group
started, not owned by this user — from "removed". A sweep that only logs what it deleted cannot be
audited for what it should not have deleted. Tested: a driver log survives while cell junk beside it
is still swept.

**The last cell's report.** `run_cell_v2.sh` now resets the checkout AFTER the cell as well as before,
placed after artifact capture, report extraction and the isolation check so nothing needed is
discarded, and warns if anything survives. Found FIVE subjects in the reported state, not one:
grafana#117615, immich#28886, mattermost#36824 and prometheus#18081 each still held a
`.decaf/code-reviews/CODE_REVIEW_*.md` of 20-38 KB alongside the PostHog case. All cleaned.

**The grading blind had no control.** New `verify_grading_isolation.sh`, the mirror of
`verify_cell_isolation.sh` pointed the other way: `--precheck` refuses to grade in a dirty checkout,
and the transcript mode flags a pass that touched tool output, the pending result, or any PROSE
write-up quoting either — the class the hand-enumerated forbidden list kept missing, which is how an
annotator came to read a note saying no tool matched the threads it was judging. Both modes are wired
into `/bench-analyze` as a new step 2b.
