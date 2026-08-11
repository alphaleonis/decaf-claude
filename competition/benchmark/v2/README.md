# Benchmark v2 — operational guide

**Status: built, not yet run at scale.** The corpus, the leak controls and the scoring pipeline all
exist and are exercised. No cross-tool comparison has ever run under v2 — that is the pilot
(`dcc-vkeh`), and it is blocked. See `Where this stands`.

Design rationale and both subject-construction procedures live in
[`../METHODOLOGY-v2.md`](../METHODOLOGY-v2.md) (§4c pooled, §4d anchor). Work is tracked by milestone
**`dcc-ho2w`**. The pre-pilot review of this harness is
[`analysis/HARNESS-REVIEW.md`](analysis/HARNESS-REVIEW.md).

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
├── pooled/<owner>-<repo>-<pr>/      THE CORPUS — 12 subjects, size x application type
│   ├── fixture.json                 checkpoint sha, base, date, diff stat, vintage, thread counts
│   ├── threads.json                 218 raw / 120 admitted human review threads — THE ANSWERS
│   └── repo/                        airtight checkout at the checkpoint (gitignored)
├── null/<repo>-<pr>/                3 null subjects — the noise floor; same shape, no scored threads
├── subjects/NN-<lang>-<size>.json   ANCHOR fixtures (blind-spot detection only, never ranks)
├── repos/<id>/                      anchor checkouts (gitignored)
├── analysis/
│   ├── subject-NN/answer-key.json   anchor keys: entries[] + rejected[] with admission evidence
│   ├── CANDIDATES.md                how the pooled corpus was selected and what it covers
│   ├── GROUND-TRUTH-AUDIT.md        the 12-subject audit that ended the key-only design
│   ├── NULL-ARM.md                  per-subject nullness verdicts and the line-level reasoning
│   └── HARNESS-REVIEW.md            the pre-pilot review of this harness (dcc-3cm6)
├── runs/<sid>__<tool>__shim-<on|off>__r<n>/
│   ├── final-output.md              the review
│   ├── access.log                   every external access, with verdicts
│   ├── build-capability.json        what the cell could build and run
│   ├── isolation.txt                transcript proof it did not read the answers
│   └── meter.json                   cost/token telemetry
├── scoring/                         ALL arithmetic — score_pooled.py, check_artifacts.py, tests
├── fixture_lib.sh                   resolve any subject id to its kind, fixture, checkout, threads
├── shim/{gh,curl,wget,docs-at}      ENFORCING access controls (treatment arm)
├── shim-log/gh                      PASS-THROUGH logger (control arm)
├── run_cell_v2.sh                   the cell runner
├── leak_audit.sh                    per-cell channel coverage report
└── verify_cell_isolation.sh         per-cell filesystem-leak check
```

## Running a cell

```sh
cd competition/benchmark
bash v2/run_cell_v2.sh sveltejs-kit-15685 ours-review                          # shim ON (treatment)
BENCH_SHIM=off BENCH_REPEAT=2 bash v2/run_cell_v2.sh sveltejs-kit-15685 anthropic-code-review
```

The subject id is whatever `fixture_lib.sh` resolves: a pooled or null directory name
(`sveltejs-kit-15685`), a slug (`sveltejs/kit#15685`), or an anchor number (`2`, `9`).

Tools wired: `ours-bugs`, `ours-review`, `ours-audit`, `anthropic-code-review`.
`superpowers` and the other competitors still need v2 invocations (`dcc-vkeh`).

Every tool gets the same prompt and reviews the local `base..checkpoint` diff. **No prompt names the
PR or tells a tool to fetch one** — under pooled adjudication the review threads on that page are a
scored target, so pointing one tool at it would be pointing it at the answer.

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
| `gh pr/issue view` | allowed if created ≤ checkpoint; `--json` required, and its fields are an **allowlist** |
| `gh pr list` | allowed with `created:<=CHECKPOINT` injected into `--search`; same field allowlist |
| `gh pr diff` | **denied** — returns the merged state, future information at an earlier checkpoint |
| `gh api` / `graphql` / `search` | **denied** — cannot be date-bounded |
| bare `gh pr view` | **denied** — prints `state: MERGED`, reviewers and approvals |
| a target given as a URL | resolved to its number and date-checked like any other |
| `curl` / `wget` | GitHub hosts **denied** (case-insensitively); everything else permitted and logged |
| WebFetch / WebSearch | **denied** (harness built-ins, not shimmable) — use `docs-at` |
| `docs-at <url>` | Wayback snapshot pinned at or before the checkpoint date |

**The `--json` allowlist is `number title body author createdAt url id baseRefName headRefName
isCrossRepository` — everything else is refused.** It has to be an allowlist: `gh pr view --json`
accepts 46 fields, and the blocklist this replaced let `latestReviews` through (it spelled `reviews`,
and the match was case-sensitive), along with `commits`, `files`, `reviewDecision` and the whole
merge-state family. On `sveltejs/kit#15685` that returned `CHANGES_REQUESTED` from 2026-05-18 and
`APPROVED` from 2026-07-01 against a 2026-04-09 checkpoint, plus all 8 post-checkpoint commits.

Residual and accepted: `title` and `body` can be edited after the checkpoint, and the API serves only
the current text — there is no historical variant to request.

Every hole above was found by *testing*, not by writing the doc. `gh pr list` returned the revert
PR's title verbatim; bare `gh pr view` printed `state: MERGED` and an approval; the field blocklist
and the URL bypass were found by probing the shim with `BENCH_POLICY_DRYRUN=1` (`dcc-3cm6`).

## Filesystem isolation

The shims cover the network. The local tree needs its own control, because this subject's
`threads.json` — the thread axis's answer key — sits one directory above the checkout, the anchor
keys and every earlier cell's output a couple more, and `--dangerously-skip-permissions` removes path
gating entirely.

`v2/hooks/block-answer-access.js` is a `PreToolUse` guard that denies any path resolving **inside
`competition/benchmark/` but outside the cell's own checkout**. It fires under
`--dangerously-skip-permissions` (exit 2 blocks the call, verified against `Read` and the `Bash`
fallback) and it is behavior-neutral: on a normal review cell it evaluated 29 paths and denied 0.

`run_cell_v2.sh` generates the settings file per cell, records every verdict in `access.log` under
the `fs` channel, and then runs `verify_cell_isolation.sh` over the transcript — prevention *and*
proof, since a control that has only been reasoned about is not a control.

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

Built and validated:

- **the 12-subject pooled corpus** — size × application type, 9 repos, 120 admitted threads of 218
  (`dcc-ixyy`); a checkout was destroyed and rebuilt byte-identically from its committed fixture
- **the null arm** — 3 subjects, one per size bucket (`dcc-mjj5`), each re-adjudicated at line level
  over its *full* file list and recorded in `analysis/NULL-ARM.md` (`dcc-nvrt`)
- **the ground-truth audit** — all 12 anchor candidates; 5 unusable, TypeScript eliminated
  (`dcc-5xad`)
- **the scoring pipeline** — `scoring/score_pooled.py` with 25 self-tests, and `check_artifacts.py`
  asserting the layers describe one finding set (`dcc-y2e6`)
- **found-vs-reported** — every recall metric computed twice, per tool and corpus-wide (`dcc-c92m`)
- **leak controls** — DENY path exercised by a real reviewer, control arm instrumented, and the
  filesystem channel both *enforced* (a `PreToolUse` guard that holds under
  `--dangerously-skip-permissions`) and *audited* per cell from the transcript

Not done:

- **no cross-tool comparison** has ever run under v2 — the pilot, `dcc-vkeh`
- **anchor keys exist for 4 of 7 subjects** — 2, 7, 9, 12, totalling 5 entries; subjects 1, 8 and 10
  are validated but unbuilt (`dcc-9ncz`)

## Vintage: 5 of 12 subjects are not poolable

Anthropic publishes no day-level training cutoff, so Opus 5's "2026-05" is read as end-of-May: a
subject is provably out-of-window only if it merged on **2026-06-01** or later (`dcc-vvf0`). Five
subjects merged inside May 2026 and are kept but **flagged and excluded from cross-subject figures**
— `backend` S/M/L, `contract` L, and `app-ui` M. **There is no reportable backend number in this
corpus.** The citable seven are contract S/M, app-ui S/L, and library S/M/L.

`v2/scoring/vintage.py` computes the status per (subject, model) pair at analysis time — never from
a flag in the fixture, since the answer changes when a model ships — and `check_pooling()` makes a
silent average fail loudly. `find_candidates.sh` screens at 2026-06-01 so the flagged set cannot
grow. The null arm is exempt: soak time beats vintage there, and a memorized null subject deflates
the noise floor, which is the safe direction.

## Results so far

`runs/RESULTS.md` — the first cells and the found-but-suppressed effect.
`runs/CONTROLLED-TEST.md` — shim on vs off, 4 cells. Two results worth carrying forward: the shim
does not change *detection* (4/4 reported the defect either way), and **output-grepping undercounts
leaks** — a control cell read two post-checkpoint comments and cited neither, so it would have scored
clean. Every leak measurement taken before `shim-log/gh` existed is a lower bound.
