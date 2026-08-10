# subagent agent-ad428ca6e3a0e84d5

I have enough to complete the knowledge-preservation review.

<review_analysis>
Context: k8s repo, no local CLAUDE.md governing kube-proxy Go style; upstream conventions (issue links in comments are idiomatic here). Applying RULE 0 and RULE 2.

Change: consolidates node watching into `NodeManager` that reads NodeIPs/PodCIDRs once at startup and crashes kube-proxy on any subsequent change (NodeIP, PodCIDR, delete); proxiers narrow from all node labels to zone-only topology labels.

Key knowledge checks:
- Crash model: os.Exit on NodeIP change (NEW), PodCIDR change (existed), node delete (NEW — old handler only logged). Doc states WHAT, never WHY (values baked into proxier at startup, no runtime reconfig). Not inferable from a single read; durably relevant (maintainer could "fix" the crash). Passes gates.
- Dropped `https://issues.k8s.io/111321` — old NodePodCIDRHandler carried the origin rationale for restart-on-PodCIDR-change; now gone. BASELINE_REFERENCE lost.
- Zone-only narrowing: DOCUMENTED via new topology.go cross-ref comment (2145-2148). Not flagged.
- 5-min timeout: rationale preserved (node.go:59). Not flagged (weak comment-scope mismatch only).
- Tombstone branch in handleChangeNode wired only to UpdateFunc; tombstones arrive via DeleteFunc only → false context.
- Discarded GetNodeHostIPs errors in NodeIPs()/line143: correctness/other-reviewer scope.
</review_analysis>

## VERDICT: NEEDS_CHANGES

## Project Standards Applied
No kube-proxy-scoped project documentation found governing this code. Applying RULE 0 and RULE 2 only. (Upstream k8s convention treats `issues.k8s.io/NNN` links in comments as idiomatic context, not noise.)

## Findings

### [DECISION_LOG_MISSING SHOULD]: Crash-on-change model has no recorded rationale
- **RULE**: 0 (knowledge preservation)
- **Location**: pkg/proxy/node.go:41-43 (type doc), 140-180 (OnNodeChange / OnNodeDelete)
- **Issue**: `NodeManager` calls `exitFunc(1)` (→ `os.Exit`) on NodeIP change, PodCIDR change, and node deletion. The doc comment and log lines state *what* happens ("NodeIPs changed", "Node is being deleted") but nowhere records *why* crashing the whole process is the chosen response rather than reconfiguring in place. Two of these are new behavior: crash-on-NodeIP-change did not previously exist (IPs were fetched once via `getNodeIPs`), and crash-on-delete is new (the old `NodePodCIDRHandler.OnNodeDelete` only logged an error). Open question — "what would a maintainer misunderstand here?": that the crash is a defect. NodeIPs/PodCIDRs are consumed once in `newProxyServer` and baked into the proxier; runtime reconfiguration is unsupported, so a restart is required — that constraint is the load-bearing "why" and it is invisible in code.
- **Failure Mode / Rationale**: A future maintainer, seeing kube-proxy self-terminate on a transient delete/IP event, "fixes" it into a graceful in-place update, silently reintroducing stale-proxier-rules behavior that the crash exists to prevent. The design constraint is unrecoverable from the code alone.
- **Suggested Fix**: On the `NodeManager` type doc (node.go:41), state why a change forces a restart, e.g. "NodeIPs and PodCIDRs are read once at startup and baked into the proxier; kube-proxy cannot reconfigure them at runtime, so any change (including node deletion, which invalidates them) triggers a process restart to re-read them cleanly."
- **Confidence**: 75
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: YES.

### [BASELINE_REFERENCE SHOULD]: Dropped issues.k8s.io/111321 reference for PodCIDR-restart behavior
- **RULE**: 0 (knowledge preservation)
- **Location**: pkg/proxy/node.go:148-157 (was on old `NodePodCIDRHandler`, diff lines 1520-1522)
- **Issue**: The removed `NodePodCIDRHandler` carried `// https://issues.k8s.io/111321`, the pointer to the original bug that justifies restarting kube-proxy when PodCIDRs change under `LocalModeNodeCIDR`. The new PodCIDR-change exit path (node.go:150-157) drops it. Open question — "what assumption does this rely on, and where is it documented?": that PodCIDR-change-restart is required for correct `LocalModeNodeCIDR` local-detection; the source of that requirement is now unreferenced anywhere in the code.
- **Failure Mode / Rationale**: A maintainer reviewing the `watchPodCIDRs` crash path has no thread to pull to understand the originating defect and may weaken or remove the behavior. The specific issue context is not reconstructable from the surrounding code.
- **Suggested Fix**: Restore the `https://issues.k8s.io/111321` reference on the PodCIDR-change exit branch (node.go:150) so the rationale for restart-on-PodCIDR-change remains traceable.
- **Confidence**: 75
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: YES.

### [DEAD_CODE COULD]: Tombstone handling in update-only handler creates false context
- **RULE**: 2 (dead code that misleads future readers)
- **Location**: pkg/proxy/config/config.go:320-332 (`handleChangeNode`)
- **Issue**: `handleChangeNode` is wired exclusively to `UpdateFunc` (config.go:290), yet it contains a `cache.DeletedFinalStateUnknown` tombstone branch (322-331). Informers only deliver `DeletedFinalStateUnknown` through the delete handler; an `UpdateFunc`'s `newObj` is never a tombstone. `handleDeleteNode` (339-351) already handles tombstones correctly. The branch here is unreachable and tells a reader "node updates can arrive as deletion tombstones," which is false.
- **Failure Mode / Rationale**: A future reader (or LLM) copies this pattern or reasons that update events may carry tombstones, propagating an incorrect model of informer event delivery.
- **Suggested Fix**: Remove the tombstone branch from `handleChangeNode`; keep only the `*v1.Node` type assertion with the `unexpected object type` error path. Leave the tombstone handling in `handleDeleteNode` unchanged.
- **Confidence**: 75
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: YES.

## Reasoning
Applied RULE 0 and RULE 2. Found the new crash-on-change design and a dropped issue reference lack recorded "why," and a tombstone branch in an update-only path fabricates false context. Verdict: NEEDS_CHANGES because SHOULD-level knowledge gaps are present.

## Considered But Not Flagged
- **Zone-only label narrowing** (topology.go, proxiers): the reduction from all node labels to `LabelTopologyZone` is well-documented by the new cross-reference comment at topology.go:2145-2148 pointing back to `NodeTopologyConfig.handleNodeEvent`. Coupling knowledge is preserved — this is a positive.
- **5-minute poll timeout**: rationale ("wait for allocators to assign a PodCIDR after registration") is preserved at node.go:59. Minor scope mismatch — the poll now also gates node existence + NodeIP readiness even when `watchPodCIDRs` is false, which the PodCIDR-only comment doesn't mention — but the value and its primary justification remain documented. Below flag threshold.
- **Discarded `GetNodeHostIPs` errors** in `NodeIPs()` (node.go:123) and on the old node in `OnNodeChange` (node.go:143), plus `n.node = node` being set before the new node's IPs are validated (145 vs 159): correctness/robustness concerns owned by quick-reviewer, not knowledge loss.
- **winkernel `TODO(imroc)`**: the implementation-pending marker was correctly carried over to `OnTopologyChange` (diff 2200-2205). No lost context.
