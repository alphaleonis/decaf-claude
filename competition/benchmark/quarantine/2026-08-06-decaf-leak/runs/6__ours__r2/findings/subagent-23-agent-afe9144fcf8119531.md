# subagent agent-afe9144fcf8119531

Both mechanisms check out against the actual code at HEAD (f9070acd).

**Mechanism 1 (gated cleanup):** `resolveClipboardResources` (lines 287-327) only calls `cleanupRemoteClipboardTempDir()` at line 302, which sits inside the `if (remoteResources.length > 0)` block (299-324). If a user copies a remote resource once — setting `this.remoteClipboardTempDir` at line 306 — and later invokes `setToCopy`/`resolveClipboardResources` again with only local (`Schemas.file`) resources, `remoteResources.length` is 0, the entire branch (including the cleanup call) is skipped, and the previously-set `remoteClipboardTempDir` is never cleared or deleted from disk. It persists until either another remote copy happens (which cleans up the *prior* dir before creating a new one) or the service is disposed (window/editor close). This is a real, reachable leak from ordinary usage, not just an error path.

**Mechanism 2 (unawaited async cleanup in dispose):** `dispose(): void` (lines 567-570) has a synchronous return type and calls `this.cleanupRemoteClipboardTempDir()` — declared `private async cleanupRemoteClipboardTempDir(): Promise<void>` at line 572 — without `await`. This is a genuine floating promise: `dispose()` returns synchronously right after issuing the call, and `this.disposables.dispose()` on line 569 runs immediately without waiting for the `fileService.del` operation (line 575) inside the async method to settle. If the window/process tears down concurrently, the delete may never complete.

Both claimed lines and mechanisms are accurate; the class is `ExplorerService` (line 36), field declared at line 50. This is genuinely new code — `git log` shows this file/method pair introduced by the PR under review (remote-clipboard temp-dir handling), not pre-existing.

```json
{
  "finding": "#(unspecified)",
  "verdict": "confirmed",
  "reason": "Verified at src/vs/workbench/contrib/files/browser/explorerService.ts: (1) cleanup call at line 302 is nested inside `if (remoteResources.length > 0)` (299-324), so a subsequent local-only copy skips it entirely, leaving a prior remoteClipboardTempDir set and its on-disk contents unreclaimed; (2) `dispose(): void` (567-570) calls the `async` `cleanupRemoteClipboardTempDir()` (572) without `await`, then immediately runs `this.disposables.dispose()` synchronously — a genuine floating promise that can be abandoned mid-flight during teardown.",
  "corrections": {
    "pre_existing": false
  }
}
```
