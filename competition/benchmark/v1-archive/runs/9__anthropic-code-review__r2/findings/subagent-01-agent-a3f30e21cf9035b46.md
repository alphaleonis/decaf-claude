# subagent agent-a3f30e21cf9035b46

## Findings — historical git context

### Issue 1 (critical): `NewNodeManager` blocks kube-proxy startup and fails fatally when a Node has no IPs yet, regardless of `watchPodCIDRs`

**File/lines:** `pkg/proxy/node.go:84-109` (`newNodeManager`), called from `cmd/kube-proxy/app/server.go:210-213` (`newProxyServer`)

```go
pollErr := wait.PollUntilContextCancel(ctx, pollInterval, true, func(context.Context) (bool, error) {
    node, err = nodeLister.Get(nodeName)
    if err != nil { return false, nil }
    _, err = utilnode.GetNodeHostIPs(node)
    if err != nil { return false, nil }
    if watchPodCIDRs && len(node.Spec.PodCIDRs) == 0 {
        err = fmt.Errorf("node %q does not have any PodCIDR allocated", nodeName)
        return false, nil
    }
    return true, nil
})
if pollErr != nil {
    return nil, err   // fatal — propagates through newProxyServer, RunE, and terminates kube-proxy
}
```

The requirement that `utilnode.GetNodeHostIPs(node)` succeed is unconditional (not gated by `watchPodCIDRs`), and failure to satisfy it within 5 minutes returns a hard error that aborts `newProxyServer`/kube-proxy startup entirely.

**Historical evidence:** This PR (#130837) is itself the exact commit set that was reverted in full by **PR #132958** ("Revert 'Kube proxy node manager'", `kind bug`, body: `Reverts kubernetes/kubernetes#130837`), merged 2025-07-15. The revert was triggered by **kubernetes-sigs/cloud-provider-azure#9266**: "cloud-node-manager doesn't set Node IPs before kube-proxy expects them" — CAPZ e2e failures with `kube-proxy` logging `"command failed" err="host IP unknown; known addresses: [...]"` while `cloud-node-manager` simultaneously logged `Failed to wait for apiserver being healthy: ... dial tcp 10.96.0.1:443: i/o timeout`. The issue was explicitly attributed to this PR ("Looks like this was an unintended side effect of the upstream change") and closed once the revert merged.

The reintroduction, **PR #133059** ("kube-proxy node manager (take 2)"), states directly: *"Re-push of #130837, with more care to exactly preserve backward-compatibility so as to fix cloud-provider-azure#9266."* Its fixed version of `newNodeManager` explicitly separates the NodeIPs wait from the PodCIDRs wait and, for NodeIPs, **never returns an error** — it logs and continues with empty `nodeIPs`, matching the pre-#130837 `getNodeIPs()` in `cmd/kube-proxy/app/server.go`, whose own removed doc comment said: *"if is not able to get in time, it keeps going using the localhost address"* (echoed in the closed, never-merged predecessor design **PR #125382**, which this PR's own description says it "carries the work" from — that PR's author put it on `/hold` with *"This needs more work, it keeps adding tech debt instead of reducing it"* and it was closed unmerged).

**Failure scenario:** On any cluster using an out-of-tree cloud provider where a separate `cloud-node-manager`/CCM component is responsible for populating `Node.status.addresses` (e.g. Azure, and structurally any provider with the same pattern), and where that component itself needs to reach the API server via the in-cluster Service IP (which requires kube-proxy's iptables/ipvs/nftables rules to be programmed): kube-proxy blocks in `NewNodeManager` waiting for `GetNodeHostIPs` to succeed → never reaches `Run()` → never programs Service routing rules → `cloud-node-manager` can never reach the apiserver Service IP to become healthy → it never sets the Node's addresses → deadlock, up to 5 minutes then kube-proxy exits fatally and CrashLoopBackOffs.

**Reason:** historical git context

---

### Issue 2: `OnNodeDelete` now unconditionally exits kube-proxy — new behavior absent from the code it replaced, and disabled again shortly after this PR's own revert/reintroduction cycle for being unsafe

**File/lines:** `pkg/proxy/node.go:175-180`

```go
func (n *NodeManager) OnNodeDelete(node *v1.Node) {
    klog.InfoS("Node is being deleted", "node", klog.KObj(node))
    klog.Flush()
    n.exitFunc(1)
}
```

**Historical evidence:** The two handlers this replaces never exited on delete. `NodePodCIDRHandler.OnNodeDelete` only logged (`n.logger.Error(nil, "Current Node is being deleted", ...)`), and `NodeEligibleHandler.OnNodeDelete` only called `HealthServer.SyncNode(node)`. This PR is the first to make Node deletion a hard-exit trigger. When the same author redid this work as **PR #133059** shortly after the revert, the exit-on-delete path (and the analogous exit-on-NodeIP-change path in `OnNodeChange`, `pkg/proxy/node.go:165-172`) were both deliberately commented out with `// FIXME: exit` in that PR's own commit `facbb6614` ("Temporarily revert restart-on-node-IP-change behavior of proxy NodeManager"). They were only carefully restored ~9 months later in dedicated **PR #138183** ("Restart kube-proxy on node IP changes and deletion"), whose description states: *"That was no longer happening for node IP changes or node deletion because the exit path had been commented out"* — confirming the original authors judged this exact exit-on-change/exit-on-delete logic (as written in this PR) too risky to ship as-is, alongside the primary bug.

**Failure scenario:** Combined with Issue 1's boot-order race (Node IPs/addresses assigned asynchronously and out of kube-proxy's control by an external component), any transient informer-driven delete/relist event, or a real but momentary Node recreation during normal cluster operation, causes kube-proxy to immediately `os.Exit(1)` rather than tolerate and recover — a new crash-loop surface that didn't exist before this PR, and one the same authors chose to disable again immediately after reintroducing this code.

**Reason:** historical git context

---

### Summary

The core regression (Issue 1) is not speculative — this PR is the literal commit set that was merged, found to deadlock kube-proxy against cloud-provider node-address bootstrapping, reverted (PR #132958), and reintroduced with an explicit "preserve backward-compatibility" fix (PR #133059) that changed exactly the block of code at `pkg/proxy/node.go:84-109` flagged above. Issue 2 is a secondary consequence of the same over-aggressive-exit design philosophy, corroborated by the same author disabling it in the very next iteration of this code.
