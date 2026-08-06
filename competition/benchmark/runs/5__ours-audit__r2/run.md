# Benchmark run: 5__ours-audit__r2

| field | value |
|---|---|
| tool | ours-audit |
| subject | 5 (typescript / medium) — microsoft/vscode#308517 |
| review diff | `ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9^1..ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9` (merge ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 1130 |
| longest single subagent (s) | 504 |
| duration_ms (orchestrator self) | 1126840 |
| duration_api_ms (summed parallel API time, not wall) | 3046649 |
| num_turns | 26 |
| cost_usd | 15.062824400000004 |
| input_tokens | 28 |
| output_tokens | 55341 |
| cache_creation_tokens | 233669 |
| cache_read_tokens | 1462458 |
| total_tokens (orchestrator only) | 1751496 |
| **subagents** | 10 |
| **ws output_tokens** | 167622 |
| ws input_tokens | 253 |
| ws cache_creation | 980123 |
| ws cache_read | 9030914 |
| ws total_tokens | 10178912 |
| session_id | 49de7cd3-93a8-4c1a-95be-60f6e420fceb |
| findings (raw lines) | 11 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (1130s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a048741845347be9d | 229 | 136761 | 173 |
| agent-a0a3a2051480c9877 | 8342 | 607146 | 198 |
| agent-a4395a703abcea5bb | 13229 | 481634 | 243 |
| agent-a4b31ad87eafc6a23 | 18316 | 1140387 | 291 |
| agent-a839a851e12f62f48 | 31996 | 2776814 | 504 |
| agent-a871df6396a894f64 | 9422 | 213323 | 184 |
| agent-a8db7e1d1e26f8c4e | 11283 | 588768 | 188 |
| agent-a92103e0d69095725 | 7094 | 1308299 | 156 |
| agent-adc1eb0a96e92aa53 | 3171 | 136556 | 62 |
| agent-ade16ee8a9de14953 | 9199 | 1037728 | 315 |

## Findings (final result text)

```
Review complete. This is the first review in `.decaf/code-reviews/`, so no recurring-findings section applies.

✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-06_14-35-38.md`

**Findings by severity: 2 High · 5 Medium · 4 Low · 3 Minor (0 Critical) → NEEDS_CHANGES**

Notes on the run:
- **PR #308517 is MERGED** — reviewed per your explicit instruction, strictly review-only (nothing posted).
- Two headline High findings: (#1) the `withStreamIdleTimeout` fix was applied to only 3 of ~6 `DestroyableStream`-body sites — the `completions-core` SSEProcessor twin and two pass-through servers still hang (I verified the full census); (#2) hardcoded uniform 60s/120s timeouts with no override regress legitimate slow streams (local BYOK/Ollama, reasoning models).
- I resolved the one direct reviewer conflict inline against source: adversarial-reviewer's "timeout → terminal `Failed`, no retry" is **refuted** — `err.fetcherId` is stamped and `isFetcherError` (`fetcherServiceImpl.ts:195`) routes it to a retryable `NetworkError`; the finding was retained (Medium #3) reframed around missing distinct telemetry/disposition.
- Nominated revert-probes were **not executed** (full monorepo build out of scope for a historical-PR review); affected findings kept at static-reasoning confidence and marked as such.
```
