# Benchmark run: 6__anthropic-code-review__r2

| field | value |
|---|---|
| tool | anthropic-code-review |
| subject | 6 (typescript / large) — microsoft/vscode#320685 |
| review diff | `f9070acd20a269fb07dd15389676bd6875b9db05^1..f9070acd20a269fb07dd15389676bd6875b9db05` (merge f9070acd20a269fb07dd15389676bd6875b9db05) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 1204 |
| longest single subagent (s) | 744 |
| duration_ms (orchestrator self) | 1201729 |
| duration_api_ms (summed parallel API time, not wall) | 2780929 |
| num_turns | 23 |
| cost_usd | 10.388674200000002 |
| input_tokens | 833 |
| output_tokens | 28087 |
| cache_creation_tokens | 131474 |
| cache_read_tokens | 318182 |
| total_tokens (orchestrator only) | 478576 |
| **subagents** | 19 |
| **ws output_tokens** | 123600 |
| ws input_tokens | 2189 |
| ws cache_creation | 1040006 |
| ws cache_read | 15215390 |
| ws total_tokens | 16381185 |
| session_id | 9843919c-3612-414b-a1ee-0fcf2059ff81 |
| findings (raw lines) | 30 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (1204s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a03207dc21e93f080 | 5851 | 465727 | 106 |
| agent-a120d2b5c7258740a | 5041 | 859330 | 95 |
| agent-a1763d0d6aaa029ca | 4490 | 260855 | 55 |
| agent-a304e1631d0bed109 | 4256 | 215657 | 58 |
| agent-a32fef1226202f55b | 3121 | 184379 | 41 |
| agent-a35e64a00e2f841d9 | 3088 | 358672 | 50 |
| agent-a394cfee1cd199966 | 2228 | 134403 | 40 |
| agent-a3f5a9862770555a8 | 271 | 71509 | 6 |
| agent-a6577adb808106099 | 3920 | 233466 | 62 |
| agent-a69295a4f7199e0cf | 10999 | 2474706 | 485 |
| agent-a7ec1bb75c043c132 | 7990 | 1326826 | 278 |
| agent-a8d3d574da648b480 | 2862 | 196744 | 58 |
| agent-a9a5fbc7d75040a4e | 267 | 46991 | 15 |
| agent-aa2bf976671c04e18 | 16002 | 4917431 | 744 |
| agent-adfbcf598f377b95e | 5829 | 487039 | 94 |
| agent-af06e17e1e4eab8b4 | 3878 | 568083 | 92 |
| agent-af89912481a3f2eac | 1250 | 48233 | 15 |
| agent-af9ad1807c34553f9 | 5393 | 1053256 | 131 |
| agent-afc63f0a53365cb34 | 8777 | 1999302 | 285 |

## Findings (final result text)

```
Line numbers pinned. All steps complete — filtering left **3 issues (≥80)**. Per your instruction I am **not** posting to GitHub; below is the exact review comment I *would* post, printed to the terminal.

---

### Code review

Found 3 issues:

**1. Recognizing native OS clipboard formats makes internal copies double-paste.** `writeResources`/`readResources`/`hasResources` now read and write the platform-native file clipboard formats (`NSFilenamesPboardType`, `text/uri-list`, `FileNameW`) in addition to VS Code's own format. This populates `event.clipboardData.files` for *internal* VS Code copies, so the unmodified DOM `paste` listener in `explorerView.ts` fires `filesExplorer.paste` alongside the keybinding-triggered paste — pasting every file twice (`File copy.txt` → `File copy 2.txt`). Directly confirmed by the post-merge regression reports ([#321387](https://github.com/microsoft/vscode/issues/321387), [#321394](https://github.com/microsoft/vscode/issues/321394)), the follow-up guard added to that exact listener ([#323002](https://github.com/microsoft/vscode/pull/323002)), and the fact that this PR was reverted ([#321516](https://github.com/microsoft/vscode/pull/321516) / [#323490](https://github.com/microsoft/vscode/pull/323490)).

https://github.com/microsoft/vscode/blob/6b744d6d73a2ec2a121ccdc1c7225b3bd1652588/src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts#L132-L148

**2. Unconditionally staging remote resources through a local temp file breaks same-authority paste.** `resolveClipboardResources` downloads *every* non-`file://` resource to a local temp dir and swaps in a `file://` URI — even when copy source and paste target are the same remote authority (WSL→WSL, SSH→SSH). This makes `sourceProvider !== targetProvider`, permanently bypassing `fileService`'s same-provider fast path, and produces `EEXIST` / "already exists at destination" errors on same-machine paste (confirmed by [#321498](https://github.com/microsoft/vscode/issues/321498) and [#321394](https://github.com/microsoft/vscode/issues/321394); part of why the PR was reverted).

https://github.com/microsoft/vscode/blob/6b744d6d73a2ec2a121ccdc1c7225b3bd1652588/src/vs/workbench/contrib/files/browser/explorerService.ts#L286-L307

**3. Proxy provider is re-registered (and leaked) on every remote file access.** `RemoteFileSystemProxyClient.register` constructs a new provider and calls `fileService.registerProvider(Schemas.vscodeRemote, provider)` *inside* the `onWillActivateFileSystemProvider` handler. `FileService.activateProvider()` fires that event on every operation against the scheme (checking `provider.has(scheme)` only afterward), so from the 2nd access onward `registerProvider` throws "already registered" — swallowed by the `catch` as error-log spam — while a fresh, orphaned provider is pushed into `disposables` each time (unbounded accumulation for the window's lifetime). The sibling `RemoteFileSystemProviderClient.register()` avoids this by building the registration promise once, outside the handler.

https://github.com/microsoft/vscode/blob/6b744d6d73a2ec2a121ccdc1c7225b3bd1652588/src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts#L55-L66

🤖 Generated with [Claude Code](https://claude.ai/code)

<sub>- If this code review was useful, please react with 👍. Otherwise, react with 👎.</sub>

---

**Notes on the run:**
- **No CLAUDE.md** exists anywhere in microsoft/vscode, so there were no repo-specific guidance findings (Agent #1 confirmed 404).
- **7 lower-confidence findings were filtered out** (score < 80): `getRendererChannel` can hang forever (75), single-field temp-dir race (75), hardcoded `PathCaseSensitive` — unaddressed reviewer comment (75), eager/blocking download — unaddressed reviewer comment (75), dnd.ts dropping `DataTransfers.TEXT` for remote-only selections (68), inaccurate docstring contract (48), and non-preserved clipboard order (45). Several are legitimate but were judged not-important-enough or too niche by the scoring pass.
- The PR is **merged (and was later reverted for excessive regressions)**; nothing was posted to GitHub — this review is terminal-output only, as requested.
```
