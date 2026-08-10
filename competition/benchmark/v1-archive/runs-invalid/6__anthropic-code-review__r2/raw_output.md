The `/code-review` completed. Nothing was posted to GitHub — findings are terminal-only, as requested. Here's the full review of **microsoft/vscode PR #320685** ("Improve the local to native and remote to local copy, paste, and DND experience").

## Findings (most severe first)

### 1. Proxy provider re-registers on every remote activation — log spam + leak
`src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts:116`
The proxy provider is (re)registered inside the `onWillActivateFileSystemProvider` handler. Because `fileService.activateProvider` fires that event *before* its `if (this.provider.has(scheme)) return` early-out (`fileService.ts:99-108`), every access to a `vscode-remote://` URI in a local window constructs a new `RemoteFileSystemProxyClient` (added to the `DisposableStore`, never disposed until window close) and calls `registerProvider`, which throws *"A filesystem provider for the scheme vscode-remote is already registered"* → caught and logged. Result: repeated error logs + unbounded provider-instance leak. The sibling `RemoteFileSystemProviderClient.register` avoids this by creating the registration promise once outside the handler.

### 2. Partial download failure duplicates already-copied resources
`src/vs/workbench/contrib/files/browser/explorerService.ts:322`
On partial failure the catch runs `result.push(...remoteResources)` even though some temp targets were already added to `result`. Copy `[remoteA, remoteB]`: `remoteA` succeeds (`result = [..., tempA]`), `remoteB` throws → `result = [..., tempA, remoteA, remoteB]`. `remoteA` now appears twice on the clipboard, so paste yields a duplicate/inconsistent set.

### 3. `hasResources()` true while `readResources()` empty — Paste enabled but no-op
`src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts:139`
`has*` checks any native clipboard format; `read*` filters to `file://` only. On Linux, a non-file `text/uri-list` entry (e.g. a copied URL) makes `hasResources()` true, enabling the Paste command (`explorerView.ts:656`), but `readResources()` returns `[]` and the paste does nothing. Same asymmetry on macOS (plist) and Windows (FileNameW).

### 4. `plistToFiles` can't parse Finder's binary plist
`src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts:191`
The read path intends to support Finder→VS Code paste, but Finder writes `NSFilenamesPboardType` as a **binary** plist (bplist). The XML regex `/<string>([^<]+)<\/string>/` matches nothing → returns `[]` → nothing pasted.

### 5. Eager full-tree download on every copy (also breaks web)
`src/vs/workbench/contrib/files/browser/explorerService.ts:314`
`setToCopy` awaits `resolveClipboardResources` → `fileService.copy(remoteFolder, temp, true)`, downloading the entire remote tree before the clipboard write returns. The copy hangs and fills local disk even if the user never pastes. In web (vscode.dev) every resource is non-`file` scheme, so every explorer copy triggers a full download to `cacheHome` — a regression versus the old `writeResources(items.map(...))`.

### 6. Mixed-selection copy loses selection order
`src/vs/workbench/contrib/files/browser/explorerService.ts:292`
`resolveClipboardResources` emits all local files before all remote files. Selecting `[remoteA.ts, localB.ts]` produces `[localB.ts, tempA.ts]`. Any consumer relying on order (or the first entry) targets the wrong file.

### 7. `fileNameWToFile` throws on odd byte offset — dropped Windows read
`src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts:247`
`new Uint16Array(buffer.buffer, byteOffset, len)` throws `RangeError` when the IPC-deserialized `VSBuffer` has an odd `byteOffset` (offset must be a multiple of 2). The try/catch swallows it → returns `[]`, so a validly copied single-file `FileNameW` can't be pasted.

### 8. Remote drag-to-text inserts nothing (regression)
`src/vs/workbench/browser/dnd.ts:244`
Remote resources no longer contribute `DataTransfers.TEXT` (only `file://` do now). Dragging a `vscode-remote` file into an editor/text field inserts no text; previously it inserted the path. Intentional for the Finder `.webloc` case, but a behavior regression for remote drag-to-text.

### 9. Dead code: unreachable `exists`/`resolve` server handlers
`src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts:74`
The only consumer (`RemoteFileSystemProxyClient`) is a filesystem provider that calls just `stat`/`readdir`/`readFile`. The `exists` (line 74) and `resolve` (line 78) methods plus their switch cases (lines 42-43) — and resolve's `IFileStatWithMetadata` plumbing — are never invoked.

### 10. Temp copies deleted on window dispose — delayed native paste fails
`src/vs/workbench/contrib/files/browser/explorerService.ts:609`
Temp clipboard copies are deleted on window dispose (and on the next remote copy). If the user copies remote files then closes that window before pasting into Finder, `dispose()` → `cleanupRemoteClipboardTempDir` deletes the temp dir while the OS clipboard still references those paths → native paste fails.

---

**Not defects (verified):** routing (`configuration.windowId = window.id` matches ctx `window:${id}`), DI wiring (`IEnvironmentService.cacheHome`, `IMainProcessService.registerChannel`), the ctx-format assumption, and provider-registration semantics all check out.

The standout is **#1** — it diverges from the established `RemoteFileSystemProviderClient` pattern and produces both log spam and a memory leak on every remote file access in a local window. Nothing was posted to GitHub and no approval was given.
