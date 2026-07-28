# subagent agent-a5fe79e404868a607

I have all the evidence needed. Here are my findings.

## Findings

All core logic is in `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/base/parts/ipc/common/ipc.ts`, in `IPCServer.getChannel` (lines 889-930).

### 1. Filter evaluated at call time, not getChannel time

`getChannel` (line 891) only captures `routerOrClientFilter` in a closure via `const that = this;` and returns an object literal. Nothing is evaluated eagerly. The filter runs *inside* the returned `call` method, so it re-evaluates against the current connection set on every `.call()`:

```ts
// line 896-901
call(command, arg, cancellationToken): Promise<T> {
    let connectionPromise: Promise<Client<TContext>>;
    if (isFunction(routerOrClientFilter)) {
        const connection = getRandomElement(that.connections.filter(routerOrClientFilter));
```

`that.connections` (getter at lines 842-846) snapshots the live `_connections` set each time. So evaluation is lazy, at call time, against whatever clients are connected then.

### 2. No matching client at call time → the call HANGS (never rejects/throws)

Lines 901-907:

```ts
const connection = getRandomElement(that.connections.filter(routerOrClientFilter));
connectionPromise = connection
    // if we found a client, let's call on it
    ? Promise.resolve(connection)
    // else, let's wait for a client to come along
    : Event.toPromise(Event.filter(that.onDidAddConnection, routerOrClientFilter));
```

If nothing matches, `getRandomElement(...)` returns `undefined`, so it falls to `Event.toPromise(Event.filter(that.onDidAddConnection, routerOrClientFilter))`. This promise resolves only when a *future* `onDidAddConnection` fires with a client that passes the filter. It does **not** throw or reject — it waits indefinitely. The `.call()` promise (`getDelayedChannel(channelPromise).call(...)`, lines 912-916) stays pending forever if no matching client ever reconnects. Note there is no `client === undefined` error path here; `undefined` simply triggers the waiting branch.

(Contrast: the router path at line 909 delegates to `routerOrClientFilter.routeCall`; `StaticRouter.route` at lines 1105-1114 has the same wait-forever behavior via `await Event.toPromise(hub.onDidAddConnection)` then recursion.)

### 3. No timeout on waiting for a matching client

`Event.toPromise(Event.filter(...))` (line 907) has no timeout parameter — nothing cancels or rejects it. There is a 1000ms `timeoutDelay` in `ChannelServer` (lines 340-342, 490-500: `Channel name '...' timed out after ${this.timeoutDelay}ms`), but that only fires *after* a connection is found and the request reaches a server whose channel isn't registered. It does **not** apply to the client-filter waiting-for-a-connection step. So a filter that matches no one produces an indefinite hang, not a timeout rejection.

### 4. `ctx` property: origin and format `window:{id}`

- On the server, `ctx` is read from the client's first protocol message and stored on the connection: ipc.ts lines 854-863:
  ```ts
  const ctx = deserialize(reader) as TContext;
  ...
  const connection: Connection<TContext> = { channelServer, channelClient, ctx };
  ```
- The client supplies it in the `IPCClient` constructor, ipc.ts lines 1021-1031 (`serialize(writer, ctx); protocol.send(writer.buffer);`).
- For renderer windows it is the literal string `window:${windowId}`, set at `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/ipc/electron-browser/mainProcessService.ts:25`:
  ```ts
  this.mainProcessConnection = this._register(new IPCElectronClient(`window:${windowId}`));
  ```
- Format confirmed at `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/windows/node/windowTracker.ts:54` (`return \`window:${id}\`;`) and documented at `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts:77` ("The connection context format is `window:{id}`.").
- Other variants exist for non-window clients, e.g. `window:${windowId},module:${process.moduleId}` (`utilityProcessWorkerWorkbenchService.ts:130`). So `id` is the numeric Electron window id; a plain renderer window is exactly `window:<number>`.

The electron-main server that populates these connections is `Server extends IPCServer` at `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/base/parts/ipc/electron-main/ipc.electron.ts:29`.

### 5. Multiple matching clients → routes to a RANDOM match (no error)

Line 901: `getRandomElement(that.connections.filter(routerOrClientFilter))`. All matches are collected by `.filter`, then `getRandomElement` (imported from `../../../common/arrays.js`, line 6) picks one at random. It does not error and does not deterministically pick the first. For a `ctx === 'window:2'` filter this is normally a single unique match, so it is effectively that one client — but if two connections shared the ctx it would pick one at random.

### Note on the specific example
`(client) => client.ctx === 'window:2'` is used verbatim in production at `/home/decaf/code/decaf-claude/competition/benchmark/repos/6/src/vs/platform/files/electron-main/remoteFileSystemProxyMainHandler.ts:78-81` (`getRendererChannel`). Given the above, if window 2 has closed/dropped its connection before `.call()`, that channel's `.call()` will hang indefinitely waiting for a `window:2` client to (re)connect, rather than rejecting.
