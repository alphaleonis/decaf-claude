# subagent agent-aeab86b43446cbe29

I have all the evidence needed. Here are the precise findings.

## 1. `onWillActivateFileSystemProvider` / `IFileSystemProviderActivationEvent`

Interface declaration — `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/files/common/files.ts:42-46`:
```
/** ...Listeners can join this event with a long running promise to help in the activation process. */
readonly onWillActivateFileSystemProvider: Event<IFileSystemProviderActivationEvent>;
```

Type — `files.ts:935-938`:
```ts
export interface IFileSystemProviderActivationEvent {
	readonly scheme: string;
	join(promise: Promise<void>): void;
}
```

Implementation — `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/files/common/fileService.ts:94-113`:
```ts
async activateProvider(scheme: string): Promise<void> {
	const joiners: Promise<void>[] = [];
	this._onWillActivateFileSystemProvider.fire({
		scheme,
		join(promise) { joiners.push(promise); },
	});
	if (this.provider.has(scheme)) {
		return; // provider is already here so we can return directly
	}
	await Promises.settled(joiners);
}
```

- **What `e.join(promise)` does:** pushes the caller's promise into a per-call `joiners` array (line 101-103). `activateProvider` then `await Promises.settled(joiners)` (line 112), so activation does not complete until all joined promises settle. This lets a listener (e.g. an extension host) register the provider for `scheme` before `activateProvider` resolves. Doc at `files.ts:42-45`.
- **Fired every time?** Yes. `activateProvider` fires the event unconditionally at the top (line 99) every time it is called, and it is called on every resource access via `withProvider` (`fileService.ts:145`) and `canHandleResource` (`fileService.ts:118`). Note the early `return` at line 106-108 happens *after* the event has already fired — so even when a provider is already registered, the event still fires (only the `await joiners` is skipped).
- **Concurrent multiple fires for same scheme before registration?** Yes. There is no dedup / in-flight caching. Each `activateProvider(scheme)` call builds its own local `joiners` array and fires its own event; two concurrent calls for the same scheme both fire before registration completes.
- **Double-registration guard in `registerProvider`?** Yes — it **throws**. `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/files/common/fileService.ts:52-55`:
```ts
registerProvider(scheme: string, provider: IFileSystemProvider): IDisposable {
	if (this.provider.has(scheme)) {
		throw new Error(`A filesystem provider for the scheme '${scheme}' is already registered.`);
	}
```
So if two concurrent activations both try to register, the second `registerProvider` throws.

## 2. `IEnvironmentService.cacheHome`

- Interface declaration: `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/environment/common/environment.ts:60` — `cacheHome: URI;`
- Native implementation: `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/environment/common/environmentService.ts:62`:
```ts
get cacheHome(): URI { return URI.file(this.userDataPath); }
```
with `userDataPath` = `this.paths.userDataDir` (line 53).
- **electron-browser/desktop renderer:** uses `NativeWorkbenchEnvironmentService`, which `extends AbstractNativeEnvironmentService` (`/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/workbench/services/environment/electron-browser/environmentService.ts:59`) and does **not** override `cacheHome`. So it inherits `URI.file(userDataPath)`.
- **Is it a `file://` URI on local disk?** Yes. `URI.file(...)` produces a `file`-scheme URI pointing at the local user-data directory. (Only the web/browser variant overrides it: `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/workbench/services/environment/browser/environmentService.ts:111` returns `joinPath(this.userRoamingDataHome, 'caches')`.)

## 3. `IFileService.copy(source, target, overwrite)`

`/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/files/common/fileService.ts:803-815` delegates to `doMoveCopy(..., 'copy', ...)`.

- **Recursive folder copy?** Yes. In `doMoveCopy` (`fileService.ts:834-850`), when providers differ (no fast-copy), it resolves the source and if `sourceFile.isDirectory` calls `doCopyFolder`. `doCopyFolder` (`fileService.ts:898-914`) does `targetProvider.mkdir(targetFolder)` then recurses over `sourceFolder.children`, calling itself for subdirectories and `doCopyFile` for files. When source and target share the same provider and it has `hasFileFolderCopyCapability`, it uses the provider's native `copy()` (line 837-838).
- **Cross-provider (remote vscode-remote -> local file) supported?** Yes. The fast path requires `sourceProvider === targetProvider` (line 837); otherwise it falls through to the manual buffer/unbuffered traversal (`doCopyFolder` / `doCopyFile`, lines 843-849), which works across different providers.
- **Stream or buffer whole file in memory?** Streams in fixed-size chunks — it does **not** load the whole file into memory. `doCopyFile` (`fileService.ts:875-896`) picks a pipe strategy by capability; the buffered-to-buffered path `doPipeBufferedQueued` (`fileService.ts:1389-1428`) allocates one `VSBuffer.alloc(this.BUFFER_SIZE)` and loops `read`/`doWriteBuffer` until `bytesRead <= 0`. `BUFFER_SIZE` = `256 * 1024` (256 KB) at `fileService.ts:33`. (Unbuffered fallbacks `doPipeUnbuffered*` exist for providers lacking open/read/write/close.)

## 4. `IWindowsMainService.getWindows()`

- Interface: `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/windows/electron-main/windows.ts:50` — `getWindows(): ICodeWindow[];`
- Implementation: `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/windows/electron-main/windowsMainService.ts:1822-1824`:
```ts
getWindows(): ICodeWindow[] {
	return Array.from(this.windows.values());
}
```
- **Returns all windows including not-yet-loaded / closing?** Yes — no filtering. A window is added to the `windows` map (`windowsMainService.ts:212`, `Map<number, ICodeWindow>`) at creation time in `windowsMainService.ts:1624` (`this.windows.set(createdWindow.id, createdWindow)`) — this happens before `load()` and before the window is ready. It is only removed in `onWindowClosed` at `windowsMainService.ts:1758-1761` (`this.windows.delete(window.id)`). So `getWindows()` returns windows that are created but not yet loaded/ready, and returns a closing window until its close handler runs. `ICodeWindow` exposes an `isReady: boolean` and `ready()` to distinguish load state (`/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/window/electron-main/window.ts:67-68`), but `getWindows()` does not use it.
- **Does a code window expose `remoteAuthority`?** Yes. `ICodeWindow.remoteAuthority?: string` at `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/window/electron-main/window.ts:62`.
- **Can two windows share the same `remoteAuthority`?** Yes. Nothing enforces uniqueness of `remoteAuthority` across windows. The service routinely filters/groups windows by matching authority, implying multiple windows can carry the same one — e.g. `windowsMainService.ts:587`: `this.getWindows().filter(window => filesToOpen && isEqualAuthority(window.remoteAuthority, filesToOpen.remoteAuthority))`. Two windows both connected to the same `ssh-remote+host` will have equal `remoteAuthority` values.
