# Benchmark run: 6__tag1-comprehensive-review__r2

| field | value |
|---|---|
| tool | tag1-comprehensive-review |
| subject | 6 (typescript / large) — microsoft/vscode#320685 |
| review diff | `f9070acd20a269fb07dd15389676bd6875b9db05^1..f9070acd20a269fb07dd15389676bd6875b9db05` (merge f9070acd20a269fb07dd15389676bd6875b9db05) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 1404 |
| longest single subagent (s) | 581 |
| duration_ms (orchestrator self) | 390275 |
| duration_api_ms (summed parallel API time, not wall) | 5327942 |
| num_turns | 8 |
| cost_usd | 24.51796175000001 |
| input_tokens | 16 |
| output_tokens | 30924 |
| cache_creation_tokens | 35689 |
| cache_read_tokens | 2078708 |
| total_tokens (orchestrator only) | 2145337 |
| **subagents** | 13 |
| **ws output_tokens** | 87829 |
| ws input_tokens | 558 |
| ws cache_creation | 1325733 |
| ws cache_read | 24848528 |
| ws total_tokens | 26262648 |
| session_id | 0e31675f-b3d1-4f8f-8b2b-2bca177f8fd4 |
| findings (raw lines) | 49 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (1404s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a32332a7070672b51 | 5621 | 4175072 | 560 |
| agent-a337a858da7a5b482 | 239 | 1438659 | 325 |
| agent-a3b41ef6c0615f967 | 271 | 2714587 | 406 |
| agent-a566db39e16195b70 | 710 | 1070344 | 310 |
| agent-a5fe79e404868a607 | 14 | 145070 | 62 |
| agent-a7e63c35826b4e793 | 285 | 1601192 | 373 |
| agent-a84b88721e3ffa501 | 12 | 149767 | 36 |
| agent-ab5c0505050651b03 | 1372 | 4188483 | 581 |
| agent-ab837631f99d125a9 | 28 | 604007 | 433 |
| agent-ac2cfa0578a169b07 | 11 | 152847 | 220 |
| agent-ac3a8901a3a80976b | 503 | 2111334 | 383 |
| agent-aeab86b43446cbe29 | 38 | 311764 | 121 |
| agent-af0fd7742bf6fd322 | 32 | 531460 | 412 |

## Findings (final result text)

```
Done. The review is complete and written to the output file. Nothing was posted (`--local`).

## `.decaf/tag1-review-320685.md`

## Comprehensive review — microsoft/vscode PR #320685 (MERGED)

Reviewed the PR's own diff locally (`HEAD~1...HEAD` = squash commit `f9070acd20`; 10 files, +688/−13, all TypeScript, **TIER=medium**). 11 review agents ran in parallel; findings deduplicated, severities normalized (several agents over-rated issues as "Critical"), and cross-file claims verified against the repo.

### Findings by severity — Overall Risk: **High**

**Critical: 0** — no exploitable breach, no guaranteed data loss/crash on normal use.

**High: 5**
1. **Eager, unbounded, synchronous remote download on every copy/cut** (`explorerService.ts:298`) — recursive `fileService.copy` into `userDataPath`, no cap/progress/cancel; fires even for same-remote paste and when never pasted. *(adversarial's "Most Critical Gap")*
2. **Cut (move) of a remote file silently becomes a copy** (`explorerService.ts` → `fileActions.ts:1223`) — the move edit operates on the temp copy, leaving the original remote file. **I verified this myself** on the paste side.
3. **Partial-download failure duplicates clipboard entries** (`explorerService.ts:322`) — confirmed by 6 agents.
4. **Proxy provider re-registered on every remote file op → leak + error spam** (`remoteFileSystemProxyClient.ts:110`) — confirmed by 5 agents, verified against `fileService.ts`.
5. **Routed proxy call hangs forever when target window isn't connected** (`remoteFileSystemProxyMainHandler.ts:34`) — no timeout; confirmed by 4 agents, verified against `ipc.ts`.

**Medium: 6** — Windows `FileNameW` read silently fails (Uint16Array alignment; `readUInt16LE` fix); macOS may write *binary* plist the regex can't read *(Unverified — needs Mac)*; remote-content temp files with lax perms + un-awaited/empty-catch cleanup; hardcoded `window:${id}` IPC-ctx coupling; proxy server lacks its own scheme check (defense-in-depth); substantial new logic untested (+ a false-positive in existing test 3).

**Low: 9** — server `stat`/`readdir` bypass `withProvider`; `===` vs case-insensitive `isEqualAuthority`; hand-rolled plist parser duplicates existing `plistParser.ts`; interfaces not `Pick<>`-derived; untyped IPC where `ProxyChannel` exists; resource ordering; no progress/observability; parsers log nothing on catch; several doc inaccuracies.

**Reconciled (dismissed with evidence):** `FileReadWrite | Readonly` is a verified VS Code idiom (not a bug); `uriListToFiles` whole-list-discard doesn't occur (`URI.parse` is non-throwing); no ReDoS.

### Token utilization

| Agent | Model | Tokens | Tools | Est. Cost |
|---|---|---|---|---|
| pr-summarizer | Sonnet | 59,530 | 3 | ~$0.54 |
| code-reviewer | Sonnet | 135,046 | 55 ⚠ | ~$1.22 |
| architecture-reviewer | Opus | 82,929 | 18 | ~$3.73 |
| security-reviewer | Opus | 66,279 | 4 | ~$2.98 |
| adversarial-general | Opus | 88,998 | 13 | ~$4.00 |
| blind-hunter | Sonnet | 110,684 | 6 | ~$1.00 |
| edge-case-hunter | Sonnet | 120,309 | 46 ⚠ | ~$1.08 |
| silent-failure-hunter | Sonnet | 114,337 | 24 | ~$1.03 |
| pr-test-analyzer | Sonnet | 86,776 | 20 | ~$0.78 |
| comment-analyzer | Sonnet | 96,218 | 20 | ~$0.87 |
| type-design-analyzer | Sonnet | 112,587 | 60 ⚠ | ~$1.01 |
| **Agents total** | | **~1.07M** | | **~$18.24** |
| Orchestrator (est.) | Opus | — | — | — see /cost |

*Costs are blended-rate estimates; run `/cost` for exact figures.*

### Run notes
- **Diff tier:** medium (701 lines, 10 files) — full agent roster.
- **Skipped:** issue-linker (explicit `--local`); CVE/dependency check (no dependency manifests changed); opportunistic static analyzers (semgrep/trufflehog absent; eslint skipped as unreliable on a partial checkout).
- ⚠ Address the 5 High findings before relying on this feature (it is already merged).
```
