# Benchmark run: 5__ours__r2

| field | value |
|---|---|
| tool | ours |
| subject | 5 (typescript / medium) — microsoft/vscode#308517 |
| review diff | `ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9^1..ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9` (merge ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 1681 |
| longest single subagent (s) | 626 |
| duration_ms (orchestrator self) | 1679382 |
| duration_api_ms (summed parallel API time, not wall) | 5711347 |
| num_turns | 33 |
| cost_usd | 23.267301800000002 |
| input_tokens | 701 |
| output_tokens | 81929 |
| cache_creation_tokens | 189236 |
| cache_read_tokens | 1466588 |
| total_tokens (orchestrator only) | 1738454 |
| **subagents** | 16 |
| **ws output_tokens** | 95389 |
| ws input_tokens | 1349 |
| ws cache_creation | 1341814 |
| ws cache_read | 21363273 |
| ws total_tokens | 22801825 |
| session_id | 645c98fa-4a17-4dba-9dfc-1209221a946e |
| findings (raw lines) | 11 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (1681s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a07e9fa7e27db72ba | 1967 | 1502658 | 241 |
| agent-a17b8ac373240327d | 203 | 992594 | 112 |
| agent-a1dfd676ffd0cbe00 | 315 | 300115 | 78 |
| agent-a29689de952cb04a7 | 1100 | 1484385 | 589 |
| agent-a30dbf2609aad9fbf | 2578 | 2474477 | 275 |
| agent-a3959bcf45aa3b00a | 1257 | 3739713 | 626 |
| agent-a4437832360f9d633 | 902 | 1366222 | 229 |
| agent-a824e86a776deda9b | 790 | 852628 | 356 |
| agent-a9e6f1616371b157e | 73 | 1989741 | 500 |
| agent-aa3117a56394a7701 | 3261 | 1866002 | 515 |
| agent-aac8c57e06af2bed4 | 23 | 322888 | 283 |
| agent-ac3da3c520b44f5be | 57 | 899821 | 108 |
| agent-ac4a4b8fdda756b5b | 25 | 257837 | 142 |
| agent-ae18794412ae3d9f0 | 764 | 2091402 | 545 |
| agent-af0e0ddbd549546cf | 53 | 562440 | 86 |
| agent-af7114265ec72c7fa | 92 | 360448 | 111 |

## Findings (final result text)

```
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-07-22_23-26-57.md`

**Findings: 2 Critical, 1 High, 2 Medium, 0 Low (primary) + 4 Minor + 3 Pre-existing — Verdict: ❌ NEEDS_CHANGES**

Highlights of the run:

- **PR #308517** (merged 2026-04-08) reviewed retrospectively — the skill's merged-PR guard was overridden per your explicit instruction; **nothing was posted to the PR**.
- **Wave**: 9 reviewers (mid mode, gated roster; knowledge/design/adversarial on Opus, volume agents on Sonnet) → 7-validator wave (all Sonnet): **7 confirmed, 0 refuted, 0 uncertain**.
- The two Criticals are knowledge-reviewer MUSTs (mapped MUST→Critical per convention): the undocumented liveness contract behind the 60 s idle timeout, and the undocumented destroy→`{done:true}`→flag→throw signaling mechanism. The High is a confirmed false-positive test (validator empirically reproduced that it passes with the cleanup it names removed).
- Validators reattributed two confirmed findings to pre-existing (the unwrapped completions-core `SSEProcessor` twin and the telemetry cancel-vs-error blind spot), and corrected finding #4's failure trace (design-reviewer's NetworkError-with-firewall-message account is right; adversarial's no-retry account refuted).
- `--report` session metrics are appended to the review file (reviewer wave ≈1.08 M tokens, validator wave ≈445 k, harness figures verbatim; 6 nominated probes unrunnable — no `node_modules`). A recurring-findings table cross-references the earlier 22:59:58 review of the same PR — the two independent runs converged on the same core findings.
```
