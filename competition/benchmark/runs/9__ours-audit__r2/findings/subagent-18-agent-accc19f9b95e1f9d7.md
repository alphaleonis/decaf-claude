# subagent agent-accc19f9b95e1f9d7

```json
{
  "finding": "prior-feedback: OnNodeChange GetNodeHostIPs-error path does not exit",
  "verdict": "confirmed",
  "reason": "Code matches the claim exactly: pkg/proxy/node.go lines 159-163 log 'Failed to retrieve NodeIPs' and `return` with no call to n.exitFunc, while the PodCIDR-change path (152-156), NodeIP-change path (166-171 in OnNodeChange), and OnNodeDelete (177-179) all call n.exitFunc(1). There is no test case in pkg/proxy/node_test.go covering a GetNodeHostIPs failure inside OnNodeChange, so the behavior is genuinely untested/unaddressed, consistent with the reviewer's comment never having been fully resolved by merge time. It's also not a purely academic gap: cmd/kube-proxy/app/server.go:217 shows NodeManager.NodeIPs() is read exactly once, at process startup, to derive s.NodeIPs/s.PrimaryIPFamily — kube-proxy has no live re-derivation path, which is precisely why the sibling branches force a restart on change. An address set that becomes unparseable (GetNodeHostIPs returns an error when node.Status.Addresses yields zero parseable Internal/External IPs, per pkg/util/node/node.go:65-89) is the same category of 'derived state is now wrong' event but is the one case that doesn't trigger a restart, so it is a legitimate, still-open gap worth flagging exactly as the finding frames it (medium/hedged, not a hard crash bug).",
  "corrections": {
    "line": 159
  },
  "note": "One nuance for the write-up: the finding's mechanistic description ('kube-proxy keeps running with the OLD stale IPs') is slightly imprecise. n.node is unconditionally overwritten to the new node object at the top of OnNodeChange (line 145) before the GetNodeHostIPs(node) check, so on error the manager's cached node is already the broken one — a subsequent NodeManager.NodeIPs() call would return an empty slice (error discarded), not the previous good IPs. In practice this is moot either way because NodeIPs() is only ever consulted once, at startup in cmd/kube-proxy/app/server.go — so the real-world impact is 'kube-proxy fails to restart-and-recover when it arguably should,' not 'it actively serves traffic on stale IPs.' This doesn't undermine the finding, just refines the failure description."
}
```
