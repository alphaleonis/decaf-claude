---
description: Run benchmark v2 cells — one cell, or a subject × tool × repeat matrix — under the time-boxed access controls
argument-hint: "<subject-id> [<tool-id>|all] [--repeats N] [--arm on|off]"
---

Run **v2** cells. Never v1 — its dataset is void and `scripts/bench_next.sh` refuses without
`BENCH_V1_ALLOW=1`.

## Before spending

Run `/bench-status` first and read the `DO NOT SCORE` list — a cell that failed with *partial* output
still has a non-empty `final-output.md`, and re-running it is the fix.

Then check the three things that have each cost a cell:

```
df -Pm /tmp | awk 'NR==2{print "  /tmp free: "$4"MB"}'          # tmpfs floor; the runner refuses under 4096
git -C competition/benchmark/v2/pooled/<subject>/repo status --porcelain | wc -l   # must be 0
git -C competition/benchmark/v2/pooled/<subject>/repo worktree list | wc -l        # must be 1
pgrep -cf 'claude -p'                                            # a cell already running?
```

## Running

One cell:

```
cd competition/benchmark
BENCH_REPEAT=1 bash v2/run_cell_v2.sh <subject_id> <tool_id>
```

A matrix — resumable, and this is the normal path:

```
cd competition/benchmark
bash v2/run_pilot.sh <subjects-csv> <tools-csv> <repeats>
```

**Launch it detached.** A background shell started by a Claude Code session dies with that session —
this has already killed a cell twenty minutes in:

```
setsid nohup bash -c 'cd competition/benchmark && bash v2/run_pilot.sh …' \
  > /tmp/bench-run.log 2>&1 < /dev/null & disown
```

Then watch the log with a Monitor whose filter matches **failure as well as success** — `rc=`,
`isolation:`, `REFUSING`, `EMPTY`, `api-error`, and a `/tmp` free-space check. A filter that greps
only for completion is silent through a crashloop.

## Rules the runner enforces, and one it cannot

- Cells on the **same subject can never overlap** — `run_cell_v2.sh` resets that subject's checkout
  before every cell, so a second cell would wipe the first's working tree mid-review. If a matrix
  is already running on a subject, **queue** rather than launch: wait for the driver's done-marker,
  and give up loudly if it never arrives.
- Cells on **different subjects may run concurrently** as of 2026-08-18 (dcc-xhku): the `/tmp`
  sweep in `cell_tmp.sh` is scoped by a live-cell registry, so a finishing cell defers its
  top-level sweep while siblings are live and the last one out sweeps the group (before that fix,
  the first cell to finish deleted the other's build artifacts — a $17.61 prometheus cell was lost).
  Watch RAM and disk when you do: a cell that dies from resource contention is indistinguishable in
  the artifacts from a tool that found nothing, and `tmp-cleanup.tsv` records `deferred` rather than
  `removed` for a cell that finished with siblings live. `bash v2/test_cell_tmp.sh` exercises the
  two-cell case.
- Resume skips a cell that already **succeeded**, judged by `is_error` in `meter.json`, not by file
  size. Pass `BENCH_FORCE=1` to re-run regardless.
- The runner refuses on a dirty checkout (77), a missing checkpoint (78), a surviving worktree (79)
  and a tight tmpfs (80). Those are all "fix the environment", not "retry".

## After

Report per cell: cost, wall, isolation verdict, the terminal-capture ratio, and artifacts captured.
Flag anything the runner warned about — a capture ratio under 80% means `final-output.md` is a
fragment and only `cell-report.md` is scoreable. Then re-run `/bench-status`.
