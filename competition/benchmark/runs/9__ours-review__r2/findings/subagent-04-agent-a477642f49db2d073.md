# subagent agent-a477642f49db2d073

## Performance Review — PR #130837 "Kube proxy node manager"

```json
[
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 176,
    "severity": "High",
    "category": "performance",
    "issue": "[PERF_HOT_PATH] NodeEligible() now calls hs.nodeManager.Node(), which acquires NodeManager's mutex and performs a full v1.Node DeepCopy on every invocation. This is executed unconditionally on every /healthz request (healthzHandler.ServeHTTP calls it once per call, never for /livez). Before this PR, eligibility was a push-model cached bool (SyncNode() computed it once per node watch event; NodeEligible() was a plain RLock+bool read with no allocation). The regression turns a formerly event-driven O(1) read into a per-request DeepCopy of the entire Node object (labels, annotations, status conditions, addresses, and the potentially sizable Status.Images list) on the primary kube-proxy health-check path, which is polled continuously by kubelet probes and, more aggressively, by cloud load-balancer health checks for services with externalTrafficPolicy=Local (often sub-10s intervals, sometimes multiple concurrent checks per node).",
    "fix": "Avoid cloning the whole node on the read path. Either (a) keep computing/caching the eligible bool inside NodeManager.OnNodeChange (push model, as before) and expose a cheap NodeManager.IsEligible() bool that just reads the cached value under the lock, or (b) add a NodeManager accessor that inspects DeletionTimestamp/Taints while holding the internal mutex without calling DeepCopy() (the node is only read, not retained, by NodeEligible).",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **NodeManager.Node() also called from NodeIPs()/PodCIDRs()** (pkg/proxy/node.go:120-132) — these DeepCopy-free accessors are only invoked once at `newProxyServer` startup, a cold path. Not flagged.
- **Duplicate informer factory** — verified this is *not* present: the old `currentNodeInformerFactory` in `cmd/kube-proxy/app/server.go` was fully removed; `NodeManager.thisNodeInformerFactory` is the only node informer, and its lister/informer is now shared between `NodeConfig` and the new `NodeTopologyConfig` via `s.NodeManager.NodeInformer()`. No duplicated watch. Not flagged.
- **Resync churn (ConfigSyncPeriod) on NodeConfig/NodeTopologyConfig** (pkg/proxy/config/config.go) — the node informer is field-selected to exactly one node (`metadata.name=<nodeName>`), so relist/resync replays exactly one object; `reflect.DeepEqual` cost per resync is bounded and cheap regardless of `ConfigSyncPeriod` value. Anchor 0 (bounded input) — not flagged.
- **`hs.lock.Lock()` (exclusive) inside NodeEligible() instead of RLock()** (pkg/proxy/healthcheck/proxy_health.go:177-178) — serializes concurrent `/healthz` requests against each other and against `Health()`'s RLock users, where before `NodeEligible()` used `RLock()`. Real, but the extra cost is lock contention/serialization, not amplified work per call, and whether concurrent hits to the same instance are frequent enough to matter depends on external LB configuration outside this diff. Anchor 50 — suppressed per persona bar; noting since it compounds with the DeepCopy finding (the DeepCopy now happens *while holding the exclusive lock*, extending the critical section length under load).
- **PollUntilContextCancel 1s-interval poll loop for up to 5 minutes** (pkg/proxy/node.go:85-104) — one-time startup cost bounded to at most 300 iterations of a cheap lister `Get`, not a recurring/hot-path cost. Not flagged.
- **OnTopologyChange propagation into iptables/ipvs/nftables/metaproxier proxiers** — stores a small `map[string]string` (0 or 1 entries: `topology.kubernetes.io/zone`), read directly (no copy) inside `CategorizeEndpoints` during the service sync hot path. No added per-service-sync cost. Not flagged.

Relevant files reviewed: `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/pkg/proxy/node.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/pkg/proxy/healthcheck/proxy_health.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/pkg/proxy/config/config.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/pkg/proxy/topology.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/cmd/kube-proxy/app/server.go`.
