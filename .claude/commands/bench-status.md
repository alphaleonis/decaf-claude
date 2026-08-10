---
description: Show review-tool benchmark progress (done / pending / failed per tool and subject)
---

> **⚠️ This command drives the retired v1 benchmark.** Its dataset is void (contamination, GitHub
> leak, unaudited ground truth, unpinned effort) and is archived under
> `competition/benchmark/v1-archive/` — see that README. **Never cite a v1 number**, and never
> present its output as a tool comparison. `scripts/bench_next.sh` refuses to run without
> `BENCH_V1_ALLOW=1`. Current work is v2: `competition/benchmark/v2/README.md`, milestone `dcc-ho2w`.

Run and report the benchmark status summary:

```
bash competition/benchmark/scripts/bench_status.sh
```

Read-only — just relay the output.
