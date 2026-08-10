# Benchmark run: 5__ours-audit__r1

| field | value |
|---|---|
| tool | ours-audit |
| subject | 5 (typescript / medium) — microsoft/vscode#308517 |
| review diff | `ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9^1..ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9` (merge ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 1118 |
| longest single subagent (s) | 354 |
| duration_ms (orchestrator self) | 1114494 |
| duration_api_ms (summed parallel API time, not wall) | 2877615 |
| num_turns | 41 |
| cost_usd | 15.67202545 |
| input_tokens | 690 |
| output_tokens | 59183 |
| cache_creation_tokens | 275008 |
| cache_read_tokens | 3781572 |
| total_tokens (orchestrator only) | 4116453 |
| **subagents** | 13 |
| **ws output_tokens** | 189261 |
| ws input_tokens | 921 |
| ws cache_creation | 1049725 |
| ws cache_read | 9821593 |
| ws total_tokens | 11061500 |
| session_id | 068eebfa-bc59-4817-b468-201b8ca62759 |
| findings (raw lines) | 13 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (1118s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a358d23e99049b4d5 | 10520 | 183707 | 154 |
| agent-a5960d70638d1161d | 3200 | 456330 | 107 |
| agent-a629a251de0c997b9 | 4345 | 177726 | 72 |
| agent-a6835b8126be2c814 | 8046 | 460245 | 132 |
| agent-a7a8a291bf39d29df | 1920 | 415418 | 53 |
| agent-a8ad72e8ded0dda97 | 7134 | 1691625 | 144 |
| agent-a9d031972a9d1445e | 12994 | 536055 | 212 |
| agent-aa355cbdf6e600aaa | 27261 | 882827 | 354 |
| agent-ac5485819cd526999 | 17388 | 574428 | 270 |
| agent-ad445250f4fc92e4b | 3859 | 538424 | 68 |
| agent-adadad6cc008acccf | 8155 | 268556 | 121 |
| agent-ae2926533b0af6511 | 12794 | 146691 | 173 |
| agent-afac6697a7c3a6b94 | 12462 | 613015 | 253 |

## Findings (final result text)

```
Review complete. Working tree is clean (only the `.decaf/` artifacts are untracked; the two revert-probes were fully restored). Nothing was posted to the PR — this was review-only.

✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-06_14-29-55.md`

**Findings: 0 Critical · 0 High · 4 Medium · 0 Low · 11 Minor** (+1 pre-existing) → Verdict **APPROVED**

The four Medium findings (all hardening / edge-case gaps, not merge blockers) on this merged PR:
1. **Idle watchdog keys on raw byte arrival, not progress** — SSE keepalive/trickle traffic resets the timer forever, defeating hung-stream protection; no absolute deadline. *(confirmed by validator; High→Medium, incomplete-mitigation not a regression)*
2. **Spurious `StreamIdleTimeoutError` on slow socket close** — `messagesApi`/`responsesApi` don't break on the `[DONE]` sentinel (unlike `SSEProcessor`), so a complete response can throw if the server lingers >60s. *(confirmed)*
3. **Undocumented load-bearing contract** — the timeout only fires because `destroy()` cancels the in-flight read; a future change could silently hang.
4. **Hardcoded, non-injectable timeouts** — no override/`AbortSignal`/config, tests bound to real 60s/120s constants.

Two nominated revert-probes were run: both **refuted** `test-reviewer`'s "vacuous test" concern — the slow-consumer and positive-timeout tests genuinely bite. One adversarial "cleanup hang" claim was **refuted** by the validator. The three prior Copilot-bot comments were verified already fixed.
```
