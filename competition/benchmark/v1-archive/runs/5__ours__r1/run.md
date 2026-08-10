# Benchmark run: 5__ours__r1

| field | value |
|---|---|
| tool | ours |
| subject | 5 (typescript / medium) — microsoft/vscode#308517 |
| review diff | `ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9^1..ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9` (merge ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 2541 |
| longest single subagent (s) | 757 |
| duration_ms (orchestrator self) | 2540235 |
| duration_api_ms (summed parallel API time, not wall) | 6492513 |
| num_turns | 35 |
| cost_usd | 24.781900200000006 |
| input_tokens | 20 |
| output_tokens | 139547 |
| cache_creation_tokens | 245733 |
| cache_read_tokens | 1422183 |
| total_tokens (orchestrator only) | 1807483 |
| **subagents** | 17 |
| **ws output_tokens** | 148994 |
| ws input_tokens | 514 |
| ws cache_creation | 1441347 |
| ws cache_read | 16281700 |
| ws total_tokens | 17872555 |
| session_id | 61803988-9c1b-4c9d-a6fe-b884deeff76e |
| findings (raw lines) | 14 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (2541s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a123e9219d9bfe887 | 371 | 494887 | 93 |
| agent-a160c47e96343a142 | 699 | 1095943 | 553 |
| agent-a18ae6c33071dff71 | 1018 | 2730695 | 757 |
| agent-a1901af5f73be11aa | 34 | 557789 | 322 |
| agent-a1de23e01ed9f9b1f | 371 | 956651 | 523 |
| agent-a25d1d886e2daf91c | 18 | 223001 | 397 |
| agent-a317d5ca56a1681bb | 1384 | 212462 | 139 |
| agent-a3ad67a9f2a157455 | 212 | 1095757 | 482 |
| agent-a4658e96dfaf2932a | 358 | 821680 | 313 |
| agent-a52f656c26ae50c59 | 355 | 1444420 | 214 |
| agent-a693ed17fb3246be8 | 95 | 518572 | 136 |
| agent-a6bb7f0ff32d93ecd | 117 | 323301 | 107 |
| agent-a6e8a589b48712b3f | 165 | 314357 | 84 |
| agent-a8593af8c6b0f56d1 | 3689 | 2276552 | 252 |
| agent-a8f015f2b0ba25a5f | 44 | 538364 | 145 |
| agent-a9188c2694e5cd589 | 111 | 286095 | 102 |
| agent-a9f8434733e3db146 | 406 | 2174546 | 533 |

## Findings (final result text)

```
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-07-22_22-59-58.md`

**Findings: 2 Critical, 1 High, 2 Medium, 1 Low (primary) + 2 Minor + 1 Pre-existing → ❌ NEEDS_CHANGES**

Summary of the run:

- **PR #308517** "Support timing out hung streams" (microsoft/vscode, merged) — reviewed from the local squash-merge commit `ba8d730b`; nothing was posted to the PR.
- **Roster**: 10 reviewers (mid mode — floor + all gate-matched specialists; spec-compliance, prior-feedback, data-migration, and non-TS stack reviewers hard-gated out). Judgment agents on opus, volume agents + 7 validators on sonnet.
- **Headline findings**:
  - 🔴 The new "consumer break releases the reader lock" test is a **false-positive test** — it passes even with the cleanup it verifies deleted (validator-confirmed statically).
  - 🔴 The watchdog's correctness hinges on an **undocumented Web Streams invariant** (cancel resolves the pending read `{done:true}`) — a silent-regression trap if the backing stream ever changes.
  - 🟠 The 2-minute TTFT budget **collapses to 60s after the first administrative transport chunk** (documented in-repo at `stream.ts:409`), and the policy has no configurability/kill switch.
  - 🟡 Watchdog kills are telemetered as `outcome: 'cancel'` (indistinguishable from user cancels), and 🟡 `StreamIdleTimeoutError` is classified only by accident — users get a misleading *"check your firewall rules"* message.
- **Validation wave**: 7 validators — 6 confirmed, 1 refuted (the timeout-calibration-docs finding: uncalibrated constants are the codebase norm). Notably, validator #1 refuted the mechanism behind the classification finding's Critical rating and confirmed the Medium account, so severity was re-derived — recorded as an anomaly in the report's Session Metrics, along with the merged-PR override and the two-batch dispatch. Per `--report`, the full per-agent usage table (≈1.40M subagent tokens total, [Unverified] child-inclusion caveat) is appended to the review file.
```
