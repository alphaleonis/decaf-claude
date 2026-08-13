# Review-tool benchmark harness

> ## ⚠️ v1 RESULTS ARE VOID — READ THIS FIRST (2026-08-10)
>
> Everything below describes **v1**, whose dataset is invalid on four independent counts:
>
> 1. **Cross-cell contamination** — `.decaf/` reports leaked between cells via a shared checkout and
>    were read by the decaf recurring-findings cross-check, inflating decaf-family recall. Fixed in
>    `run_cell.sh`; 27 cells invalidated (`dcc-2cxq`).
> 2. **GitHub leak** — 11 of 12 subjects have the fixing PR cross-linked on the original's timeline.
>    `anthropic-code-review`'s finders cited the revert PR in *both* subject-9 repeats.
> 3. **Unreliable ground truth** — 2 of the first 3 subjects audited had invalid ground truth
>    (`dcc-5xad`).
> 4. **Unpinned effort** — reasoning effort was ambient and unrecorded until 2026-08-10.
>
> The two leaks push in **opposite** directions (contamination flattered `ours`, the GitHub leak
> flattered `anthropic`), so the direction of any headline gap is *unknown*, not merely imprecise.
> **Do not cite a v1 number.**
>
> The v1 data — 88 cells, 9 graded subjects, the metrics CSV, the run ledger, and both earlier
> quarantines — is archived under [`v1-archive/`](./v1-archive) with a README stating what it may
> still be cited for (leak mechanism, cost telemetry) and what it may not (any tool comparison).
> `scripts/bench_next.sh` refuses to run without `BENCH_V1_ALLOW=1`.
>
> Current work is **benchmark v2**: [`METHODOLOGY-v2.md`](./METHODOLOGY-v2.md) and
> [`v2/README.md`](./v2/README.md), tracked by milestone **`dcc-ho2w`**.
> The `ours` tool no longer exists — it was retired in favour of the `ours-bugs` / `ours-review` /
> `ours-audit` presets. Nib `dcc-z1xw` referenced below is scrapped.


Controlled cost + quality comparison of five Claude Code review tools across the same 12
subjects (4 languages × 3 sizes). Design and subject grid live in nib **`dcc-z1xw`**.

Each cell is run in its **own isolated `claude -p` session** so token/cost metering is clean and
uncontaminated. **State lives on disk** (`manifest.jsonl`), so you run a few cells now and resume
in a fresh session later. Nothing runs automatically — you drive it a cell at a time.

## Subjects

The 12 review subjects — one per (language × size) cell. Each is a **real merged PR that was later
reverted or fixed for a named regression**, so every cell carries an objective escaped-bug ground
truth (bug summary + human-review threads in [`subjects/*.json`](./subjects)). The `#N` is the
**subject id** — use it as `/bench-run --subject <N>`.

| Language ↓ / Size → | Small (<~100 lines) | Medium (~100–500) | Large (>~500) |
|---|---|---|---|
| **C#** | #1 [efcore#32770](https://github.com/dotnet/efcore/pull/32770)<br>+63/−9, 2f | #2 [aspnetcore#67075](https://github.com/dotnet/aspnetcore/pull/67075)<br>+168/−1, 2f | #3 [runtime#127146](https://github.com/dotnet/runtime/pull/127146)<br>+417/−7, 13f |
| **TypeScript** | #4 [TypeScript#61928](https://github.com/microsoft/TypeScript/pull/61928)<br>+21/−16, 7f | #5 [vscode#308517](https://github.com/microsoft/vscode/pull/308517)<br>+270/−6, 5f | #6 [vscode#320685](https://github.com/microsoft/vscode/pull/320685)<br>+688/−13, 10f |
| **Go** | #7 [prometheus#13777](https://github.com/prometheus/prometheus/pull/13777)<br>+32/−21, 1f | #8 [kubernetes#129768](https://github.com/kubernetes/kubernetes/pull/129768)<br>+326/−91, 5f | #9 [kubernetes#130837](https://github.com/kubernetes/kubernetes/pull/130837)<br>+757/−803, 18f |
| **Rust** | #10 [ripgrep#3185](https://github.com/BurntSushi/ripgrep/pull/3185)<br>+22/−11, 4f | #11 [tokio#7757](https://github.com/tokio-rs/tokio/pull/7757)<br>+340/−126, 6f | #12 [rust#153540](https://github.com/rust-lang/rust/pull/153540)<br>+383/−328, 18f |

Size buckets are by changed lines (generated files/lockfiles excluded). Diff stats are the PR's raw
totals — some large-by-line PRs are test/fixture-heavy (e.g. Rust-large is ~270 `.stderr` lines of
its 711). Full ground truth (the reverting/fixing PR, regression issue, human threads) is in each
`subjects/NN-*.json`.

## Tools

The 5 tools under test — the **`id`** is what you pass as `/bench-run --tool <id>` (full invocation
templates + model policy in [`tools.json`](./tools.json)):

- **`ours`** — `decaf-quality:code-review` (mid mode, `--report`)
- **`anthropic-code-review`** — Anthropic `/code-review`
- **`pr-review-toolkit`** — Anthropic PR Review Toolkit (comprehensive run of all 6 agents)
- **`tag1-comprehensive-review`** — Tag1 `/comprehensive-review` (full, `--local`)
- **`superpowers`** — obra/superpowers `requesting-code-review`

## Quick start

**The v1 commands no longer exist.** `/bench-init`, `/bench-status`, `/bench-run`, `/bench-analyze`
and `/bench-synthesize` were rewritten to drive v2 (`dcc-j21q`) and now refer to the current corpus,
not this one. The v1 scripts remain under `scripts/`, and **every entry point among them refuses
unless `BENCH_V1_ALLOW=1`** — a banner on a command was not a control, and eleven of the twelve
scripts had no guard at all.

To regenerate v1 evidence (reproducing a leak, rebuilding an archived artifact) call the script
directly and opt in:

```
BENCH_V1_ALLOW=1 bash competition/benchmark/scripts/bench_status.sh
BENCH_V1_ALLOW=1 bash competition/benchmark/scripts/bench_next.sh 1__ours__r1
```

Run IDs below are historical, describing what the archive contains.

Run IDs are `<subject_id>__<tool>__r<repeat>` (e.g. `11__tag1-comprehensive-review__r2`).

> **Metering (validated on the pilot).** `claude -p --output-format json`'s `.usage` covers the
> **orchestrator session only** — it misses every subagent's tokens (for a 5-agent tool that's ~60%
> of the real spend). So the harness ALSO sums the subagent transcripts
> (`~/.claude/projects/<proj>/<session_id>/subagents/agent-*.jsonl`), deduped by message id, into
> `session_tokens` (the `ws_*` columns). Things to keep in mind:
> - **`cost_usd` is the authoritative whole-session figure** (Claude Code sums subagents; it is billed
>   cost, not an estimate) — the primary cross-tool comparable.
> - **`ws total_tokens` is prompt-cache-inflated** (cache_read is re-counted every turn), so it is not a
>   clean "work" measure. **`ws output_tokens`** is the clean, cache-independent token signal.
> - **Dedup takes the LAST usage record per message id, not the first.** A transcript writes one line
>   per *content block*, and on streamed responses each line carries the usage as it stood when that
>   block was emitted — one message reads e.g. `[5, 5, 278]` and only the final entry is cumulative.
>   Taking the first under-counted **sub-agent** output by ~10× (orchestrator figures were unaffected,
>   their lines already carrying the final value). Fixed and all runs backfilled 2026-07-28; see
>   #dcc-m8ar. Check any run with `scripts/verify_subagent_tokens.py` — it compares each
>   `per_subagent[].output` against the agent's own archived transcript and exits non-zero if a
>   recorded figure is below the text that agent demonstrably emitted.
> - **`per_subagent[].output` is unrecoverable for 2 of 742 rows** (`5__tag1…__r1`, `7__tag1…__r2`):
>   those transcripts hold a single message id whose usage lines are all partial, so no final count
>   was ever written. That is an upstream capture gap; both are allowlisted in the verifier with
>   their reason. Six further rows sit 1–2× under the verifier's `bytes/4` estimate, which is inside
>   that heuristic's error band rather than evidence of a defect.

## What each run captures (`runs/<run_id>/`)

| file | contents |
|------|----------|
| `prompt.txt` | exact prompt handed to `claude -p` |
| `meter.json` | full `claude -p --output-format json` result (cost, usage, num_turns, duration_ms, session_id, …) |
| `stderr.log` | the CLI's stderr |
| `raw_output.md` | the tool's final result text (findings) |
| `findings/` | any report file the tool wrote in the subject repo (ours: `.decaf/code-reviews/*`; Tag1: `.decaf/tag1-review-*`) |
| `meta.json` | normalized metrics + provenance for this run |
| `run.md` | human-readable normalized report (same shape for every tool) |

Aggregate: `results/metrics.csv` — one row per finished run (token usage, wall-clock, cost, findings
size, status). This is the comparable dataset for the write-up.

## Metrics captured

- **Cost:** `cost_usd` (whole session, incl. subagents), `input/output/cache_creation/cache_read`
  tokens, summed `total_tokens`, `num_turns`.
- **Time:** harness `wall_clock_s` (independent), plus the CLI's self-reported `duration_ms` /
  `duration_api_ms`.
- **Findings:** the full raw output and any tool-written report file, for later quality grading.
- **Provenance:** subject repo/PR/merge SHA, review diff range, session model, tool, exit status.

## Fairness controls & known confounds

- **Same subject, same diff.** Every tool reviews the same PR. PR-oriented tools (ours PR mode,
  Anthropic, Tag1) target the PR number; local-diff tools (superpowers) diff `merge^1..merge`. Same
  content either way. Review target is pinned to the merge commit SHA (see `subjects/*.json`), so it
  is reproducible even as the repos move on.
- **Session model held constant** (`BENCH_MODEL` in `config.env`). **Confound (documented, not
  removed):** some tools hard-pin their own models regardless — Anthropic `/code-review` pins
  haiku/sonnet by role (5 Sonnet reviewers, Haiku for triage and confidence scoring; no Opus
  subagents); Tag1 pins Opus for 2 agents; ours tiers off the session model. Each
  tool's policy is in `tools.json` `model_policy`. We measure each tool "as it ships."
- **Local / no-post only** — every invocation is instructed to post nothing to the real PRs.
- **N=2 repeats** per cell to expose stochasticity; report mean + range, don't trust a single run.

## Ground truth & quality grading (later phase)

`subjects/*.json` carries the `ground_truth` per subject: the escaped bug (from the revert/fix PR) and
the human review threads. Grading is a **separate, blind** pass over the collected `raw_output.md`
files (grader not told which tool produced which) → TP / FP / other-valid / FN against ground truth.
Not done by this harness; it only collects.

## Files

```
config.env               # BENCH_MODEL, CLAUDE_BIN, PERM_FLAGS, REPEATS
tools.json               # 5 tools: invocation template + model policy + findings-file glob
subjects.annotations.json# curated ground truth per subject (input to gen_subjects)
.pr-meta.jsonl           # fetched PR metadata (SHAs, diffstat) — provenance
subjects/NN-lang-size.json  # 12 generated subject fixtures (pinned SHAs + ground truth)
manifest.jsonl           # 120 cells + status (the resumable state)
scripts/                 # lib.sh, gen_subjects, gen_manifest, bench_init, run_cell, bench_next, bench_status
repos/<subject_id>/      # shallow checkouts fetched on demand by run_cell
runs/<run_id>/           # per-run artifacts (above)
results/metrics.csv      # aggregate
```

## Prerequisites

- `jq`, `gh` (authenticated), `git`, and the `claude` CLI on PATH.
- Each tool's plugin installed (see `tools.json` `install_hint`; `/bench-init` reports which are
  missing). `pr-review-toolkit` is a dependency of Tag1.
- `PERM_FLAGS` defaults to `--dangerously-skip-permissions` for unattended headless runs (reviews are
  read-only / no-post). Review this before running.
