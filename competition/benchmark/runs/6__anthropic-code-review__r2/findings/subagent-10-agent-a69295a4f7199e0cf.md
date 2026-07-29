# subagent agent-a69295a4f7199e0cf

## Code Review: PR #320685 (microsoft/vscode)

I fetched the diff with `gh pr diff 320685 --repo microsoft/vscode` and cross-checked the flagged findings against the actual files in the local checkout (verifying call chains, not just the diff context).

### 1. Proxy file-system provider is repeatedly re-registered on every remote file access, throwing and leaking on each occurrence

**File:** `src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts`, lines 56–69 (inside `static register(...)`)

```js
disposables.add(fileService.onWillActivateFileSystemProvider(e => {
    if (e.scheme === Schemas.vscodeRemote) {
        e.join((async () => {
            try {
                const provider = new RemoteFileSystemProxyClient(mainProcessService, logService);
                disposables.add(provider);
                disposables.add(fileService.registerProvider(Schemas.vscodeRemote, provider));
                logService.info('RemoteFileSystemProxyClient: Registered proxy provider for vscode-remote scheme');
            } catch (error) {
                logService.error('RemoteFileSystemProxyClient: Failed to register proxy provider', error);
            }
        })());
    }
}));
```

`FileService.activateProvider()` (`src/vs/platform/files/common/fileService.ts:94-106`) **unconditionally fires** `onWillActivateFileSystemProvider` on every single file operation against an unresolved scheme, and only afterward checks `if (this.provider.has(scheme)) return;`. That means this handler runs again on every subsequent `stat`/`readFile`/`readdir` against a `vscode-remote://` URI from this window — not just the first time.

Each re-run constructs a brand-new `RemoteFileSystemProxyClient` and calls `fileService.registerProvider(Schemas.vscodeRemote, provider)`, which **throws** (`fileService.ts:52-53`: `"A filesystem provider for the scheme 'vscode-remote' is already registered."`) since the scheme is already registered from the first activation. The `catch` swallows this, so it only manifests as a log-spammed `logService.error(...)` on every remote file touch plus an orphaned `RemoteFileSystemProxyClient` instance pushed into `disposables` each time (never disposed until the whole window's `disposables` store tears down) — an unbounded accumulation for the life of the window.

Compare with the established sibling pattern this was clearly modeled on, `RemoteFileSystemProviderClient.register()` (`src/vs/workbench/services/remote/common/remoteFileSystemProviderClient.ts:20-51`), which creates the registration promise **once outside** the event handler and simply re-joins the same (already-settled) promise on subsequent firings — no re-registration attempt. This PR's version creates a fresh promise/provider inside the handler on every firing, which is the bug.

### 2. Race condition in remote-clipboard temp-file staging can serve the wrong clipboard content and leak temp directories

**File:** `src/vs/workbench/contrib/files/browser/explorerService.ts`, lines 287–327 (`resolveClipboardResources`) and 567–575 (`dispose` / `cleanupRemoteClipboardTempDir`)

`ExplorerService` tracks only a single `remoteClipboardTempDir: URI | undefined` field. `resolveClipboardResources` — invoked from `setToCopy` on every copy — does:
```js
await this.cleanupRemoteClipboardTempDir();          // deletes the CURRENT this.remoteClipboardTempDir
const tempDir = joinPath(..., generateUuid());
await this.fileService.createFolder(tempDir);
this.remoteClipboardTempDir = tempDir;
for (const resource of remoteResources) { ... await this.fileService.copy(...); }
```
If the user copies a second batch of remote resources before the first `setToCopy` call's copy loop finishes (a realistic scenario since these are network transfers taking real time), the second call's `cleanupRemoteClipboardTempDir()` deletes the directory that the *first* call is still writing into (since both reference the same `this.remoteClipboardTempDir` field), and then overwrites `this.remoteClipboardTempDir` with its own new directory. The first call keeps working from its own local `tempDir` variable, so:
- its in-flight `fileService.copy` calls can fail against a directory that was just deleted out from under it (falls into the catch, silently substituting raw remote URIs — a different clipboard payload than expected), and
- if it doesn't fail (i.e., it created its subfolders after the delete), its temp directory is never tracked by `this.remoteClipboardTempDir` anymore (overwritten by the second call), so it is **never cleaned up** by `cleanupRemoteClipboardTempDir()` or `dispose()` — a leaked temp directory tree.

Additionally, whichever `setToCopy` call's `await this.clipboardService.writeResources(...)` resolves *last* wins the actual OS clipboard content, which is not guaranteed to be the most recent user action under this race. There is no serialization/queueing of concurrent `setToCopy` invocations to prevent this.

(Related, minor: `dispose()` at line 568 calls `this.cleanupRemoteClipboardTempDir()` without `await` — since `dispose()` must be synchronous, any pending delete may not complete before the process/window exits, so temp files can survive shutdown. This is likely accepted as "best effort," but is part of the same fragile state-sharing design.)

### 3. Clipboard resource order is not preserved when mixing local and remote selections (lower severity)

**File:** `src/vs/workbench/contrib/files/browser/explorerService.ts`, lines 291–296 and 308–316

```js
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
Previously `writeResources` received `items.map(s => s.resource)` in the user's original selection order. Now `resolveClipboardResources` unconditionally emits all local files first, then all downloaded remote files, regardless of how they were interleaved in the original selection. If a user multi-selects a mix of local and remote items, the order pasted will not match the order selected. This is a real (if narrow) behavioral regression, not just a style nit — flagging at lower confidence/severity than the two issues above since it does not cause data loss or errors, only reordering.

---

No other large, obvious bugs were found in `remoteFileSystemProxyMainHandler.ts`, `remoteFileSystemProxyServer.ts`, `dnd.ts`, `app.ts`, `desktop.main.ts`, or `clipboardService.ts` — the main-process routing (window lookup by `remoteAuthority`, `ctx === 'window:${id}'` channel filtering) matches the existing `ElectronIPCMainProcessService`/`Server` conventions correctly, and the clipboard native-format read/write branching (mac/linux/windows) is internally consistent between `writeResources`/`readResources`/`hasResources`.
