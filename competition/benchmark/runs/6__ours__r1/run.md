# Benchmark run: 6__ours__r1

| field | value |
|---|---|
| tool | ours |
| subject | 6 (typescript / large) — microsoft/vscode#320685 |
| review diff | `f9070acd20a269fb07dd15389676bd6875b9db05^1..f9070acd20a269fb07dd15389676bd6875b9db05` (merge f9070acd20a269fb07dd15389676bd6875b9db05) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 1897 |
| longest single subagent (s) | 583 |
| duration_ms (orchestrator self) | 1895722 |
| duration_api_ms (summed parallel API time, not wall) | 6256012 |
| num_turns | 33 |
| cost_usd | 28.05863045000001 |
| input_tokens | 26 |
| output_tokens | 98403 |
| cache_creation_tokens | 307016 |
| cache_read_tokens | 1677949 |
| total_tokens (orchestrator only) | 2083394 |
| **subagents** | 19 |
| **ws output_tokens** | 116705 |
| ws input_tokens | 675 |
| ws cache_creation | 1778227 |
| ws cache_read | 26272489 |
| ws total_tokens | 28168096 |
| session_id | ec2fef52-0209-4743-9c4c-9af5877fbadb |
| findings (raw lines) | 10 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (1897s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a010a301296d20c43 | 1429 | 3875903 | 583 |
| agent-a0686424faa4a9d57 | 172 | 355539 | 89 |
| agent-a105013ca33cd0c74 | 2444 | 2041427 | 240 |
| agent-a1260b5176d4c1788 | 376 | 1175169 | 360 |
| agent-a14a4c8f57c902b7c | 364 | 1303918 | 229 |
| agent-a1c1f5d0cf76537dc | 30 | 435382 | 67 |
| agent-a27baeefc99ab5743 | 4219 | 566190 | 157 |
| agent-a2dade6926306839c | 129 | 1528473 | 460 |
| agent-a3b6eb4b28273530b | 48 | 685174 | 162 |
| agent-a92d3519eb4ea291e | 6733 | 6032276 | 582 |
| agent-aa123b7f39028e67d | 29 | 561087 | 246 |
| agent-aaaa43eec58c4c3ae | 27 | 399068 | 83 |
| agent-abad4f0bbde043e2d | 69 | 625672 | 402 |
| agent-abe577f7e3dcca68d | 16 | 222099 | 202 |
| agent-ac086e70d92167ff5 | 313 | 831255 | 107 |
| agent-ac85bbd536c1938a5 | 751 | 3451148 | 566 |
| agent-ae0832980437f0ebf | 94 | 917521 | 334 |
| agent-af0a527de60b8eb22 | 977 | 643135 | 77 |
| agent-afd75ce6db98c6ef8 | 82 | 434266 | 91 |

## Findings (final result text)

```
✅ Review complete. No comments, reviews, or status were posted to the PR — read-only throughout (`gh pr view`/`pr diff`/`api` reads only).

**Report:** `.decaf/code-reviews/CODE_REVIEW_2026-07-28_12-56-15.md`

**Findings by severity:** 🔴 0 Critical · 🟠 5 High · 🟡 7 Medium · 🟢 2 Low · 🔵 7 Minor → **❌ NEEDS_CHANGES**

Brief notes on the run:
- **PR #320685 is merged.** I proceeded because you explicitly directed a review of this specific PR and asked for a report file — a retrospective review — which overrides the skill's default "stop on merged PR" guardrail. The verdict is retrospective, not a gate on an open PR.
- **`mid` mode, 12-agent gated roster** (opus judgment agents + sonnet volume agents), then a **7-validator wave** (all confirmed, 0 refuted). Pre-flight build/test could not run (no `node_modules`), so I ground-truthed the top mechanisms directly against `fileService.ts`, `ipc.ts`, and `buffer.ts`.
- **Headline confirmed defects:** proxy provider re-registers on every `vscode-remote` activation (error spam + leak); serial/blocking/unbounded remote download on copy; whole-file buffering over IPC with no streaming; main-handler routing can hang forever (no timeout/cancellation); and Windows `fileNameW` decode throws `RangeError` on odd IPC-buffer offsets (validator empirically reproduced the odd offset) → silent native-paste failure. The maintainer's own unresolved thread (`mjbvz`) maps directly onto findings #2/#8/#9.
```
