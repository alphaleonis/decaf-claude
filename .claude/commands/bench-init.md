---
description: One-time setup for the review-tool benchmark (generate subjects + manifest, check deps/tools)
argument-hint: "[--force]"
---

> **⚠️ This command drives the retired v1 benchmark.** Its dataset is void (contamination, GitHub
> leak, unaudited ground truth, unpinned effort) and is archived under
> `competition/benchmark/v1-archive/` — see that README. **Never cite a v1 number**, and never
> present its output as a tool comparison. `scripts/bench_next.sh` refuses to run without
> `BENCH_V1_ALLOW=1`. Current work is v2: `competition/benchmark/v2/README.md`, milestone `dcc-ho2w`.

Run the benchmark init script and report its output verbatim, including any tools still needing install:

```
bash competition/benchmark/scripts/bench_init.sh $ARGUMENTS
```

Do not review any code or run any cells yourself — this only scaffolds. After it finishes, remind the
user to run a single pilot cell before the full matrix (see `competition/benchmark/README.md`).
