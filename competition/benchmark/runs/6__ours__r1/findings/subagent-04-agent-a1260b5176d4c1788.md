# subagent agent-a1260b5176d4c1788

I have enough to complete the system model and finalize findings. Let me write the report.

## System Model

**Boundaries/seams.** A new renderer→main→renderer proxy for `vscode-remote://` reads. Three coordinated pieces plus a common constants file: `RemoteFileSystemProxyServer` (per-renderer `IServerChannel`, exposes `stat/readdir/readFile/exists/resolve`), `RemoteFileSystemProxyMainHandler` (main-process `IServerChannel`, routes by URI authority to the window owning that remote connection), and `RemoteFileSystemProxyClient` (read-only `IFileSystemProvider` registered in windows with no direct remote connection). Consumers: `explorerService.setToCopy` (downloads remote resources to a temp dir), `clipboardService` (native clipboard formats), `dnd.ts` (file-scheme filtering).

**Contracts.** The channel contract is hand-rolled: string command + positional-arg encoding, duplicated independently across the three files; no shared interface. The proxy client implements `IFileSystemProviderWithFileReadWriteCapability`. The sibling `RemoteFileSystemProviderClient`/`DiskFileSystemProviderClient` is the reference pattern.

**Concurrency/lifecycle.** Routing is a TOCTOU sequence: enumerate windows in main → `getChannel(..., clientFilter)` → `call`. `getChannel` with a client-filter (ipc.ts:896-917) *waits for a matching connection* rather than failing when none exists.

Findings follow.

```json
[
  {
    "file": "src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts",
    "line": 62,
    "severity": "High",
    "category": "design",
    "issue": "[CONCURRENCY_DESIGN] The router has a TOCTOU gap with no timeout, no target-liveness check, and no cancellation propagation. `findWindowForAuthority` reads the main-process window list, then `getRendererChannel(id).call(...)` is invoked. Per ipc.ts:896-917, `getChannel` with a client-filter resolves against `getRandomElement(connections.filter(filter))` and, when no connection currently matches, falls back to `Event.toPromise(Event.filter(onDidAddConnection, filter))` — i.e. it waits indefinitely for a `window:{id}` connection to appear. A window can be present in `windowsMainService.getWindows()` while its IPC connection is gone or not yet registered (closing/teardown), so the forwarded call hangs forever with no rejection. Additionally, the `call(_, command, arg)` handler ignores the `cancellationToken` 4th parameter (IServerChannel.call, ipc.ts:35) and forwards `targetChannel.call(command, arg)` without it, so an in-flight large remote read cannot be canceled across the proxy hop.",
    "fix": "Make routing resilient: verify a live connection/channel exists for the target window before forwarding and reject with a defined error otherwise; wrap the forwarded call in a timeout; and thread the received cancellationToken through to `targetChannel.call(command, arg, token)`. Consider re-resolving to another window with the same authority (failover) rather than committing to the first match.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts",
    "line": 62,
    "severity": "High",
    "category": "design",
    "issue": "[API_CONTRACT] Provider registration is not idempotent, violating the `onWillActivateFileSystemProvider` contract. `fileService.activateProvider` (fileService.ts:94-112) fires the activation event on EVERY call, before the `provider.has(scheme)` short-circuit, and `withProvider` calls it on every filesystem operation. This listener creates a NEW `RemoteFileSystemProxyClient` and calls `fileService.registerProvider(vscodeRemote, provider)` inside the event body each time. After the first success, every subsequent vscode-remote operation constructs another provider, adds it to the DisposableStore (accumulating zombies), then hits `registerProvider`'s duplicate guard (fileService.ts:53-55) which throws 'already registered' — swallowed by the try/catch and logged as an error. The sibling `RemoteFileSystemProviderClient` (remoteFileSystemProviderClient.ts:28-48) avoids this by memoizing a single `environmentPromise` and having the listener just `e.join(environmentPromise)`; this new code diverges from that established pattern.",
    "fix": "Follow the sibling pattern: perform registration once (memoized promise or a guard checking `fileService.getProvider(vscodeRemote)` / a boolean flag) and have the activation listener join the single registration promise, so repeated activations are idempotent and produce no failed re-registrations or accumulated providers.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts",
    "line": 84,
    "severity": "Medium",
    "category": "design",
    "issue": "[DATA_MODEL] `PathCaseSensitive` is hardcoded in the proxy provider's capabilities, but the real provider it stands in for derives case sensitivity from the remote OS: `RemoteFileSystemProviderClient` passes `{ pathCaseSensitive: remoteAgentEnvironment.os === OperatingSystem.Linux }` (remoteFileSystemProviderClient.ts:54). For a Windows or macOS remote, the owning window treats `vscode-remote` paths as case-insensitive while the local window's proxy declares them case-sensitive. `fileService`/`uriIdentityService` consume this capability for identity comparisons (e.g. FileChangesEvent case handling at fileService.ts:67, `isEqual` in explorer dedup), so the two windows disagree on whether two case-differing remote URIs denote the same resource. The proxy has no OS information to set this correctly because the authority→OS mapping lives in the owning window.",
    "fix": "Have the proxy derive case sensitivity from the authoritative source rather than hardcoding it — e.g. expose the remote OS / capabilities through the proxy channel (a `capabilities` command routed like the others) and mirror the owning provider's PathCaseSensitive bit, or default conservatively and document the limitation.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts",
    "line": 42,
    "severity": "Medium",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] The renderer↔main↔renderer contract is hand-rolled and untyped across three files, where the codebase's standard is `ProxyChannel.fromService` (used throughout app.ts). Command names ('stat','readdir','readFile',...) and positional-arg encoding are duplicated independently in the server switch, the client call sites, and the main handler's blind forward — adding or renaming an operation requires editing all three in lockstep with zero compiler enforcement. The server exposes `exists` and `resolve` commands that no client ever calls (the only holder of the handler channel is RemoteFileSystemProxyClient, which issues only stat/readdir/readFile) and that are not part of the IFileSystemProvider interface — dead, speculative surface. The delegation is also inconsistent: `stat`/`readdir` call the raw `provider.*` directly (bypassing fileService), while `readFile`/`exists`/`resolve` go through `fileService`, mixing abstraction levels on the same channel.",
    "fix": "Define one shared typed interface for the proxied operations and drive both ends from it (ProxyChannel or an explicit interface implemented by client and server), so the command set and arg shapes are single-sourced and compiler-checked. Remove the unused `exists`/`resolve` until a caller exists, and make the server delegate uniformly (all via provider, or all via fileService).",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 304,
    "severity": "Medium",
    "category": "design",
    "issue": "[DATA_MODEL] Ownership/lifetime mismatch between the downloaded temp files and the OS clipboard reference. `resolveClipboardResources` downloads remote resources into a temp dir whose lifetime is tied to ExplorerService: it is deleted on the next `setToCopy` (line 302) and on `dispose()` (line 605). But the resources it writes to the native clipboard are `file://` URIs into that temp dir, and the OS clipboard outlives ExplorerService. After copying a remote file and then closing the copying window (or copying again), the native clipboard still points at now-deleted temp paths, so a subsequent paste into a native file manager silently references missing files. The `dispose()` cleanup is also fire-and-forget (async `cleanupRemoteClipboardTempDir()` is not awaited), so deletion may not even complete on shutdown, and `remoteClipboardTempDir` is shared mutable state mutated across un-synchronized async `setToCopy` calls.",
    "fix": "Decide and document the ownership model: either keep temp copies alive as long as the clipboard may reference them (e.g. defer cleanup, or only reap on a generational basis when the clipboard no longer holds those URIs), or scope the feature to same-session paste. At minimum, guard `remoteClipboardTempDir` against concurrent `setToCopy` races.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Authority→window routing picks the first match with no failover.** `findWindowForAuthority` returns the first window whose `remoteAuthority` matches. When multiple windows share an authority, any of them can serve the read (same underlying FS), so first-match is functionally correct; the only real weakness (no fallback when that window is unhealthy/closing) is already captured inside the CONCURRENCY_DESIGN finding, so not double-reported.
- **The `IRemoteFileSystemProxyWindowsService` / `IRemoteFileSystemProxyIPCServer` structural seams.** Re-declaring minimal structural interfaces in the main handler (instead of importing `IWindowsMainService` / the concrete IPC server) is deliberate dependency inversion that makes the handler unit-testable, and the shapes are compatible with the real types (`ICodeWindow`, `Client<string>`). Sound design, not a boundary violation.
- **Implicit "arg[0] is always the routing URI" assumption in the main handler.** The router reveals a positional contract (every command's first arg is the URI whose authority selects the target). It is consistently honored by all current commands; noted as part of the untyped-contract finding rather than separately.
- **Whole-file unbuffered `readFile` over IPC / proxy under-declares `FileReadStream` and `FileFolderCopy`** that the underlying `DiskFileSystemProviderClient` supports. This forces whole-file buffering and many round-trips for folder copies. The correctness path is fine (fileService falls back to readdir+readFile recursion); the cost dimension is performance-reviewer scope, so only the capability-fidelity angle is folded into the DATA_MODEL/EVOLUTION findings.
- **`resolveClipboardResources` reorders resources** (all local first, then remote). Behavioral ordering nuance for paste, not a system-design defect.
- **`dnd.ts` file-scheme filtering and the clipboard native-format encoders** (plist/uri-list/FileNameW). These are content/encoding correctness concerns (escaping, UTF-16 surrogate handling, multi-file Windows limitation) that belong to quick-reviewer / language-stack reviewers, not system-level design.

All findings are in newly added code (`pre_existing: false`).

### Probe Requests
- Run `src/vs/platform/files/test/electron-main/remoteFileSystemProxy.test.ts` plus a targeted test that (a) calls the handler for a `windowId` with no matching IPC connection to confirm the indefinite-wait behavior, and (b) fires `activateProvider('vscode-remote')` twice against a registered `RemoteFileSystemProxyClient` to confirm the second registration throws and is logged. Node modules are not provisioned, so these could not be executed; confidence is set from static tracing accordingly.
