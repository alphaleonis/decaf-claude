---
# dcc-vkeh
version: 1
title: 'Pilot: full roster on two pooled subjects — validate the instrument'
status: in-progress
type: task
priority: high
created_at: 2026-08-10T17:43:28Z
updated_at: 2026-08-11T14:10:26Z
parent: dcc-ho2w
blocked_by:
    - dcc-5xad
    - dcc-y2e6
    - dcc-fhp1
    - dcc-3cm6
    - dcc-suz4
    - dcc-vvf0
    - dcc-qwt3
order: 8k
---

Everything run under v2 so far is essentially one tool on one subject: four anthropic cells plus one
`ours-review` cell, all on old subject 2. **There has been no cross-tool comparison under v2**, which
is the benchmark's entire purpose.

Rescoped by the instrument decision ([[dcc-595v]]): the pilot runs **pooled adjudication on two
pooled-corpus subjects** ([[dcc-ixyy]]), not the key-based anchor. Its job is to answer whether the
instrument works *before* the full run spends against all 12 subjects.

## What the pilot must establish

1. **Is the judge stable at the `valid-other` / `nitpick` boundary?** This is the single load-bearing
   subjectivity in the design — v1's own distribution put 58 of 98 clusters in `nitpick` and only 6
   in `false-positive`, so that boundary *is* the metric. Re-judge a sample blind and twice; if the
   two passes disagree materially, pooled adjudication does not yet work.
2. **Do the tools separate?** On precision, nitpick ratio, and unique real findings. If everyone
   scores alike the instrument is not discriminating and the full run is wasted.
3. **Does thread recall separate them?** The miss detector is the axis that catches what pooled
   adjudication structurally cannot. Report it separately from pooled precision — never merged.
4. **Does the judge dismiss what expert humans raised?** Any admitted thread the judge rules
   not-real, when a tool did report it, is a direct calibration failure. This check exists only
   because subjects were drawn from review-disciplined repos.

## Subject choice

Two subjects with dense admitted-thread sets, from different repos and different cells. Suggested:
`PostHog/posthog#52408` (backend/L, 19 admitted of 27) and `dotnet/efcore#34127` (library/M, 11 of
15). Both are well above the thread-thin cells and exercise different languages and application
types. Avoid the two thin cells (`immich#28886` at 2, `sveltejs/kit#15685` at 3) — their thread axis
cannot carry a validation.

## Scope

- Full roster: `ours-bugs`, `ours-review`, `ours-audit`, `anthropic-code-review`, `superpowers`, plus
  whichever competitors survive tool-definition rot (`pr-review-toolkit` and
  `tag1-comprehensive-review` are absent from `tools.json`)
- 2 subjects x roster x 2 repeats, shim ON
- Score through the pipeline ([[dcc-y2e6]]), not by hand
- Include a null cell ([[dcc-mjj5]]) if ready, so precision has an absolute floor on day one

`superpowers` needs a v2 invocation — it is local-diff-only already, which fits v2 naturally.
`run_cell_v2.sh` currently supports only the three decaf presets and anthropic, and still points at
`v2/repos/<id>`; pooled subjects live in `v2/pooled/<owner>-<repo>-<pr>/repo`.

## Acceptance

- [ ] `run_cell_v2.sh` runs against pooled fixtures, and every roster tool has a working invocation
- [ ] 2 subjects x roster x 2 repeats completed with clean leak audits
- [ ] Judge stability measured by a blind re-judge of a sample, with the disagreement rate reported
- [ ] Tools measurably separate on pooled precision, or a written explanation of why they do not
- [ ] Thread recall reported as its own axis, plus any threads the judge dismissed


## Pilot subjects (2026-08-11, post-census)

Run the pilot on **library M — dotnet/efcore#34127** (10 human threads of 11, 9% bot, citable) and
**library L — prometheus/prometheus#18081** (10 of 10 human, 0% bot, citable): the only two cells
clean on every axis at once — vintage, human-thread density, and bot share ([[dcc-qwt3]],
`v2/analysis/THREAD-AXIS.md`). The pilot does NOT wait for the corpus repair ([[dcc-2gu2]],
[[dcc-ryo4]], [[dcc-scc3]]) — only for [[dcc-qwt3]]'s axis split, so thread recall is computed
against human threads from the first cell.


## Pilot scope, decided 2026-08-11 (operator)

**Roster: all 7.** `ours-bugs`, `ours-review`, `ours-audit`, `anthropic-code-review`, `superpowers`,
`pr-review-toolkit`, `comprehensive-review` — the last three wired into `run_cell_v2.sh` for this
pilot and probed before the matrix spends. Any tool that fails its probe drops out and the reason is
recorded rather than the tool quietly missing.

**Null arm included:** `grafana-122269` (backend M), roster x 1 repeat, so pooled precision has an
absolute noise floor from day one. Scored with `--allow-silent-cells` and WITHOUT `--threads` — every
null thread is `not-scored`, and passing them would trip the "no thread is admitted" guard.

**Matrix: 35 cells.** 2 pooled subjects x 7 x 2 repeats = 28, plus null x 7 x 1 = 7. Shim ON only;
no control arm in the pilot.

**Cells run strictly sequentially, detached from the driving session.** Two operational facts, both
learned by losing work: `run_cell_v2.sh` resets the subject checkout before every cell, so cells
sharing a subject cannot overlap; and a background shell started by a Claude Code session dies with
that session — the first probe was killed at ~20 minutes, billed, with an empty `meter.json` and no
`final-output.md`. The driver runs under `setsid` for that reason.


## Probe results, 2026-08-11 — the three newly wired tools

Run as `r0` cells on `dotnet-efcore-34127` (library M) with the shim on. **`r0` cells are probes and
are excluded from scoring**: they ran before the stray-worktree fix below, and the pr-review-toolkit
probe ran with another tool's worktree present. Cheap to re-run; not worth a condition difference in
the scored matrix.

| Tool | rc | wall | cost | isolation | output |
|---|---|---|---|---|---|
| `superpowers` | 0 | 804s | $4.28 | CLEAN | 143 lines, built base + HEAD, ran an executable probe |
| `pr-review-toolkit` | 0 | 1384s | $19.57 | CLEAN | 145 lines, 6 specialist agents, each building |

Both independently reported the same Critical — `NullPropagatedOperands` recursing into
`AndAlso`/`OrElse`, which do not propagate NULL in three-valued logic. Convergence between two
unrelated tools on a specific, executable claim is the first evidence under v2 that pooled
adjudication has something to adjudicate.

**Cost basis corrected.** The pilot was scoped against archived v1-era cells ($0.5-4.2). Real v2
cells cost several times that, because v2 hands every tool a working build toolchain (`dcc-fhp1`) and
the tools use it — both probes compiled EF Core and ran code. Full-7 matrix re-estimated at ~$285
against the ~$90-120 the roster decision was originally taken on; operator re-confirmed full 7 at the
corrected figure.

## Harness defect found by probing, not by reading

`superpowers` created `/tmp/review-base` — a live git worktree of the base commit — and left it
registered in `.git/worktrees` after claiming to have removed it. `pr-review-toolkit` did the same
with `/tmp/efbase`. Nothing caught it: `git status --porcelain` does not report a worktree outside
the checkout, `clean -xfd` cannot reach it, and `hooks/block-answer-access.js` guards
`competition/benchmark/` only. That is per-cell state surviving into the next cell through a channel
no control covered — the `dcc-2cxq` shape in a new door.

No scored result is affected: the strays hold the base commit, which contains no answers. Fixed in
`reset_repo()`, which now prunes, force-removes every worktree that is not the checkout, and exits 79
if any survives. Verified by planting one and watching the reset remove it.


## Probe 3 and a second harness defect — `.result` is not the review

| Tool | rc | wall | cost | isolation | report captured |
|---|---|---|---|---|---|
| `comprehensive-review` | 0 | 1925s | $17.61 | CLEAN | **20%** |
| `pr-review-toolkit` | 0 | 1384s | $19.57 | CLEAN | 93% |
| `superpowers` | 0 | 804s | $4.28 | CLEAN | 99% |

All three run. `comprehensive-review` needed no git remote after all — `--local` carried it past
provider detection, so the full 7-tool roster is viable.

**`final-output.md` is `jq -r '.result'`, which is the session's final assistant message and nothing
else.** For a tool whose last act is to print its report that is the whole review; for one that
prints a report and then keeps working it is a fragment. `comprehensive-review` printed an
11,605-char report as assistant block 5, then closed with a 3,104-char addendum beginning "Everything
else in my previous report stands unchanged" — and that addendum is all `final-output.md` holds.
Every original finding was outside the file the scorer reads.

Nothing caught it. The file was non-empty, well-formed and plausible, so every guard passed. The bias
is one-directional: it deletes findings, making a verbose tool look quiet and precise. On a
cross-tool precision comparison that is a wrong answer, not a noisy one.

Fixed by `v2/extract_cell_report.sh`, wired into `run_cell_v2.sh`: it rebuilds the cell's complete
MAIN-CHAIN output from the transcript into `cell-report.md` and prints what fraction of it
`final-output.md` held, flagging anything under 80%. Sidechains are excluded on purpose — a finding a
sub-agent produced but the orchestrator never surfaced is not something the reader was shown, and
that reported-vs-found split is itself a scored axis ([[dcc-c92m]]). `/bench-analyze-v2` now extracts
from `cell-report.md`.
