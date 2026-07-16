---
# dcc-z1xw
version: 1
title: 'Benchmark: controlled cost/quality comparison of code-review tools'
status: in-progress
type: feature
created_at: 2026-07-16T11:47:14Z
updated_at: 2026-07-16T12:58:59Z
order: zzk
---

# Goal

Produce an apples-to-apples cost **and** quality comparison of a selected set of Claude Code
code-review tools by running each on the **same** set of PRs, under controlled conditions.
Replaces the current mix of measured (ours, Tag1) and estimated (others) figures in
`competition/COST.md` with one comparable dataset.

# Tools under test (5)

Pinned to the sources vendored in `competition/` (see each `PROVENANCE.md` for SHA):
1. `anthropic-code-review` — `/code-review` (single fixed config)
2. `anthropic-pr-review-toolkit` — comprehensive run (all 6 agents)
3. `tag1-comprehensive-review` — `/comprehensive-review` (full run; needs pr-review-toolkit dep)
4. `obra-superpowers-code-review` — `requesting-code-review` (one reviewer subagent)
5. ours — `decaf-quality:code-review mid --report`

# Design — two orthogonal axes (full 4×3 factorial)

- **Language (4):** C#, TypeScript, Go, Rust.
- **Size (3):** small/simple (<~100 changed lines, 1–3 files), medium (~100–500 lines),
  large (>~500 lines or many files). Generated files/lockfiles excluded from the count.

**Full cross = 4 × 3 = 12 cases** (every language × every size).

## Subjects grid (12 cases — full 4×3 factorial)

Selected from live-`gh`-verified candidates (2026-07-16). Bug evidence = the reverting/fixing PR that
establishes the escaped defect (ground-truth false-negative). "Human threads" = genuine human inline
review comments (bot/Copilot threads noted separately; in current-era TS/vscode, human inline review is
largely displaced by Copilot).

| # | Lang | Size | Repo / PR | Escaped-bug evidence (revert/fix) | Human threads | Notes |
|---|------|------|-----------|-----------------------------------|:-------------:|-------|
| 1 | C# | small | [dotnet/efcore#32770](https://github.com/dotnet/efcore/pull/32770) (+63/-9, 2f) | revert #32945 "reverts … due to test failures"; issue #32944 assertion failure | 4 | real SQLite data-reader logic bug |
| 2 | C# | medium | [dotnet/aspnetcore#67075](https://github.com/dotnet/aspnetcore/pull/67075) (+168/-1, 2f) | revert #67712 spells out why the `FlattenHierarchy` fix was wrong | 9 | prod change ~11 lines (rest tests); rich review |
| 3 | C# | large | [dotnet/runtime#127146](https://github.com/dotnet/runtime/pull/127146) (+417/-7, 13f) | revert #127301 "Reverts #127146"; issue #127259 test failure | 3 (+5 Copilot) | ⚠ borderline size; specialized JIT domain |
| 4 | TS | small | [microsoft/TypeScript#61928](https://github.com/microsoft/TypeScript/pull/61928) (+21/-16, 4 src) | revert #62423 "Reverts #61928 / Fixes #62188"; downstream eslint crashes | 1 (DanielRosenwasser) | bug visible mainly downstream |
| 5 | TS | medium | [microsoft/vscode#308517](https://github.com/microsoft/vscode/pull/308517) (+270/-6, 5f) | revert #308779 + user-regression issue #308627 (idle timer kills live streams) | 0 (bot only) | ⚠ no human threads; escaped-bug evidence excellent |
| 6 | TS | large | [microsoft/vscode#320685](https://github.com/microsoft/vscode/pull/320685) (+688/-13, 10f) | reverted twice (#321516, #323490) for aggregate regressions | 1 (mjbvz) (+4 bot) | ~590 prod lines; strong large subject |
| 7 | Go | small | [prometheus/prometheus#13777](https://github.com/prometheus/prometheus/pull/13777) (+32/-21, 1f) | revert #14515 (use-after-close of mmap-backed iterators); issue #14422 | 0 | swapped from #15141 for crisper bug ground truth |
| 8 | Go | medium | [kubernetes/kubernetes#129768](https://github.com/kubernetes/kubernetes/pull/129768) (+326/-91, 5f) | revert #133979 (e2e "not found" flakes); issue #133976 | 2 | clean, tightly-scoped regression |
| 9 | Go | large | [kubernetes/kubernetes#130837](https://github.com/kubernetes/kubernetes/pull/130837) (+757/-803, 18f) | revert #132958 `/kind bug` + take-2 #133059 confirming the bug | 30 | best all-round large subject |
| 10 | Rust | small | [BurntSushi/ripgrep#3185](https://github.com/BurntSushi/ripgrep/pull/3185) (+22/-11, 3 src) | revert #3195 "Fixes #3194" (line-buffered regression; reverts the exact introducing commit) | 0 (solo maintainer) | ⚠ no human threads; clean correctness regression |
| 11 | Rust | medium | [tokio-rs/tokio#7757](https://github.com/tokio-rs/tokio/pull/7757) (+340/-126, 6f) | revert #8057 (`spawn_blocking` hang); issue #8056 | 30 | reviewer flagged the exact memory-ordering bug — ideal |
| 12 | Rust | large | [rust-lang/rust#153540](https://github.com/rust-lang/rust/pull/153540) (+383/-328, 18f) | revert #157150 (Fixes #157107 rustdoc-json regression) | 27 | ⚠ partial (single-commit) revert; ~270 lines are .stderr |

**Alternates (if a cell is rejected):** C# small → aspnetcore#59876 (strongest ground truth: ~17 months
in the wild, 2 named regression issues, but 2 prod lines / 2 threads); Go medium → prometheus#12363
(13 threads, but revert states no reason); Rust large → rust#157702 (clean ICE ground truth, fixture-heavy
/ 5 threads) or tokio#7431 (medium-large boundary); Rust small → tokio-rs/tokio#7843 (5 human threads, but its revert is a dependency-policy objection, not a logic bug).

**Per-cell evidence quality is uneven** (human-thread counts, perf-vs-logic bugs, partial reverts) — see
Notes column. Awaiting operator sign-off before any runs.

# Decisions locked (2026-07-16)

- **Subjects:** 12 real, public OSS PRs (full 4×3 grid above). Each has a **known escaped bug fixed in a
  later PR/revert** and, where available, human review threads on the original PR.
- **Ground truth (per subject):** the escaped bug the follow-up fix/revert addressed (a real
  false-negative test) **+** the human review comments on the original PR. Objective, external.
- **Repeats:** **N=2** per (tool × subject) cell → **5 × 12 × 2 = 120 runs**.
- **Ours mode:** **`mid` only** (`--report`).
- **Results location:** `competition/benchmark/`.

# Run matrix

120 runs = 5 tools × 12 subjects × 2 repeats. Rough token budget `[Estimate]`:
ours ~0.6M×24 ≈ 14.4M · Tag1 ~0.4M×24 ≈ 9.6M · Anthropic /code-review ~0.2M×24 ≈ 4.8M ·
pr-review-toolkit ~0.15M×24 ≈ 3.6M · superpowers ~0.04M×24 ≈ 1M → **~33M review-side + grading**.

# Methodology

- One **fresh Claude Code session per run** (no cross-contamination). Save each tool's raw output.
- **Hold the session model constant** across all runs; record it. NOTE confound: some tools hard-pin
  their own models (Anthropic /code-review pins haiku/sonnet/opus by role; Tag1 pins opus for 2 agents;
  ours tiers off the session model) — we measure each tool "as it ships / as recommended" and document
  each tool's internal model policy rather than forcing identical tiers.
- Each tool at its **default/recommended** setting; ours at `mid`.
- **Local/no-post only** — never post comments to the real PRs.

# Metrics

Cost: total tokens (in/out/cache) per run via a uniform external meter (transcript JSONL usage sum),
cross-checked against each tool's self-report where present; agent count; wall-clock; derived USD.

Quality (vs ground truth): recall on known issues, precision (TP/(TP+FP)), false-positive noise,
severity calibration, verdict correctness, dedup quality, actionability.

Operability: manual interventions, setup friction, output-format usefulness.

# Measurement harness

Per run: fresh session; record command, session model, timestamps, subject id, repeat #. Token meter:
sum `usage` from the session transcript JSONL (tool-agnostic common unit); verify it captures subagent
tokens on a pilot run. Persist raw output + self-report + meter totals → one row per (tool×subject×repeat).

# Scoring

Build the ground-truth issue list per subject up front. Grade each tool's findings **blind** (grader
not told which tool produced them): TP / FP / other-valid / FN via an LLM judge against a fixed rubric,
human spot-check. Avoids home-field bias.

# Threats to validity + mitigations

- Stochasticity → N=2 + report range.
- Home-field bias → external ground truth (real PRs) + blind grading.
- Language bias → C#/TS/Go/Rust spread (Rust + Go are our weaker stack lanes — deliberate).
- Size confound → dedicated small/medium/large axis (full factorial isolates it from language).
- Uneven ground-truth quality → per-cell evidence flags recorded; some bugs are perf/resource or
  downstream-only, some reverts partial — weight scoring accordingly, don't treat all cells identically.
- Model/tiering confound → fix session model; document each tool's internal policy.
- Version drift → tools pinned to competition/ SHAs.
- Unit mismatch → one external meter; self-reports as cross-check only.
- Side effects → local/no-post only.

# Deliverables

- `competition/benchmark/`: harness notes, raw per-run outputs, per-run metrics table.
- Results write-up: matrix (tool × subject → cost, agents, wall-clock, recall, precision, verdict) + narrative.
- Update `competition/COST.md` and `competition/README.md` with the measured cross-tool numbers.

# Next action

Harness built. Next: (1) operator signs off the 12 subjects (Go-small swap open) and picks a PERM_FLAGS posture in competition/benchmark/config.env; (2) run a pilot cell to validate metering; (3) work the 120-cell matrix incrementally via /bench-run.

# Done checklist

- [x] Key decisions resolved (subjects strategy, languages incl. Rust, size axis, repeats, our mode, results location)
- [x] Candidate PRs sourced + verified for all 12 cells
- [x] Ground-truth issue lists written per cell (subjects/*.json); operator sign-off on the 12 still pending (Go-small #15141 vs #13777 open)
- [ ] Tools installed/pinned; dependencies resolved (pr-review-toolkit for Tag1)
- [x] Measurement harness built (competition/benchmark/: scripts + 120-cell manifest + /bench-init /bench-run /bench-status; metrics parsing validated on a synthetic payload)
- [ ] Pilot: run one cell, verify subagent-token capture + headless completion + chosen permission posture
- [ ] Run matrix executed (120 cells)
- [ ] Findings graded blind against ground truth
- [ ] Results doc written; COST.md / README.md updated


## Update log

- 2026-07-16: Harness built under `competition/benchmark/` (12 fixtures, 120-cell manifest, `/bench-init` `/bench-run` `/bench-status`). `/bench-init` run: deps OK; `ours` + `pr-review-toolkit` already installed; `code-review`, `superpowers`, `comprehensive-review` pending.
- 2026-07-16: PERM_FLAGS = `--dangerously-skip-permissions` (operator-approved; read-only/no-post reviews of public PRs in throwaway checkouts).
- 2026-07-16: Session model = `claude-opus-4-8`; each tool's internal model policy honored (harness sets only the session model; subagent pins/tiering unchanged). Pilot must confirm `--model` does not override subagent model choices.
- 2026-07-16: Go-small SWAPPED prometheus#15141 → prometheus#13777 (crisper use-after-close bug; 0 human threads). Former #15141 (5 threads, perf bug) is the fallback.
