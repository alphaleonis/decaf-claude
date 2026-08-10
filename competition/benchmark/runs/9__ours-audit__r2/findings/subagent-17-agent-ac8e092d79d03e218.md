# subagent agent-ac8e092d79d03e218

I have the complete picture. Let me apply the knowledge-preservation lens to the flagged candidates.

Key facts extracted:
- `NodeManager.OnNodeChange`/`OnNodeDelete` call `exitFunc(1)` (prod `os.Exit`) on NodeIP change, PodCIDR change (if `watchPodCIDRs`), or node deletion — `node.go:139-180`.
- Old behavior: node deletion → `NodeEligibleHandler.SyncNode` → mark node ineligible (503), *not* exit. NodeIP changes were never watched at runtime (`getNodeIPs` was startup-only). So the hard-exit-on-delete and exit-on-NodeIP-change are *new* contract expansions.
- The `https://issues.k8s.io/111321` reference (which anchored *why* kube-proxy restarts on PodCIDR change) existed in both old `server.go` and old `NodePodCIDRHandler`; both are removed.
- 5-min timeout carries a rationale comment ("allocators to assign a PodCIDR ... after it is registered"); 1s interval does not but is inferable.
- topology.go↔config.go coupling: the dangerous edit direction *is* now documented via the new note in `CategorizeEndpoints`.

Report follows.

---

## VERDICT: NEEDS_CHANGES

## Project Standards Applied
No project CLAUDE.md/CONTRIBUTING guidance was surfaced in the reviewed tree for kube-proxy beyond kubernetes conventions. Applying RULE 0 and RULE 2. (kubernetes uses issue-link references in code as an established convention — relevant to the BASELINE_REFERENCE finding below.)

## Findings

### [ASSUMPTION_UNVALIDATED SHOULD]: Crash-to-restart contract and its "an external supervisor restarts us" assumption are undocumented at the exit sites
- **RULE**: 0 (knowledge preservation)
- **Location**: `pkg/proxy/node.go:139-180` (`OnNodeChange`, `OnNodeDelete`); registered at `cmd/kube-proxy/app/server.go:~610`
- **Issue**: `OnNodeChange` calls `n.exitFunc(1)` on any NodeIP change and (when `watchPodCIDRs`) any PodCIDR change; `OnNodeDelete` calls `n.exitFunc(1)` unconditionally. The struct doc says the manager "crashes kube-proxy," i.e. the *what*, but nowhere is the *why*: (a) why deliberately exit rather than reconfigure in place, and (b) the load-bearing assumption that a supervisor (kubelet static-pod / DaemonSet `restartPolicy`) will restart the process so it re-derives NodeIPs/PodCIDRs at startup. This also silently *changes* prior behavior: node deletion previously marked the node ineligible (503 via `NodeEligibleHandler.SyncNode`), and runtime NodeIP changes were never acted on at all (`getNodeIPs` ran once at startup). The refactor turns both into hard process exit.
- **Failure Mode / Rationale**: A future maintainer reading `n.exitFunc(1)` on delete/IP-change has no in-code signal that the exit *is* the reconfiguration mechanism. They may "gracefully handle" an IP change instead of exiting — silently leaving stale proxy rules and misrouted traffic — or embed/run the proxier in a context without auto-restart, where `os.Exit(1)` permanently tears down node networking instead of bouncing. The rationale is not reconstructable from names/types alone (inferability gate passes), is a live forward-relevant constraint rather than change history (durable-relevance passes), and must live at the exit sites to be safe (not-recorded-elsewhere passes: it is an operating contract, not "why this PR happened").
- **Suggested Fix**: Add a short comment at the exit sites (or on `NodeManager`) stating the contract explicitly, e.g.: "kube-proxy intentionally exits so its supervisor (kubelet static pod / DaemonSet restartPolicy) restarts it; NodeIPs and PodCIDRs are only re-derived at startup, so in-place reconfiguration is deliberately not attempted. This assumes the process is always run under an auto-restarting supervisor."
- **Confidence**: 75
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: YES.

### [BASELINE_REFERENCE COULD]: Removal of the issues.k8s.io/111321 anchor drops the rationale for the whole PodCIDR-restart mechanism
- **RULE**: 0 (knowledge preservation)
- **Location**: `pkg/proxy/node.go` (new `NodeManager` doc, replacing old `NodePodCIDRHandler` at former lines with `// https://issues.k8s.io/111321`); `cmd/kube-proxy/app/server.go` (removed `// https://issues.k8s.io/111321` above the `LocalModeNodeCIDR` handler registration)
- **Issue**: The old code carried `https://issues.k8s.io/111321` in two places — it was the single pointer explaining *why* kube-proxy watches PodCIDR and restarts on change under `LocalModeNodeCIDR`. Both occurrences are deleted and not replaced. The new `NodeManager` doc describes the mechanics but preserves no link to the originating design discussion.
- **Failure Mode / Rationale**: A maintainer tempted to remove or relax the `watchPodCIDRs` exit path (it looks aggressive) can no longer trace the decision to the issue that motivated it, and may reintroduce the bug 111321 fixed. kubernetes convention permits issue-link references in code, so this is not a style violation to leave in. This is durably relevant design provenance, not ephemeral history.
- **Suggested Fix**: Re-add `// https://issues.k8s.io/111321` to the `NodeManager` doc comment (or to the `watchPodCIDRs` exit branch) so the PodCIDR-restart rationale remains traceable.
- **Confidence**: 75
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: YES.

## Reasoning
Applied RULE 0. Found an undocumented, newly-expanded crash-to-restart contract with an implicit "supervisor restarts us" assumption, and the removal of the only design-rationale anchor (111321). Verdict: NEEDS_CHANGES because both are SHOULD/COULD knowledge-preservation gaps, no MUST.

## Considered But Not Flagged
- **5-minute poll timeout (`node.go:59-60`)**: rationale ("allocators assign PodCIDR after registration") is preserved in the comment — knowledge intact.
- **1-second poll interval (`node.go:60`)**: undocumented but inferable as an ordinary poll cadence; fails the inferability gate.
- **topology.go ↔ config.go zone-only coupling**: the *dangerous* edit direction is now documented by the new note in `CategorizeEndpoints` (`topology.go`) pointing at `NodeTopologyConfig.handleNodeEvent`. The reverse ("why filter only `LabelTopologyZone`") is inferable from the consuming code — adequately preserved.
- **Removed startup-eligibility comment in `proxy_health.go`** ("node is eligible while starting up ... until first contrary event"): the default-true bool was replaced by on-demand `nodeManager.Node()`, which is guaranteed non-nil by `NewNodeManager`'s blocking poll; the behavior shift is real but inferable from the new construction invariant. Borderline; not a clear loss.
- **Deleted `waitForPodCIDR` DeletionTimestamp-skip logic**: the new poll doesn't skip nodes pending deletion as the old watch did — a behavioral/correctness matter for quick/adversarial reviewers, not a knowledge-preservation gap.
- **`PodCIDRs()` returns the internal slice without copy (`node.go:128-132`)** while `Node()` deep-copies: an aliasing/concurrency concern, out of this lane.

### Probe Requests
None — findings are grounded in source read from disk; no regression probe required.
