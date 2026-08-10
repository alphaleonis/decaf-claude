# Benchmark v2 — operational guide

**Status: proof of concept.** Fixture construction and leak controls are validated on real subjects;
scoring is not built. Do not run a full benchmark yet — see `Where this stands` below.

Design rationale and the subject-construction procedure live in
[`../METHODOLOGY-v2.md`](../METHODOLOGY-v2.md). Work is tracked by milestone **`dcc-ho2w`**.

---

## Why v2 exists

A reviewer under v1 could read the answer. Four channels, all confirmed by measurement:
GitHub cross-references (11 of 12 subjects link the fixing PR), review threads and revert bodies,
cross-cell `.decaf/` contamination, and training-data memorization. v2's job is to make the first
three impossible and the fourth bounded — and to make it *provable per cell* that a reviewer did not
cheat.

## Layout

```
v2/
├── subjects/NN-<lang>-<size>.json   fixture: checkpoint sha, base, date, diff stat
├── repos/<id>/                      airtight checkout at the checkpoint (gitignored)
├── analysis/subject-NN/
│   └── answer-key.json              entries[] + rejected[] with admission evidence
├── runs/<sid>__<tool>__shim-<on|off>__r<n>/
│   ├── final-output.md              the review
│   ├── access.log                   every external access, with verdicts
│   └── meter.json                   cost/token telemetry
├── shim/gh                          ENFORCING: time-boxed gh (treatment arm)
├── shim/docs-at                     Wayback-pinned documentation fetch
├── shim-log/gh                      PASS-THROUGH logger (control arm)
└── run_cell_v2.sh                   the cell runner
```

## Running a cell

```sh
cd competition/benchmark
bash v2/run_cell_v2.sh <subject_id> <tool_id>              # shim ON (treatment)
BENCH_SHIM=off BENCH_REPEAT=2 bash v2/run_cell_v2.sh 2 anthropic-code-review   # control arm
```

Tools wired: `ours-bugs`, `ours-review`, `ours-audit`, `anthropic-code-review`.
`superpowers` and the other competitors still need v2 invocations (`dcc-vkeh`).

The runner sets these itself; they matter if you invoke a shim by hand:

| Env | Meaning |
|---|---|
| `BENCH_CHECKPOINT_DATE` | the cutoff — anything created after it is refused |
| `BENCH_REAL_GH` | absolute path to the real `gh` |
| `BENCH_ACCESS_LOG` | file the shims append to |
| `BENCH_ENFORCING_SHIM` | path to `shim/gh`, used by the logger as a policy oracle |
| `BENCH_POLICY_DRYRUN=1` | makes `shim/gh` print its verdict and exit 0 without running gh |

## The access controls

**Not blanket denial — time-boxing.** A reviewer legitimately needs library docs and prior PRs;
what it must not see is anything dated after the checkpoint.

| Channel | Treatment |
|---|---|
| local git | free — ancestry *is* the time boundary. Fetch `--depth 500`, drop the remote |
| `gh pr/issue view` | allowed if created ≤ checkpoint; `--json` required, safe fields only |
| `gh pr list` | allowed with `created:<=CHECKPOINT` injected into `--search` |
| `gh pr diff` | **denied** — returns the merged state, future information at an earlier checkpoint |
| `gh api` / `graphql` / `search` | **denied** — cannot be date-bounded |
| `--comments`, `--json reviews/state/...` | **denied** — post-checkpoint content on a pre-checkpoint PR |
| WebFetch / WebSearch | **denied** (harness built-ins, not shimmable) — use `docs-at` |
| `docs-at <url>` | Wayback snapshot pinned to the checkpoint date |

Every hole above was found by *testing*, not by writing the doc. `gh pr list` returned the revert
PR's title verbatim; bare `gh pr view` printed `state: MERGED` and an approval.

## Per-cell isolation

`run_cell_v2.sh` resets the fixture checkout (`checkout -f <checkpoint>` + `clean -xfd`) before every
cell and **refuses to run** if the tree is still dirty afterwards (exit 77) or the checkpoint is
missing (exit 78). Review tools write into the working tree — decaf's skills drop reports in
`.decaf/code-reviews/` and read that directory back for recurring findings — so without the reset a
cell inherits the previous cell's artifacts. That is the v1 failure (`dcc-2cxq`) and it is the one
thing v2 cannot afford to repeat.

This guard was missing until 2026-08-10. A stray `ours-review` report sat in `v2/repos/2/` for all
eight subsequent subject-2 cells. Checking every one of their transcripts — parents and subagent
sidechains — showed no cell read it, so the results stand; the guard closes the hole for the next
run. Note that the *outputs* alone could not have settled this: only the transcripts record what was
read.

## Two rules that are easy to get wrong

**Fetch the checkpoint and nothing else.** A second `fetch --depth 1` of the merge base re-shallows
the repository and discards the deep history — observed collapsing 129,013 commits to 7. The base is
an ancestor; it arrives with the checkpoint. Verify with `git rev-list --count HEAD`.

**Each checkpoint has its own merge base.** Reusing an earlier base against a later head drags in
everything the target branch merged in between — 18 files became 240 on subject 9.

## Where this stands

Validated end to end:

- fixture construction on 3 subjects, with 4 procedure bugs found by executing it
- leak controls, with the DENY path exercised by a real reviewer and the control arm instrumented
- key-building, which caught **3 invalid ground truths** before any cost a review cell
- 8 review cells run and hand-graded

Not built:

- **no scoring pipeline** — zero references to `analysis/scripts/*.py` from `v2/`; cells are graded by
  reading them (`dcc-y2e6`)
- **keys are thin** — 1–2 entries each; a 1-entry key cannot rank tools (`dcc-595v`)
- **found-vs-reported unresolved** — a tool found the defect and headlined "No blocking issues
  found"; headline-only extraction scores that a miss (`dcc-c92m`)
- **9 subjects unaudited**, base rate of bad ground truth currently 2 in 3 (`dcc-5xad`)
- **no cross-tool comparison** has ever run under v2 (`dcc-vkeh`)

## Results so far

`runs/RESULTS.md` — the first cells and the found-but-suppressed effect.
`runs/CONTROLLED-TEST.md` — shim on vs off, 4 cells. Two results worth carrying forward: the shim
does not change *detection* (4/4 reported the defect either way), and **output-grepping undercounts
leaks** — a control cell read two post-checkpoint comments and cited neither, so it would have scored
clean. Every leak measurement taken before `shim-log/gh` existed is a lower bound.
