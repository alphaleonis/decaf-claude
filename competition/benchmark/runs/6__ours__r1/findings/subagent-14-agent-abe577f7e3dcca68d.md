# subagent agent-abe577f7e3dcca68d

I have enough to complete the threat analysis. Key facts confirmed:
- `cacheHome` = `URI.file(userDataPath)` (the user-data dir, e.g. `~/.config/Code`), not `/tmp` — so the prompt's "/tmp disclosure" framing is inaccurate; the exposure is plaintext-at-rest under userData, not /tmp.
- `diskFileSystemProvider.mkdir` calls `promises.mkdir(path)` with no `mode` → default perms (umask-dependent, typically 0755).
- IPC routing: a renderer's server channel is reachable only via the main process's `IPCServer.getChannel(name, clientFilter)` — renderers cannot address each other directly, so the main handler is the sole gateway and its scheme gate is effective *today*. Its `call(_: unknown, …)` ignores the caller context entirely — no caller authorization.

Findings below.

```json
[
  {
    "file": "src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts",
    "line": 42,
    "severity": "High",
    "category": "security",
    "issue": "[THREAT_PRIVILEGE] Confused-deputy: the main handler routes a remote-FS read to any window matching the URI authority without authorizing the CALLER. The caller context (`_`) is ignored, there is no workspace-trust check, and no scoping to resources the target window actually shared. Any window (local, auxiliary, or a window on an untrusted/restricted workspace) can read the ENTIRE remote filesystem of another window via that window's remote connection — including a window connected to remote Y reading remote X's files through a third window it has no credentials for.",
    "fix": "Introduce an authorization boundary at the routing layer: verify the calling window is entitled to the target authority (e.g. it initiated a copy of that resource), honor workspace-trust state, and scope reads to an explicitly-shared set (per-copy capability/token) rather than exposing the whole provider surface. Do not derive authority solely from attacker-supplied URI components.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts",
    "line": 69,
    "severity": "Medium",
    "category": "security",
    "issue": "[THREAT_ATTACK_SURFACE] The resource-access layer trusts the routing layer for scheme enforcement. `readFile`/`exists`/`resolve` perform no scheme validation and `stat`/`readdir` only check provider existence, so the server will read ANY scheme (including local `file://`) for whichever window it runs in. The vscode-remote allow-list exists only in the main handler. If any future caller reaches this channel, or the handler gate is loosened/duplicated, this becomes an arbitrary-provider / local-file read of the serving window.",
    "fix": "Enforce the scheme allow-list independently inside the server channel (reject non-vscode-remote at the point of provider access), so access control does not depend on a single upstream router. Defense-in-depth for a cross-window read primitive.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts",
    "line": 30,
    "severity": "Medium",
    "category": "security",
    "issue": "[THREAT_AUDIT] Cross-window file reads produce no audit trail on the serving side. The server returns file contents to another window with no record of which window read which resource; the only logging is a client-side `trace` in the requesting window. After an incident (e.g. exfiltration of remote files by a compromised extension in a local window) there is no way to reconstruct what was read.",
    "fix": "Log cross-window proxy reads at the server/main-handler boundary with caller window id, target authority, resource, and operation, at a persisted (non-trace) level suitable for incident response.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 573,
    "severity": "Medium",
    "category": "security",
    "issue": "[THREAT_COMPLIANCE] Remote-sourced files — which may contain secrets (SSH keys, .env, tokens) that never previously touched local disk — are copied in plaintext into the local user-data cache (`cacheHome/remote-clipboard/...`) on every copy. Cleanup is best-effort and only fires on the next copy or on `dispose()`, so after a crash or hard exit the plaintext remote copies persist indefinitely. Folders are created via `createFolder` with default (umask) permissions, not a restrictive mode.",
    "fix": "Treat this as sensitive data-at-rest: create the temp root with restrictive (0700) permissions, register OS-level/process-exit cleanup (not only dispose), sweep stale `remote-clipboard/*` dirs on startup, and consider scoping/retention limits. Document that remote content is materialized locally so downstream data-handling policies apply.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts",
    "line": 69,
    "severity": "Low",
    "category": "security",
    "issue": "[THREAT_RESOURCE_BOUNDS] The proxy read path has no rate limiting and no size bound. `readFile` reads an attacker-chosen remote file fully into memory and serializes it twice (remote window -> main -> requesting window) with no cap or streaming, and callers can issue unbounded stat/readdir/readFile requests. A single window can drive memory amplification across three processes or enumerate a remote filesystem at speed.",
    "fix": "Add a maximum-size limit (reject/stream beyond a threshold) on proxied reads and rate-limit requests per calling window on the cross-window read channel.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **plist generation injection (`filesToPlist`)** — paths are escaped for `&`, `<`, `>` before insertion into `<string>` XML text content; that is sufficient to prevent tag/element injection into plist. Inputs are also local `file://` paths (guarded by `allLocal`), not cross-trust data. No injection.
- **Clipboard parse trust (`plistToFiles`/`uriListToFiles`/`fileNameWToFile`)** — these parse untrusted cross-application clipboard data, but the resulting `file://` URIs are only used as sources for user-initiated paste/copy under the user's own OS privileges (a file the user could already read). No privilege escalation; parse failures are caught and return `[]`. `uriListToFiles` additionally restricts to `file://`. quick-reviewer's input-handling scope, low impact.
- **`String.fromCharCode(...u16.subarray(...))` spread in `fileNameWToFile`** — a pathological multi-hundred-KB clipboard value could throw `RangeError` (arg-count limit), but it is wrapped in try/catch returning `[]`. Robustness nit, not a security gap.
- **DnD text filter to `file://` (`dnd.ts`)** — narrows what is exposed to native drop targets (removes remote URIs); reduces surface, no new exposure.
- **macOS `NSFilenamesPboardType` / Linux `text/uri-list` write** — writes local file paths the user chose to copy; no secret material introduced beyond what the user selected.
- **`/tmp` path-disclosure concern from the brief** — not applicable: downloads go to `cacheHome` (= `userDataPath`), a user-scoped directory, not `/tmp`. Folded the real exposure (plaintext-at-rest + perms) into the explorerService finding.
- **Main handler forwards arbitrary `command` string** — the target server channel switches on a fixed command set and throws otherwise; unknown commands cannot reach other channels. No command-routing bypass.

## Threat Model Notes

- **Trust boundaries.** New cross-window read primitive: local window (client) → main-process handler (router + sole gateway) → remote-connected window (server) → its FS providers. All windows run as the same OS user within one VS Code instance, so this is not a cross-user boundary. The meaningful boundaries it crosses are (a) **workspace trust** — a restricted/untrusted-workspace window can read a trusted remote window's files; (b) **credential/connection ownership** — a window borrows another window's remote authority/connection it never authenticated to; (c) **extension trust** — a compromised extension in a local window gains a read path into a remote filesystem that the local window holds no credentials for.
- **Caller authorization is absent.** `RemoteFileSystemProxyMainHandler.call` ignores the connection context; authority is derived entirely from the attacker-supplied URI. Routing correctness (right window) is enforced; access authorization (may this window read that authority, and only shared paths?) is not.
- **Scheme allow-list is single-layered.** Only the main handler gates `vscode-remote`. The renderer server independently would serve any scheme; the design relies on there being exactly one gateway registration (currently true in `app.ts`).
- **IPC reachability (verified statically).** `mainProcessService.registerChannel` in a renderer exposes the channel only to the main-process `IPCServer`, which reaches it via `getChannel(name, clientFilter)`. Renderers cannot address each other's channels directly, so the handler gate is effective today; findings 2 are defense-in-depth against future routing changes.
- **Data sensitivity.** Remote file contents (potentially secrets) flow through two extra processes and are additionally materialized to local disk (`explorerService`) — expanding both the in-memory and at-rest exposure of remote data on the local machine.
- **Attack-surface delta.** Three new IPC channels (`remoteFileSystemProxy`, `remoteFileSystemProxyHandler`) reachable by every renderer; a new local on-disk cache of remote content; three new hand-rolled clipboard-format parsers consuming cross-application input.

### Probe Requests
- Confirm no other registration point routes to `REMOTE_FILE_SYSTEM_PROXY_CHANNEL_NAME` beyond `app.ts`: `grep -rn "REMOTE_FILE_SYSTEM_PROXY_CHANNEL_NAME\|remoteFileSystemProxyHandler" src/` (would raise/lower confidence on finding 2's "single gateway" assumption).
- Confirm effective permissions of `userDataPath` on target Linux/macOS deployments (bears on finding 4's multi-user readability).

Relevant files: `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/workbench/contrib/files/browser/explorerService.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts`.
