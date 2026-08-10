# Benchmark run: 6__tag1-comprehensive-review__r1

| field | value |
|---|---|
| tool | tag1-comprehensive-review |
| subject | 6 (typescript / large) — microsoft/vscode#320685 |
| review diff | `f9070acd20a269fb07dd15389676bd6875b9db05^1..f9070acd20a269fb07dd15389676bd6875b9db05` (merge f9070acd20a269fb07dd15389676bd6875b9db05) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 1139 |
| longest single subagent (s) | 501 |
| duration_ms (orchestrator self) | 260042 |
| duration_api_ms (summed parallel API time, not wall) | 4076490 |
| num_turns | 3 |
| cost_usd | 19.068714400000005 |
| input_tokens | 5 |
| output_tokens | 20965 |
| cache_creation_tokens | 24193 |
| cache_read_tokens | 700777 |
| total_tokens (orchestrator only) | 745940 |
| **subagents** | 11 |
| **ws output_tokens** | 110249 |
| ws input_tokens | 372 |
| ws cache_creation | 1289224 |
| ws cache_read | 14465337 |
| ws total_tokens | 15865182 |
| session_id | fc354ffb-0392-4dc3-8519-ac29b651de05 |
| findings (raw lines) | 21 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (1139s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a25dc0e80a6f61be1 | 12 | 135507 | 29 |
| agent-a29ad281c603ca4e7 | 17 | 354059 | 237 |
| agent-a30b98ca786ec327c | 492 | 1510509 | 324 |
| agent-a3e93c35b3e7b137a | 14 | 222781 | 207 |
| agent-a85c2594739c154fd | 610 | 2407194 | 501 |
| agent-aa3134e2cb9ff68c1 | 40468 | 284870 | 463 |
| agent-ab7b4faa34718512e | 1219 | 2557335 | 370 |
| agent-ac1b1a1dbb3403f0f | 325 | 396182 | 348 |
| agent-ac8713ca943dc165a | 29 | 267879 | 191 |
| agent-ace0c1756805395d8 | 6097 | 1800535 | 388 |
| agent-af7d6b7d93aecf14e | 367 | 1226530 | 338 |

## Findings (final result text)

```
Review complete. Nothing was posted (`--local`).

## Output file
`/home/decaf/code/decaf-claude/competition/benchmark/repos/6/.decaf/tag1-review-320685.md`

## Findings by severity

**Overall risk: HIGH** — 26 consolidated findings across 11 review agents.

| Severity | Count | Headline items |
|----------|:-----:|----------------|
| **Critical** | 0 | — |
| **High** | 2 | (1) `RemoteFileSystemProxyClient.register()` re-creates + re-registers the provider on **every** `vscode-remote://` file op — leaks an object and logs an error each time. **Confirmed** by me against `fileService.ts` and by 4 agents. (2) Clipboard temp dir is deleted on window-close/next-copy while the OS clipboard still points at it → **silent data loss on paste**. |
| **Medium** | 6 | Partial multi-file copy → duplicate/mixed clipboard URIs · temp-dir disk leak (no crash sweep, fire-and-forget `dispose`, empty catch) · proxy handler authorizes on target authority only, ignoring caller (no server-side re-validation) · unbounded `readFile` (no streaming/size cap → OOM) · `uriListToFiles` drops the whole paste on one bad line · material test-coverage gaps. |
| **Low** | 18 | Selection reordering · unguarded `args[0]` TypeError · `window:${id}` single-source-of-truth · dead `exists`/`resolve` endpoints · inconsistent server layering · hard-coded `PathCaseSensitive` · Windows multi-file (`CF_HDROP`) read gap · no user notification on download failure · silent parser failures · native-clipboard blast radius on chat widgets · inert `watch()` · bare `Error` vs `NotSupportedError` · no telemetry · no kill switch · re-entrant `setToCopy` race · startup channel-not-ready hang · misleading comments · possible binary-plist gap. |

**Convergence:** the re-registration bug surfaced from code-reviewer, silent-failure-hunter, edge-case-hunter, and blind-hunter independently; the temp-dir and duplicate-URI issues each from 3–5 agents.

**Three candidates were verified as NOT issues** and documented so they aren't re-raised: the `FileReadWrite | Readonly` capability combo (established idiom, gated by `throwIfFileSystemIsReadonly`), the untyped `call()` dispatch (matches `diskFileSystemProviderServer` convention), and the `window:${id}` routing assumption (verified correct against `mainProcessService.ts:25`). Security parsers were assessed and cleared (no XXE, no ReDoS, correct escape ordering).

**Note:** PR #320685 is already **merged** — the default behavior is to stop on merged PRs, but since `--local` posts nothing and you requested it explicitly, I reviewed the merged squash commit's diff. Skipped: issue-linker (`--local`), CVE check (no dependency manifests), static analyzers (semgrep/trufflehog absent; eslint needs the vscode build env).
```
