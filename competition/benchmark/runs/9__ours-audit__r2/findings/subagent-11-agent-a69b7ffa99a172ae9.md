# subagent agent-a69b7ffa99a172ae9

```json
{
  "finding": "kube-proxy NodeManager.OnNodeChange/OnNodeDelete unconditional os.Exit(1) with no debounce/rate-limit",
  "verdict": "confirmed",
  "reason": "Direct read of pkg/proxy/node.go confirms OnNodeChange calls n.exitFunc(1) unconditionally whenever reflect.DeepEqual(oldNodeIPs, nodeIPs) is false (and, if watchPodCIDRs, whenever PodCIDRs differ), and OnNodeDelete calls n.exitFunc(1) unconditionally with no debounce, backoff, or rate limiting anywhere in the file. exitFunc is wired to os.Exit in production via NewNodeManager -> newNodeManager(..., os.Exit, ...), and NodeManager is registered as the node-informer event handler in cmd/kube-proxy/app/server.go (`nodeConfig.RegisterEventHandler(s.NodeManager)`). The pre-change claim is also verified directly from `git diff 7a31dd60 46e2c22f -- pkg/proxy/node.go` and the companion server.go diff: previously (a) NodeIPs were fetched once at startup via `getNodeIP(s)` (one-shot ExponentialBackoff GET, never re-checked, never fatal on later change) — this function is deleted in the diff; (b) NodeIPs were never watched for change at all (only `NodePodCIDRHandler` existed, and it only ever compared PodCIDRs, only under LocalModeNodeCIDR); (c) `NodePodCIDRHandler.OnNodeDelete` only logged an error (`n.logger.Error(nil, \"Current Node is being deleted\", ...)`), no exit; (d) a separate `NodeEligibleHandler` handled node add/update/delete by calling `HealthServer.SyncNode(node)`, i.e., updating health-check eligibility (503), not terminating the process. So both the mechanism (unconditional, unrated exit) and the before/after behavioral contrast asserted by the finding are accurate and directly evidenced in this repo's own commit history, not speculative.",
  "corrections": {
    "line": null,
    "pre_existing": false
  }
}
```

Note on severity (part 3 of the ask): I could not refute "High" but also could not independently raise or fully validate it as precisely calibrated — it is a judgment call resting on threat-model assumptions (NodeRestriction scoping kubelet to its own node's Status.Addresses, and which principals typically hold cluster-scoped `nodes` update/delete in real deployments) that are standard Kubernetes RBAC/admission behavior but are not verifiable from this repo's source alone. The underlying mechanism (crash on own-node IP change or delete, no rate limit) is real and newly introduced by this PR (#130837, commit 46e2c22f), so the finding stands; whether "High" vs "Medium" is correct is a defensible severity judgment I did not find grounds to overturn.
