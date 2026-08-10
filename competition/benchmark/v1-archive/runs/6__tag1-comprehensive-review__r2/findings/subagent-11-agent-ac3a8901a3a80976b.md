# subagent agent-ac3a8901a3a80976b

# Silent-Failure Audit — PR #320685 (Remote File System Proxy for local↔remote copy/paste/DND)

Reviewed: `/tmp/cr-diff-daQNG83h.txt` against the working tree at the PR commit. All line numbers below are from the post-PR files I read directly (paths given). All claims are evidence-based (file:line cited); where I reason beyond what's directly demonstrated in the code, I mark it `[Inference]`.

---

## 1. `ExplorerService.resolveClipboardResources` — fallback produces a duplicated/broken clipboard (CRITICAL)

**Location**: `src/vs/workbench/contrib/files/browser/explorerService.ts:287-327`, catch block at `317-323`

```ts
for (const resource of remoteResources) {
    const uniqueDir = joinPath(tempDir, generateUuid());
    await this.fileService.createFolder(uniqueDir);
    const target = joinPath(uniqueDir, basename(resource));
    await this.fileService.copy(resource, target, true);
    result.push(target);
}
} catch (error) {
    // If download fails, fall back to the original remote URIs.
    this.logService.warn('Failed to download remote files for clipboard', error);
    result.push(...remoteResources);
}
```

**Issue**: The loop pushes each successfully-copied resource's local temp `target` into `result` as it completes. If copying resource N of M throws (network hiccup, remote disconnect, permission error, disk full on the temp dir), the `catch` unconditionally does `result.push(...remoteResources)` — pushing **all** original remote URIs, including the ones that already got a `target` pushed in the loop. `result` now contains **both** the local temp copy *and* the original remote URI for every resource that succeeded before the failure.

**Hidden errors**: This is a broad `catch (error)` around `cleanupRemoteClipboardTempDir()`, `createFolder`, and `copy` — any of `FileSystemProviderError`, network/timeout errors from the remote connection, disk-full errors on the local temp dir, or an unrelated bug in `generateUuid()`/`joinPath()` all collapse into the same "fall back to originals" branch, with no differentiation.

**User impact**: `writeResources(clipboardResources)` is then called with duplicate entries for the same logical file (one `file://` temp path, one `vscode-remote://` URI). Because not all entries are `file://`, `allLocal` is false, so the custom VS Code format is written with the duplicates intact. Pasting will produce **two copies of the same file** (one via the local temp file, one via the cross-window proxy), with zero indication to the user that anything went wrong — the only trace is a `logService.warn` line no ordinary user will ever see.

**Recommendation**: Don't blindly re-add `remoteResources` on catch. Track success per-resource (e.g., build `result` from a map of `resource → target | resource`), and only fall back the *specific* resource(s) that failed:

```ts
for (const resource of remoteResources) {
    try {
        const uniqueDir = joinPath(tempDir, generateUuid());
        await this.fileService.createFolder(uniqueDir);
        const target = joinPath(uniqueDir, basename(resource));
        await this.fileService.copy(resource, target, true);
        result.push(target);
    } catch (error) {
        this.logService.warn(`Failed to download remote file for clipboard: ${resource.toString()}`, error);
        result.push(resource); // fall back to this resource only
    }
}
```
This also removes the top-level `try/catch` around the whole batch, which is the actual root cause of the duplication.

---

## 2. `ExplorerService.resolveClipboardResources` — failure is invisible to the user (HIGH)

**Location**: same as above, `explorerService.ts:321`

**Issue**: The *only* signal on failure is `this.logService.warn('Failed to download remote files for clipboard', error)`. There is no `notificationService` toast, no status bar message, nothing surfaced through the Explorer UI (`this.view`). The comment even acknowledges the degraded behavior ("native paste will not [work]") but nothing communicates that to the user.

**User impact**: A user who copies remote files, then pastes into Finder/Explorer and gets nothing (or, per finding #1, duplicates) has no way to know *why* — they'd have to open the Output panel and search logs at `warn` level. This directly matches the audit brief's question: "Does the user get any signal that native paste won't work?" — no.

**Recommendation**: At minimum, log at a level with more context (which resource, how many of N failed), and consider a lightweight, non-blocking notification (e.g., `notificationService.warn(...)`, rate-limited) the first time a copy operation degrades, so users aren't left guessing.

---

## 3. `ExplorerService.cleanupRemoteClipboardTempDir` — literal empty catch block (CRITICAL)

**Location**: `src/vs/workbench/contrib/files/browser/explorerService.ts:572-581`

```ts
private async cleanupRemoteClipboardTempDir(): Promise<void> {
    if (this.remoteClipboardTempDir) {
        try {
            await this.fileService.del(this.remoteClipboardTempDir, { recursive: true });
        } catch {
            // Best-effort cleanup
        }
        this.remoteClipboardTempDir = undefined;
    }
}
```

**Issue**: This is a textbook empty catch block — no logging at any level, not even `trace`. Per the project's own stated standard ("Never use empty catch blocks... always log errors"), this is a direct violation, not just a stylistic nit.

**Hidden errors**: Any `del` failure — permission denied, file locked by an AV scanner, disk error, or a bug elsewhere that mutated `remoteClipboardTempDir` to point somewhere unexpected — is swallowed identically.

**User impact / risk**: These temp directories (`<cacheHome>/remote-clipboard/<uuid>/...`) contain **copies of remote file content**, potentially from an SSH/WSL/container host the user considers separated from their local disk. If cleanup silently and repeatedly fails, that content accumulates on local disk indefinitely with zero diagnostic trail — nobody would ever notice to investigate, and there's no periodic sweep for orphaned `remote-clipboard` directories elsewhere in this diff. This is a genuine, if low-probability, information-residue concern, not just tidiness.

**Recommendation**: Never leave a catch block truly empty. At minimum:
```ts
} catch (error) {
    this.logService.trace('ExplorerService: failed to clean up remote clipboard temp dir', this.remoteClipboardTempDir?.toString(), error);
}
```
"Best-effort" is a legitimate policy for *not blocking* on failure — it does not justify zero logging.

*(Minor, same block)*: `dispose()` at `explorerService.ts:567-570` calls `this.cleanupRemoteClipboardTempDir()` without awaiting it — a fire-and-forget promise in `dispose()`. Because the callee's own try/catch means it can never reject, this won't produce an unhandled-rejection, but cleanup is not guaranteed to run to completion before disposal proceeds. Low severity, worth a comment explaining it's intentionally fire-and-forget.

---

## 4. `RemoteFileSystemProxyClient.register` — catch swallows the real registration failure, downstream error is generic (HIGH)

**Location**: `src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts:58-67`

```ts
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
```

**Issue**: `e.join(promise)` feeds this promise into `FileService.activateProvider`'s `joiners` array, which is awaited via `Promises.settled` (`src/vs/platform/files/common/fileService.ts:94-113`; `Promises.settled` implementation at `src/vs/base/common/async.ts:1835-1851` — confirmed it *does* rethrow the first rejection it sees). Because this catch swallows the error and never rethrows, the joined promise **always resolves**, so `Promises.settled` never learns registration failed, and `activateProvider` returns normally.

**What actually happens next**: `FileService.withProvider` (`fileService.ts:137-157`) then checks `this.provider.get(scheme)`; since registration failed, no provider was added, so it throws a generic:
```
ENOPRO: No file system provider found for resource '...'
```
This *is* an error the user/caller eventually sees (not a silent hang), but it's the **wrong** error — it discards the actual root cause (e.g., "scheme already registered," a `mainProcessService.getChannel` failure, or any other reason `registerProvider` threw) which is only visible in `logService.error`, invisible to the calling code and to any user-facing error surface.

**User impact**: A user attempting to paste/drag remote files into a window without its own remote connection would see a confusing generic "no provider found" error (if surfaced at all through the file operation's own error path) instead of a message indicating the cross-window proxy failed to set up — actively harder to debug than if the original error propagated.

**Recommendation**: Either don't catch here (let it propagate through `e.join`, so `Promises.settled` surfaces the real error to `activateProvider`'s caller with full context), or catch-log-and-rethrow:
```ts
} catch (error) {
    logService.error('RemoteFileSystemProxyClient: Failed to register proxy provider', error);
    throw error;
}
```

---

## 5. `RemoteFileSystemProxyMainHandler.getRendererChannel` — can hang forever instead of erroring (CRITICAL)

**Location**: `src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts:75-82`

```ts
private getRendererChannel(windowId: number): IChannel {
    return this.electronIpcServer.getChannel(
        REMOTE_FILE_SYSTEM_PROXY_CHANNEL_NAME,
        (client) => client.ctx === `window:${windowId}`,
    );
}
```

**Issue** (verified from base `IPCServer.getChannel`, `src/vs/base/parts/ipc/common/ipc.ts:891-917`): when called with a plain filter function (as here) rather than an `IClientRouter`, if no *currently connected* client matches the filter, `getChannel` does **not** throw — it falls back to:
```ts
connectionPromise = connection
    ? Promise.resolve(connection)
    : Event.toPromise(Event.filter(that.onDidAddConnection, routerOrClientFilter));
```
i.e., it waits indefinitely for a *future* connection matching `window:{id}` to appear. There is no timeout anywhere in this path.

Compare this to the existing, structurally identical sibling feature in this same codebase, `NodeRemoteResourceRouter.routeCall` (`src/vs/platform/remote/common/electronRemoteResources.ts:16-29`), which explicitly checks *current* connections only and fails fast:
```ts
const connection = hub.connections.find(c => c.ctx === uri.authority);
if (connection) { return connection; }
throw new Error(`Caller not found`);
```
The new handler deliberately does not reuse this established, fail-fast pattern.

**Why this is reachable, not just theoretical** `[Inference from verified source, timing scenario not empirically reproduced]`: `findWindowForAuthority` (line 65-73) matches against `window.remoteAuthority`, which — confirmed at `src/vs/platform/windows/electron-main/windowImpl.ts:638` — is `this._config?.remoteAuthority`, i.e., the window's **static launch configuration**, set at window creation, independent of whether the renderer has finished booting and actually registered its `RemoteFileSystemProxyServer` channel (which happens deep in `DesktopMain.open()`, `desktop.main.ts:290`, well after Electron `webContents` load and workbench service init). So a window can legitimately appear in `getWindows()` with the correct `remoteAuthority` before its proxy server channel exists — e.g., during multi-window session restore, or if a paste into a not-yet-fully-loaded remote window is attempted shortly after it opens.

**User impact**: In that window, `RemoteFileSystemProxyMainHandler.call` never throws `"No window found"` (a window *was* found) — it just hangs on `targetChannel.call(command, arg)` forever. No error, no log, no timeout — a paste/DND operation that just spins with no feedback and no way for the user or a developer to know why, which is a worse outcome than a swallowed exception.

**Recommendation**: Use an `IClientRouter` (mirroring `NodeRemoteResourceRouter`) that inspects only *current* connections and throws immediately if the target window's channel isn't registered yet, or add an explicit timeout/race against a "no connection within N seconds" rejection so failures surface instead of hanging silently.

---

## 6. `RemoteFileSystemProxyServer` / main handler `throw new Error(...)` paths — propagate correctly (no finding)

**Location**: `src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts:53-80`, `remoteFileSystemProxyMainHandler.ts:42-63`

Checked for completeness per the brief. These use plain `throw new Error(...)` with no surrounding try/catch, and rely on the standard `IPCServer`/`ChannelServer` error-marshaling path (`ipc.ts:388,429,624,748`), which is exercised throughout the codebase and correctly turns a thrown error into a rejected promise on the calling side. This part is fine — errors here are neither swallowed nor obscured, and the messages ("No provider for scheme", "Unsupported scheme", "No window found with remote authority") are reasonably specific. No action needed here; the hang described in #5 happens *before* any of these throw sites are reached.

---

## 7. `NativeClipboardService.plistToFiles` / `uriListToFiles` / `fileNameWToFile` — catch blocks log nothing at all (MEDIUM)

**Location**: `src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts:201-203`, `224-226`, `253-255`

```ts
} catch (error) {
    return []; // do not trust clipboard data
}
```
(and the `fileNameWToFile` variant with no `error` binding used, `253-255`)

**Issue**: All three new methods mirror the pre-existing `bufferToResources` convention (`clipboardService.ts:165-167`, unchanged by this PR) of catching broadly and returning `[]` with a "do not trust clipboard data" comment. That rationale is legitimate for genuinely untrusted, foreign-app-authored clipboard payloads — `uriListToFiles`'s `URI.parse(line)` can throw on malformed external URI-list text, and `fileNameWToFile`'s raw UTF-16LE decode can plausibly throw (`RangeError`, e.g. from `String.fromCharCode(...largeArray)` on an unbounded/non-null-terminated buffer, or from `Uint16Array` alignment) on malformed/oversized external clipboard buffers `[Inference — plausible from the code shape, not reproduced]`.

However, **`plistToFiles`'s catch is close to dead code for a different reason**: the operations inside its `try` (regex `exec` + `.replace()` calls) cannot realistically throw for any string input — the only way an exception reaches this catch is a genuine programmer bug (e.g., a future edit to the regex making `match[1]` optional, so `.replace()` is called on `undefined`). Right now, this catch's only real effect is to silently convert a hypothetical *programmer* bug into "clipboard had no files" — exactly the "genuine parse/encoding bug silently yields 'no files pasted' with no log" scenario the brief asks about.

More generally, **none of the three new methods log anything, even at `trace` level** — unlike the rest of this same PR (`RemoteFileSystemProxyClient` logs `trace`/`info`/`error` at every step, `ExplorerService` logs `warn` on its fallback). A regression here (e.g., "paste from Finder stopped working after an OS update changed the plist format slightly") would be indistinguishable, from logs alone, from "the user just didn't have anything on the clipboard."

**Recommendation**: Add a `trace`-level log in each catch (consistent with this class's own established logging discipline elsewhere), without changing the `return []` behavior for untrusted data:
```ts
} catch (error) {
    this.logService.trace('NativeClipboardService#plistToFiles: failed to parse clipboard plist', error);
    return [];
}
```
This is not a regression introduced by this PR (the pattern predates it in `bufferToResources`), but the PR triples the number of silent instances of it, and it's the most straightforward, in-place fix.

---

## Summary table

| # | Location | Severity | One-line issue |
|---|---|---|---|
| 1 | `explorerService.ts:287-327` (catch 317-323) | CRITICAL | Partial copy failure duplicates entries in the clipboard (local temp + original remote URI both present) |
| 2 | `explorerService.ts:321` | HIGH | Clipboard-copy degradation only logged at `warn`, no user-facing signal at all |
| 3 | `explorerService.ts:572-581` | CRITICAL | Literal empty catch block; violates project's explicit "never empty catch" rule; silently leaks copies of remote file content on disk |
| 4 | `remoteFileSystemProxyClient.ts:58-67` | HIGH | Catch swallows real registration failure; downstream error becomes a generic, misleading "no provider found" |
| 5 | `remoteFileSystemProxyMainHandler.ts:75-82` | CRITICAL | No-match filter falls back to `getChannel`'s indefinite wait-for-future-connection with no timeout; established sibling pattern (`NodeRemoteResourceRouter`) fails fast instead |
| 6 | `remoteFileSystemProxyServer.ts` / `remoteFileSystemProxyMainHandler.ts` throws | — (no finding) | Errors propagate correctly via standard IPC error marshaling |
| 7 | `clipboardService.ts:201-203, 224-226, 253-255` | MEDIUM | No logging at all (not even trace) in any of the three new clipboard-format parsers; `plistToFiles`'s catch is nearly dead code that would only ever hide a real programmer bug |

No test in the diff (`remoteFileSystemProxy.test.ts:391-468`) exercises the partial-failure duplication path, the empty-catch cleanup path, or the "window known but channel not yet registered" hang — all three are currently unguarded by any regression test.
