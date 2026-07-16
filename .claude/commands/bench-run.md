---
description: Run the next pending benchmark cell(s) and record metrics (operator-driven)
argument-hint: "[--count N] [--tool <id>] [--subject <id>] [<run_id>]"
---

Invokes the benchmark driver, which runs each selected cell as a separate `claude -p` session using
the permission posture the operator configured in `competition/benchmark/config.env` (`PERM_FLAGS`,
empty by default). Metrics land in `competition/benchmark/results/metrics.csv` and `runs/<run_id>/`.

```
bash competition/benchmark/scripts/bench_next.sh $ARGUMENTS
```

Notes:
- Do NOT review any PR yourself — the isolated sessions do the reviewing; only invoke the driver and
  relay what it printed (per-cell status, wall-clock, cost, findings size).
- If `PERM_FLAGS` is empty and a cell stalls waiting on a permission prompt, tell the operator they
  need to set a posture in `config.env` (see its comments) — do not add `--dangerously-skip-permissions`
  or otherwise weaken permissions on their behalf.
- On a `failed` cell, surface the tail of `runs/<run_id>/stderr.log`.
