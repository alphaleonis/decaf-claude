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
