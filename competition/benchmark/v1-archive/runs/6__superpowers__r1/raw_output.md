Below is the reviewer subagent's full report, verbatim.

---

### Strengths

- **Correct reuse of the established main-process routing pattern.** The new IPC design mirrors `ElectronRemoteResourceLoader` / `NodeRemoteResourceRouter`: a per-renderer server channel, a main-process handler that routes by window, and the `window:${id}` connection `ctx` convention. I confirmed against `src/vs/base/parts/ipc/common/ipc.ts:889-913` (the `clientFilter` overload) and `electronRemoteResources.ts` that `client.ctx === 'window:${windowId}'` is exactly how existing code addresses a specific renderer. This is the right mechanism, on the right process boundary.
- **Good testability decoupling.** `RemoteFileSystemProxyMainHandler` depends on two minimal structural interfaces (`IRemoteFileSystemProxyWindowsService`, `IRemoteFileSystemProxyIPCServer`) instead of the heavy electron-main types, so the routing logic is unit-testable without a live IPC server. `ICodeWindow` and `mainProcessElectronServer` structurally satisfy them, so the app.ts wiring still type-checks. Nice.
- **Read-only proxy provider is genuinely read-only** — `writeFile`/`mkdir`/`delete`/`rename` all throw, and `watch` is a no-op; capabilities advertise `Readonly`.
- **Sensible scheme gating.** The main handler rejects any non-`vscode-remote` URI before routing (`remoteFileSystemProxyMainHandler.ts:329`), explicitly to avoid routing UNC/`file://` authorities. The `dnd.ts` change (filter TEXT transfer to `file://` only, to avoid Finder `.webloc` bookmarks) is a clean, well-commented, targeted fix.
- **Encoding round-trip correctness.** The plist escape/unescape ordering is right (escape `&`→`&amp;`; unescape `&amp;` *last*), and `filePathToUtf16LE` correctly emits null-terminated UTF-16LE. The `readResources`/`hasResources` fallback chain (VS Code format first, then platform-native) is coherent with the write side.
- Comments explain the non-obvious "why" (loop avoidance when a window has its own remote connection, Electron's one-format-per-write limitation, Windows CF_HDROP gap).

### Issues

#### Critical (Must Fix)

**1. Cut/paste of remote files silently degrades to copy — the original is left behind.**
`explorerService.ts:setToCopy` now unconditionally routes every non-`file://` resource through `resolveClipboardResources`, which downloads each remote file to a local temp dir and puts the **temp `file://` URI** on the clipboard (`explorerService.ts:568-585`). `setToCopy` is the single entry point for both copy *and* cut (`fileActions.ts:1059` and `1068`). On paste, `pasteFileHandler` reads the source URIs from `clipboardService.readResources()` (`fileActions.ts:1318`) — i.e. the temp URIs — and when `pasteShouldMove` is true it issues `ResourceFileEdit(tempFileUri, target)` as a **move** (`fileActions.ts:1223-1232`). The move therefore operates on the *local temp copy*, not the original remote file. Result: cutting a file in a remote (SSH/WSL/dev-container) workspace and pasting it into another remote folder leaves the original remote file in place and creates a duplicate sourced from a local snapshot. This is a data-integrity regression on a very common operation. Previously the clipboard held the real remote URI and the move deleted the source.
*Fix:* don't temp-download on cut, or key the temp-download strictly to the native-paste path and keep the real remote URI on the clipboard for in-app paste (the proxy provider already makes cross-window remote reads work). At minimum, confirm the intended cut behavior for remote files.

#### Important (Should Fix)

**2. Proxy provider is re-created and re-registered on every remote file access → memory leak + error-log spam.**
`RemoteFileSystemProxyClient.register` constructs a **new** provider and calls `fileService.registerProvider(...)` *inside* the `onWillActivateFileSystemProvider` handler (`remoteFileSystemProxyClient.ts:110-123`). But `FileService.activateProvider` fires that event **unconditionally on every call, before its has-provider check** (`fileService.ts:99` vs `106`), and `activateProvider` runs on essentially every file op via `withProvider` (`fileService.ts:145`). `registerProvider` throws if the scheme is already registered (`fileService.ts:53-55`). So: the first activation registers successfully; every subsequent `vscode-remote` access constructs another `RemoteFileSystemProxyClient`, adds it to the `DisposableStore`, attempts to register, throws "already registered", and logs `Failed to register proxy provider`. Feature still works (first provider stays), but you get unbounded provider accumulation and error spam proportional to remote file activity. The canonical `remoteFileSystemProviderClient.ts:30-48` shows the correct idiom: register **once** eagerly and have the activation handler merely `e.join(sharedPromise)`.
*Fix:* register once (guard with `fileService.hasProvider` or a shared registration promise) and only `join` in the event handler.

**3. Eager, blocking, whole-selection download on every remote copy — even for in-app paste.**
`resolveClipboardResources` awaits `fileService.copy` of every selected remote file into temp before `setToCopy` resolves (`explorerService.ts:577-584`), with a `createFolder` per file. This runs on the copy gesture itself, has no progress UI and no cancellation, and is unbounded for large selections/large files. Because it happens for *all* remote copies, pasting back into the same remote workspace now downloads to local disk and re-uploads (and pastes a stale snapshot if the file changed between copy and paste), where previously it was a server-side remote copy. This is the performance/staleness half of issue #1; both stem from unconditionally materializing temp copies in `setToCopy`.

**4. Main-handler routing can hang instead of failing.** `getRendererChannel` calls `getChannel(name, clientFilter).call(...)` (`remoteFileSystemProxyMainHandler.ts:356-363`). Per `ipc.ts:901-907`, when no connection currently matches the filter, the call **waits for a matching connection to appear** rather than rejecting. The handler pre-checks that a *window* with the authority exists (`findWindowForAuthority`), but window existence does not guarantee a live IPC connection with `ctx === window:${id}` (startup, reload, crashed renderer). In that window the proxy `stat`/`readFile` — and the paste awaiting it — can hang indefinitely with no timeout or cancellation token.

**5. Test coverage is thin and misses the bug-prone code.** The only tests (`remoteFileSystemProxy.test.ts`) cover the main handler's window-selection over a mocked channel — good, but they do **not** exercise a real client→main→server round-trip, and none cover the pure, easily-testable, encoding-sensitive functions (`filesToPlist`/`plistToFiles`/`uriListToFiles`/`filePathToUtf16LE`/`fileNameWToFile`) or the explorer temp-download/cleanup path. Those encoding functions are exactly where regressions will hide.

**6. Whole file buffered in memory across two IPC hops.** Cross-window remote reads go renderer→main→renderer as a single `VSBuffer` with no streaming (the proxy advertises only `FileReadWrite`, not `FileReadStream`). Large remote files copied/dragged between windows are fully buffered in each process. Acceptable for typical files; a scale concern worth acknowledging.

#### Minor (Nice to Have)

- **Resource reordering:** `resolveClipboardResources` emits all local resources first, then all remotes (`explorerService.ts:561-585`), so a mixed selection's clipboard order no longer matches selection order.
- **Fire-and-forget cleanup on dispose:** `dispose()` calls the async `cleanupRemoteClipboardTempDir()` without awaiting (`explorerService.ts:566`); temp copies may linger past shutdown. Also, after a cut+paste-move the temp file is consumed, so the recursive `del` partially no-ops (harmless, best-effort).
- **Dead server surface:** `RemoteFileSystemProxyServer` implements `exists` and `resolve` commands the client never calls (`remoteFileSystemProxyServer.ts:236-274`).
- **`fileNameWToFile` alignment:** `new Uint16Array(buffer.buffer.buffer, buffer.buffer.byteOffset, …)` throws `RangeError` if `byteOffset` is odd (`clipboardService.ts:856`); it's caught and returns `[]`, so Windows single-file paste-from-Explorer could intermittently and silently return nothing.
- **Windows multi-file native copy unsupported** (CF_HDROP needs a predefined format ID Electron can't write), so "local → native" multi-file paste doesn't work on Windows — an acknowledged but real gap in the stated goal.
- **[Unverified] Native clipboard interop.** Whether `NSFilenamesPboardType` (XML plist), `text/uri-list`, and `FileNameW` written via Electron's `clipboard.writeBuffer` are actually honored by Finder / GNOME-KDE file managers / Explorer is inherent, platform-dependent behavior not covered by any test; this is expected to work but needs manual cross-platform verification, not a guarantee.

### Recommendations

- Decouple the two concerns: keep real remote URIs on the clipboard for in-app copy/cut/paste (correctness + move semantics + server-side remote copy), and produce temp `file://` copies *only* for the native-clipboard/DND path. This fixes issues #1 and #3 together.
- Adopt the `remoteFileSystemProviderClient.ts` registration idiom (register once, `join` a shared promise) to fix #2.
- Give the proxy round-trip a failure mode (reject/timeout) when the target window has no live connection, and thread a cancellation token through the copy/paste flow.
- Add unit tests for the clipboard encoders (round-trip + malformed input) and at least one integration test that drives the client through the handler to a fake server.

### Assessment

**Ready to merge?** No — with fixes.

**Reasoning:** The IPC proxy architecture is sound and idiomatic, but the change silently breaks remote cut/paste move semantics (original not removed) and introduces a provider re-registration leak on the hot file-access path; both are concrete, common-workflow defects that must be fixed, and the encoding-heavy code is largely untested.
