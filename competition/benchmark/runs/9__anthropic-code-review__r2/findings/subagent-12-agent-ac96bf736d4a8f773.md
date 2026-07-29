# subagent agent-ac96bf736d4a8f773

## Findings

I compared the merged code at HEAD `46e2c22f` against review threads on PR #130837 itself, its stated predecessor PR #125382, and (per instructions) PR #132796 — the last of these turned out to be an unrelated kubelet-preemption PR that only happens to be adjacent in `main`'s commit graph (`pkg/kubelet/preemption/preemption.go`), so it has no bearing on `pkg/proxy/*`; no findings come from it.

I also checked what happened to this code *after* merge (commit history on `pkg/proxy/node.go` / `proxy_health.go`), because a reviewer comment posted 4 days after merge turned out to correspond to a real, confirmed regression — which sharpens finding #1 into something concretely verified rather than speculative.

### 1. `pkg/proxy/node.go` lines 148-180 — exit-on-NodeIPs-change / exit-on-Node-delete is the exact risk flagged in the predecessor PR, and it broke production shortly after merge

```go
// lines 148-157 (PodCIDRs change, gated by watchPodCIDRs)
if n.watchPodCIDRs {
    if !reflect.DeepEqual(oldPodCIDRs, node.Spec.PodCIDRs) {
        ...
        n.exitFunc(1)
    }
}
...
// lines 165-172 (NodeIPs change, unconditional)
if !reflect.DeepEqual(oldNodeIPs, nodeIPs) {
    ...
    n.exitFunc(1)
}
...
// lines 176-180 (OnNodeDelete, unconditional)
func (n *NodeManager) OnNodeDelete(node *v1.Node) {
    klog.InfoS("Node is being deleted", "node", klog.KObj(node))
    klog.Flush()
    n.exitFunc(1)
}
```

**Prior PR feedback (PR #125382):** danwinship, https://github.com/kubernetes/kubernetes/pull/125382#discussion_r1669405761:
> "Thinking about the big picture of kube-proxy Node handling, we don't really deal well with the case where the Node is deleted and then not created (but kube-proxy is still running); we will crashloop in that case. Perhaps it would be better for kube-proxy to ignore Node deletion and _only_ restart on Node recreation?"

This concern was explicitly carried forward into review of THIS PR — danwinship reposted it verbatim as a live open question on `node.go` line 161 (comment id 1996997813, https://github.com/kubernetes/kubernetes/pull/130837#discussion_r1996997813): *"(by the end of the PR we should be exiting in this case too probably) There's some discussion of what cases we need to care about in [the #125382 thread above]."* The discussion in #125382 concluded that `DeletionTimestamp` handling specifically wasn't needed, but never fully resolved whether unconditionally exiting on **any** NodeIPs change or Node deletion was safe across all environments — and it was not.

**How it applies here / evidence it's a real, confirmed problem:** This exact logic (lines 165-172 and 176-180 above) shipped in the merged code. Four days later, a user reported it broke cluster bring-up: nojnhuh, https://github.com/kubernetes/kubernetes/pull/130837#discussion_r2206231267 ("I'm trying to debug why this PR seems to have broken creating clusters for me... logs stop right after caches sync, no error"). danwinship replied "sigh, sorry" and the whole PR was reverted the same day in PR #132958 (`bc5088cbf3`, merged 2025-07-15). The re-landed version, PR #133059 "kube-proxy node manager (take 2)", explicitly says it exists to "fix https://github.com/kubernetes-sigs/cloud-provider-azure/issues/9266" and its commit `facbb66142` "Temporarily revert restart-on-node-IP-change behavior of proxy NodeManager" **comments out exactly these two exit paths** (NodeIPs-change and Node-delete) with `// FIXME: exit` markers — because cloud providers can legitimately update a Node's IPs across multiple steps during bring-up, and the unconditional `exitFunc(1)` here caused a crash loop. That FIXME sat in the codebase for roughly a year until PR #138183 "Restart kube-proxy on node IP changes and deletion" (merged 2026-07-10) restored it with more care.

In short: the code being reviewed at HEAD `46e2c22f` contains precisely the crashloop-on-Node-churn risk danwinship warned about in the predecessor PR, it was never satisfactorily resolved before merge, and it caused a real production regression that necessitated a full revert.

### 2. `cmd/kube-proxy/app/server.go` lines 217-220 — logging gap for `--bind-address` override, from this PR's own thread

```go
rawNodeIPs := s.NodeManager.NodeIPs()
s.podCIDRs = s.NodeManager.PodCIDRs()
logger.Info("Successfully retrieved NodeIPs", "NodeIPs", rawNodeIPs)
s.PrimaryIPFamily, s.NodeIPs = detectNodeIPs(ctx, rawNodeIPs, config.BindAddress)
```

**Prior PR feedback (this PR, #130837):** danwinship, https://github.com/kubernetes/kubernetes/pull/130837#discussion_r2152324428, gave a specific checklist: log a warning if `rawNodeIPs` is empty, log the `rawNodeIPs` otherwise, warn if the primary IP is loopback, **and** "otherwise, if we used `bindAddress` to override `rawNodeIPs`, log the resulting `NodeIPs`" — his stated rationale was that today's code "log[s] `rawNodeIPs` but then we don't log anything if `s.NodeIPs` ends up being different from that."

**How it applies here:** The merged code implements the first three items (the empty case can't happen by construction, the loopback warning exists in `detectNodeIPs`), but the fourth item — logging the resulting `NodeIPs` when `--bind-address` overrides the detected primary IP — was never added. An operator debugging a node-IP mismatch (arguably related in spirit to finding #1, where wrong/stale IP data caused confusion) has no log line showing that `bindAddress` changed the effective primary IP.

### Items I checked but found already resolved (not reported as findings)

For thoroughness: I verified line-by-line that the large majority of open threads on THIS PR (naming nits, `OnNodeSynced` doc wording, `OnTopologyChange(map[string]string)` single-callback design per the ServiceCIDR precedent, hollow-proxy's `NodeConfig` creation guarded by `if s.NodeManager != nil`, removal of the region topology label, the `getPodIPs`/`getPodCIDRs` loop merge into `NodeManager`, deep-copy-vs-document-only resolution on `Node()`, and the flaky-timing/test-coverage suggestions in `node_test.go`) were in fact incorporated into the final diff at HEAD `46e2c22f`. I'm not reporting those since the underlying concern is addressed in the code being reviewed.
