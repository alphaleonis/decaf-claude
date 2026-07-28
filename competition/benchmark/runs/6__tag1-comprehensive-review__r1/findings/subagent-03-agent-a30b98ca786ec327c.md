# subagent agent-a30b98ca786ec327c

Reviewing the merged PR diff at `/tmp/cr-diff-URxdbEpr.txt` (base `826d1e76a3` → HEAD `f9070acd20`, "Improve the local to native and remote to local copy, paste, and DND experience"). Files in scope: `src/vs/code/electron-main/app.ts`, `src/vs/platform/files/common/remoteFileSystemProxy.ts`, `src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts`, `src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts`, `src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts`, `src/vs/platform/files/test/electron-main/remoteFileSystemProxy.test.ts`, `src/vs/workbench/browser/dnd.ts`, `src/vs/workbench/contrib/files/browser/explorerService.ts`, `src/vs/workbench/electron-browser/desktop.main.ts`, `src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts`. I cross-checked the new proxy-registration pattern against its established sibling (`src/vs/workbench/services/remote/common/remoteFileSystemProviderClient.ts`) and the core `FileService.activateProvider`/`registerProvider` implementation.

## Critical / Important

**1. `RemoteFileSystemProxyClient` re-creates and re-registers the provider on every single `vscode-remote://` file operation, not just once — causing repeated failing registrations, log-error spam, and an unbounded per-call object leak.**
File: `src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts:56-69`
Confidence: 90

```ts
disposables.add(fileService.onWillActivateFileSystemProvider(e => {
    if (e.scheme === Schemas.vscodeRemote) {
        e.join((async () => {
            try {
                const provider = new RemoteFileSystemProxyClient(mainProcessService, logService);
                disposables.add(provider);
                disposables.add(fileService.registerProvider(Schemas.vscodeRemote, provider));
                ...
            } catch (error) {
                logService.error('RemoteFileSystemProxyClient: Failed to register proxy provider', error);
            }
        })());
    }
}));
```

`FileService.activateProvider` (`src/vs/platform/files/common/fileService.ts:94-113`) fires `onWillActivateFileSystemProvider` **unconditionally, before** checking whether a provider is already registered — and it is invoked by `withProvider`/`withReadProvider` on *every* `stat`, `readdir`, `readFile`, etc. call (verified: `fileService.ts:160,170,210,314,322,334,541,581,971,1044,1219`). `FileService.registerProvider` throws if the scheme is already registered (`fileService.ts:52-55`).

So after the first successful registration, every subsequent remote file operation in a window without a direct remote connection re-fires the listener, which constructs a *new* `RemoteFileSystemProxyClient`, adds it to `disposables` (never disposed until the window closes), and then throws/catches/logs an error via `registerProvider`. The result: an error is logged to the log service for essentially every remote file access in a proxy window (e.g., browsing a folder tree, drag preview, repeated stats), plus an ever-growing number of leaked, unused provider+channel objects for the life of the window.

Compare with the pre-existing, correct pattern in `src/vs/workbench/services/remote/common/remoteFileSystemProviderClient.ts:26-48`, which builds the registration `environmentPromise` **once**, outside/before the listener, and the listener only does `e.join(environmentPromise)` on every fire — it never re-creates or re-registers.

Fix: hoist provider creation/registration into a single memoized promise created once in `register()` (mirroring `RemoteFileSystemProviderClient`), and have the listener only `e.join()` that same promise on repeat fires, e.g.:
```ts
const registrationPromise = (async () => {
    try {
        const provider = disposables.add(new RemoteFileSystemProxyClient(mainProcessService, logService));
        disposables.add(fileService.registerProvider(Schemas.vscodeRemote, provider));
    } catch (error) {
        logService.error(...);
    }
})();
disposables.add(fileService.onWillActivateFileSystemProvider(e => {
    if (e.scheme === Schemas.vscodeRemote) {
        e.join(registrationPromise);
    }
}));
```

## Important

**2. `RemoteFileSystemProxyClient` hardcodes `PathCaseSensitive`, ignoring the actual remote OS's case sensitivity.**
File: `src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts:81-85`
Confidence: 62

```ts
get capabilities(): FileSystemProviderCapabilities {
    return FileSystemProviderCapabilities.FileReadWrite |
        FileSystemProviderCapabilities.Readonly |
        FileSystemProviderCapabilities.PathCaseSensitive;
}
```

The sibling implementation this deliberately mirrors, `RemoteFileSystemProviderClient` (`remoteFileSystemProviderClient.ts:53-55`), derives case-sensitivity from the actual remote environment (`pathCaseSensitive: remoteAgentEnvironment.os === OperatingSystem.Linux`). This new proxy always reports case-sensitive regardless of whether the real remote OS is Windows/macOS (case-insensitive). `FileService.isPathCaseSensitive`/`toFileStat` use this flag for path-trie matching and dedup logic, so entries that only differ by case on a case-insensitive remote could be treated as distinct. Given the proxy is used for read-only single-file/dir browsing during copy rather than full workspace resolution, blast radius is limited, but it's a real, easily-fixed correctness deviation from the established convention — worth plumbing the real capability through the proxy channel (e.g. via an added `stat`/handshake call) rather than hardcoding it.

**3. `resolveClipboardResources` reorders the copied selection — all local files are placed before all downloaded remote files, regardless of original selection order.**
File: `src/vs/workbench/contrib/files/browser/explorerService.ts:287-296` (locals loop) vs. `308-316` (remotes loop)
Confidence: 62

```ts
// Local files: use as-is
for (const resource of resources) {
    if (resource.scheme === Schemas.file) {
        result.push(resource);
    }
}
...
for (const resource of remoteResources) {
    ...
    result.push(target);
}
```

If a user selects [localA, remoteB, localC] and copies, the resulting clipboard order is [localA, localC, remoteB(temp)] instead of the original interleaved order. This changes paste ordering behavior (e.g., in target explorers/apps that respect drop order) without acknowledgment in the comment ("Local files: use as-is" implies no reordering). A fix that preserves original order would need a single pass building an index-ordered result (e.g., map each original index to its resolved URI, or process remotes first into a lookup map, then iterate `resources` once in original order).

**4. Remote clipboard temp directory is only cleaned up on the *next remote copy* or on `dispose()` — a purely local copy after a remote copy leaves the previous temp directory (and its downloaded file copies) on disk for the rest of the window's lifetime.**
File: `src/vs/workbench/contrib/files/browser/explorerService.ts:287-322` (guarded by `if (remoteResources.length > 0)`), cleanup only at `298-302` and `567-569`/`572-581`
Confidence: 60

Sequence: user copies a remote file → `remoteClipboardTempDir` is set to a new temp folder containing a downloaded copy. User then copies only local files → `resolveClipboardResources` never enters the `remoteResources.length > 0` branch, so `cleanupRemoteClipboardTempDir()` is never called for the stale directory; it lingers until either the next remote copy or the window is disposed. `dispose()` (line 567-569) does call `cleanupRemoteClipboardTempDir()`, but doesn't `await` the async delete, so it's best-effort on graceful shutdown only. This is a bounded, session-scoped disk leak but is easily avoided by unconditionally invoking cleanup at the top of `resolveClipboardResources` (or tracking/clearing `remoteClipboardTempDir` whenever a copy completes without remote resources).

## Notes not rising to a reportable finding (below confidence threshold, listed only for completeness)
- `clipboardService.ts`'s `fileNameWToFile` builds a `Uint16Array` view directly over the `VSBuffer`'s underlying `ArrayBuffer` at an arbitrary `byteOffset` (`clipboardService.ts:856`); if that offset is ever odd, the `Uint16Array` constructor throws. Whether IPC-delivered clipboard buffers can have an odd offset couldn't be confirmed from this diff alone, so this stays speculative.
- `RemoteFileSystemProxyMainHandler.getRendererChannel` (`remoteFileSystemProxyMainHandler.ts:356-363`) returns a channel proxy that waits indefinitely (no timeout) for a matching IPC connection if the target window hasn't connected yet; a pathological race (target window closing mid-call) could hang a caller forever with no user-visible error. Plausible but not clearly reachable from the current call sites, so kept below the reporting bar.
