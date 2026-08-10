# subagent agent-a7ec1bb75c043c132

## Findings

I reviewed PR #320685's diff (`gh pr diff 320685`), then searched commit/PR history for each of the 9 changed files and read the review comments on the prior PRs and on #320685 itself. Two of the four new proxy files and `app.ts`/`desktop.main.ts` registration hooks had no prior history to compare against (net-new code/new registration lines), so the applicable prior history is concentrated in `explorerService.ts`, `clipboardService.ts`, and the PR's own review thread.

### 1. Reintroduces the exact clipboard/double-paste hazard that #200396 and #200601 already had to fix in this same code path

- **Current PR file/lines:** `src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts:62-133` (`writeResources`/`hasResources`, which now write and check platform-native OS clipboard formats — `NSFilenamesPboardType`, `text/uri-list`, `FileNameW` — in addition to VS Code's custom `code/file-list` format), consumed by the **unmodified** `src/vs/workbench/contrib/files/browser/views/explorerView.ts` PASTE DOM listener (`if (event.clipboardData?.files?.length) { await this.commandService.executeCommand('filesExplorer.paste', ...) }`).
- **Prior PR citations:** [#200396 "Patch crashing explorer on paste"](https://github.com/microsoft/vscode/pull/200396) and [#200601 "Fix explorer paste"](https://github.com/microsoft/vscode/pull/200601), both against `explorerService.ts`'s copy/paste flow, which had to add guards after discovering that (a) writing multiple clipboard formats for the same copy operation and (b) the browser PASTE event double-firing alongside the keybinding-triggered paste command caused crashes/duplicate pastes.
- **Why it applies here:** Before #320685, `event.clipboardData.files` was only populated when files came from a native app (Finder/Explorer), so internal VS Code copy→paste never double-triggered. #320685 makes `writeResources()` also populate a native OS file-clipboard format for pure-local copies, so the OS now reports `event.clipboardData.files.length > 0` for internal-to-VS-Code copies too — triggering `filesExplorer.paste` from both the keybinding and this dormant DOM listener. This is not speculative: it's exactly what happened. TPI testing on the merged PR (issue [#321354](https://github.com/microsoft/vscode/issues/321354)) surfaced this as issue [#321387 "Copy/Paste files broken"](https://github.com/microsoft/vscode/issues/321387) (files pasted twice / incrementing counters), the whole PR was reverted ([#321516](https://github.com/microsoft/vscode/pull/321516), later re-reverted via [#323490](https://github.com/microsoft/vscode/pull/323490)), and the fix ([#323002](https://github.com/microsoft/vscode/pull/323002)) had to add `if (await this.clipboardService.hasResources()) { return; }` to the very PASTE listener above — a file not touched by #320685's diff.

### 2. Unresolved reviewer comment on this same PR: hardcoded `PathCaseSensitive`

- **File/line:** `src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts:81-84`
```ts
get capabilities(): FileSystemProviderCapabilities {
    return FileSystemProviderCapabilities.FileReadWrite |
        FileSystemProviderCapabilities.Readonly |
        FileSystemProviderCapabilities.PathCaseSensitive;
}
```
- **Citation:** Inline review comment by `Copilot` on PR #320685 itself (2026-06-09, before the "Address comments" follow-up commit): *"The proxy provider currently hard-codes `PathCaseSensitive`... It would be better to derive case-sensitivity from the target window's remote environment/provider... instead of hard-coding."* This comment was never addressed — the merged diff still hardcodes it.

### 3. Unresolved reviewer comment on this same PR: eager, blocking temp-file download design

- **File/line:** `src/vs/workbench/contrib/files/browser/explorerService.ts:287-320` (`resolveClipboardResources`)
- **Citation:** Inline comment by `mjbvz` on PR #320685 (2026-06-09): *"We are creating the file eagerly on copy and blocking the copy on this... I worry about leaking the `/tmp` file path... the web clipboard api should support writing a Promise that resolves to a Blob."* Also unaddressed — the merged code still synchronously downloads remote files to `cacheHome/remote-clipboard/<uuid>/<uuid>/...` inside `setToCopy()`.

Note on scope: findings 2 and 3 are technically comments on PR #320685's *own* review thread (this repo's PR #320685 is the real, already-merged-then-reverted GitHub PR, not a hypothetical), not a separate prior PR — but since they were left unaddressed by the "Address comments" commit and are directly on the lines in question, I'm flagging them as directly applicable open feedback. Two other Copilot comments on the same thread (unique subfolder naming for temp downloads at `explorerService.ts`, and `file://`-only filtering for `text/uri-list` at `clipboardService.ts`) **were** addressed in the final diff and don't need re-raising.

### Not applicable / checked and clear
- `dnd.ts`'s `Schemas.file` filtering for `DataTransfers.TEXT` — no prior-PR comments on this file warned about scheme filtering for native drag; the change looks locally sound.
- `app.ts`/`desktop.main.ts` channel registration — compared against the similarly-shaped `Proxy browser requests in remote workspaces` (#315843) and `ElectronRemoteResourceLoader` history; no applicable disposal/leak comments surfaced there.
- The four new `remoteFileSystemProxy*.ts` files have no prior-PR history (net new files), so there's nothing previous to compare against beyond the same-PR comments already listed above.
