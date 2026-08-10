# subagent agent-a247e900d38383cf8

## Review Findings: Prior/Subsequent PR Feedback Applicable to PR #129768

This PR's history contains something more concrete than ordinary code-review comments: **the exact commit under review (`1dd33c8e6`) was merged, then reverted three days later (PR #133979) because it caused real production/CI breakage**, and the same author (liggitt) opened a reattempt (PR #133995, still open/stale) that fixes two specific gaps in this exact code. This is effectively "review feedback from the future" on the identical diff and should be treated as high-confidence, verified findings, not speculation.

### Timeline (verified via `gh pr view` / `gh issue view`)
1. PR #129768 merged 2025-09-08 (commit `1dd33c8e6`, exactly the code we're reviewing).
2. E2e tests immediately started flaking with `pods "<name>" not found` on delete (issue #133976), tracked at https://storage.googleapis.com/k8s-triage/index.html?text=delet.*not%20found.
3. liggitt reverted it the next day in PR #133979 (merged 2025-09-09): *"After #129768 merged, some e2e tests started flaking with 'not found' errors when attempting to delete pods... I suspect that there were existing races with pod deletion that the unconditional delete masked."*
4. liggitt opened PR #133995 ("Reattempt of #129768... I found and addressed two gaps in the original PR"), which is a near-identical restructuring of `Store.Delete` in `staging/src/k8s.io/apiserver/pkg/registry/generic/registry/store.go` with two targeted fixes plus new tests.

### Finding 1 — Internal RV precondition uses the stale (pre-update) `accessor`, not the post-update object
- **File**: `staging/src/k8s.io/apiserver/pkg/registry/generic/registry/store.go`, lines 1178–1188 and 1207–1213
- **Source**: PR #133995 description: *"When a graceful deletion object is both updated and deleted in the store#Delete function, the RV from the updated object must be used as the internal RV precondition."*

Current code:
```go
if graceful || pendingFinalizers || shouldUpdateFinalizers {
    err, ignoreNotFound, deleteImmediately, out, lastExisting = e.updateForGracefulDeletionAndFinalizers(ctx, name, key, options, preconditions, deleteValidation, obj)
    // Update the preconditions.ResourceVersion if set since we updated the object.
    if err == nil && deleteImmediately && preconditions.ResourceVersion != nil {
        accessor, err = meta.Accessor(out)   // <-- accessor only refreshed here
        ...
        preconditions.ResourceVersion = &resourceVersion
    }
}
...
retryOnRVConflict := false
if preconditions.ResourceVersion == nil {
    retryOnRVConflict = true
    preconditions.ResourceVersion = ptr.To(accessor.GetResourceVersion())  // <-- uses stale accessor when user didn't supply a precondition
}
```
`accessor` is only reassigned to `meta.Accessor(out)` when the caller supplied an explicit `preconditions.ResourceVersion`. In the common case (no caller-supplied precondition — the exact path this PR's internal retry logic targets), `accessor` still refers to the object fetched *before* `updateForGracefulDeletionAndFinalizers` ran (before finalizers/deletionTimestamp were added). The internally-computed RV precondition at line 1213 is therefore stale and mismatches what's actually now in etcd, causing `e.Storage.Delete` to spuriously fail with a ResourceVersion-precondition conflict even without any real concurrent actor.

The fix in #133995 unconditionally refreshes `accessor = meta.Accessor(out)` whenever `deleteImmediately` is true (not gated on `preconditions.ResourceVersion != nil`), and only updates `preconditions.ResourceVersion` itself when the caller supplied one.

### Finding 2 — Retry-on-conflict path re-Gets without the NotFound tolerance the delete path has
- **File**: `staging/src/k8s.io/apiserver/pkg/registry/generic/registry/store.go`, lines 1141–1143 (the `Get` at the top of the loop) combined with 1219–1234 (the `continue` at line 1231)
- **Source**: PR #133995 description, second bullet: *"When a graceful deletion object is both updated and then immediately deleted... if something else deleted the object in between, Delete tolerates a NotFound error and returns the last updated object. If the Delete now fails on an RV precondition error, the Get we do on the reattempt should also react to a NotFound error in the same way to preserve user-facing behavior."*

When `e.Storage.Delete` fails with the internally-added RV-precondition conflict (Finding 1 makes this failure much more likely to occur spuriously), the loop does `continue` (line 1231) and re-enters at the top, calling `e.Storage.Get` (line 1141). If a legitimate concurrent deletion happened in between, that `Get` now returns `NotFound`, and the current code just returns that as a client-visible error (line 1142) via `storeerr.InterpretDeleteError` — instead of applying the same `ignoreNotFound && lastExisting != nil` tolerance the non-retry path uses later in the function. This is precisely the observed CI symptom: `deleting Pod: pods "..." not found` (issue #133976).

The fix in #133995 threads a `handleNotFoundErr` closure through the loop so a NotFound hit on the retry `Get` gets the same "return `finalizeDelete(lastExisting)`" treatment as the original path.

### Reviewer discussion on #129768 itself
No inline review comments caught either gap before merge — deads2k and liggitt both approved/LGTM'd without flagging this. liggitt's own post-merge comment on #129768: *"humph, some e2e's started flaking with 'not found' errors attempting to delete pods... reverting... until I figure out why."* This confirms the gaps were not caught in review and only surfaced via e2e flake triage.

### Note on current review status
Since this diff is byte-for-byte the reverted change, whoever is merging PR #129768 today should be told it **will need the two fixes above** (or should pull in #133995's superseding commits) to avoid reintroducing the known "not found" delete flake. This is not a style nitpick — it's a confirmed regression with a documented root cause and an available fix from the same author.
