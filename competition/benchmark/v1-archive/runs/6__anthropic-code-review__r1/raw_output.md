All scores are in. Final tally against the ≥80 threshold:

| # | Finding | Score | Verdict |
|---|---------|-------|---------|
| G1 | Native clipboard write on internal copy → double-paste | 100 | keep |
| G3 | Temp-URI substitution → same-folder paste "already exists" | 95 | keep |
| B | Cut+paste of remote file silently becomes copy | 85 | keep |
| G2 | `dnd.ts` breaks remote drag into in-app text areas | 85 | keep |
| A | Proxy provider re-registers on every activation | 80 | keep |
| C | Partial-failure clipboard duplication | 72 | **filtered out** |

Eligibility recheck (step 7): PR #320685 is not a draft and the user explicitly requested this review — proceeding. Per your instruction I am **not** posting to GitHub (no `--comment`, nothing sent); output is terminal-only below.

---

### Code review

Found 5 issues (this PR was subsequently reverted upstream in [microsoft/vscode#323490](https://github.com/microsoft/vscode/pull/323490) after regression reports [#321354](https://github.com/microsoft/vscode/issues/321354) and an `EntryExists` telemetry spike [#323157](https://github.com/microsoft/vscode/issues/323157) — the findings below line up with why):

**1. Writing the OS-native file clipboard format on ordinary *internal* copies re-triggers the native-paste path, causing a double paste and a spurious "confirm paste" dialog.** For all-local copies, `writeResources` now writes `NSFilenamesPboardType` / `text/uri-list` / `FileNameW` to the real OS clipboard, so an in-app `Ctrl+V` now satisfies the `event.clipboardData?.files?.length` guard in the explorer's DOM paste listener (added by [#200601](https://github.com/microsoft/vscode/pull/200601) precisely to keep that path external-only) — firing `filesExplorer.paste` a second time. Confirmed in production by [#321387](https://github.com/microsoft/vscode/issues/321387) and the follow-up guard in [#323002](https://github.com/microsoft/vscode/pull/323002).

https://github.com/microsoft/vscode/blob/f9070acd20a269fb07dd15389676bd6875b9db05/src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts#L72-L98

https://github.com/microsoft/vscode/blob/f9070acd20a269fb07dd15389676bd6875b9db05/src/vs/workbench/contrib/files/browser/views/explorerView.ts#L340-L343

**2. Copy/paste into the same folder in a remote (WSL/SSH/dev-container) workspace fails with "already exists" instead of auto-renaming.** `resolveClipboardResources` replaces each `vscode-remote://` source with a downloaded local temp `file://` URI before it reaches the clipboard, so the paste target/rename logic loses the source's in-workspace identity. Reproduced exactly by [#321394](https://github.com/microsoft/vscode/issues/321394) ("Unable to move/copy '…/remote-clipboard/…/LICENSE.txt' because target 'vscode-remote://wsl+ubuntu/…/LICENSE.txt' already exists"), matching the `EntryExists` spike that led to the revert.

https://github.com/microsoft/vscode/blob/f9070acd20a269fb07dd15389676bd6875b9db05/src/vs/workbench/contrib/files/browser/explorerService.ts#L298-L324

**3. Cut + paste of a remote file silently degrades to copy — the original is never deleted.** `setToCopy` calls `resolveClipboardResources` unconditionally, ignoring the `cut` flag, so the clipboard holds a local temp copy. `pasteFileHandler` then builds a move edit against that temp copy (`pasteShouldMove` is true), moving the temp file to the destination and leaving the original remote file in place — so "Cut" behaves like "Copy" for remote resources.

https://github.com/microsoft/vscode/blob/f9070acd20a269fb07dd15389676bd6875b9db05/src/vs/workbench/contrib/files/browser/explorerService.ts#L271-L277

https://github.com/microsoft/vscode/blob/f9070acd20a269fb07dd15389676bd6875b9db05/src/vs/workbench/contrib/files/browser/fileActions.ts#L1222-L1233

**4. Restricting `DataTransfers.TEXT` to `file://` breaks dragging remote resources into in-app text targets.** The same TEXT channel that feeds native drops also feeds in-VS-Code text-capable areas (terminal, search, editors) — "Text: allows to paste into text-capable areas". Filtering to local files means dragging any `vscode-remote://` resource into those in-app targets now sets no text at all. The revert explicitly restored "setting text from all file-service resources".

https://github.com/microsoft/vscode/blob/f9070acd20a269fb07dd15389676bd6875b9db05/src/vs/workbench/browser/dnd.ts#L242-L248

**5. The proxy file-system provider re-registers on every scheme activation, logging an error and leaking a provider instance each time.** `RemoteFileSystemProxyClient.register` puts `registerProvider` *inside* the `onWillActivateFileSystemProvider` listener. Because `FileService.activateProvider` fires that event on every file op (before its already-registered check) and `registerProvider` throws on a duplicate scheme, every remote file operation after the first logs `RemoteFileSystemProxyClient: Failed to register proxy provider` and adds a fresh, never-disposed `RemoteFileSystemProxyClient` to the store. The sibling `RemoteFileSystemProviderClient.register` shows the correct pattern (register once, `e.join` the same promise).

https://github.com/microsoft/vscode/blob/f9070acd20a269fb07dd15389676bd6875b9db05/src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts#L55-L69

---

One issue was investigated and dropped below the confidence bar: the partial-failure path in `resolveClipboardResources` (`catch` re-adds all remote URIs even for files already added as temp copies, duplicating clipboard entries) — real, but it requires a mid-loop copy failure, so it scored 72 and was filtered out.

I did not post anything to GitHub. Let me know if you'd like this formatted differently or narrowed to a subset.
