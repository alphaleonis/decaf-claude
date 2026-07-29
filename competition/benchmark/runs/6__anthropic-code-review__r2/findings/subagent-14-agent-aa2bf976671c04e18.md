# subagent agent-aa2bf976671c04e18

## Summary

PR #320685 was merged 2026-06-11, and after multiple rounds of regression reports it was fully reverted on 2026-06-29 (revert commit `26d36469b0`, PR #323490 — "TPI indicated more than normal regressions"). An earlier attempted revert (#321516) also landed 2026-06-15 citing the same TPI test pass (issue #321354). I traced the reported regressions back to the exact changed lines below using `gh api`/GraphQL blame, the `fileService.ts`/`ipc.ts` code the new files build on, and the real post-merge bug reports.

## Findings

**1. `clipboardService.ts` — `hasResources()`/`readResources()` broadening causes double-paste of natively-copied files**
File: `src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts`, lines 106–151 (`readResources()`, `hasResources()`).
Before this PR, both methods only ever consulted VS Code's own `FILE_FORMAT`. `src/vs/workbench/contrib/files/browser/views/explorerView.ts` (unchanged by this PR) has a DOM `paste` listener that already independently invokes `filesExplorer.paste` whenever the browser's native `clipboardData.files` is populated (i.e. whenever the OS clipboard holds real native files). Because `hasResources()`/`readResources()` now *also* recognize native OS clipboard formats (`MAC_FILE_FORMAT`/`LINUX_FILE_FORMAT`/`WINDOWS_FILE_FORMAT`), a single Ctrl+V/Cmd+V that used to hit only one of these two paste paths now hits both, each independently executing a real paste. This exactly matches the symptom reported in vscode-remote-release-linked issue https://github.com/microsoft/vscode/issues/321394 (Windows: "Paste" creates `File copy.txt`, then a confirmation dialog fires and a second paste creates `File copy 2.txt`), and is precisely what the emergency follow-up PR https://github.com/microsoft/vscode/pull/323002 tried to patch by adding `if (await this.clipboardService.hasResources()) return;` to that same DOM handler — a guard which itself later had to be reverted (https://github.com/microsoft/vscode/pull/323885) because it was still buggy. Issue https://github.com/microsoft/vscode/issues/321498 ("Linux SSH session file paste via keybinding causes false error notification... EEXIST... after successful keybinding paste") is consistent with the same double-dispatch pattern.

**2. `explorerService.ts` — unconditional remote→temp-file round-trip discards the file service's native same-provider copy path and breaks same-location paste**
File: `src/vs/workbench/contrib/files/browser/explorerService.ts`, lines 266–280 (`setToCopy`) and 287–327 (`resolveClipboardResources`).
`resolveClipboardResources` downloads *every* non-`file:` resource to a local temp dir and replaces it on the clipboard with a `file://` URI — even when source and paste target are the **same** remote authority (e.g. WSL→WSL, SSH→SSH). `src/vs/platform/files/common/fileService.ts:837` (`if (sourceProvider === targetProvider && hasFileFolderCopyCapability(sourceProvider))`) is an existing fast path that lets same-provider folder copies happen atomically, server-side. By interposing a local temp file, `sourceProvider` (local disk) is now always different from `targetProvider` (remote), so that fast path is permanently bypassed for what should be a pure remote-side copy, forcing every remote→remote copy through the generic recursive `doCopyFolder`/`doCopyFile` streaming path. This matches issue https://github.com/microsoft/vscode/issues/321498 (`EEXIST: file already exists, mkdir '.../nested'` on a same-remote-machine keybinding paste). Separately, the exact error text from issue https://github.com/microsoft/vscode/issues/321394 ("Unable to move/copy '...remote-clipboard\...' because target '...' already exists at destination") is the literal string thrown by `fileService.ts:941` when `overwrite=false` and the paste-target name-collision check (`findValidPasteFileTarget` in `fileActions.ts`, which walks the client-side Explorer model) fails to detect/avoid the conflict — a scenario introduced by routing the same-location paste through a stale local proxy instead of the original remote URI.

**3. `remoteFileSystemProxyMainHandler.ts` — `getRendererChannel()` can hang forever instead of failing fast, unlike the pattern it claims to follow**
File: `src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts`, lines 75–82.
```ts
private getRendererChannel(windowId: number): IChannel {
    return this.electronIpcServer.getChannel(
        REMOTE_FILE_SYSTEM_PROXY_CHANNEL_NAME,
        (client) => client.ctx === `window:${windowId}`,
    );
}
```
Per `IPCServer.getChannel` in `src/vs/base/parts/ipc/common/ipc.ts` (~line 899–907), passing a plain filter function (rather than an `IClientRouter`) causes the call to wait indefinitely for a *future* `onDidAddConnection` event if no client currently matches — it never rejects. The class's own doc comment says "This follows the same pattern as {@link ElectronRemoteResourceLoader}", but the actual analogous main-process router, `NodeRemoteResourceRouter` in `src/vs/platform/remote/common/electronRemoteResources.ts`, deliberately implements a custom `IClientRouter.routeCall` that does a one-shot lookup and **throws** `Caller not found` when no connection currently matches — specifically to avoid this open-ended wait. `RemoteFileSystemProxyMainHandler` deviates from that established, deliberate precedent. Combined with the fact that none of `RemoteFileSystemProxyClient`'s `stat`/`readdir`/`readFile` (`src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts`, lines 99–113) pass a `CancellationToken` through `channel.call(...)`, a request issued before the target window's `RemoteFileSystemProxyServer` has registered (e.g. during startup or right after a window reload) will hang silently forever with no error and no way to cancel it.

**4. `dnd.ts` — filtering `DataTransfers.TEXT` to `file:` only removes all plain-text drag payload for remote-only selections**
File: `src/vs/workbench/browser/dnd.ts`, lines 240–248.
```ts
// Text: allows to paste into text-capable areas
// Only include file:// URIs — remote URIs are not meaningful to
// native apps and macOS would create .webloc URL bookmark files
// when these are dragged to Finder.
const nativeResources = fileSystemResources.filter(({ resource }) => resource.scheme === Schemas.file);
if (nativeResources.length) {
    ...
    event.dataTransfer.setData(DataTransfers.TEXT, ...);
}
```
Before this PR (see blame: this block dates to PR #197809, "Aux window - allow to drag tabs/groups out to open in windows"), `DataTransfers.TEXT` was set unconditionally for *all* `fileSystemResources` regardless of scheme. A codebase-wide check confirms no VS Code-internal drop target (terminal, editor drop target, list/tree views) ever reads `DataTransfers.TEXT`/`text/plain` — it exists solely so dragging a file/tab out of VS Code onto an external, non-VS-Code text-capable surface (terminal apps, a browser address bar, chat apps, Notes) yields a usable path/label. The new guard, added to fix a real macOS Finder `.webloc`-file problem, is scoped far more broadly than that specific target: for a selection consisting entirely of `vscode-remote://` resources, `nativeResources.length` is 0 and **no** `DataTransfers.TEXT` is set at all, silently disabling the "paste into text-capable areas" behavior the comment on the same line describes, for every external target, not just Finder. (Contrast with the untouched `DOWNLOAD_URL` block a few lines below, which was already correctly scoped to just that one OS-materialization feature rather than to the general-purpose text payload.) I did not find a specific filed issue naming this exact regression, so this one is inference from code/behavior analysis rather than a directly-confirmed bug report — flagged with lower confidence than findings 1–3.

No other issues found in `app.ts`, `desktop.main.ts`, `remoteFileSystemProxy.ts`, or `remoteFileSystemProxyServer.ts` that are tied to specific historical regressions beyond what's covered above.
