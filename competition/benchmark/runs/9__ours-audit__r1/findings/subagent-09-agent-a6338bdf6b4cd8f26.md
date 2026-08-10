# subagent agent-a6338bdf6b4cd8f26

```json
{
  "finding": "#kube-proxy-nodeip-exit",
  "verdict": "confirmed",
  "reason": "All three claims verified against actual code. (1) HEAD~1's cmd/kube-proxy/app/server.go:getNodeIPs fetched node IPs once at startup via exponential backoff (6 steps) with no informer/watch — a NodeIP change after startup produced no restart (only NodePodCIDRHandler.OnNodeAdd/OnNodeUpdate watched PodCIDRs for restart, and OnNodeDelete in old node.go merely logged, did not exit). (2) Current pkg/proxy/node.go OnNodeChange (lines 158-171) calls `n.exitFunc(1)` unconditionally whenever `!reflect.DeepEqual(oldNodeIPs, nodeIPs)`, with no debounce, cooldown, or min-uptime guard — confirmed by direct read of the merged code, and NewNodeManager wires exitFunc to os.Exit in production (node.go:60). (3b) utilnode.GetNodeHostIPs (pkg/util/node/node.go:65-97) builds `allIPs` by iterating node.Status.Addresses in their given order (InternalIPs first, then ExternalIPs) and returns `nodeIPs[0] = allIPs[0]` plus the first IP of the other family — so if node.Status.Addresses for an unchanged address *set* is reported in a different order between two observations, GetNodeHostIPs' output differs and reflect.DeepEqual sees a change, triggering the exit. This mechanism is real and code-verified; whether kubelet/cloud providers ever actually reorder Status.Addresses for equivalent state is [Inference] and not verifiable from this repo alone. One correction to the framing: the doc comment on NodeManager ('crashes kube-proxy if there are any changes in NodeIPs or PodCIDRs') shows the NodeIP-change-triggers-exit behavior is intentional design, not an accidental side effect — but the finding's core complaint (no debounce/rate-limit protecting against spurious or churny changes) is a valid, separate reliability concern layered on top of that intentional design, exactly as the finding itself notes. Medium severity is appropriate.",
  "corrections": {
    "pre_existing": false
  }
}
```
