# subagent agent-a81070ca7f51d3753

I now have everything needed to reach a verdict. Let me confirm my analysis of each sub-claim.

**Verification results:**

**Sub-claim 1 (removed `getNodeIPs` was one-shot; NodeIP change never restarted kube-proxy — genuinely new behavior):** CONFIRMED.
- The removed `getNodeIPs` (diff, `cmd/kube-proxy/app/server.go`) is a one-shot `wait.ExponentialBackoff` `Nodes().Get(...)` at startup; it returns once IPs exist and nothing re-watches for NodeIP changes.
- The old node event handlers exited only on **PodCIDR** change and only in `LocalModeNodeCIDR` (old `NodePodCIDRHandler.OnNodeAdd/OnNodeUpdate` → `klog.FlushAndExit(...,1)`). `NodeEligibleHandler` only synced health. Crucially, the old `NodePodCIDRHandler.OnNodeDelete` merely **logged an error and did not exit**. So neither NodeIP change nor node deletion restarted kube-proxy before. Both exits are new.

**Sub-claim 2 (`OnNodeChange` NodeIP `!reflect.DeepEqual` → `exitFunc(1)`; `OnNodeDelete` unconditional `exitFunc(1)`; default `exitFunc = os.Exit`):** CONFIRMED directly at `pkg/proxy/node.go` lines 159–172 (NodeIP compare + `n.exitFunc(1)`), lines 176–180 (`OnNodeDelete` unconditional `n.exitFunc(1)`), and line 60 (`newNodeManager(..., os.Exit, ...)`).

**Sub-claim 3 (order-dependent slice + `reflect.DeepEqual` → added family or reorder yields "change"):** Plausible and concrete. `GetNodeHostIPs` (`pkg/util/node/node.go:65-97`) builds the slice in `node.Status.Addresses` order (InternalIPs then ExternalIPs), takes `allIPs[0]` as primary and appends the first differing family. So adding an IPv6 InternalIP after IPv4 changes `[v4]` → `[v4,v6]`, and reordering that changes the first InternalIP flips the primary — both make `reflect.DeepEqual` false. `NewNodeManager` returns as soon as *one* usable IP exists, so later dual-stack/CCM address settling arrives as `OnNodeChange` → `exit(1)`.

**Sub-claim 4 (no debounce/settle/set-normalization):** CONFIRMED. `OnNodeChange` does an immediate `!reflect.DeepEqual(oldNodeIPs, nodeIPs)` → `n.exitFunc(1)` with no settle window and no order-insensitive/sorted comparison; `reflect.DeepEqual` on `[]net.IP` is order-sensitive.

**Attribution:** New in this changeset (commit `46e2c22f`, the merged PR); not pre-existing.

All required sub-claims (1, 2, 4) hold, 3 is concretely plausible, and the location description is accurate.

```json
{
  "finding": "#1",
  "verdict": "confirmed",
  "reason": "pkg/proxy/node.go:159-172 exits (n.exitFunc(1), default os.Exit set at line 60) whenever GetNodeHostIPs differs by order-sensitive reflect.DeepEqual, and OnNodeDelete (176-180) exits unconditionally, with no debounce/settle/set-normalization; the removed getNodeIPs was a one-shot startup Get and the old handlers exited only on PodCIDR change (old OnNodeDelete merely logged), so exit-on-NodeIP-change and exit-on-delete are genuinely new. GetNodeHostIPs (pkg/util/node/node.go:65-97) orders IPs by Status.Addresses order, so a later-added IPv6 family or a reorder during bringup flips the DeepEqual result and triggers os.Exit(1)."
}
```
