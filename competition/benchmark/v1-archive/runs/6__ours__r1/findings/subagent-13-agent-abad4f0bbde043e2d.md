# subagent agent-abad4f0bbde043e2d

Depth: deep — new cross-process IPC proxy layer + clipboard rewrite + explorer temp-file lifecycle, well over 200 executable lines, touching data mutation (temp copy/delete) and external IPC integration. All four techniques applied; mechanisms verified against `fileService.ts` (activation fires before the already-registered check), `ipc.ts` (`getChannel` clientFilter waits on `onDidAddConnection` with no timeout), and the paste consumer in `fileActions.ts`.

```json
[
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 568,
    "severity": "High",
    "category": "resource-management",
    "issue": "[ADV_CASCADE] Copy remote file → temp copy backs OS clipboard → window reload/close fires dispose()→cleanupRemoteClipboardTempDir() deletes the temp dir → user pastes in Finder/Explorer/another window → clipboard points at deleted file → paste silently copies nothing.",
    "fix": "Do not delete the temp dir on dispose (the OS clipboard outlives the process). Clean up on a schedule/age-out or on next copy only, or write remote-source URIs (not temp paths) into the code format so cross-window paste survives cleanup. At minimum, gate cleanup on 'am I still the clipboard owner'.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts",
    "line": 58,
    "severity": "Medium",
    "category": "resource-management",
    "issue": "[ADV_ABUSE] FileService.activateProvider fires onWillActivateFileSystemProvider BEFORE its 'already registered' early-return (fileService.ts:99 vs 106); the client's listener calls registerProvider on EVERY activation, which throws on duplicate (fileService.ts:53). Copying a remote folder → stat+readdir+readFile per entry → each vscode-remote op re-fires → one caught ERROR log + one leaked RemoteFileSystemProxyClient (added to the store, never disposed until window teardown) per operation → thousands of ERROR logs and leaked provider objects for a large-folder copy.",
    "fix": "Register the proxy provider exactly once (guard with fileService.hasProvider(vscode-remote) or a local 'registered' flag; register eagerly at startup instead of per-activation), so repeated activations are no-ops.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts",
    "line": 75,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_CASCADE] findWindowForAuthority selects a window from getWindows(), but getRendererChannel calls electronIpcServer.getChannel(name, ctx==='window:{id}'); when no connection currently matches (target window reloading, or closed after selection — TOCTOU), ipc.ts:907 does Event.toPromise(Event.filter(onDidAddConnection,...)) with NO timeout, so the forwarded call hangs indefinitely. No CancellationToken is passed by the client, so the awaiting stat/readFile in the local window cannot be canceled → copy/paste spinner stuck forever. Routing also picks the FIRST matching window and never falls back to a healthy sibling with the same authority.",
    "fix": "Only route to a window whose IPC connection is currently present; if none, throw fast instead of waiting. Add a timeout to the forwarded call and thread a CancellationToken from the provider through channel.call. When multiple windows share an authority, iterate to a live one.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 322,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_COMPOSITION] Copy [remote1, remote2]; remote1 downloads to temp t1 (pushed), remote2's fileService.copy throws → catch does result.push(...remoteResources), pushing BOTH originals. result = [t1, remote1, remote2]: remote1 now appears twice (temp copy + original remote URI) and t1's temp folder is orphaned. writeResources sees a non-all-local list → code/file-list → cross-window paste yields a duplicated remote1 plus a wasted temp copy.",
    "fix": "On partial failure push only the originals that were not already successfully downloaded (track per-resource success), or fail the whole batch to remote URIs atomically. Delete the just-created temp dir when falling back.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 302,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_ABUSE] Two overlapping setToCopy calls (rapid Ctrl+C while a large remote download is in flight — nothing serializes them) race on shared this.remoteClipboardTempDir. Copy#1 sets field=A and starts copying into A; Copy#2's cleanupRemoteClipboardTempDir() reads field=A and del(A, recursive) while Copy#1 is still writing into A → Copy#1's copy throws → falls back to remote URIs → Copy#1 (the EARLIER copy) writes the clipboard LAST → clipboard holds remote1 though the user's last action copied remote2. Wrong file pasted; dir B orphaned.",
    "fix": "Serialize setToCopy (queue/mutex) or scope each invocation to its own local temp dir variable rather than a shared field, and only delete dirs owned by the current invocation.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts",
    "line": 133,
    "severity": "Low",
    "category": "other",
    "issue": "[ADV_COMPOSITION] hasResources() returns true whenever a platform-native format is present (e.g. Linux text/uri-list set by copying a hyperlink in a browser, or a mac/win native buffer), but readResources() filters uri-list/plist strictly to file:// scheme. Copy a browser link → hasResources()=true → explorer 'Paste' enabled (fileCopiedContextKey) → readResources()=[] → paste is a silent no-op.",
    "fix": "Make hasResources() apply the same file:// validity check as readResources() (or have it call a shared 'has any pasteable file resource' predicate) so the enabled state matches actual content.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Two windows with the SAME remote authority (routing picks first)** — both connect to the same remote FS, so reading via either yields identical bytes; no correctness divergence. The only harm (first window reloading while a healthy sibling exists) is folded into the getChannel-hang finding as an amplifier.
- **Windows multi-file native paste (N>1) silently dropped** — falls through to the `code/file-list` format, so data is preserved for VS Code paste; only native-Explorer paste of >1 file is unsupported, which the author documents (CF_HDROP limitation). No data loss, no regression.
- **mac plist XML escape/unescape asymmetry** — traced a filename containing literal `&lt;`: writer escapes `&`→`&amp;` first, reader unescapes `&lt;`/`&gt;` before `&amp;`; round-trips correctly. No bug.
- **UTF-16LE surrogate pairs (emoji in path)** — `charCodeAt`/`fromCharCode` operate on UTF-16 code units and `path.length` counts code units, so non-BMP chars survive the FileNameW round trip. No bug.
- **readFile loads whole remote file into memory then ships renderer→main→renderer** — copying a multi-GB remote file could spike memory across three processes, but the threshold is unpinned and it's inherent to the FileReadWrite-only capability; speculative (anchor 25).
- **dnd.ts: remote-only drag now sets no DataTransfers.TEXT** — behavior change (dragging a remote file to a text area yields no path text), but it is the stated intent of the PR (avoid macOS `.webloc` bookmarks) and internal DnD uses CodeDataTransfers, not TEXT. Intended, not a defect.

### Probe Requests
- Run `src/vs/platform/files/test/electron-main/remoteFileSystemProxy.test.ts` plus a new test that calls `getChannel` with a filter matching no current connection, to confirm the forwarded call hangs (no timeout) — settles Finding B's confidence.
- Instrument a local-window remote-folder copy and count `onWillActivateFileSystemProvider(vscode-remote)` fires vs. `registerProvider` throws — settles Finding C's per-operation amplification.
