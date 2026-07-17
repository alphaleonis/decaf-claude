# subagent agent-abf6ca1fd58068664

I have enough to complete the cost analysis. Let me record my task state and finalize.

My verification confirms:
- `NodeEligible()` is called exactly once per `/healthz` HTTP request (proxy_health.go:218) — not per sync, not per-user-request. It is the sole caller of `nodeManager.Node()` (the deep copy).
- `NodeIPs()` / `PodCIDRs()` are called once each at startup (server.go:217-218).
- The startup poll (`PollUntilContextCancel`, 1s) reads `nodeLister.Get()` — the in-memory informer cache, not the API server.
- `OnTopologyChange` fires only on zone-label change (config.go:661 DeepEqual gate); the old proxier gate fired on *any* label change.

Here is my report.

```json
[]
```

No performance findings meet the reporting bar (anchor >= 75). The change is net-neutral-to-positive on cost. Details below.

## Considered But Not Flagged

**[PERF_QUERY / resync frequency] `OnTopologyChange` vs. old all-labels `reflect.DeepEqual` gate — net REDUCTION in full syncs. Not a finding.**
Old path (`iptables/ipvs/nftables OnNodeAdd/OnNodeUpdate`, now deleted) set `needFullSync = true` and called `Sync()` on *any* change to this node's label set (`reflect.DeepEqual(proxier.nodeLabels, node.Labels)`). Any churn on an unrelated node label (instance-type, OS, custom controller labels, region) forced a full proxier resync. The new `NodeTopologyConfig.handleNodeEvent` (pkg/proxy/config/config.go:648-670) extracts only `v1.LabelTopologyZone` into a 1-entry map and de-dups centrally with `reflect.DeepEqual(n.topologyLabels, topologyLabels)` (config.go:661), firing `OnTopologyChange` → `needFullSync`/`Sync()` only when the *zone* changes. The zone-change set is a strict subset of the all-labels-change set, so full-sync frequency can only drop or stay equal. Informer resyncs (ConfigSyncPeriod, ~15m) also no longer produce spurious full syncs, since the zone is unchanged across a resync. This is a performance improvement, not a regression.

**[PERF_HOT_PATH / PERF_MEMORY] `NodeEligible()` now deep-copies the whole node per `/healthz` request. Real waste, but bounded by external probe interval — anchor 50, suppressed.**
`proxy_health.go:176-190` — `NodeEligible()` now calls `hs.nodeManager.Node()` (node.go:186-190), which does a full `node.DeepCopy()` under the NodeManager mutex, and holds `hs.lock.Lock()` (a full write lock, was `RLock`) for the duration. It reads only `DeletionTimestamp` and `Spec.Taints` — two tiny fields — yet copies the entire `v1.Node`, including `Status.Images` (can be tens of KB on image-heavy nodes), `Status.Conditions`, `Capacity`, `Allocatable`, all labels/annotations. Old code returned a cached bool with an `RLock` (O(1), zero allocation); eligibility was computed once per node event.
- Multiplication: one full-node deep copy per `/healthz` request.
- Scale: `NodeEligible()` has exactly one caller — `healthzHandler.ServeHTTP` (proxy_health.go:218), invoked once per `/healthz` request on port 10256. Frequency is bounded by external health-checkers (cloud LB node-eligibility probes / monitoring), typically one probe every several seconds per node — single-digit req/s even in aggressive setups. At that rate a few-KB deep copy is a few KB/s of short-lived garbage: negligible for the process, felt by no operator. I cannot show this path is hot at any scale that hurts, so it does not reach anchor 75. Worth noting for a maintainer as a cheap cleanup (read the two fields under the manager lock instead of `DeepCopy()`, or expose a purpose-built `NodeEligible`-style accessor), but not a scale-cost finding. The `RLock`→`Lock` change is likewise immaterial at this QPS.

**[PERF_HOT_PATH] Startup poll loop (`newNodeManager`, node.go:87-104). Reasonable, not a finding.**
`wait.PollUntilContextCancel(ctx, pollInterval=1s, immediate=true, ...)` with a 5m timeout polls `nodeLister.Get(nodeName)` — the informer's in-memory cache, populated by the watch — not the API server. Worst case ~300 in-memory cache reads over 5 minutes before PodCIDR/NodeIP allocation completes. No API load, no allocation of note. Cheaper than the old `toolswatch.UntilWithSync` watch it replaces.

**[PERF_MEMORY] Fresh `map[string]string` allocation per event in `handleNodeEvent` (config.go:655). Trivial, not a finding.**
One 1-entry map allocated per Add/Update event, plus a 2-map `reflect.DeepEqual`. The informer is field-selected to this single node (node.go:69-71), so events fire only on this node's object updates (status/label/condition changes) — minutes-to-~10s cadence, not a hot path. As the task notes, acceptable given event rarity; the allocation is a handful of bytes per infrequent event.

**[PERF_HOT_PATH] `NodeManager.OnNodeChange` (node.go:140-173) per node event. Trivial, not a finding.**
Two `GetNodeHostIPs` scans of `Status.Addresses` (small) plus slice `DeepEqual`s, per single-node update event. Bounded and cheap.

No cost that survives scale was found in this changeset.
