# Benchmark run: 6__ours__r2

| field | value |
|---|---|
| tool | ours |
| subject | 6 (typescript / large) — microsoft/vscode#320685 |
| review diff | `f9070acd20a269fb07dd15389676bd6875b9db05^1..f9070acd20a269fb07dd15389676bd6875b9db05` (merge f9070acd20a269fb07dd15389676bd6875b9db05) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 1980 |
| longest single subagent (s) | 624 |
| duration_ms (orchestrator self) | 1978053 |
| duration_api_ms (summed parallel API time, not wall) | 6688115 |
| num_turns | 37 |
| cost_usd | 30.948394699999987 |
| input_tokens | 26 |
| output_tokens | 95229 |
| cache_creation_tokens | 462634 |
| cache_read_tokens | 1502821 |
| total_tokens (orchestrator only) | 2060710 |
| **subagents** | 23 |
| **ws output_tokens** | 120224 |
| ws input_tokens | 863 |
| ws cache_creation | 2148638 |
| ws cache_read | 26889430 |
| ws total_tokens | 29159155 |
| session_id | 24dea64b-2f2d-48a9-965a-a02b62ae699e |
| findings (raw lines) | 12 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (1980s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a21c2be090031b36a | 217 | 785470 | 446 |
| agent-a38deb82b80f46130 | 29 | 252651 | 210 |
| agent-a45593268cd85912d | 76 | 443289 | 93 |
| agent-a53ff5722c5e9e95a | 1206 | 770055 | 86 |
| agent-a6a4fce6b0809bdf6 | 6268 | 7573069 | 583 |
| agent-a75d76f16b0483b3b | 291 | 570647 | 78 |
| agent-a935ed78fa331f355 | 9138 | 3628603 | 624 |
| agent-aa71da899a99bd313 | 152 | 561523 | 75 |
| agent-aa8d8006c417ad7d8 | 788 | 2922973 | 573 |
| agent-aa9241f047b3b6d0f | 910 | 453032 | 90 |
| agent-ab67f4c2b3eb9d5d4 | 1591 | 333848 | 57 |
| agent-ac099673ec24f3319 | 21 | 221160 | 209 |
| agent-ac49a7798eab021ef | 180 | 1216613 | 277 |
| agent-ac722bc87a0796f74 | 1245 | 402982 | 60 |
| agent-ac91a3aad6848f1a0 | 44 | 560326 | 126 |
| agent-aca55e72e4974ba00 | 64 | 394513 | 79 |
| agent-ad9a9f6691cfdc766 | 88 | 618862 | 262 |
| agent-ada911c77da7ac242 | 38 | 870757 | 304 |
| agent-adce40b59d24b008c | 285 | 671435 | 64 |
| agent-ae541a9f749786347 | 656 | 1057470 | 295 |
| agent-aef4e1a5ca5b83f4b | 597 | 2149032 | 554 |
| agent-afb9a095ee3112138 | 165 | 473136 | 354 |
| agent-afe9144fcf8119531 | 946 | 166999 | 23 |

## Findings (final result text)

```
✅ Review complete.

**Report:** `.decaf/code-reviews/CODE_REVIEW_2026-07-28_13-28-35.md`

**Findings by severity:** 🔴 1 Critical · 🟠 7 High · 🟡 8 Medium · 🟢 0 Low · 🔵 18 Minor — **Verdict: NEEDS_CHANGES**

Notes on the run:
- **PR #320685 is MERGED.** The skill's default guard would stop on a merged PR, but I treated your explicit "review this PR and produce a report" instruction as an override and ran a full retrospective review. Nothing was posted to the PR (review-only).
- **Mid mode, full gate-matched roster of 12 reviewers** + an **11-agent validation wave** (all 11 returned *confirmed*, 0 refuted). Four heavily-corroborated/quotable findings were waived from validation.
- The headline finding is a **Critical** provider re-registration leak (`remoteFileSystemProxyClient.ts`) independently found by three agents. The 7 Highs cluster around the eager blocking download on copy (the unresolved human-reviewer mjbvz concern), temp-dir lifecycle bugs that reintroduce the original empty-file symptom, whole-file IPC buffering, a cross-window arbitrary-remote-read trust gap, the hard-coded `PathCaseSensitive`, and a Windows `FileNameW` `RangeError`.
- A near-identical **prior review of this same PR from earlier today** independently corroborates 11 of the findings (Recurring Findings section).
- Pre-flight gates and all reviewer-nominated probes were **not run** — the full vscode build/test suite and the GUI/OS-clipboard probes are out of scope for a review-only pass.
```
