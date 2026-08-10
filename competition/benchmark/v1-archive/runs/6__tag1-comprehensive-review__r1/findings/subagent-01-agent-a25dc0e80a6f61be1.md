# subagent agent-a25dc0e80a6f61be1

## Summary

Adds a cross-window remote-file-system proxy (main-process router plus per-renderer client/server IPC channels) so a window without a direct remote connection can read files owned by another window's remote connection, and reworks native clipboard/DND handling so remote files are downloaded to a local temp location and written in platform-native clipboard formats (macOS `NSFilenamesPboardType` plist, Linux `text/uri-list`, Windows `FileNameW`) instead of only VS Code's internal format. This fixes copy/paste and drag-and-drop of files between remote (SSH/WSL) workspaces and the native OS file manager/desktop, tracked as microsoft/vscode-remote-release#2008.

**Type:** feature
**Effort:** 4/5 — new IPC subsystem (main-process routing handler + per-window read-only proxy provider/server) plus hand-rolled platform-specific clipboard format encode/decode (plist XML, UTF-16LE, uri-list) across 10 files, ~690 net lines including new unit tests; self-contained to the copy/paste/DND path but touches process-boundary wiring in `app.ts` and `desktop.main.ts`.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts | Modified | Adds native OS clipboard file formats (macOS plist, Linux uri-list, Windows FileNameW) for read/write/hasResources, with fallback to VS Code's custom format |
| src/vs/workbench/contrib/files/browser/explorerService.ts | Modified | On copy, downloads remote resources into a per-copy temp dir (cleaned up on next copy/dispose) so remote files paste as local `file://` copies |
| src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts | Added | Read-only `vscode-remote://` file system provider registered only in windows lacking a direct remote connection; proxies stat/readdir/readFile through the main process |
| src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts | Added | Main-process `IServerChannel` that finds the renderer window whose remote authority matches the URI and forwards the call to that window's proxy server channel |
| src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts | Added | Per-renderer server channel exposing stat/readdir/readFile/exists/resolve backed by that window's `IFileService` |
| src/vs/platform/files/test/electron-main/remoteFileSystemProxy.test.ts | Added | Unit tests for `RemoteFileSystemProxyMainHandler` routing: unknown authority, unsupported scheme, correct-window dispatch |
| src/vs/platform/files/common/remoteFileSystemProxy.ts | Added | Shared IPC channel name constants for the proxy client/server and main handler |
| src/vs/workbench/electron-browser/desktop.main.ts | Modified | Registers `RemoteFileSystemProxyServer` and `RemoteFileSystemProxyClient` per renderer window on startup |
| src/vs/code/electron-main/app.ts | Modified | Registers `RemoteFileSystemProxyMainHandler` as a main-process IPC channel |
| src/vs/workbench/browser/dnd.ts | Modified | Native text drag transfer now only includes `file://` resources, avoiding macOS `.webloc` bookmarks for remote/non-file URIs |

## Related Issues & PRs

<!-- issue-linker output will be merged here — the orchestrator replaces this placeholder -->
