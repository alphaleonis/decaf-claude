# subagent agent-a84b88721e3ffa501

## Summary

Adds a remote file system proxy IPC path (per-renderer server channel + main-process router + read-only client provider) so a window without its own remote connection can read `vscode-remote://` files owned by another window, and uses it to make cross-window/native copy-paste and drag-and-drop of remote files work: the Explorer now downloads remote files to a temp dir on copy, the clipboard service writes/reads platform-native file formats (macOS `NSFilenamesPboardType` plist, Linux `text/uri-list`, Windows `FileNameW`) instead of only VS Code's custom format, and DnD text-transfer data is filtered to `file://` URIs to avoid macOS creating `.webloc` bookmarks for remote paths. Addresses microsoft/vscode-remote-release#2008.

**Type:** Feature
**Effort:** 4/5 — new cross-process IPC subsystem (3 new platform files + wiring in `app.ts`/`desktop.main.ts`) plus native clipboard-format encode/decode logic across 3 platforms in `clipboardService.ts`; ~688 lines across 10 files, moderate per-line complexity but touches main process, renderer bootstrap, explorer, clipboard, and DnD.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts | Added | Read-only `IFileSystemProviderWithFileReadWriteCapability` that proxies `vscode-remote://` stat/readdir/readFile calls through the main process; self-registers only when the window has no direct remote connection |
| src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts | Added | Main-process `IServerChannel` that finds the renderer window whose `remoteAuthority` matches the requested URI and forwards the call to that window's proxy server channel |
| src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts | Added | Per-renderer `IServerChannel` exposing `stat`/`readdir`/`readFile`/`exists`/`resolve` against the local `IFileService`, consumed by other windows via the main handler |
| src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts | Modified | Writes/reads platform-native file clipboard formats (macOS plist, Linux `text/uri-list`, Windows `FileNameW`) alongside the existing `code/file-list` format, with fallback parsing |
| src/vs/workbench/contrib/files/browser/explorerService.ts | Modified | On copy, downloads remote resources to a per-copy temp directory under `cacheHome` and substitutes local `file://` URIs so native paste works; cleans up the temp dir on next copy/dispose |
| src/vs/platform/files/test/electron-main/remoteFileSystemProxy.test.ts | Added | Unit tests for `RemoteFileSystemProxyMainHandler`: no-window-match error, non-`vscode-remote` scheme rejection, correct window routing by authority |
| src/vs/code/electron-main/app.ts | Modified | Registers `RemoteFileSystemProxyMainHandler` on the main process IPC server under `REMOTE_FILE_SYSTEM_PROXY_HANDLER_CHANNEL_NAME` |
| src/vs/workbench/electron-browser/desktop.main.ts | Modified | Instantiates `RemoteFileSystemProxyServer` and registers `RemoteFileSystemProxyClient` during renderer bootstrap |
| src/vs/platform/files/common/remoteFileSystemProxy.ts | Added | Declares the two shared IPC channel name constants used by the client/server/main-handler trio |
| src/vs/workbench/browser/dnd.ts | Modified | Restricts the plain-text DnD transfer payload to `file://` resources, dropping remote URIs to prevent macOS `.webloc` bookmark creation on Finder drop |

## Related Issues & PRs

<!-- issue-linker output will be merged here — the orchestrator replaces this placeholder -->
