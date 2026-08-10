# subagent agent-ac1b1a1dbb3403f0f

## Adversarial Review

### Summary
This PR bolts three loosely-coupled subsystems together (a cross-window remote-file IPC proxy, native OS clipboard formats, and remote→temp download on copy) and the seams between them are where it breaks. The dominant class of defect is lifecycle: temp files backing the OS clipboard are deleted out from under a clipboard that still points at them, and there is no cleanup on crash, no size ceiling on what gets read into memory over IPC, and no authorization boundary on the proxy. The happy path works; composition, teardown, and abuse do not.

### Findings

#### High

- **[other]** OS clipboard is left pointing at a temp dir that gets deleted on window close / next copy — `src/vs/workbench/contrib/files/browser/explorerService.ts:275,567`
  - **What's wrong/missing:** `resolveClipboardResources` downloads remote files to `cacheHome/remote-clipboard/<uuid>/…`, writes those `file://` temp paths onto the *native OS clipboard* (via `clipboardService.writeResources` → `NSFilenamesPboardType`/`text/uri-list`/`FileNameW`), and records the dir in `remoteClipboardTempDir`. `dispose()` (line 567) and the next remote copy (line 302) both `del(..., {recursive:true})` that dir. The OS clipboard is process- and lifetime-independent of VS Code — it still references the now-deleted paths. Sequence: copy remote file → close that VS Code window → paste into Finder/Explorer/another app → the files are gone. VS Code's own paste is equally affected: `fileActions.ts:1318` (`getFilesToPaste`) calls `readResources()` and copies from those temp URIs.
  - **Why it matters:** Silent data-loss on paste. The user copied something, the clipboard says it has files, and paste yields nothing or errors — with no indication why.
  - **Fix:** Don't delete the temp dir while it may still be the live clipboard payload. Options: keep the last N temp dirs and sweep by age instead of deleting eagerly on the next copy; on dispose, only delete if this window is not the current clipboard owner; or copy into an OS-managed temp location with its own retention. At minimum, don't clean on window close.
  - **Confidence:** 82/100

- **[other]** Unbounded remote `readFile` into memory, then across two IPC hops — `src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts:69`
  - **What's wrong/missing:** The proxy provider declares only `FileReadWrite` capability (client, `capabilities` getter) — no `FileReadStream`, no `FileFolderCopy`. So `explorerService`'s `fileService.copy(remoteResource, target)` (line 314) resolves to a buffered `readFile`. `RemoteFileSystemProxyServer.readFile` (line 70) does `fileService.readFile(uri)` with no size option and returns the whole `content.value` `VSBuffer`, which is then serialized target-renderer → main → requesting-renderer. A multi-hundred-MB or GB remote file is fully materialized in memory three times and pushed through the IPC message channel. There is no size limit, no streaming, no `FileOperationError.FILE_TOO_LARGE` guard.
  - **Why it matters:** Copying a large remote file OOM-crashes the renderer (or blows the IPC frame). Users copy folders/large binaries routinely; this is a foreseeable production crash, not an edge case.
  - **Fix:** Enforce a size cap (reject or fall back to remote-URI paste above a threshold) and/or implement streaming read (`readFileStream`) through the proxy. Surface `FILE_TOO_LARGE` rather than crashing.
  - **Confidence:** 80/100

- **[authz]** No authorization boundary on the proxy handler — any renderer can read any file on any connected remote — `src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts:42`
  - **What's wrong/missing:** `call()` accepts a `vscode-remote://<authority>/<path>` from *any* window holding the handler channel, resolves *any* window whose `remoteAuthority` matches, and forwards `stat/readdir/readFile/exists/resolve`. There is no check that the *requesting* window has any relationship to (or trust for) that remote. A window opened on an untrusted local workspace (or a compromised/extension-driven renderer) can craft `vscode-remote://<victim-authority>/etc/passwd` and exfiltrate arbitrary files from another window's privileged remote connection.
  - **Why it matters:** Crosses a workspace/remote trust boundary that the rest of VS Code takes seriously (workspace trust, remote isolation). [Surfaced per governance as an adjacent harm; security-reviewer owns the exploit depth, but the *missing control* is the gap here.]
  - **Fix:** Scope access — e.g., only route when the requesting window shares the authority, or gate the capability behind workspace trust / an explicit opt-in. At minimum document the threat model and why same-user cross-window read is considered acceptable.
  - **Confidence:** 78/100

#### Medium

- **[other]** Temp files never cleaned on crash; `dispose()` cleanup is fire-and-forget — `src/vs/workbench/contrib/files/browser/explorerService.ts:567,572`
  - **What's wrong/missing:** `remote-clipboard` temp dirs are only removed by (a) the next copy that includes remote resources or (b) `dispose()`. `dispose()` calls `this.cleanupRemoteClipboardTempDir()` without `await` (it returns `void`), so on window shutdown the async `del` likely does not complete. On crash/kill nothing runs at all. There is no startup sweep of `cacheHome/remote-clipboard/*` (confirmed: only reference to that path is the writer). Copy-remote-then-copy-local also leaks, because the local-only branch never triggers cleanup (`remoteResources.length === 0`).
  - **Why it matters:** Unbounded disk growth under the user cache dir across sessions and crashes, with no visibility and no reclamation.
  - **Fix:** Sweep stale `remote-clipboard/*` on startup (by age), and make shutdown cleanup best-effort-synchronous or rely on the startup sweep instead of dispose.
  - **Confidence:** 80/100

- **[other]** Partial-download fallback pushes duplicate + mixed temp/remote URIs — `src/vs/workbench/contrib/files/browser/explorerService.ts:322`
  - **What's wrong/missing:** In the remote loop, each successful `copy` pushes its temp `target` to `result`. If a later file's `copy` throws, the `catch` does `result.push(...remoteResources)` — re-adding *all* originals, including ones already copied. Result becomes `[locals…, temp(file1), remoteFile1, remoteFile2]`: file1 appears twice (once as temp, once as remote), and the clipboard ends up a mix of local temp and remote URIs. Since it's no longer `allLocal`, `writeResources` falls to `code/file-list` — so even the successfully-downloaded native paste is lost, and duplicates get pasted.
  - **Why it matters:** Duplicated/inconsistent paste results from a single failed file in a multi-file copy. [Overlaps silent-failure-hunter's "dangerous fallback" lane.]
  - **Fix:** On failure, either discard partial temp results and fall back cleanly to the full original remote set, or push only the *not-yet-copied* originals. Don't mix.
  - **Confidence:** 78/100

- **[observability]** No telemetry/metrics for remote-clipboard download — operational blindness — `src/vs/workbench/contrib/files/browser/explorerService.ts:287`
  - **What's wrong/missing:** The only signals are `logService.warn` on total failure and `trace`-level per-call logging in the proxy client. There is no counter/metric for how often remote download runs, bytes downloaded, failure rate, or temp-dir footprint. When a user reports "paste from remote doesn't work," there is nothing in production to distinguish download failure, proxy routing failure, or dangling-temp cleanup.
  - **Why it matters:** A new cross-process, cross-window data path ships with no way to tell if it's working in the field.
  - **Fix:** Add telemetry around download attempts/outcomes/sizes and proxy-routing failures (respecting existing telemetry conventions/consent).
  - **Confidence:** 76/100

- **[other]** No feature flag / kill switch for the proxy or native-clipboard writes — `src/vs/workbench/electron-browser/desktop.main.ts:289`, `src/vs/code/electron-main/app.ts:1306`
  - **What's wrong/missing:** The main-process handler channel, the per-window server, the proxy client, and the new native-clipboard write formats are all wired in unconditionally. There is no setting/EXP gate to disable them — contrast the sibling commit `826d1e76a3` which gates a far less risky feature behind `chat.*.preferAgentHost` EXP settings. If routing, endianness, or the dangling-temp issue misbehaves in production, there is no rollback short of a full revert.
  - **Why it matters:** A cross-window file-read capability + OS-clipboard behavior change with no runtime off-switch is hard to de-risk operationally.
  - **Fix:** Put the cross-window proxy and/or native-clipboard writes behind a config/EXP flag defaulting on, so it can be disabled without a client update.
  - **Confidence:** 68/100 *(judgment call — VS Code does ship features ungated; excluded from JSON)*

#### Low

- **[other]** Native OS clipboard write now applies to *all* `writeResources([localFile])` callers, not just explorer copy — `src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts:63`. Chat widgets (`chatInlineAnchorWidget.ts:405`, `chatReferencesContentPart.ts:579`) copy a single local file reference; post-change, that now populates the *native* file clipboard (Finder/Explorer will offer to paste the file). Previously these only wrote the internal `code/file-list`. Broadened blast radius / possible user surprise; not obviously wrong but untracked. Confidence 66/100.
- **[edge-case]** Re-entrant `setToCopy` races on the single `remoteClipboardTempDir` field — a second copy's `cleanupRemoteClipboardTempDir()` can `del` the dir the first, still-running copy is writing into. No serialization. Confidence 60/100 (edge-case-hunter lane).
- **[docs]** Windows multi-file copy silently has no native paste (`resources.length === 1` gate, line ~703) — documented in a code comment but there is no user-facing signal that pasting multiple files into Explorer won't work. Confidence 62/100.
- **[edge-case]** Target window's `RemoteFileSystemProxyServer` channel may not be registered yet when the main handler routes to it during startup — `getRendererChannel` will find the window (its `remoteAuthority` is known to main early) but the `call` rejects with an unknown-channel error until the renderer finishes `DesktopMain` init. No retry/readiness wait. Confidence 55/100.
- **[edge-case]** `fileNameWToFile` (clipboardService, ~line 856) constructs `new Uint16Array(buffer.buffer.buffer, byteOffset, …)`, which throws `RangeError` on an odd `byteOffset`; the `catch` swallows it and returns `[]`, so a misaligned buffer silently yields "no files" on paste. Windows-only, LE-only path. Confidence 52/100.

### Most Critical Gap
The clipboard/temp-dir lifecycle: VS Code writes deleted-able temp paths onto the OS clipboard and then deletes those temp dirs on window close or the next copy, so pasting after the source window closes silently loses the files. Fix the retention model before merge — decoupling temp-dir deletion from window/copy lifecycle is the load-bearing change.

### Positive Observations
- The proxy handler correctly restricts routing to `vscode-remote://` and rejects other authority-bearing schemes (UNC), with a test for it.
- Clipboard read paths are defensively wrapped and return `[]` on parse failure ("do not trust clipboard data").
- The download-failure path degrades to remote-URI paste (cross-window still works via the proxy), and the loop file-per-subfolder design avoids `index.ts`-style name collisions.
- The proxy client explicitly avoids the self-routing loop by not registering in windows that own a remote connection, with a clear rationale comment.

```json-findings
[
  {"severity":"High","confidence":82,"category":"other","file":"src/vs/workbench/contrib/files/browser/explorerService.ts","line":567,"finding":"Remote files are downloaded to a temp dir whose file:// paths are written to the native OS clipboard, but that dir is deleted on window dispose() and on the next remote copy while the OS clipboard still references it — pasting into a native app or another VS Code window after the source window closes silently loses the files.","remediation":"Decouple temp-dir deletion from window/copy lifecycle: retain recent temp dirs and sweep by age, or only delete when this window is not the current clipboard owner. Do not clean on window close.","source":"adversarial-general"},
  {"severity":"High","confidence":80,"category":"other","file":"src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts","line":69,"finding":"Proxy readFile reads the entire remote file into memory (no size limit, no streaming; provider declares only FileReadWrite) and serializes it across two IPC hops; copying a large remote file materializes it three times and can OOM the renderer or exceed IPC frame limits.","remediation":"Enforce a max-size guard (fall back to remote-URI paste above threshold) and/or implement streaming reads through the proxy; surface FILE_TOO_LARGE instead of crashing.","source":"adversarial-general"},
  {"severity":"High","confidence":78,"category":"authz","file":"src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts","line":42,"finding":"The main-process proxy handler routes stat/readdir/readFile from any renderer to any window matching the URI authority with no check that the requesting window is entitled to that remote; a window on an untrusted local workspace can craft vscode-remote://<victim-authority>/path to read arbitrary files from another window's privileged remote connection.","remediation":"Scope access to windows sharing the authority or gate behind workspace trust / explicit opt-in; at minimum document and justify the same-user cross-window read threat model.","source":"adversarial-general"},
  {"severity":"Medium","confidence":80,"category":"other","file":"src/vs/workbench/contrib/files/browser/explorerService.ts","line":572,"finding":"Temp remote-clipboard dirs are never swept on crash and dispose() calls the async cleanup without awaiting it; copy-remote-then-copy-local also never triggers cleanup, so temp dirs leak indefinitely under cacheHome with no reclamation.","remediation":"Add a startup sweep of cacheHome/remote-clipboard/* by age and rely on it rather than fire-and-forget dispose cleanup.","source":"adversarial-general"},
  {"severity":"Medium","confidence":78,"category":"other","file":"src/vs/workbench/contrib/files/browser/explorerService.ts","line":322,"finding":"When a file's copy throws mid-loop, the catch does result.push(...remoteResources), re-adding already-copied originals; the clipboard ends up with duplicate entries (temp + remote for the same file) and a mixed local/remote set that loses native paste for the files that did download.","remediation":"On failure discard partial temp results and fall back to the full original remote set, or push only the not-yet-copied originals; never mix temp and remote for the same file.","source":"adversarial-general"},
  {"severity":"Medium","confidence":76,"category":"observability","file":"src/vs/workbench/contrib/files/browser/explorerService.ts","line":287,"finding":"The new remote-download/proxy data path emits only warn-on-failure and trace logs — no telemetry for download frequency, size, failure rate, or proxy-routing failures — leaving no way to tell in production whether remote clipboard copy/paste is working.","remediation":"Add telemetry around download attempts/outcomes/sizes and proxy routing failures, following existing telemetry consent conventions.","source":"adversarial-general"}
]
```
