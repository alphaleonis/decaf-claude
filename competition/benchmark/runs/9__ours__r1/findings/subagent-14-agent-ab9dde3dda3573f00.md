# subagent agent-ab9dde3dda3573f00

## PR #130837 — Performance Review (kube-proxy node manager consolidation)

**Scope reviewed**: `pkg/proxy/node.go`, `pkg/proxy/config/config.go`, `pkg/proxy/healthcheck/proxy_health.go`, `cmd/kube-proxy/app/server.go`, plus the proxier (`iptables`/`ipvs`/`nftables`/`winkernel`/`metaproxier`) topology-label changes, against `/tmp/pr130837.diff` and current HEAD source.

### Findings

```json
[
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 176,
    "severity": "High",
    "category": "performance",
    "issue": "[PERF_HOT_PATH] NodeEligible() — invoked once per /healthz request (kubelet's own liveness probe hits this endpoint on every kube-proxy pod, typically ~every 10s per node by default, and it is the same endpoint external load-balancer health checks poll for services with externalTrafficPolicy=Local, often at higher frequency) — now calls hs.nodeManager.Node() which does a full v1.Node DeepCopy() (pkg/proxy/node.go:186-190) on every call. v1.Node carries NodeStatus.Images ([]ContainerImage, up to node-status-max-images=50 entries with tag-name slices), ManagedFields, Annotations, Conditions, Capacity/Allocatable maps, etc. — a full structural copy that previously did not exist on this path at all. Before this PR, NodeEligible() was a cheap RLock+bool read of a value computed only on node *events* (SyncNode, called on the infrequent NodeConfig watch callback); the refactor moved a full-object deep copy from the infrequent node-event path onto the frequent per-request healthz path. Additionally, NodeEligible() takes hs.lock.Lock() (ProxyHealthServer's own RWMutex, full exclusive) for the duration of that copy, even though hs.lock no longer protects any node-related state (that state now lives behind NodeManager's own internal mutex). That exclusive lock is the same lock used by Health() (RLock, called by every /healthz and /livez request) and by Updated()/QueuedUpdate() (called by the proxier's sync loop on essentially every service/endpoint/topology sync). So every healthz probe now both allocates a full node copy and briefly serializes against the proxy sync loop's health bookkeeping, where before it did neither.",
    "fix": "Keep the pre-refactor shape: have NodeManager maintain a small, already-computed eligibility bool (or just DeletionTimestamp + Taints) updated once per node event under its own mutex, and have NodeEligible() do a cheap read of that instead of DeepCopy()-ing the whole Node per request. If the live node is genuinely needed, expose a narrow NodeManager accessor (e.g. IsEligible() or Taints()) that reads the two needed fields under NodeManager's own mutex without copying the rest of the object (Images, ManagedFields, Annotations, Conditions, etc.), and drop the now-unneeded hs.lock.Lock() from NodeEligible() (or downgrade the parts that still need it to RLock).",
    "confidence": 75,
    "pre_existing": false
  }
]
```

### Considered But Not Flagged

- **Informer/factory duplication (reviewer concern 1)**: Verified in `cmd/kube-proxy/app/server.go:608` and `:610` — `NewNodeConfig(...)` and `NewNodeTopologyConfig(...)` both consume the *same* `s.NodeManager.NodeInformer()` (a single node-scoped `SharedInformerFactory` created once in `newNodeManager`, `pkg/proxy/node.go:68-79`). They each call `AddEventHandlerWithResyncPeriod` on the same underlying `SharedIndexInformer`, which is the standard, cheap client-go pattern for multiple listeners on one watch/cache — no second informer, no second `List`/`Watch` to the apiserver. This was already true pre-refactor (patch 1 also shared one `currentNodeInformerFactory` between the two configs) and remains correct; not a finding.
- **`reflect.DeepEqual` on `[]net.IP` / `[]string` PodCIDRs in `NodeManager.OnNodeChange`** (`pkg/proxy/node.go:143-172`): slices are tiny (1-2 IPs, 1-2 CIDRs), and Node *object* update events are infrequent in practice — kubelet heartbeats go through the separate Lease object, not repeated Node-status PATCHes, so the Node informer's `UpdateFunc` fires only on real spec/status/label changes or on `resyncPeriod` (`ConfigSyncPeriod`, typically minutes). Per the task's own framing, this is correctly weighted as negligible. Anchor 0/25 — suppressed.
- **`NodeTopologyConfig.handleNodeEvent` fresh map + `reflect.DeepEqual` per node event** (`pkg/proxy/config/config.go:485-...`): the map holds at most one key (`topology.kubernetes.io/zone`) today, so the allocation and comparison are O(1) on a tiny structure, and the invocation rate is the same infrequent node-event rate as above. Not a nameable cost at any realistic scale. Anchor 0/25 — suppressed.
- **`NodeManager.PodCIDRs()` / `NodeIPs()`**: called once at proxy-server startup (`cmd/kube-proxy/app/server.go:211-215`) to seed `s.podCIDRs`/`s.NodeIPs`, not on a recurring hot path — cold path, not a finding.
- **Poll timeout increase from 30s → 5 minutes** (`NewNodeManager`, `pkg/proxy/node.go:56-61`): affects only kube-proxy startup latency in a pathological case (node object slow to appear/get IPs), not steady-state cost — out of scope for this persona (startup/cold path, not a recurring multiplication).

### Probe Requests

None — no destructive probes needed; the finding above was confirmed by direct code reading (`pkg/proxy/healthcheck/proxy_health.go`, `pkg/proxy/node.go`) and diff comparison against the pre-refactor `SyncNode`/cached-bool implementation, no test execution required.
