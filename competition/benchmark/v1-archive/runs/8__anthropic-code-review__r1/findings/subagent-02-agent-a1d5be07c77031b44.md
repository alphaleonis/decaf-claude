# subagent agent-a1d5be07c77031b44

Now I have everything needed. Let me report the findings.

## Findings

Both findings below are independently derivable from the code, but are also **directly confirmed** by upstream history: this exact commit (`1dd33c8e`, PR #129768) was merged 2025‑09‑08 and **reverted the next day** (PR #133979, "Revert \"protect against race between deletion and adding finalizers\"") after it caused a spike of `pods "..." not found` e2e flakes (kubernetes/kubernetes#133976). The author (`liggitt`) subsequently opened a reattempt, kubernetes/kubernetes#133995 ("WIP - protect against race..."), whose description states verbatim: *"I found and addressed two gaps in the original PR"* — and those two gaps are exactly the two issues below.

### 1. Internal retry re-`Get` does not tolerate a concurrent `NotFound` — causes spurious 404s to the client
`staging/src/k8s.io/apiserver/pkg/registry/generic/registry/store.go:1141` and the `continue` at line 1231.

```go
for {
    ...
    if err = e.Storage.Get(ctx, key, storage.GetOptions{}, obj); err != nil {
        return nil, false, storeerr.InterpretDeleteError(err, qualifiedResource, name)   // no NotFound tolerance
    }
    ...
    if retryOnRVConflict && storage.IsPreconditionErrorForField(err, storage.PreconditionResourceVersion) {
        continue   // jumps back to the Get above
    }
```

The existing (pre-PR) code already had a documented reason to swallow a `NotFound` from `Storage.Delete` in one place — `if storage.IsNotFound(err) && ignoreNotFound && lastExisting != nil { ... finalizeDelete(lastExisting, ...) }` (line 1222) — precisely because deletion can legitimately race with another actor finishing the delete first, and the caller should still get a success response with the best-known last object rather than a 404. The new retry loop reintroduces exactly that race one level up: when the internally-added RV precondition conflicts, the loop jumps back to `e.Storage.Get`, and if the object was deleted by that same concurrent actor in the interim, this `Get` 404s — but this code path has no `ignoreNotFound`/`lastExisting` fallback, so the 404 is returned straight to the caller. Upstream's own triage log for issue #133976 traced this exact sequence (`GuaranteedUpdate ... failed because of a conflict, going to retry` → subsequent `DELETE` returns `resp=404`) and root-caused it to this PR. The follow-up WIP fix (#133995) addresses it by threading a `handleNotFoundErr` closure through the loop so a `NotFound` hit on the retried `Get` (or on the retried `Delete`) is treated the same as the pre-existing `ignoreNotFound` tolerance.

### 2. Stale `resourceVersion` used as the internal retry precondition when no caller precondition was set
`staging/src/k8s.io/apiserver/pkg/registry/generic/registry/store.go:1176-1187` combined with 1207-1213.

```go
if graceful || pendingFinalizers || shouldUpdateFinalizers {
    err, ignoreNotFound, deleteImmediately, out, lastExisting = e.updateForGracefulDeletionAndFinalizers(...)
    // Update the preconditions.ResourceVersion if set since we updated the object.
    if err == nil && deleteImmediately && preconditions.ResourceVersion != nil {   // <-- gated on caller-supplied RV
        accessor, err = meta.Accessor(out)
        ...
        preconditions.ResourceVersion = &resourceVersion
    }
}
...
retryOnRVConflict := false
if preconditions.ResourceVersion == nil {
    retryOnRVConflict = true
    preconditions.ResourceVersion = ptr.To(accessor.GetResourceVersion())   // <-- accessor is the PRE-update obj here
}
```

`accessor` is only rebound to the post-update object (`out`) when `preconditions.ResourceVersion != nil`, i.e. only when the *caller* supplied an RV precondition. But the new internal-precondition logic fires in the opposite case (`preconditions.ResourceVersion == nil`) — exactly when `accessor` was never rebound and still refers to the object fetched at the top of the loop, *before* `updateForGracefulDeletionAndFinalizers` ran (which can add/remove finalizers and bump the resource version, e.g. via `markAsDeleting`/GC finalizer updates). The final `Storage.Delete` then gets handed a stale RV as its "internal" precondition, so it spuriously conflicts against the object's *actual* current RV even with no external interference, forcing an unnecessary retry (or, combined with finding 1, potentially surfacing as a false 404 if the object is gone by the time the retry's `Get` runs). PR #133995 explicitly calls this out as gap #2 ("the RV from the updated object must be used as the internal RV precondition") and fixes it by unconditionally rebinding `accessor` to `out` whenever `deleteImmediately` is true, independent of whether `preconditions.ResourceVersion` was caller-supplied.

### Summary
Both findings point at the same two code regions:
- `store.go:1176-1187` (accessor rebinding after `updateForGracefulDeletionAndFinalizers`) — uses stale resource version for the internal retry precondition when no caller precondition exists.
- `store.go:1141` + `1229-1231` (retry loop's `Get` and `continue`) — no `NotFound`-tolerance on the retried `Get`, unlike the pre-existing tolerance for the final `Storage.Delete`'s `NotFound`.

This is not speculative: the exact commit under review (`1dd33c8e`) was reverted in production 24 hours after merging for precisely this class of bug (kubernetes/kubernetes#133976, revert PR #133979), and the same author's follow-up WIP PR #133995 fixes precisely these two gaps. If this PR is being reviewed/merged as-is in this local repo, it will very likely reproduce the same "pod not found" delete-race flakes that hit upstream CI.
