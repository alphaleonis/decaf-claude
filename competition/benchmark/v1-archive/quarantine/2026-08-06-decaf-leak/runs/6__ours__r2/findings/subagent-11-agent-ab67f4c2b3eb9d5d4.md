# subagent agent-ab67f4c2b3eb9d5d4

Confirmed: this is a brand-new file entirely introduced by the PR (not pre-existing code), so the finding is correctly attributed as new.

All four load-bearing claims are verified directly against the code:

1. **`activateProvider` fires unconditionally before the `has()` check** — `src/vs/platform/files/common/fileService.ts:94-108`. The `_onWillActivateFileSystemProvider.fire(...)` call happens at line 99, and only afterward (line 106) does it check `this.provider.has(scheme)` to short-circuit. The fire is unconditional on every call.

2. **`withProvider`/`withReadProvider` call `activateProvider` on essentially every operation** — `withProvider` (line 137) calls `await this.activateProvider(resource.scheme)` at line 145, and is invoked from `stat`, `readFile`, `readdir`, `copy`, etc. (lines 210, 314, 322, 334, 971, 1044, 1115, 1219, plus via `withReadProvider` at 159-160 used at 541, 581, 777, 804).

3. **`registerProvider` throws on duplicate scheme** — `fileService.ts:52-54`: `if (this.provider.has(scheme)) { throw new Error(...) }`.

4. **The `register()` callback re-creates and re-registers on every firing, with `disposables.add(provider)` executing before the throwing `registerProvider` call, and no memoization** — `remoteFileSystemProxyClient.ts:56-69` (matches the cited anchor exactly). Line 60 creates a new `RemoteFileSystemProxyClient` every time the listener fires; line 61 `disposables.add(provider)` unconditionally adds it to the outer, window-lifetime `DisposableStore` *before* line 62's `fileService.registerProvider(...)` call, which throws on the second and all subsequent firings; the throw is caught at line 64-65 and merely logged via `logService.error`. There is no promise/flag stored outside the listener to short-circuit repeat firings.

5. **Sibling `RemoteFileSystemProviderClient.register()` does memoize** — `src/vs/workbench/services/remote/common/remoteFileSystemProviderClient.ts:28-48`: `environmentPromise` is built once, outside and above the `onWillActivateFileSystemProvider` listener (lines 29-40), and the listener (lines 42-46) only does `e.join(environmentPromise)` — the actual registration work runs exactly once regardless of how many times the event fires.

Given `activateProvider` fires the event unconditionally on every `withProvider`/`withReadProvider` call, and those are invoked on essentially every file operation against a `vscode-remote` resource in a window without its own direct remote connection, each such operation after the first triggers: construct a new `RemoteFileSystemProxyClient` (with its own `Emitter`), permanently add it to the window-lifetime `DisposableStore`, attempt `registerProvider` which throws, and log a spurious error — exactly as claimed. This is a genuine unbounded resource leak plus log spam, not a one-time cost.

```json
{
  "finding": "#pending",
  "verdict": "confirmed",
  "reason": "Directly re-derived from code: fileService.ts:99 fires onWillActivateFileSystemProvider unconditionally before the has(scheme) short-circuit at line 106; withProvider/withReadProvider (lines 137-166) call activateProvider on every stat/readFile/readdir/copy call; registerProvider (lines 52-54) throws on a duplicate scheme; and remoteFileSystemProxyClient.ts:56-69 constructs a new RemoteFileSystemProxyClient and disposables.add(provider) on every firing (line 60-61) before the throwing registerProvider call (line 62), with no memoized promise outside the listener -- contrasted correctly against remoteFileSystemProviderClient.ts:28-48 which builds environmentPromise once outside the listener and only e.join()s it on each firing.",
  "corrections": {
    "line": "56-69 (anchor is exact, matches the full `disposables.add(fileService.onWillActivateFileSystemProvider(...))` block)",
    "pre_existing": false
  }
}
```
