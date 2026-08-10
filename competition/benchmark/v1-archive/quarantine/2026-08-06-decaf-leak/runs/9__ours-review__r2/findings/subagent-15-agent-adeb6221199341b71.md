# subagent agent-adeb6221199341b71

## Performance Review — PR 130837 (kube-proxy Node Manager)

```json
[
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 180,
    "severity": "High",
    "category": "performance",
    "issue": "[PERF_HOT_PATH] NodeEligible() now calls nodeManager.Node() (full v1.Node DeepCopy — Status.Images, Conditions, Addresses, Capacity/Allocatable maps, Annotations, Labels, Taints) on every /healthz request, while holding hs.lock.Lock() (upgraded from RLock to a full exclusive Lock). Before this PR, node eligibility was computed once per node ADD/UPDATE event via SyncNode() and cached as a bool, so the per-request read was O(1) under RLock (see diff hunk around line 1059: old NodeEligible() was `hs.lock.RLock(); return hs.nodeEligible`). This regresses an event-driven cached read into a request-time DeepCopy done under an exclusive lock. hs.lock is the same lock the proxier's hot sync path uses on every Service/EndpointSlice sync via Updated()/QueuedUpdate() (pkg/proxy/iptables/proxier.go:525,535,1520; nftables/proxier.go:745,755,1812; ipvs/proxier.go:759,769,1440), so the DeepCopy's hold time now stalls proxy-rule-sync health signaling for its duration, on every kube-proxy process in the cluster, for the life of the process.",
    "fix": "Restore the push model: keep NodeEligible cached from the OnNodeChange/OnNodeDelete handlers (as SyncNode did before), updating it under the lock only when the node object actually changes, and have NodeEligible() do a cheap read (RLock, no DeepCopy) as before. If Node() must be read at request time, avoid DeepCopy for a read-only eligibility check (inspect DeletionTimestamp/Taints directly under NodeManager's own lock without copying the whole object), and don't hold hs.lock while doing it.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Redundant node informer** (explicitly asked to check): Before this PR, `NewNodeConfig` already used a dedicated single-node field-selector informer (`currentNodeInformerFactory`), separate from the general `informerFactory`. This PR consolidates that same kind of informer into `NodeManager` and now shares one `NodeInformer()` between both `NewNodeConfig` and the newly-added `NewNodeTopologyConfig` (cmd/kube-proxy/app/server.go:608,610). That's a reduction from what could have been two node watches to one — not a regression. No finding.
- **NodeIPs() / PodCIDRs() DeepCopy-adjacent cost**: `NodeManager.NodeIPs()` and `PodCIDRs()` take `n.mu.Lock()` per call, but the only call sites found (cmd/kube-proxy/app/server.go:217-218) are at process startup, once. Not a hot path. Anchor 0, suppressed.
- **Startup poll loop** (`wait.PollUntilContextCancel`, 1s interval, 5min timeout in `newNodeManager`, pkg/proxy/node.go:87-100): bounded to at most 300 iterations, runs once at process startup before the proxy is serving, not repeated. Cold path. Anchor 0, suppressed.
- **`NodeManager.mu` using `sync.Mutex` (exclusive) instead of `sync.RWMutex` for `Node()`/`NodeIPs()`/`PodCIDRs()`**: real but low-scale — writer (`OnNodeChange`) is rare (node object changes, not per-sync), and readers other than the flagged `NodeEligible()` path are startup-only. Anchor 25-50, suppressed per gate.
- **`OnNodeChange`'s `reflect.DeepEqual` on PodCIDRs/NodeIPs`** (pkg/proxy/node.go:148,163): operates on tiny slices (single node's IPs/CIDRs), fires only on node-object watch events, not a per-sync hot path. Anchor 0, suppressed.

Relevant files read: `/tmp/pr130837.diff`, `pkg/proxy/node.go`, `pkg/proxy/healthcheck/proxy_health.go`, `cmd/kube-proxy/app/server.go`, `pkg/proxy/config/config.go`, `pkg/proxy/iptables/proxier.go`, `pkg/proxy/nftables/proxier.go`, `pkg/proxy/ipvs/proxier.go`.
