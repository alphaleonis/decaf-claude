# subagent agent-a1184c4622dbe58ad

Based on reading the full diff and the surrounding code in all six target files, here are the concrete comment-vs-code mismatches I found. Most of the wiring (proxy client/server/main-handler IPC routing, the `Readonly` capability contract, the `window:{id}` connection-context convention, and the `dnd.ts` file-only text/download-url filtering) checks out and matches its comments. Two real issues stand out, both in `explorerService.ts`:

**1. `resolveClipboardResources` JSDoc contract is violated on download failure**
`src/vs/workbench/contrib/files/browser/explorerService.ts:282-286` (method body through line 327)

The JSDoc states: *"Returns `file://` URIs for all resources... Remote files are downloaded to a temp directory and their temp `file://` URIs are returned instead."* But the `catch` block at line 322 (`result.push(...remoteResources)`) pushes the original remote-scheme URIs straight into the result array when the download fails — these are not `file://` URIs at all, directly contradicting the stated contract. Callers (e.g. `writeResources` in `clipboardService.ts`, which branches on `resources.every(r => r.scheme === Schemas.file)`) rely on this guarantee.

**2. Partial-failure fallback duplicates entries instead of cleanly falling back**
`src/vs/workbench/contrib/files/browser/explorerService.ts:308-323`

The comment at lines 318-320 says *"If download fails, fall back to the original remote URIs"*, implying an either/or fallback. But the `for` loop (308-316) pushes a `target` (temp local copy) into `result` for each resource as it succeeds. If the copy throws partway through (e.g. on the 3rd of 5 remote files), the `catch` block then pushes **all** of `remoteResources` (line 322) — including the ones that already got a successful `target` pushed earlier. The result array ends up containing both the temp-local copy and the original remote URI for the same source files, so a paste after a partial failure duplicates those files instead of cleanly falling back.

**3. (Related, more consequential) The unconditional download breaks "cut" (move) semantics for remote files**
`src/vs/workbench/contrib/files/browser/explorerService.ts:266-280`, comment at 272-274

Before this PR, `setToCopy` wrote the original resource URI (including `vscode-remote://…`) straight to the clipboard, so a "Cut" of a remote item followed by "Paste" performed a real move (`ResourceFileEdit(source=original remote URI, target=…)`, deleting the source). Now `resolveClipboardResources` is called unconditionally regardless of the `cut` flag, so the clipboard ends up holding a temp `file://` copy instead. `pasteFileHandler` (`src/vs/workbench/contrib/files/browser/fileActions.ts`, not touched by this PR) reads sources purely from `clipboardService.readResources()`, so when `pasteShouldMove` is true, the "move" edit is applied to the ephemeral temp copy, not the original remote resource — the original remote file is never deleted. Cut+paste of a remote file (even within the same remote workspace, same window) silently degrades into "copy, leave original," which contradicts what the `cut` parameter/UI communicates to the user. The comment describing the download ("so they can be pasted both in other VS Code windows and into native file managers") does not acknowledge this side effect on move semantics.

Minor/soft note (not flagged as a hard finding): `clipboardService.ts:230-231`'s comment "Uint16Array naturally uses the platform's char encoding (UTF-16)" glosses over endianness — the byte reinterpretation (`new Uint8Array(encoded.buffer)`) only yields UTF-16LE bytes on little-endian hosts. This happens to hold for all architectures Electron currently ships on, so I'm not treating it as a real bug, just an imprecise comment.
