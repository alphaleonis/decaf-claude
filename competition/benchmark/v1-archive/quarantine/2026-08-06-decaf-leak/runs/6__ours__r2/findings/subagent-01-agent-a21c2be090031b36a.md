# subagent agent-a21c2be090031b36a

Depth: deep — ~688 added lines spanning data-mutation (remote→local temp copy), cross-process IPC routing, and native-clipboard serialization; multiple high-risk domains (data mutation + external OS integration). All four techniques applied; multi-step chains traced end to end.

I verified the load-bearing mechanisms directly against source: `registerProvider` throws on duplicate scheme (fileService.ts:53), `activateProvider` fires `onWillActivateFileSystemProvider` **unconditionally before** the `has()` check (fileService.ts:99-106) and `withProvider` calls it on every op (fileService.ts:145), `writeClipboardBuffer` → Electron `clipboard.writeBuffer(format,…)` single-format write (nativeHostMainService.ts:1006), and `isEqualAuthority` is case-insensitive (resources.ts:280-282) whereas the new router uses strict `===`.

```json
[
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 314,
    "severity": "High",
    "category": "resource-management",
    "issue": "[ADV_CASCADE] Copy remote file → temp copy written under cacheHome, OS clipboard points at it → window closes (dispose() → cleanupRemoteClipboardTempDir at 568) OR next remote copy runs cleanup at 302 → temp dir recursively deleted while the OS clipboard still references it → user pastes in Finder/Explorer → empty/missing file (the exact vscode-remote-release#2008 symptom this PR set out to fix). Native clipboard paste is lazy and can occur any time after copy; temp-file lifetime is tied to VS Code's session/next-copy, not the clipboard's lifetime.",
    "fix": "Do not delete the temp dir on dispose or on the next copy while it may still back the OS clipboard. Either keep copies in a stable per-copy dir cleaned by age/OS temp policy, or clear the OS clipboard when deleting the dir. At minimum, gate cleanup on 'is this dir still the current clipboard target'.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 302,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_COMPOSITION] Two rapid Ctrl+C on remote files: Copy1 creates tempDir1, sets the single `remoteClipboardTempDir` field, and suspends at `fileService.copy` (line 314, slow for large remote files). Copy2 enters resolveClipboardResources, cleanupRemoteClipboardTempDir del()s tempDir1 recursively (line 302) mid-write, overwrites the field with tempDir2, writes a good clipboard. Copy1 resumes: its copy() target parent is gone → throws → catch pushes original remote URIs (line 322) → writeResources clobbers Copy2's clipboard with vscode-remote URIs. Result: most-recent copy silently replaced; VS Code paste (code/file-list) and native paste (stale format) disagree; tempDir1 partial writes orphaned.",
    "fix": "Serialize setToCopy/resolveClipboardResources (single-flight queue or per-call local temp dir + swap the field only after copy completes). Never delete a temp dir that an in-flight copy is still writing into; scope each copy's dir to that invocation, not a shared mutable field.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts",
    "line": 110,
    "severity": "Medium",
    "category": "resource-management",
    "issue": "[ADV_ABUSE] `onWillActivateFileSystemProvider` fires on EVERY vscode-remote op (activateProvider fires unconditionally before its has()-check; withProvider calls it per stat/readFile/copy). The listener runs each time: constructs a new RemoteFileSystemProxyClient, `disposables.add(provider)` (line 115), then `registerProvider` throws 'already registered' for every call after the first (caught, logged as error at 119). Each remote file interaction therefore leaks one provider into a DisposableStore that is only cleared on window close, and emits a spurious error log. Over a session of copy/paste/stat the store grows unbounded.",
    "fix": "Guard registration idempotently: `if (fileService.getProvider(Schemas.vscodeRemote)) return;` at the top of the join callback, and/or dispose the onWillActivate listener after the first successful registration so it does not re-run per operation.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts",
    "line": 100,
    "severity": "High",
    "category": "other",
    "issue": "[ADV_COMPOSITION] writeClipboardBuffer maps to Electron clipboard.writeBuffer(format,…), which writes a single format without clearing the others. Copy1 = all-local → writes NSFilenamesPboardType/uri-list/FileNameW. Copy2 = mixed or remote-download-failed fallback → allLocal is false → writes ONLY code/file-list (line 100), leaving Copy1's stale native format in place. Native paste (Finder/Nautilus/Explorer) reads the stale native format → silently pastes Copy1's previously-copied files instead of Copy2's. VS Code paste reads code/file-list → Copy2. The two paste destinations diverge on stale data.",
    "fix": "Clear the clipboard (or write an empty/authoritative value to the OTHER native formats) before writing the current one, so exactly one coherent set of file paths is present across all formats on every copy.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts",
    "line": 343,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_CASCADE] findWindowForAuthority returns the FIRST window matching the authority (line 346-353) with no liveness check and no fallback. With two windows on the same remote authority, or when that first window is closing, the handler resolves its id, then targetChannel.call routes to `window:{id}` (line 343). If that window closes between selection and the call, the IPC router channel has no matching client and the call never resolves — the local window's paste/readFile hangs with no timeout — even though another same-authority window could have served it.",
    "fix": "Prefer a live/last-active window among all authority matches, verify the target still has an active connection before routing, add a timeout/retry that re-selects another matching window on failure, and reject clearly if none remain.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 314,
    "severity": "Medium",
    "category": "performance",
    "issue": "[ADV_ABUSE] Copy a remote FOLDER: fileService.copy(resource, target, true) recursively downloads the entire directory tree to local temp on the synchronous Ctrl+C gesture (setToCopy awaits it before returning), with no size cap, progress, or cancellation. A large remote repo/node_modules blocks the copy action and can fill cacheHome. On a mid-tree failure (remote disconnect), the catch pushes original remote URIs (line 322) but the partially-downloaded temp tree is left orphaned until the next remote copy or dispose. (Matches mjbvz's unresolved concern (a): eager + blocking on copy.)",
    "fix": "Bound and background the download: defer/stream on paste rather than eagerly on copy, or cap size and surface progress+cancellation; on failure, clean up the partial temp tree before falling back.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts",
    "line": 349,
    "severity": "Medium",
    "category": "other",
    "issue": "[ADV_ASSUMPTION] Authority routing uses strict `window.remoteAuthority === authority` (line 349) while the rest of the codebase compares remote authorities case-insensitively via isEqualAuthority (resources.ts:280, e.g. getLastActiveWindow-for-authority at windowsMainService.ts:1793). A vscode-remote URI whose authority differs only in case from the window's configured authority → strict === misses it → 'No window found with remote authority' → paste fails despite a valid owning window.",
    "fix": "Use isEqualAuthority(window.remoteAuthority, authority) to match the comparison contract used everywhere else for remote authorities.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts",
    "line": 170,
    "severity": "Medium",
    "category": "other",
    "issue": "[ADV_ASSUMPTION] filesToPlist writes NSFilenamesPboardType as an XML-plist STRING and plistToFiles parses it with an XML `<string>` regex (line 191). macOS delivers NSFilenamesPboardType as a binary plist (bplist00)/archived NSArray, not XML text. Write direction: Finder may not interpret a raw XML string buffer as an array of filenames → native paste from VS Code produces nothing. Read direction: pasting FROM Finder yields a binary buffer the regex never matches → returns [] silently. Both break the mac copy/paste bridge the PR intends.",
    "fix": "Serialize/parse NSFilenamesPboardType via a real plist encoder/decoder (binary plist), not hand-rolled XML string + regex; validate round-trip against actual Finder pasteboard bytes.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **UTF-16LE surrogate pairs in filePathToUtf16LE (clipboardService.ts:232) — REFUTED.** Hypothesis was that `charCodeAt` over emoji/astral filenames breaks the encoding. It does not: JS strings are UTF-16, `path.length` counts code units and `charCodeAt(i)` returns each code unit (including both surrogate halves), so the loop produces correct UTF-16LE for astral characters. `fileNameWToFile` reconstructs via `String.fromCharCode(...codeUnits)`, also correct for surrogate pairs. Scenario fell apart under construction.
- **uri-list `\r\n` split vs filenames containing newlines (clipboardService.ts:82/220) — REFUTED.** Linux filenames may contain `\n`, but `URI.toString()` percent-encodes control characters in the path (`%0A`), so no literal newline reaches the join/split; `URI.parse` decodes it back. Round-trips safely.
- **plist XML-escape round-trip for `&`/`<`/`>` (clipboardService.ts:174/194) — REFUTED.** Checked the adversarial input `&lt;` as a literal filename: write escapes `&`→`&amp;` first, read un-escapes `&amp;`→`&` LAST, so ordering is correct and it round-trips. No double-unescape bug.
- **Uint16Array odd byteOffset in fileNameWToFile (clipboardService.ts:247).** `new Uint16Array(buf.buffer, buf.byteOffset, …)` throws RangeError if the IPC-delivered VSBuffer has an odd byteOffset; caught → returns [] → paste silently no-ops. Plausible but I could not confirm the buffer ever has an odd offset from readClipboardBuffer, and impact is a recoverable empty paste. Confidence 25 — below report threshold.
- **`String.fromCharCode(...u16.subarray(...))` argument-count limit (clipboardService.ts:249).** Extended-length Windows paths (>~32k units) could exceed the spread-arg stack limit → RangeError → caught → []. Only reachable with pathological path lengths; confidence 25.
- **Proxy server stat/readdir use getProvider without activation (remoteFileSystemProxyServer.ts:248/256).** In the owning remote window the vscode-remote provider is registered eagerly at startup, so this is only a narrow startup-window transient; readFile uses fileService.readFile which activates. Confidence 25 as a standalone timing bug.

## Probe Requests

(Static review only; suite not executed. These would confirm the three 50-confidence findings.)

1. **Electron writeBuffer format-clearing (finding #4):** In a scratch Electron main process, `clipboard.writeBuffer('NSFilenamesPboardType', bufA)` then `clipboard.writeBuffer('code/file-list', bufB)`, then read both formats back — confirm NSFilenamesPboardType still returns bufA (stale not cleared) on macOS, and the analogous check for `text/uri-list` (Linux) and `FileNameW` (Windows).
2. **macOS NSFilenamesPboardType serialization (finding #8):** Copy a file in Finder, dump the raw `NSFilenamesPboardType` bytes — confirm it is binary plist (`bplist00`) vs the XML the regex expects; and paste VS Code's XML-string buffer into Finder to confirm whether Finder accepts it.
3. **IPC router behavior on missing client (finding #5):** Confirm `mainProcessElectronServer.getChannel(name, ctx===window:{id}).call(...)` when window `{id}` has closed — does the returned promise hang indefinitely (no timeout) or reject?
