# subagent agent-a14581f7ba729b07a

I have completed my audit. Here are my complete findings.

---

# Error-Handling Audit: PR #320685 (copy/paste/DND for remote↔local)

Copy, paste, and drag-and-drop are exactly the flows where a swallowed error equals **silent data loss** for the user. Several handlers in this PR downgrade real failures to a log line (or nothing) and let the operation "succeed" with wrong or empty results. Findings are ordered most-severe first.

---

## 1. HIGH — Remote download failure is silently swallowed; the CUT/COPY reports success and can corrupt the clipboard
**File:** `src/vs/workbench/contrib/files/browser/explorerService.ts:317-323` (catch block), driven from `setToCopy` at `:266-280`

```ts
} catch (error) {
    // If download fails, fall back to the original remote URIs...
    this.logService.warn('Failed to download remote files for clipboard', error);
    result.push(...remoteResources);
}
```

**Why it's a silent failure:**
- The catch is maximally broad and downgrades a genuine failure to `logService.warn`. `resolveClipboardResources` then resolves normally, so `setToCopy` resolves, and the callers `copyFileHandler`/`cutFileHandler` (`fileActions.ts:1055-1071`) — which have **no** try/catch and **no** `notificationService.error` (unlike the sibling download/upload handlers at `fileActions.ts:1083-1090`) — report success. The user copied N remote files and got nothing usable natively, with only a log line as evidence.
- **Partial-failure corruption:** temp targets are pushed *inside* the loop (`result.push(target)` at `:315`) as each file copies. If file k throws, the catch appends `...remoteResources` (all of them) without discarding the partial results. Result becomes `[locals…, temp0, temp1, remote0, remote1, remote2]` — the already-copied files now appear **twice** under two different schemes. Cross-window paste via the proxy then creates duplicate copies of those files; native paste silently drops the remote-scheme duplicates.

**Hidden errors this catch can mask:** `createFolder` permission/ENOSPC errors, `fileService.copy` provider errors, network/timeout errors from the remote FS proxy (see finding #5 — a hang won't be caught, but any thrown remote error will), programming errors (bad `joinPath`, undefined provider), disk-full while writing temp copies.

**User impact:** "Copy" of remote files silently produces a clipboard that native paste can't use, or (on partial failure) a clipboard that pastes duplicates. No dialog, no toast — the user discovers it only when the paste target is wrong. For a CUT (move), the user may believe files were safely staged for a move when they weren't.

**Recommended fix:**
- Don't blanket-catch the whole batch. Collect per-file results; on a per-file failure decide explicitly (skip that file, or abort). Never leave `result` holding both the temp copy and the remote URI for the same file.
- Surface the failure to the user via `INotificationService` (at least a warning that native paste is unavailable), not just a log warn. If the intent is truly graceful degradation, say so to the user rather than silently.
- Include *which* resources failed in the log/notification context.

---

## 2. MEDIUM-HIGH — Cross-window proxy routing can hang forever with no error, timeout, or cancellation
**File:** `src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts:340-343` (and `getRendererChannel` at `:356-363`)

```ts
const targetChannel = this.getRendererChannel(targetWindow.id);
return targetChannel.call(command, arg);
```

**Why it's a silent failure:** `getRendererChannel` uses `electronIpcServer.getChannel(name, client => client.ctx === 'window:${id}')`. I verified the IPC server semantics at `src/vs/base/parts/ipc/common/ipc.ts:899-907`: when the client filter matches **no currently-connected** client, `getChannel().call` does **not** reject — it does `Event.toPromise(Event.filter(onDidAddConnection, filter))` and waits indefinitely for a *future* matching connection. `findWindowForAuthority` selects a window from `windowsMainService.getWindows()`, but that window's renderer IPC connection may be gone (window closing/reloading) or not yet established. Since window IDs aren't reused, a filter for `window:${id}` of a departed window can **never** match → the call hangs forever. No timeout is set and no `CancellationToken` is threaded through (`targetChannel.call(command, arg)` passes none), so a disposed caller can't cancel it either.

**User impact:** A local-window paste or drag of a remote file that routes to a stale/closing remote window hangs silently — the copy step in `resolveClipboardResources` (`fileService.copy` over the proxy) never returns, so `setToCopy`/the paste command never completes. No error, no spinner timeout — the classic un-debuggable "it just stopped working."

**Recommended fix:** Before routing, verify a live renderer connection actually exists for `window:${id}` (or catch the not-found case) and reject with a clear error instead of silently awaiting a future connection. Thread a `CancellationToken` and/or apply a timeout to `targetChannel.call` so the operation fails loudly and cancelably rather than hanging.

---

## 3. MEDIUM — Paste path swallows clipboard-parse errors and silently no-ops (no log)
**File:** `src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts`
- `readResources` `:106-131` (returns `[]` on any empty/failed native parse)
- New parsers: `plistToFiles` `:201-203`, `uriListToFiles` `:224-226`, `fileNameWToFile` `:253-255` — each `catch (error) { return []; }` with an **unused** `error` and **no logging**. (`bufferToResources` `:163-167` is the pre-existing same pattern.)

**Why it's a silent failure:** The paste flow `getFilesToPaste` (`fileActions.ts:1318`) does `await clipboardService.readResources()`. If parsing throws — e.g. one malformed line makes `bufferValue.split('\n').map(URI.parse)` throw and drops the *entire* set; or a plist/uri-list entry fails `URI.parse` — the catch returns `[]`. Paste then receives an empty file list and does nothing. The user copied files, hit paste, and nothing happened: no notification, and not even a log entry (`this.logService` is injected but unused in these catches).

**Hidden errors masked:** malformed UTF-16 in `FileNameW`, non-file URIs, unexpected plist structure, a single bad entry poisoning the whole batch, encoding issues.

**User impact:** "Paste does nothing" with zero diagnostics — impossible to triage from logs six months later.

**Recommended fix:** Log at `warn`/`trace` in each catch with the format name and byte length (not the raw untrusted content) so silent no-ops are at least traceable. Prefer per-entry resilience (skip the bad line, keep the good ones) over dropping the whole set on the first `URI.parse` throw.

---

## 4. MEDIUM — Temp-dir cleanup: fire-and-forget from `dispose()` plus a truly empty catch
**File:** `src/vs/workbench/contrib/files/browser/explorerService.ts:567-581`

```ts
dispose(): void {
    this.cleanupRemoteClipboardTempDir();   // async, not awaited, rejection dropped
    this.disposables.dispose();
}

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

**Why it's a silent failure:** The catch is empty and captures nothing — every deletion error (permission denied, file busy, provider error) is discarded with no log. `cleanupRemoteClipboardTempDir` copies **remote file contents** into `cacheHome/remote-clipboard/*`; if deletion silently fails on every copy, these temp files (potentially sensitive remote content) accumulate indefinitely with no signal. Also, `dispose()` is sync and calls the async cleanup without `await`, so on window/service teardown the deletion often won't finish before shutdown — leftover temp copies are the norm, not the exception. (No unhandled-rejection risk, since the internal catch swallows it — but that's the problem.)

**Recommended fix:** At minimum log the failure (`logService.warn`) so persistent cleanup failures are visible. Consider clearing the previous temp dir eagerly on the next copy (it already does via `cleanupRemoteClipboardTempDir()` at `:302`) and/or a startup sweep of the `remote-clipboard` dir, since dispose-time deletion is unreliable. Don't leave a comment-only empty catch on a path that handles remote file contents.

---

## 5. MEDIUM — Proxy provider registration failure is logged then swallowed, deferring to a cryptic "no provider" later
**File:** `src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts:112-122`

```ts
e.join((async () => {
    try {
        const provider = new RemoteFileSystemProxyClient(mainProcessService, logService);
        disposables.add(provider);
        disposables.add(fileService.registerProvider(Schemas.vscodeRemote, provider));
        logService.info('...Registered proxy provider for vscode-remote scheme');
    } catch (error) {
        logService.error('...Failed to register proxy provider', error);
    }
})());
```

**Why it's a silent failure:** The catch logs at `error` (good) but then lets the async IIFE resolve normally, so `onWillActivateFileSystemProvider`'s `join` completes as if activation succeeded. If `registerProvider` threw, the scheme is considered "activated" but has no working provider. The *next* remote file access then fails downstream with a generic `ENOPRO / No file system provider found for vscode-remote`, far from the real cause. This turns a clear registration failure into a confusing, delayed error.

**Recommended fix:** Let the failure propagate through `e.join` (or otherwise mark activation as failed) so the file operation that triggered activation fails with the real reason, instead of proceeding into a "missing provider" state. If swallowing is intentional, document why activation is allowed to proceed without a provider.

---

## 6. LOW / informational — Native writes silently produce a format the OS can't paste (documented, but no user signal)
**File:** `src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts:88-103`

Windows multi-file local copy (and mixed local/remote on any platform) falls through to the VS Code `code/file-list` format (`:99-103`). Native paste into Windows Explorer then silently fails for >1 file (only in-VS-Code paste works). This is acknowledged in the comment (`CF_HDROP` limitation), so it's a known degradation rather than a swallowed exception — but it's still invisible to the user. Worth a note/telemetry so the limitation is at least observable; not a blocker.

---

## Categories that are clean

- **`dnd.ts:244-248`** — Filtering the drag `TEXT` payload to `file://` resources (and skipping `setData` when none) is an intentional behavior change to avoid macOS `.webloc` bookmarks. It's not swallowing an error; no finding.
- **`remoteFileSystemProxyServer.ts:247-274`** and **`remoteFileSystemProxyMainHandler.ts:318-354`** — The `listen`/`call` "not found" and "no provider"/"no window"/"unsupported scheme" cases all **throw** and propagate over IPC rather than returning empty/default values. This is the correct fail-loud pattern. (The only gap is the *routing hang* in finding #2, which is a different mechanism.)
- **`app.ts:1306-1308`** — Synchronous channel registration; no error handling introduced, nothing swallowed.
- **`remoteFileSystemProxy.test.ts`** — Tests assert on the *throwing* behavior (`assert.rejects` for missing window / unsupported scheme). Good; no silent-pass patterns. Note they don't cover the stale-connection hang from finding #2 — worth adding.

---

### Suggested priority
1. Finding #1 (silent copy failure / clipboard corruption) — user-visible data-integrity risk in the core flow this PR ships.
2. Finding #2 (indefinite silent hang on stale window routing) — worst debuggability.
3. Findings #3–#5 (log-only / empty-catch silent no-ops) — add logging + user feedback and per-entry resilience.

Relevant files (absolute paths):
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/workbench/contrib/files/browser/explorerService.ts`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/base/parts/ipc/common/ipc.ts` (the `getChannel` waiting semantics that underlie finding #2)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/workbench/contrib/files/browser/fileActions.ts` (callers that lack error surfacing)
