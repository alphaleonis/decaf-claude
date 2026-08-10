# subagent agent-a1fefa7056d097fa8

I have enough to compile the findings. Here is the summary.

## Findings

**This exact PR was already reverted from `main` after merge**, which strongly corroborates the concerns below: PR #320685 merged as f9070acd (2026-06-11), was reverted on `release/1.125` for regressions found in TPI issue #321354 (`https://github.com/microsoft/vscode/issues/321354` — comments cite local→Finder DND dropping text files/folders, and false "already exists" error notifications after paste), then reverted again on `main` itself by PR #323490 (`https://github.com/microsoft/vscode/pull/323490`, merged 2026-06-29). The trigger for the second revert looks to be issue #323157 (`https://github.com/microsoft/vscode/issues/323157`), an automated telemetry report showing a **13.7× spike in `EntryExists` "file already exists" errors on the copy path** in the 1.126.0 release that shipped this PR, plus user reports #323739/#323770/#323997 of copy/paste failing with "already exists" errors.

### Concerns from prior PRs that apply here

1. **Prior double-paste-trigger bug likely recreated by the new multi-format fallback chain.**
   PR #200601 "Fix explorer paste" (`https://github.com/microsoft/vscode/pull/200601`) fixed a bug where "paste was being double triggered causing errors... We shouldn't trigger the native paste handler when no native files are present." This PR's `readResources()`/`hasResources()` now fall back sequentially across VS Code's own format and per-OS native formats (`src/vs/workbench/services/clipboard/electron-browser/clipboardService.ts:106-150`, `hasResources` at line 133), which reintroduces exactly the class of ambiguity #200601 fixed — multiple clipboard formats simultaneously appearing populated. This lines up with the post-merge "already exists" error spike (#323157) and user report #323770 ("copy a folder into same folder... keyboard shortcut gives error it already exists").

2. **mjbvz's review comment on this PR was never addressed in the merged diff.**
   On PR #320685 itself (`https://github.com/microsoft/vscode/pull/320685`, review comment id 3384232293), mjbvz flagged: "I feel like the temp file stuff isn't right... We are creating the file eagerly on copy and blocking the copy on this. I worry about leaking the `/tmp` file path," suggesting a `Promise<Blob>`-style clipboard API instead. mjbvz still approved the PR, but the code was not changed: `src/vs/workbench/contrib/files/browser/explorerService.ts:266-317` (`setToCopy` → `resolveClipboardResources`) still synchronously downloads every remote resource to `environmentService.cacheHome` before returning from copy, and the resulting temp `file://` paths are written straight into the native clipboard (`clipboardService.ts` `writeResources`), i.e. the temp-path leak concern still applies.

### Concerns from this PR's own review that WERE addressed

- Copilot's comment about `basename(resource)` collisions when copying multiple remote resources with the same filename — addressed: `explorerService.ts:311-313` now creates a unique `generateUuid()` subfolder per file before joining `basename(resource)`.
- Copilot's comment that `uriListToFiles` should filter to `file://` URIs — addressed: `clipboardService.ts` `uriListToFiles` now ends with `.filter(uri => uri.scheme === Schemas.file)`.
- Copilot's comment on `remoteFileSystemProxyMainHandler.ts` about not verifying `vscode-remote://` scheme — addressed (adjacent file, not one of the 3 named files).

### Minor/adjacent (not in the 3 named files, lower confidence)

- PR #257428 "Adding logs for copy paste" (`https://github.com/microsoft/vscode/pull/257428`) drew reviewer pushback on logging user data during copy/paste ("would this log user data? we should avoid it, maybe generate a unique id"). This PR adds `logService.trace('RemoteFileSystemProxyClient#stat', resource.toString())` etc. in `src/vs/platform/files/electron-browser/remoteFileSystemProxyClient.ts` (lines ~164-174), logging full resource paths — same pattern flagged before, though at `trace` level.
- Copilot's comment about `remoteFileSystemProxyClient.ts` hard-coding `PathCaseSensitive` instead of deriving it from the remote OS — left unaddressed, but outside the 3 named files and lower severity since the provider is read-only.

No relevant concerns were found in the historical PRs for `dnd.ts` (#243656 "Set DragData when directory is dragged", #284188) — this PR's `dnd.ts` change (filtering `DataTransfers.TEXT` to `file://` scheme only, around line 238-249) doesn't touch the directory/uri-list logic those threads argued about.
