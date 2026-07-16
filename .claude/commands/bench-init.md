---
description: One-time setup for the review-tool benchmark (generate subjects + manifest, check deps/tools)
argument-hint: "[--force]"
---

Run the benchmark init script and report its output verbatim, including any tools still needing install:

```
bash competition/benchmark/scripts/bench_init.sh $ARGUMENTS
```

Do not review any code or run any cells yourself — this only scaffolds. After it finishes, remind the
user to run a single pilot cell before the full matrix (see `competition/benchmark/README.md`).
