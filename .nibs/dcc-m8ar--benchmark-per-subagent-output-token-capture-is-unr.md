---
# dcc-m8ar
version: 1
title: 'Benchmark: per-subagent output-token capture is unreliable (agents report fewer tokens than text they emitted)'
status: completed
type: bug
priority: normal
estimate: m
tags:
    - benchmark
    - metrics
created_at: 2026-07-28T19:52:04Z
updated_at: 2026-07-28T20:04:55Z
order: zzz
---

# Symptom

`meta.json` → `session_tokens.per_subagent[].output` was wrong for roughly two-thirds of
sub-agents: several reported **fewer output tokens than the visible text they demonstrably
produced**, which is physically impossible. On `runs/1__ours__r1`,
`agent-aaf30ea46d101470e` recorded **6** output tokens against a 4,463-byte archived
transcript; `agent-a6de901b06125c508` recorded **25** against 10,978 bytes.

Aggregate hid it: 22,723 estimated from transcripts vs 17,875 recorded (1.3×), so cross-tool
means looked plausible while individual rows were unusable.

# Root cause — confirmed

`scripts/session_tokens.sh` deduped by message id and took the **first** usage record per id:

```jq
| group_by(.id) | map(.[0].u) ) as $u
```

A transcript writes one line per **content block**, and on streamed responses each line
carries the usage *as it stood when that block was emitted*. A single message therefore reads
`[5, 5, 278]` — only the last entry is the cumulative total. Taking `.[0]` captured a partial
count from the middle of the stream.

Verified across every transcript in the run: **LAST == MAX for every message id**, in both
affected and unaffected files, so the final record is always the cumulative one.

Two hypotheses were tested and rejected:

- **Dedup itself was wrong** — no. Dedup is correct and necessary (37 assistant lines over 17
  real `msg_…` ids for one agent; naive summing triple-counts).
- **Usage records were missing** — no. Every assistant line carried a `usage` block with
  `output_tokens > 0`; the values were simply partial.

**The orchestrator was never affected.** Its lines already carry the final value (`[169, 169,
169]`), so first == last and its figures reconcile exactly to `meta.json` under either rule.
Every orchestrator-based conclusion in #dcc-e0wj stands unchanged.

# Fix

- `scripts/session_tokens.sh`: `map(.[0].u)` → `map(.[-1].u)`, with the reasoning in a comment
  so it is not "simplified" back.
- `scripts/backfill_tokens.sh` re-run over all **90 done runs** (every raw transcript was still
  on disk, so the data was fully repairable) and `metrics.csv` rebuilt.
- New `scripts/verify_subagent_tokens.py` compares each recorded figure against the agent's own
  archived transcript and exits non-zero when a recorded value falls below the text that agent
  emitted. Confirmed to fail on the pre-fix data (exit 1, 13/16 rows) and pass after (exit 0),
  so it is a real check rather than a tautology.

# Effect of the correction

| | before | after |
|---|---|---|
| `1__ours__r1` sub-agent output | 17,875 | **187,227** (10.5×) |
| `1__ours__r1` session output | 107,045 | **276,397** |
| orchestrator share of that run | 83% | **32%** |
| orchestrator share, all tools | — | **17–24%**, uniform |
| ours session output / run | — | 367,084 vs anthropic's 186,380 |
| `r(session output, cost)` | — | **0.967** (orchestrator alone: 0.874) |

This overturned the reading that the orchestrator dominates cost. It does not — fan-out does,
and ours pays it on two dimensions at once (41% more agents, each emitting 43% more than
anthropic's). #dcc-e0wj workstream 2 has been rewritten accordingly, and its earlier
"94k output tokens vs 50k" line withdrawn.

**No published conclusion changed.** `cost_usd` is billed whole-session truth from the harness
and was never derived from this field.

# Residual — not recoverable

2 of 742 rows (`5__tag1…__r1` `agent-a1658cd2c7bb11202`, `7__tag1…__r2`
`agent-adf245456e17409d3`) hold a **single** message id whose usage lines are all partial
(`[5, 5]`), so no final count was ever written. That is an upstream capture gap; nothing on our
side can recover the true figure. Both are allowlisted in the verifier with their reason, so a
regression of the aggregation bug still fails loudly.

A further 6 rows sit 1–2× under the verifier's `bytes/4` estimate. That is inside the
heuristic's error band — markdown with tables and indentation drifts well past 4 bytes/token —
so the verifier reports them as `marginal` without failing. Its failure threshold is 3×; the
real defect ran 10×–250×.

# Acceptance

- [x] [run] `python3 scripts/verify_subagent_tokens.py runs/1__ours__r1` — expect: exit 0,
      reports each sub-agent's recorded output against its transcript and flags rows where
      recorded < visible text (a physical impossibility)
- [x] [manual] Root cause established — partial streaming usage per content block, combined
      with a first-record-wins aggregation. Confirmed by LAST == MAX across every message id,
      and by the orchestrator being unaffected because its records already carry final values.
- [x] [run] `rg -n "per_subagent" README.md` — expect: a documented caveat naming the
      field as unreliable, alongside the existing `ws total_tokens` cache-inflation caveat

# Notes

Found while investigating orchestrator cost anatomy for #dcc-e0wj. The archived
`findings/subagent-*.md` transcripts are what made this checkable at all — they are an
independent record of what each agent actually emitted, so keep archiving them.

## Summary

Root cause: `session_tokens.sh` deduped usage by message id but took the FIRST record per id.
Transcripts write one line per content block, each carrying streamed partial usage — a message
reads `[5, 5, 278]` and only the last entry is cumulative. Verified LAST == MAX for every
message id across every transcript.

Fixed `map(.[0].u)` → `map(.[-1].u)`, backfilled all 90 runs (every raw transcript was still on
disk), rebuilt metrics.csv. Added `scripts/verify_subagent_tokens.py`, confirmed to fail on the
pre-fix data (exit 1, 13/16 rows) and pass after (exit 0). README caveat documents the rule and
the residual.

Sub-agent output was under-counted ~10× (one run: 17,875 → 187,227). This overturned the reading
that orchestrators dominate cost — they are a uniform 17–24% across all five tools; fan-out
dominates. #dcc-e0wj workstream 2 rewritten with corrected figures.

Not recoverable: 2 of 742 rows whose transcripts hold a single message id with only partial
usage — an upstream capture gap, allowlisted in the verifier with reasons. `cost_usd` was never
derived from this field, so no published conclusion changed.
