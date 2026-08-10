# subagent agent-af89912481a3f2eac

## Summary

**PR #320685: Improve the local to native and remote to local copy, paste, and DND experience**

This PR enhances the copy, paste, and drag-and-drop (DND) experience for VS Code's remote connections. It fixes issue microsoft/vscode-remote-release#2008 by extending the remote file system proxy infrastructure to better handle clipboard and drag-and-drop operations between local and remote systems. The changes add new protocol methods for proxying clipboard and DND data, implement client-server handlers for these operations, and update the UI layer (drag-and-drop and explorer services) to use the new proxying capabilities.

---

## Files Changed (10 files)

| File | Additions | Deletions |
|------|-----------|-----------|
| src/vs/code/electron-main/app.ts | 6 | 0 |
| src/vs/platform/files/common/remoteFileSystemProxy.ts | 18 | 0 |
| src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts | 134 | 0 |
| src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts | 81 | 0 |
| src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts | 83 | 0 |
| src/vs/platform/files/test/electron-main/remoteFileSystemProxy.test.ts | 98 | 0 |
| src/vs/workbench/browser/dnd.ts | 8 | 2 |
| src/vs/workbench/contrib/files/browser/explorerService.ts | 77 | 3 |
| src/vs/workbench/electron-browser/desktop.main.ts | 8 | 0 |
| src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts | 175 | 8 |

**Total:** 688 additions, 13 deletions

---

## PR Head Commit SHA

`6b744d6d73a2ec2a121ccdc1c7225b3bd1652588`
