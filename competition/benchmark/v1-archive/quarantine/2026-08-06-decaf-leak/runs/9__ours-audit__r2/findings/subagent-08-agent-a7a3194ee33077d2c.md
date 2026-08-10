# subagent agent-a7a3194ee33077d2c

I have enough to construct the scenarios. Let me verify one final mechanical detail: whether the initial-node baseline can be poisoned by an intermediate errored update (n.node assigned before the error check).

Confirmed from node.go lines 140-172: `n.node = node` executes unconditionally under lock (line 145) *before* the `GetNodeHostIPs(node)` error check (lines 159-163). Baseline poisoning is mechanical.

Depth: deep — pkg/proxy/node.go is ~190 new executable lines introducing a process-lifecycle controller (os.Exit on data-mutation events) driven by an external informer; total changeset >200 executable lines. All four techniques applied.

## Findings

```json
[
  {
    "file": "pkg/proxy/node.go",
    "line": 167,
    "severity": "High",
    "category": "error-handling",
    "issue": "[ADV_CASCADE] Node bootstrap: kube-proxy captures first NodeIP at startup → kubelet/cloud-provider settles node.Status.Addresses to canonical IP moments later → OnNodeChange sees NodeIPs change → os.Exit(1) → restart → repeat until IPs stabilize (crash loop during node/cluster bring-up).",
    "fix": "Do not treat every NodeIP delta as fatal during the settling window. Either debounce (require the change to persist across N syncs), restrict the exit-on-NodeIP-change to the specific modes that need it (as the old code restricted PodCIDR watching to LocalModeNodeCIDR), or re-detect and reconfigure in place instead of os.Exit. Previously getNodeIPs fetched IPs once and never watched, so a post-startup IP settle did not crash kube-proxy — this is new, broader crash surface for all modes.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 145,
    "severity": "High",
    "category": "error-handling",
    "issue": "[ADV_ABUSE] Baseline poisoning: OnNodeChange sets n.node = node unconditionally (line 145) before the GetNodeHostIPs error check (159). A transient Update whose Status.Addresses has no parseable InternalIP/ExternalIP is stored (err path returns without exit but keeps the bad node); when the SAME original IP is restored, oldNodeIPs (from poisoned node) = nil != [IP] → false 'NodeIPs changed' → os.Exit(1), even though the node IP never actually changed.",
    "fix": "Only overwrite n.node after validating the new node yields IPs (compute nodeIPs first; on GetNodeHostIPs error, log and return WITHOUT replacing n.node so the baseline stays the last-good IP set). Same reasoning applies to address reordering when a node has multiple same-family InternalIPs (GetNodeHostIPs picks index 0).",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 170,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_CASCADE] Diagnosis blackout: exit path changed from klog.FlushAndExit(klog.ExitFlushTimeout, 1) to klog.Flush(); os.Exit(1) at lines 154/155, 170/171, 178/179. os.Exit races/bypasses the bounded flush of file/async log sinks, so the 'NodeIPs changed'/'PodCIDRs changed'/'Node is being deleted' line that explains the restart is truncated — chained onto findings 1/2 the operator sees a kube-proxy crash loop during cluster creation with no logged reason (matches the reported truncated-logs / cluster-creation regression).",
    "fix": "Restore klog.FlushAndExit(klog.ExitFlushTimeout, 1) (routed through an injectable exit for tests) so the reason line is durably flushed before process termination.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 171,
    "severity": "Medium",
    "category": "resource-management",
    "issue": "[ADV_CASCADE] Correlated crash-storm: a cluster-wide trigger that mutates many nodes' IPs at once (control-plane/CNI migration, bulk cloud maintenance re-assigning InternalIPs, mass address re-report) fires OnNodeChange → os.Exit(1) on every affected node's kube-proxy near-simultaneously → all restart → each runs WaitForNamedCacheSync + up to a 5-minute LIST/poll against the apiserver → synchronized LIST storm plus a cluster-wide dataplane programming gap.",
    "fix": "Add jittered/backoff restart or in-place reconfiguration instead of immediate os.Exit; rate-consideration for how many proxies can be triggered by one event. At minimum document the blast radius of exit-on-NodeIP-change as a lifecycle decision.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 108,
    "severity": "Low",
    "category": "error-handling",
    "issue": "[ADV_ASSUMPTION] newNodeManager returns `err` (the closure's last inner error) instead of `pollErr` on poll timeout. Today every `return false, ...` path also assigns err non-nil, so nil-nil cannot occur; but the invariant is unenforced — any future `return false, nil` added to the poll closure makes newNodeManager return (nil, nil), and server.go then runs s.NodeManager.NodeIPs() on a nil manager → panic at boot.",
    "fix": "Return a non-nil error keyed off pollErr (e.g. wrap pollErr with the last inner err) so a timeout can never yield (nil, nil); alternatively guard s.NodeManager != nil before dereferencing in server.go.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Nil `nodeManager` deref in `ProxyHealthServer.NodeEligible()` (proxy_health.go:180).** Fell apart: the only nil-NodeManager path is hollow-proxy, which constructs `ProxyServer` directly with `HealthzServer` unset (nil), and `serveHealthz` nil-guards (server.go:437). The real server always creates NodeManager before HealthzServer in `newProxyServer`, and `n.node` is guaranteed non-nil post-construction, so `Node().DeepCopy()` is safe.
- **Missing `AddFunc` on `NodeConfig` causing missed NodeIP changes.** Fell apart: the initial node is captured at construction via the lister; genuine post-startup changes and watch re-lists arrive as Sync/Update deltas (UpdateFunc), and deletes as DeleteFunc → OnNodeDelete. No change class is delivered exclusively as Add after the handler is registered.
- **Tombstone (`DeletedFinalStateUnknown`) mishandling on delete → missed exit.** Fell apart: `handleDeleteNode` (config.go:339) correctly unwraps the tombstone, so a missed-delete still reaches OnNodeDelete → exit(1). (The tombstone branch in `handleChangeNode`/UpdateFunc at config.go:323 is effectively dead code since UpdateFunc never receives a tombstone, but it is harmless.)
- **Single-stack↔dual-stack transition crashing kube-proxy.** Not flagged as a defect on its own — gaining/losing an IP family genuinely changes NodeIPs and a restart to reconfigure is defensible; it is subsumed by findings 1/2 (the fragility is the false-positive and bootstrap-settle cases, not the legitimate transition).
- **`NodeEligible()` taking a write lock (`hs.lock.Lock`) and deep-copying the node on every /healthz probe.** Real but pure cost, no failure chain — belongs to performance-reviewer.
