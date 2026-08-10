# subagent agent-ac099673ec24f3319

I have enough context. Confirmed the key architectural facts:

- `RemoteFileSystemProxyMainHandler.call(_, command, arg)` ignores its first arg (the **caller's** connection context) entirely — routing depends only on the URI authority in the payload. No caller identity check.
- The target-window server (`RemoteFileSystemProxyServer`) resolves any `vscode-remote://` URI through `fileService` with no scoping to the copied/clipboard resources and no workspace boundary — full remote filesystem reachable by that connection.
- The proxy client registers for the `vscode-remote` scheme in *every* local window, so any resolution of a crafted `vscode-remote://` URI in a local (possibly untrusted) window now routes cross-window.
- Renderer→renderer is only reachable via the main handler (main's `getChannel(name, clientFilter)` is main-process only), so the server-side missing scheme check is defense-in-depth, not directly exploitable.

Here is my report.

```json
[
  {
    "file": "src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts",
    "line": 323,
    "severity": "High",
    "category": "security",
    "issue": "[THREAT_PRIVILEGE] The main-process proxy handler grants any renderer arbitrary read access to another window's entire remote filesystem, with no caller authorization and no scoping to the copied resources. call(_, command, arg) ignores the caller's connection context (_) and routes purely on the URI authority in the payload; the target server (remoteFileSystemProxyServer.ts) then reads any vscode-remote:// path via fileService — not restricted to the user-selected/clipboard files or the shared workspace. Combined with the client registering the proxy for the vscode-remote scheme in EVERY local window (remoteFileSystemProxyClient.ts:110), any resolution of a crafted vscode-remote://<victim-authority>/etc/passwd (or ~/.ssh/id_rsa) in a local window — e.g. from an untrusted local workspace/config/link — is silently served by whatever window owns that remote connection. This is a confused-deputy: the main process forwards on behalf of the caller without verifying the caller is entitled to those files, crossing the local/remote and Workspace-Trust boundaries. Before this change a local window had NO provider for vscode-remote (the bug being fixed), so this is newly-introduced arbitrary cross-window remote read. Could be argued Critical (arbitrary remote file read across a trust boundary); rated High because the direct caller is first-party renderer/workbench code and exploitation needs a malicious workspace or compromised renderer.",
    "fix": "Add an authorization/scoping layer rather than routing every read unconditionally: (a) have the copy flow register a short-lived, per-operation grant (a token or an allow-list of exact resource URIs) that the server validates before serving, so the proxy can only read the specific resources the user actually copied/dragged; and/or (b) gate cross-window remote reads on Workspace Trust of the requesting window; and/or (c) require the target window to opt in. The read-only mutation guards are not a substitute — read IS the sensitive capability here.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts",
    "line": 247,
    "severity": "Medium",
    "category": "security",
    "issue": "[THREAT_AUDIT] Cross-window remote file reads are served with no audit trail. The server reads another window's remote files (stat/readdir/readFile/exists/resolve) on behalf of a different window without logging who requested what. The only logging is client-side trace on the requesting side. If this proxy is ever abused to exfiltrate files from a connected remote host, there is no record on the serving side of which window/authority triggered the read, defeating incident response.",
    "fix": "Emit a structured audit log entry on the serving side for each proxied operation (requesting window id/authority, target URI, op) at info level, so cross-window remote access is attributable. Pairs with the authorization control above.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/workbench/contrib/files/browser/explorerService.ts",
    "line": 573,
    "severity": "Medium",
    "category": "security",
    "issue": "[THREAT_COMPLIANCE] Remote file contents are materialized to the local cache directory (environmentService.cacheHome/remote-clipboard/<uuid>/<uuid>/<name>) in plaintext, and the resulting local file:// path is written to the OS clipboard — shared with every local application. This means (1) potentially sensitive remote data (source, secrets) is persisted unencrypted on local disk, readable by other same-user processes; (2) the local temp path (which leaks the username/cache layout — the concern mjbvz raised) is broadcast to any app that reads the clipboard, and any such app can then read the downloaded remote content directly from that path; (3) cleanup is best-effort and only runs on the next copy or on dispose() — a crash or forced quit leaves the remote data behind indefinitely with no retention bound.",
    "fix": "Treat downloaded remote data as sensitive at rest: create the temp tree with owner-only permissions, scope/limit what is eagerly downloaded, and add a robust lifecycle (cleanup on startup of stale remote-clipboard dirs, not only on dispose/next-copy). Longer term, prefer a deferred/streamed clipboard mechanism (ClipboardItem promise-to-Blob, per mjbvz) so remote bytes are not written to a broadcast-path local file.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/vs/platform/files/electron-browser/remoteFileSystemProxyServer.ts",
    "line": 263,
    "severity": "Medium",
    "category": "security",
    "issue": "[THREAT_RESOURCE_BOUNDS] The proxied readFile buffers an entire attacker-influenceable remote file into memory (VSBuffer) and ships it whole across IPC (renderer -> main -> renderer), with no size cap. A crafted vscode-remote:// URI pointing at a very large file forces a large allocation simultaneously in the serving renderer, the main process, and the requesting renderer — a memory-amplification/DoS vector. Additionally exists/resolve/readdir are exposed on the server even though the current client never calls them, letting a hand-crafted caller cheaply enumerate the remote filesystem tree. Confidence 50 because the impact depends on the caller/attacker model and on whether IPC frame limits already bound this elsewhere.",
    "fix": "Enforce a maximum readable size for proxied reads (reject or stream above a threshold) and expose only the operations the client actually needs (drop exists/resolve from the server surface, or bound resolve depth), so the proxy cannot be driven into unbounded allocation or cheap full-tree enumeration.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **plist regex parsing / XML-entity handling (clipboardService.ts `plistToFiles`)** — Single code pattern → quick-reviewer / typescript-reviewer scope. Note for the threat model: because it uses a naive `/<string>([^<]+)<\/string>/g` regex rather than a real XML parser, it does NOT process `<!DOCTYPE>`/entity declarations, so it is not exposed to XXE or billion-laughs entity expansion — arguably safer than a full parser here. The write side escapes `& < >` and the read side reverses only those three; asymmetry is a correctness nit, not a systemic control gap.
- **Path traversal / arbitrary paths from clipboard (`uriListToFiles`, `fileNameWToFile`, `plistToFiles`)** — Untrusted OS-clipboard data becomes `file://` URIs fed into paste. This is inherent to native file-paste (the OS clipboard is a trusted input for "paste files"); every native file manager does the same. Not a missing architectural control. The single-pattern robustness of each parser (UTF-16LE bounds in `fileNameWToFile`, non-file filtering) belongs to quick-reviewer / typescript-reviewer.
- **Server-side missing scheme allow-list (`remoteFileSystemProxyServer` calls `getProvider(uri.scheme)` for any scheme)** — Defense-in-depth only: the server channel is reachable renderer→renderer exclusively through the main handler, which does enforce `vscode-remote` (`remoteFileSystemProxyMainHandler.ts:329`). A renderer cannot obtain another renderer's channel directly (main's `getChannel(name, clientFilter)` is main-process only). Worth a hardening comment but not independently exploitable; low.
- **Hard-coded `PathCaseSensitive` capability (copilot thread 4)** — Correctness/caching identity concern, not a security control gap. Out of my scope.
- **Temp-name collision on copy (copilot thread 1)** — Addressed in the merged code via per-item `generateUuid()` subfolders; not a security gap.

## Threat Model Notes

- **New trust boundary introduced.** Before this PR, a local window resolving `vscode-remote://` failed with "no provider." This PR adds a main-process router + per-renderer server so a window *without* a remote connection can read files from a window that *has* one. That is a genuinely new privilege edge: local (possibly untrusted) window → arbitrary read of a connected remote host's filesystem.
- **The routing decision trusts the payload, not the caller.** `RemoteFileSystemProxyMainHandler.call` discards the caller's connection context and keys solely on `uri.authority`. There is no notion of "is this caller allowed to read from that authority," no per-resource scoping to what the user copied, and no Workspace-Trust gate. The "read-only" design (write/mkdir/delete/rename throw) constrains the *wrong* axis — exfiltration via read is the sensitive capability, and it is fully open.
- **Data sensitivity.** Flows include arbitrary remote file *contents* (source, config, potentially credentials/keys reachable by the remote user) and local filesystem paths. Copy of a remote file now writes those contents to the local cache dir in plaintext and publishes the local path to the shared OS clipboard.
- **Attack surface delta.** New IPC channels: `remoteFileSystemProxyHandler` (main, reachable by every renderer) and `remoteFileSystemProxy` (per renderer, reachable only via the main handler). The main handler exposes `stat/readdir/readFile/exists/resolve` transitively to any renderer for any `vscode-remote` authority currently open in the session.
- **Assumptions.** (1) VS Code renderers are largely first-party; the primary realistic exploit vectors are an untrusted local workspace that can cause a crafted `vscode-remote://` URI to be resolved, or a compromised renderer. (2) I did not execute the build/tests (out of scope); IPC reachability was reasoned from `ipc.ts` (`getChannel(name, clientFilter)` overload is main-process-only) and the `NodeRemoteResourceRouter` precedent, which — unlike this handler — at least requires the caller to name a specific `window:{id}` target in the URI.

### Probe Requests
- Confirm whether any existing IPC frame/message size limit already bounds `readFile` payloads across `mainProcessElectronServer` (informs Finding 4 severity): static inspection of `src/vs/base/parts/ipc/` message framing, or a runtime read of a large `vscode-remote://` file through the proxy while watching main-process RSS.
- Confirm the caller-context value passed as the first arg to `RemoteFileSystemProxyMainHandler.call` at runtime (is it the requesting `window:{id}`?), which would enable the authorization control in Finding 1's fix.
