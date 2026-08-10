# subagent agent-a16c1bd48a7e534ce

I've read the complete diff. I have everything needed to audit the error handling without touching the local repo. Here are my complete findings.

---

# Error-Handling Audit — microsoft/vscode#320685

Scope: silent failures, inadequate error handling, inappropriate fallbacks in the remote-file-system-proxy / clipboard / DND changes. File paths are absolute to the vscode source tree; line references are to the post-diff files (for new files) or to the diff hunks (for modified files).

---

## CRITICAL / HIGH

### 1. `resolveClipboardResources` fallback produces duplicate + reordered clipboard entries and hides a partial failure
**File:** `src/vs/workbench/contrib/files/browser/explorerService.ts` — `resolveClipboardResources`, diff lines 556–596 (the `catch` at 586–592).
**Severity:** HIGH

**What is swallowed/degraded:** The remote-download loop is wrapped in a single coarse `try/catch`. On any failure mid-loop, the catch does `result.push(...remoteResources)` — pushing **all** original remote URIs, including the ones that were *already successfully downloaded* earlier in the same loop and already pushed as temp `file://` targets.

**Concrete failure scenario:** User copies `[L1(local), R1, R2, R3]` (remote). Local loop → `result=[L1]`. In the try: R1 copies OK (`result=[L1, temp1]`), R2 copies OK (`result=[L1, temp1, temp2]`), R3’s `copy()` throws (network blip, permission, disk full). Catch fires → `result.push(R1, R2, R3)` → final `result=[L1, temp1, temp2, R1, R2, R3]`.
- Cross-window VS Code paste: R1 and R2 are now pasted **twice** (once from the temp copy, once from the remote URI via the proxy) — silent duplication/overwrite.
- Native paste (Finder/Explorer): temp1/temp2 paste, but R1/R2/R3 remote URIs are meaningless.
- The user is told nothing — only `logService.warn`. They asked to copy 3 remote files; they get a corrupted/partial result with zero surfaced feedback.

**Secondary silent degradation (same code):** Even on the fully-successful path, `result` is built as *all locals first, then all remotes*. The user’s original selection order is silently discarded. For paste-into-ordered-target flows this is an observable, unexplained reordering.

**Why it matters:** A user-initiated copy that partially fails is exactly the case that must surface feedback. Here it is masked behind a `warn` log, and the fallback actively corrupts the result (duplicates). The comment even admits "native paste will not [work]" — acknowledging a degraded outcome the user is never shown.

**Recommended fix:**
- Move the `try/catch` *inside* the per-resource loop so one file’s failure doesn’t discard the successes or re-add already-downloaded files. Collect failures into a list.
- Do not silently fall back to raw remote URIs for files that already have a temp copy. If some downloads fail, surface it (e.g., `notificationService` warning: "N of M files could not be prepared for paste outside VS Code").
- Preserve original ordering (build `result` in the input order, substituting temp URIs in place).
- Use `logService.error` with an error id from `errorIds.ts` for genuine failures, not `warn`.

---

### 2. Windows multi-file local copy silently drops native-paste support
**File:** `src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts` — `writeResources`, diff lines 703–718 (the `isWindows && resources.length === 1` guard and the default fall-through).
**Severity:** HIGH (silent functional gap)

**What is degraded:** The native Windows format (`FileNameW`) is only written when `resources.length === 1`. When a user copies **multiple** local files on Windows, execution falls through to the VS Code-only `code/file-list` format. No `FileNameW`, no CF_HDROP.

**Concrete failure scenario:** On Windows, select 3 files in the VS Code explorer → Copy → switch to File Explorer → Paste. Nothing happens. No error, no log, no notification. The user cannot tell whether they mis-copied, whether paste is unsupported, or whether it’s a bug.

**Why it matters:** This is the whole point of the PR (native paste), silently unavailable for the very common multi-file case on one of three platforms. The code comment explains the CF_HDROP/Electron limitation to *developers* but gives the *user* no signal.

**Recommended fix:** At minimum, `logService.warn` when the multi-file Windows native path is skipped so it’s diagnosable. Better: surface a one-time/contextual notice that pasting multiple files into Explorer isn’t supported, or investigate writing CF_HDROP. Don’t let the capability vanish with zero trace.

---

## MEDIUM

### 3. Empty `catch {}` in temp-dir cleanup — swallows deletion failures, no error captured
**File:** `src/vs/workbench/contrib/files/browser/explorerService.ts` — `cleanupRemoteClipboardTempDir`, diff lines 609–618.
**Severity:** MEDIUM

**What is swallowed:** `catch { /* Best-effort cleanup */ }` — the error object isn’t even bound, so it *cannot* be logged. This directly violates the project rule "empty catch blocks are never acceptable."

**Concrete failure scenario:** `fileService.del(remoteClipboardTempDir, {recursive:true})` fails (file locked, still-open handle from an in-flight copy, permission). Temp copies of downloaded remote files — potentially sensitive content — remain in `cacheHome/remote-clipboard/` indefinitely and accumulate across every copy operation. No one ever knows.

**Why it matters:** Leaked, potentially sensitive file content on disk plus an un-debuggable cleanup path. "Best-effort" is fine as intent, but best-effort still logs.

**Recommended fix:** `catch (error) { this.logService.warn('Failed to clean up remote clipboard temp dir', error); }`.

---

### 4. `dispose()` fires async cleanup without awaiting — floating promise, temp dir may never be deleted
**File:** `src/vs/workbench/contrib/files/browser/explorerService.ts` — `dispose`, diff lines 604–607.
**Severity:** MEDIUM

**What is degraded:** `dispose()` is synchronous and calls `this.cleanupRemoteClipboardTempDir()` (async) without awaiting, then immediately runs `this.disposables.dispose()`. The deletion is fire-and-forget.

**Concrete failure scenario:** On window close/reload, dispose returns before `del()` completes; the file service or IPC it depends on may be torn down mid-operation, so the recursive delete never finishes. Downloaded remote files leak in `cacheHome`. Because the promise is unobserved (and its internal catch is empty — finding 3), there is no rejection surfaced anywhere.

**Why it matters:** Guarantees nothing about cleanup at the exact moment cleanup matters most (teardown), and the floating promise is a swallowed async result.

**Recommended fix:** Since `IDisposable.dispose` is sync, either (a) perform temp-dir cleanup eagerly at each new copy (already done) and additionally register a best-effort teardown that logs, or (b) explicitly acknowledge the floating promise with `.catch(err => this.logService.warn(...))` so a rejection is at least observable. Do not leave an un-awaited, un-chained promise.

---

### 5. Clipboard parsers swallow real parse errors and return `[]` with no logging
**File:** `src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts` — `plistToFiles` (diff 810–812), `uriListToFiles` (diff 833–835), `fileNameWToFile` (diff 862–864).
**Severity:** MEDIUM

**What is swallowed:** All three `catch (error)` / comment-only blocks bind (or elide) `error` and `return []` without ever logging. "Do not trust clipboard data" justifies not crashing, but it does not justify zero diagnostics.

**Concrete failure scenario:** A user copies files in Finder/Nautilus and pastes into VS Code. If the parser has a bug or hits an unexpected-but-valid clipboard encoding, it throws, the catch returns `[]`, and the paste silently does nothing. There is no trace to distinguish "empty clipboard" from "parser blew up on real data" — making the paste-does-nothing class of bug essentially undebuggable 6 months out.

**Why it matters:** Combined with `readResources` returning `[]` at the end (diff line 746) and `hasResources` potentially returning `true` while `readResources` returns `[]` (finding 7), a whole family of "paste silently does nothing" reports become impossible to root-cause.

**Recommended fix:** In each catch, `this.logService.warn('Failed to parse <format> clipboard data', error)` before returning `[]`. Keep the defensive `[]` return; add the breadcrumb.

---

### 6. `uriListToFiles`: one malformed line discards ALL files
**File:** `src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts` — `uriListToFiles`, diff lines 829–835.
**Severity:** MEDIUM

**What is degraded:** `content.split(...).filter(...).map(line => URI.parse(line)).filter(...)` — the `.map(URI.parse)` runs across all lines inside one `try`. If `URI.parse` throws on a single malformed line, the entire expression throws → catch → `return []`. Every valid file on the clipboard is silently lost because of one bad line.

**Concrete failure scenario:** A file manager writes a `text/uri-list` with a trailing malformed entry or a non-standard scheme string that `URI.parse` rejects. The user pastes and gets nothing, even though 9 of 10 URIs were perfectly valid `file://` paths.

**Why it matters:** All-or-nothing parsing turns a single bad entry into total silent data loss, then hides it (finding 5).

**Recommended fix:** Parse per line with an inner try/catch, skip+log the offending line, and return the successfully-parsed `file://` URIs.

---

### 7. `hasResources` / `readResources` can disagree (silent no-op paste)
**File:** `src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts` — `hasResources` (diff 749–771) vs `readResources` + parsers.
**Severity:** MEDIUM

**What is degraded:** `hasResources` returns `true` if the native format buffer merely *exists* (`hasClipboard(FileNameW/MAC/LINUX)`), but `readResources` returns `[]` if the parser then fails or filters everything out (non-file URIs on Linux, parse error, alignment issue on Windows). UI gated on `hasResources()` (enabled Paste action) then produces nothing.

**Concrete failure scenario:** Linux clipboard holds a `text/uri-list` of only `http(s)://` URIs. `hasResources` → `true` (buffer present). Paste enabled. `uriListToFiles` filters to `file://` only → `[]`. Paste does nothing, no explanation.

**Why it matters:** Inconsistent capability signaling → user sees an enabled action that silently no-ops.

**Recommended fix:** Make `hasResources` reflect what `readResources` would actually yield (or have the paste path surface "clipboard contained no pasteable files"), and log when a present-but-unusable buffer is encountered.

---

### 8. Proxy client `register()` re-registers on every activation; failure attribution is misleading
**File:** `src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts` — `register`, lines ~56–70 (diff 110–123).
**Severity:** MEDIUM

**What is swallowed/degraded:** The `onWillActivateFileSystemProvider` handler constructs a new `RemoteFileSystemProxyClient` and calls `fileService.registerProvider(Schemas.vscodeRemote, provider)` **every time** the event fires for `vscode-remote`, with no guard for "already registered." VS Code’s `registerProvider` throws if a provider for the scheme already exists.

**Concrete failure scenario:** The scheme activates a second time. The second `registerProvider` throws "already registered," which is caught and logged as `"Failed to register proxy provider"` (diff line 119) — misattributing a benign double-register as a registration failure, and leaking an extra provider instance. Conversely, the *genuine* first-time failure and this benign case are indistinguishable in the logs.

**Why it matters:** The catch does log with the error object (good), but the control flow guarantees confusing/incorrect error messages and wasted allocations. Downstream, if the *real* first registration failed, activation still completes with no provider, and later `vscode-remote://` reads fail with an obscure "no provider" error rather than the root cause.

**Recommended fix:** Guard with a "registered" flag (or check `fileService.hasProvider`/`getProvider` before registering) so registration happens once; only the true first-time failure is logged, ideally with an error id.

---

## LOW / ACCEPTABLE (with notes)

### 9. `dnd.ts` — remote resources silently omitted from TEXT drag data
**File:** `src/vs/workbench/browser/dnd.ts` — `fillEditorsDragData`, diff lines 473–486.
**Severity:** LOW

Previously all resources contributed their label to `DataTransfers.TEXT`; now only `file://` ones do, and if there are none, the TEXT format isn’t set at all. Dragging a remote file to a text target now yields no text where it used to yield the path. This is a deliberate, reasonable change (avoids macOS `.webloc` creation, per the comment), but it is a silent behavior change for remote-only drags. Acceptable given the rationale; worth a one-line note in the PR description so it isn’t mistaken for a regression.

### 10. Proxy write methods throwing — GOOD, keep
**File:** `src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts` — `writeFile`/`mkdir`/`delete`/`rename`, lines ~115–133 (diff 169–187).
These throw explicit `Error('Remote file system proxy provider is read-only')` instead of silently no-oping — the correct pattern. Minor note: the message is developer-oriented; if it can reach a user (e.g., dropping onto a remote target routed through this proxy), consider a more actionable message. `watch()` returning `Disposable.None` is acceptable for a read-only proxy.

### 11. Proxy server & main handler error propagation — GOOD, keep
**Files:** `src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts` (diff 224–275) and `src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts` (diff 318–364).
Both consistently `throw` on missing provider / unknown command / unsupported scheme / no matching window rather than returning empty or swallowing — the right approach; errors propagate back over IPC to the caller. Two watch-items (not silent-failure defects, but fragility that will *surface as* obscure errors):
- `MainHandler.getRendererChannel` relies on the connection-context string being exactly `window:${id}` (diff 356–363). If that assumption is ever wrong, `getChannel`’s client filter matches nothing and calls route to a dead channel — an obscure downstream failure rather than a clear "target window channel not found." Consider validating that a client matched and throwing a specific error if not.
- `readFile` on the server returns the whole `VSBuffer` over IPC (diff 263–266); large remote files are fully buffered/serialized. Not error handling, but a failure (OOM) here would surface far from the cause.

---

## Summary of must-fix items
1. **Finding 1 (HIGH)** — `resolveClipboardResources` duplicate/reorder/partial-failure masking. Restructure the try/catch per-file and surface partial failures to the user.
2. **Finding 2 (HIGH)** — Windows multi-file native paste silently unavailable; at least log, ideally notify.
3. **Findings 3 & 4 (MEDIUM)** — empty `catch {}` and un-awaited async cleanup in `explorerService.ts` leak potentially sensitive temp files with no trace.
4. **Findings 5–7 (MEDIUM)** — clipboard parsers swallow errors with no logging, all-or-nothing uri-list parsing, and `hasResources`/`readResources` disagreement all combine into an undebuggable "paste does nothing" class of failure. Add logging and per-line resilience.
5. **Finding 8 (MEDIUM)** — proxy client re-registers per activation and misattributes the resulting error.

The proxy server, main handler, and read-only write stubs are the bright spots: they throw explicitly instead of swallowing. The clipboard/explorer download path is where errors, empty results, and degraded outcomes are suppressed such that neither the user nor a future debugger can tell something went wrong.
