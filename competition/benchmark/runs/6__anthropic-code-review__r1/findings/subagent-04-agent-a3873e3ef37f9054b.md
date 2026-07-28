# subagent agent-a3873e3ef37f9054b

**Verification complete.** The issue is confirmed as real.

**Key findings:**

1. **Event fires unconditionally (line 99)** BEFORE the provider existence check (line 106). Every `activateProvider()` call fires the event regardless of registration state.

2. **Listener runs on every activation:** The same listener added at line 56 executes every time the event fires, creating a new provider instance each time.

3. **Registration fails after first attempt:** Line 52-54 in fileService.ts throws "already registered" if `this.provider.has(scheme)` is true. The catch block (line 65) swallows the error.

4. **Resource leak confirmed:** Provider instances created at line 60 are added to `disposables` (line 61) BEFORE registration is attempted (line 62). Failed registrations still leave the provider in the store.

5. **High call frequency:** Every file operation via `copy()`, `withReadProvider()`, etc., calls `activateProvider()`, so the listener executes on nearly every remote file access after the first.

6. **Contrast with correct pattern:** `remoteFileSystemProviderClient.ts` creates the provider ONCE outside the listener and only joins on an existing promise (lines 28-48).

**80**

This is a real registration loop that leaks provider instances and logs errors on every file operation after the first; directly observed in the code flow and confirmed to diverge from the working sibling pattern in the same codebase.
