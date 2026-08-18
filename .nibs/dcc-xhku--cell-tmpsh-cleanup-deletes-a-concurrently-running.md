---
# dcc-xhku
version: 1
title: cell_tmp.sh cleanup deletes a concurrently-running cell's /tmp files
status: todo
type: bug
priority: high
created_at: 2026-08-18T09:18:01Z
updated_at: 2026-08-18T09:18:18Z
parent: dcc-ho2w
order: zo
---

`cell_tmp.sh cleanup` step 4 removes every top-of-`/tmp` entry that is absent from the cell's
own pre-run snapshot, is owned by the user, and does not match `PROTECT`. The scope is "created
during **the** cell" — but nothing ties an entry to *which* cell created it. With two cells
overlapping, the first to finish deletes the other's live temporary files.

Observed 2026-08-18 on the first concurrent pair ever run (dcc-u10u batch 1):
`dotnet-efcore-34127__ours-review__r3` finished at 1154s and its `tmp-cleanup.tsv` records 26
removals. efcore is a .NET subject; the list includes `/tmp/baserepo` (213 MB),
`/tmp/memprobe.test` (28 MB), `/tmp/nullprobe` (50 MB), `probe_alloc_test.go`,
`probe_read_base.go`, `probe_read_head.go`, `probe_stats_test.go`, `tqs.go`,
`review_full.diff`, `engine_test.diff` — Go artifacts belonging to the
`prometheus-prometheus-18081__ours-review__r3` cell that was still running.

Cost: that prometheus cell was terminated as unscoreable after $17.61 had been spent.

Note the sweep's original justification is gone on this machine: it exists because `/tmp` was
tmpfs (7.8G of RAM) on the previous machine. Here `/tmp` is ext4 on the root disk with ~947 GB
free, and `TMPDIR` is already redirected per cell to `/var/tmp/bench-v2/<cell>`. Steps 1-3 are
correctly scoped (own TMPDIR, own `claude-*` scratchpad by repo slug, own worktrees); only step
4 is unscoped. `verify_cell_isolation.sh` is unaffected — it matches by session id.

## Options

- Guard step 4 behind an env flag (`BENCH_TMP_SWEEP=0`) so concurrent runs can disable it.
- Scope step 4 by ownership: record the cell's own PID/process-group and only remove entries it
  created, rather than differencing a global snapshot.
- Drop step 4 where `/tmp` is not tmpfs — check `stat -f -c %T /tmp` and skip when it is not
  `tmpfs`.

Until fixed, **cells must be run one at a time**.

## Acceptance

- [ ] Step 4 cannot remove a path belonging to another live cell
- [ ] A test exercises the two-cell case
- [ ] `v2/README.md` states whether concurrent cells are supported
