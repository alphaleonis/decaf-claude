# subagent agent-a14a4c8f57c902b7c

## Performance Review — PR #320685 (cost at scale)

Scope: `src/vs/workbench/contrib/files/browser/explorerService.ts`, `src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts`, `src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts`, `src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts` (plus wiring files). Cross-referenced against `src/vs/platform/files/common/fileService.ts` (pre-existing, unchanged) to determine which code path each new provider actually exercises.

```json
[
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 308,
    "severity": "High",
    "category": "performance",
    "issue": "[PERF_HOT_PATH] resolveClipboardResources downloads every selected remote resource serially and unconditionally on every Ctrl+C/Cut, awaited synchronously by the copyFileHandler/cutFileHandler command (fileActions.ts:1059/1068) before the command returns. The for-loop (lines 308-316) awaits createFolder + fileService.copy one resource at a time with no Promise.all — for N selected top-level items, wall time is the SUM of each item's transfer time, not the max. Each remote folder in the selection is also recursively downloaded in full (via fileService.copy -> doCopyFolder) with no size/count cap or user confirmation, so copying a large remote directory (thousands of files, GBs) blocks the copy gesture until the entire tree has been pulled over the remote connection to local disk — work that is wasted entirely if paste never happens or the selection is superseded by a later copy (cleanupRemoteClipboardTempDir deletes the prior download before starting the next).",
    "fix": "Kick off downloads for all top-level resources concurrently (Promise.all/Promises.settled) instead of a sequential for-await loop, and consider deferring the download to paste-time (lazy) rather than copy-time so an unused/superseded copy doesn't pay the full transfer cost. At minimum, cap total size or prompt before downloading very large selections.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts",
    "line": 81,
    "severity": "High",
    "category": "performance",
    "issue": "[PERF_MEMORY] RemoteFileSystemProxyClient declares capabilities as FileReadWrite only (line 81-85), not FileOpenReadWriteClose. This forces fileService's copy dispatcher (fileService.ts doCopyFile) into doPipeUnbufferedToBuffered / doPipeUnbuffered, both of which call `sourceProvider.readFile(source)` to pull the ENTIRE file into one buffer before writing — no chunking, no size limit. The server side (remoteFileSystemProxyServer.ts:69-72) also reads the whole file into a single VSBuffer via fileService.readFile(). A file accessed cross-window through this proxy (the PR's core new use case: copy/paste or DND between a remote-connected window and a window without that direct remote connection) is therefore fully materialized in memory at least 3 times — source renderer, main-process IPC hop, target renderer — with no streaming fallback (no readFileStream command exposed on the proxy channel at all), unlike the direct-connection RemoteFileSystemProviderClient which streams in fixed BUFFER_SIZE chunks via FileOpenReadWriteClose. A multi-GB remote file (log, video, VM image, dataset) dragged/copied through this path spikes memory in two separate processes simultaneously and has no upper bound.",
    "fix": "Implement FileOpenReadWriteClose (open/read/close) on RemoteFileSystemProxyClient and add matching open/read/close commands to RemoteFileSystemProxyServer/MainHandler so transfers go through the existing chunked doPipeBuffered path instead of whole-buffer readFile; alternatively add a size guard that rejects or warns before proxying files above a threshold.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- `doCopyFolder` recursion in `fileService.ts` (pre-existing, unchanged) already parallelizes sibling copies via `Promises.settled` at each directory level — the algorithmic shape of a single folder's recursive copy is fine; the cost findings above are about the *outer* loop across top-level selected items (serial) and the *transport* used per file (unbuffered), both of which are new in this diff.
- `clipboardService.ts` regex/string-building helpers (`plistToFiles`, `uriListToFiles`, `filesToPlist`, `fileNameWToFile`) operate on clipboard payloads sized by *number of copied paths*, not file content — realistic selections are tens to low hundreds of entries. Linear-time regex/string ops on that scale are not a felt cost. Anchor 25, suppressed.
- `resolveClipboardResources`'s two passes over `resources` (filter + for-loop) to separate local vs. remote resources — O(n) on selection size, trivial. Anchor 0.
- `remoteClipboardTempDir` bookkeeping — only one temp dir is tracked at a time and is cleaned up before each new download and on dispose, so this does not accumulate unboundedly across repeated copies in a long-lived window. Anchor 0.
- Potential race between rapid successive Ctrl+C presses (`cleanupRemoteClipboardTempDir` deleting a dir that a still-in-flight download is writing into) is a correctness/race concern, not a cost-at-scale one — out of scope for this persona (adversarial-reviewer/quick-reviewer territory).
- `dnd.ts` filtering of `fileSystemResources` to `Schemas.file` before building the text drag payload — O(n) filter on drag selection size, no I/O, not scale-relevant. Anchor 0.

### Probe Requests

None — all findings are verifiable statically from the code paths traced above (explorerService.ts loop shape; fileService.ts dispatcher branching on provider capabilities; proxy client's declared capabilities). No execution needed to settle either finding.
