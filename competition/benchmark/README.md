# Review-tool benchmark harness

Controlled cost + quality comparison of five Claude Code review tools across the same 12
subjects (4 languages × 3 sizes). Design and subject grid live in nib **`dcc-z1xw`**.

Each cell is run in its **own isolated `claude -p` session** so token/cost metering is clean and
uncontaminated. **State lives on disk** (`manifest.jsonl`), so you run a few cells now and resume
in a fresh session later. Nothing runs automatically — you drive it a cell at a time.

## Quick start

```
/bench-init                 # generate subjects + manifest, check deps + tool installs (once)
/bench-status               # what's done / pending / failed
/bench-run                  # run the next pending cell
/bench-run --count 2        # run two
/bench-run 1__ours__r1      # run a specific cell
/bench-run --tool ours      # next pending cell for one tool
/bench-run --subject 11     # next pending cell for one subject
```

Run IDs are `<subject_id>__<tool>__r<repeat>` (e.g. `11__tag1-comprehensive-review__r2`).

> **Metering (validated on the pilot).** `claude -p --output-format json`'s `.usage` covers the
> **orchestrator session only** — it misses every subagent's tokens (for a 5-agent tool that's ~60%
> of the real spend). So the harness ALSO sums the subagent transcripts
> (`~/.claude/projects/<proj>/<session_id>/subagents/agent-*.jsonl`), deduped by message id, into
> `session_tokens` (the `ws_*` columns). Two things to keep in mind:
> - **`cost_usd` is the authoritative whole-session figure** (Claude Code sums subagents; it is billed
>   cost, not an estimate) — the primary cross-tool comparable.
> - **`ws total_tokens` is prompt-cache-inflated** (cache_read is re-counted every turn), so it is not a
>   clean "work" measure. **`ws output_tokens`** is the clean, cache-independent token signal.

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
  haiku/sonnet/opus by role; Tag1 pins Opus for 2 agents; ours tiers off the session model. Each
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
