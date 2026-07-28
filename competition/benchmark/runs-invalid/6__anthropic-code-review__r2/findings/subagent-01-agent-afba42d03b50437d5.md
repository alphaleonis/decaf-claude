# subagent agent-afba42d03b50437d5

I have completed my analysis. I traced the routing (confirmed correct: `configuration.windowId = window.id` matches ctx `window:${id}`), verified service shapes, the clipboard native-format mapping, provider-registration semantics, and callers of the changed APIs.

Per the target instructions, I am NOT posting to GitHub and NOT approving — findings output to terminal only.

Findings for PR #320685 (microsoft/vscode), ranked most-severe first:

```json
[
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts",
    "line": 116,
    "summary": "The proxy provider is (re)registered inside the onWillActivateFileSystemProvider handler, so it re-registers on every vscode-remote activation, causing error-log spam and a leaked provider instance each time.",
    "failure_scenario": "In a local window (no remote connection), dragging/pasting remote files triggers fileService operations on vscode-remote:// URIs. fileService.activateProvider fires onWillActivateFileSystemProvider BEFORE its `if (this.provider.has(scheme)) return` early-out (fileService.ts:99-108), so the event fires on every access. After the first successful registration, each subsequent firing constructs a new RemoteFileSystemProxyClient (added to the DisposableStore, never disposed until window close) and calls fileService.registerProvider, which throws 'A filesystem provider for the scheme vscode-remote is already registered.' → caught and logged as an error. Result: repeated error logs and unbounded provider-instance leak. The sibling RemoteFileSystemProviderClient.register avoids this by creating the registration promise once outside the handler and only joining it."
  },
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 322,
    "summary": "On partial download failure, the catch pushes ALL original remote URIs even though some temp targets were already added to result, duplicating the already-downloaded resources on the clipboard.",
    "failure_scenario": "setToCopy copies [remoteA, remoteB]. copy(remoteA) succeeds so result = [..., tempA]; copy(remoteB) throws. The catch runs `result.push(...remoteResources)` → result = [..., tempA, remoteA, remoteB]. remoteA now appears twice on the clipboard (its temp copy plus its original remote URI), so a paste yields a duplicate/inconsistent set."
  },
  {
    "file": "src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts",
    "line": 139,
    "summary": "hasResources() can return true while readResources() returns [] because has* checks any native clipboard format but read* filters to file:// only.",
    "failure_scenario": "On Linux, a non-file text/uri-list entry sits on the clipboard (e.g., a copied URL). hasResources() returns true because hasClipboard(LINUX_FILE_FORMAT) is true; explorerView.ts:656 sets fileCopiedContextKey from hasResources(), enabling the Paste command. readResources() → uriListToFiles filters scheme===file → returns []. The Paste action appears enabled but pastes nothing. Same asymmetry exists on macOS (plist) and Windows (FileNameW)."
  },
  {
    "file": "src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts",
    "line": 191,
    "summary": "plistToFiles parses NSFilenamesPboardType with an XML-plist regex, but native producers (Finder) write a binary plist, so files copied in Finder cannot be read.",
    "failure_scenario": "On macOS the user copies files in Finder, then pastes into the VS Code explorer. readResources() finds FILE_FORMAT empty and reads NSFilenamesPboardType, whose bytes are a binary plist (bplist). The regex /<string>([^<]+)<\\/string>/ matches nothing → plistToFiles returns [] → nothing is pasted, though the read path clearly intends to support Finder→VS Code paste."
  },
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 314,
    "summary": "setToCopy eagerly downloads the entire remote file/folder tree to a local temp dir on every copy, blocking the copy and doing work that may never be needed; it also runs in web where cacheHome is not file://.",
    "failure_scenario": "User copies a large remote folder. setToCopy awaits resolveClipboardResources → fileService.copy(remoteFolder, temp, true) downloads the whole tree before the clipboard write returns, so the copy hangs and fills local disk even if the user never pastes. In web (vscode.dev) every resource has a non-file scheme, so every explorer copy now triggers a full download to cacheHome — a regression versus the old writeResources(items.map(...))."
  },
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 292,
    "summary": "resolveClipboardResources emits all local files before all remote files, losing the original selection order for mixed selections.",
    "failure_scenario": "User selects [remoteA.ts, localB.ts] and copies. result becomes [localB.ts, tempA.ts] — reordered relative to selection. A native paste or any consumer that relies on order (or on the first entry) targets the wrong file."
  },
  {
    "file": "src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts",
    "line": 247,
    "summary": "fileNameWToFile constructs a Uint16Array over buffer.buffer.byteOffset, which throws when the offset is odd, silently dropping a valid single-file Windows clipboard read.",
    "failure_scenario": "On Windows, readResources reads the FileNameW buffer whose IPC-deserialized VSBuffer happens to have an odd byteOffset. `new Uint16Array(ab, oddOffset, len)` throws RangeError (offset must be a multiple of 2), which the try/catch swallows → returns []. A file that was validly copied (single-file FileNameW) cannot be pasted."
  },
  {
    "file": "src/vs/workbench/browser/dnd.ts",
    "line": 244,
    "summary": "Remote resources no longer contribute DataTransfers.TEXT, so dragging a remote file into a text target inserts nothing (previously it inserted the path).",
    "failure_scenario": "User drags a vscode-remote file into an editor or text field. nativeResources (file:// only) is empty, so the TEXT format is never set; the drop inserts no text. Before this change the remote path label was inserted. Intentional for the Finder .webloc case, but a behavior regression for remote drag-to-text."
  },
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts",
    "line": 74,
    "summary": "The server's 'exists' and 'resolve' handlers (and resolve's IFileStatWithMetadata plumbing) are unreachable dead code — no client ever issues those calls.",
    "failure_scenario": "The only consumer, RemoteFileSystemProxyClient, is a file-system provider that calls just stat/readdir/readFile over the channel; it never sends 'exists' or 'resolve'. The exists (line 74) and resolve (line 78) methods plus their switch cases (lines 42-43) are never invoked, adding maintenance surface with no caller."
  },
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 609,
    "summary": "Temp clipboard copies are deleted on window dispose (and on the next remote copy), so a delayed native paste after closing the source window fails.",
    "failure_scenario": "User copies remote files (temp copies created, clipboard points at them), then closes that VS Code window before pasting into Finder. dispose() calls cleanupRemoteClipboardTempDir which deletes the temp dir; the OS clipboard still references the now-deleted paths, so the native paste fails."
  }
]
```

Notes: Routing correctness, the DI wiring (`IEnvironmentService.cacheHome`, `IMainProcessService.registerChannel`), and the ctx-format assumption (`window:${id}`) all check out and are not defects. Finding #1 (repeated re-registration) is the most consequential — it diverges from the established `RemoteFileSystemProviderClient` pattern and produces both log spam and a memory leak on every remote file access in a local window. Nothing was posted to GitHub and no approval was given, per the target instructions.
