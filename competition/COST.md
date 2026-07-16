# Token-Cost Comparison — Code-Review Tools

Companion to [`README.md`](./README.md). Where the README describes *what* each tool does, this
records *what a review costs* in tokens. Compiled **2026-07-16**.

> **Truth discipline.** Two of the numbers here are **measured** (harness-verbatim): **ours**,
> from the session reports in [`../reports/`](../reports/) generated with the `--report` flag; and
> **Tag1's**, published in its own README. Everything else is `[Estimate]` derived from agent
> count × context × model tier. This is **not** a controlled benchmark — the diffs, languages,
> and accounting bases differ per row (see caveats). A proper apples-to-apples run is planned and
> tracked in nib **`dcc-z1xw`**; this file gets replaced with that dataset when it lands.

## What drives the cost

`total ≈ Σ(agents) × (context each ingests) × (model $/token) × (loop iterations)`

The multipliers that separate these tools:

1. **Fixed fleet vs. conditional dispatch** — always-N agents, or only the ones the diff warrants.
2. **A per-finding validation wave** — a second fan-out (≈1 agent per finding). Ours and Anthropic's
   spend it; Tag1 and pr-review-toolkit dedup instead.
3. **Context per agent** — full diff to everyone vs. manifest + selective reads on large diffs.
4. **Targeted execution** — reviewers running build/test/probes cost tokens pure-static reviewers don't.
5. **Model tiering** — down-tiering volume agents to a mid-tier model.
6. **Looping** — re-review after fixes multiplies everything.

## Ours — measured (from [`../reports/`](../reports/))

| Session | Shape | Metered scope | Tokens (harness-verbatim) |
|---------|-------|---------------|--------------------------:|
| **qj7m** | one `mid9` wave | 7 reviewers + 3 validators | **749,637** (per-reviewer 57k–103k) |
| **p07b** | `mid9` → `mid6` (2 iters) | reviewers + validators | **1,788,974** (iter1 `mid9` 997,765; iter2 `mid6` 791,209) |
| **batch-dev #2** | 6 nibs shipped, `--report` | 135 metered agents | **13,285,815** → **~2.2M / nib** |
| sn96 (pre-tuning) | 3× uncapped `mid`, babysat | all-in | `[Estimate]` 2.5M–4.5M |

**Anchors:** a single `mid9` wave ≈ **0.75–1.0M** tokens (reviewers+validators); a full `auto-dev`
loop ≈ **1.8–2.3M** (p07b: 1.79M reviewers+validators + 0.30M orchestrator + 0.17M build);
**~2.2M per nib** end-to-end in a batch. Per-reviewer cost is **57k–158k** — high because our
reviewers *execute* (targeted tests, race detectors, repro probes, file reads), not just ingest the
diff.

**Build : review ≈ 1 : 10–12** (measured: p07b 1:10.6, qj7m 1:12.4) — the review side dominates cost
by an order of magnitude. Mode is the primary cost dial: a `mid4`/`low` run is a fraction of a `mid9`.

## Tag1 — measured (published in its README)

| Mode | Cost |
|------|-----:|
| `--quick` | **~79K** tokens (~$0.25) |
| full run | **~317K** tokens (~$0.50–1.25) — measured on a **documentation PR**; code-heavy runs higher |

No per-finding validator wave (dedup + confidence filter instead); per-agent 25-tool-call budget;
manifest + selective reads on large diffs. These choices keep its full-run number well below ours.

## Others — `[Estimate]` (no published or captured metering)

| Tool | Per-review `[Estimate]` | Reasoning |
|------|------------------------:|-----------|
| Single-agent skills (awesome-skills, OWASP, alirezarezvani) | ~20–50K | one agent, one diff, no fan-out, no execution |
| superpowers `requesting-code-review` | ~20–50K | one `general-purpose` reviewer subagent, crafted context |
| pr-review-toolkit (all 6) | ~120–200K | 6 agents, no validators, no orchestrated execution |
| Anthropic `/code-review` | ~150–300K | 2 haiku + 1 sonnet + 4 reviewers + N validators; bug agents are **diff-only** (no targeted execution) |
| CodeRabbit | ~0 to *your* Claude budget | review runs on CodeRabbit's servers; cost is a separate subscription |
| Trail of Bits `differential-review` | ~80–200K | one deep multi-phase agent; scales with blast-radius (caller reads) |

## Reading it side by side

| Tier | Tool | Per-review | Basis |
|------|------|-----------:|-------|
| Cheapest | single-agent skills / superpowers | ~20–50K | `[Estimate]` |
| Low | pr-review-toolkit (6) | ~120–200K | `[Estimate]` |
| Low–mid | Anthropic `/code-review` | ~150–300K | `[Estimate]` |
| Mid | **Tag1 `--quick` / full** | **~79K / ~317K** | **measured** |
| **High** | **ours — one `mid9` wave** | **~750K–1.0M** | **measured** |
| **Highest** | **ours — full `auto-dev` loop** | **~1.8–2.3M** | **measured** |

**Headline:** our per-wave cost is roughly **2–3× Tag1's full-run measure** and **~3–5× the leaner
Anthropic / pr-review-toolkit estimates**. Three structural reasons, all confirmed in our corpus:
(1) reviewers do real execution (Tag1 caps tool calls + reads a manifest; Anthropic's bug agents are
diff-only); (2) a validation wave adds agents Tag1/pr-review-toolkit don't spend; (3) `mid9` is 9
reviewers, the top of the default `mid` band — `mid4`/`low` cost a fraction.

## What the extra cost buys (the quality half — from our corpus)

Per-agent *yield* data none of the competitors publish — a mixed verdict, stated honestly:

- **The validation wave earns its slot:** refuted a wrong finding in **2 of 4** sessions (e.g. p07b's
  focus-theft High — a prevented over-fix). No autonomous fix ever rode an unvalidated finding.
- **`test-reviewer`** is the standout unique finder in every session that has tests.
- **But cost-with-no-yield exists in our own roster:** `quick-reviewer` is **0 unique across ~20 waves
  / 3 sessions** — a live candidate for cutting.
- **Tuning already cut cost materially:** pre-tuning sn96 (~2.5–4.5M all-in, babysat) → post-tuning
  loops ~1.3–2.4M with zero manual interventions; orchestrator tokens fell ~49% in 5a8k.

## Caveats — why this is not yet a fair benchmark

- **Different diffs.** Tag1's 317K is one documentation PR; our 0.75–1.0M figures are `mid9` Svelte/TS
  UI waves. Not the same input.
- **Different accounting bases.** Ours = reviewers+validators (sometimes excluding the orchestrator);
  Tag1 = "agent tokens"; the estimates are whole-session. Not the same denominator.
- **Different model policies.** Each tool pins or tiers models differently; none were normalized.
- **Language bias.** Our measured sessions are all Svelte/TypeScript web-UI.

The controlled run planned in **`dcc-z1xw`** (same 3 PRs through 5 tools, one external meter, blind
quality grading) is what turns this table from "measured-but-not-comparable" into "comparable."

## Sources

- Ours — [`../reports/`](../reports/) (`--report` session metrics; `2026-07-04-cross-session-analysis.md`)
- Tag1 — [`tag1-comprehensive-review/README.md`](./tag1-comprehensive-review/README.md) ("Cost expectations", "Token efficiency")
- Estimates — derived from each tool's dispatch structure (see [`README.md`](./README.md))
