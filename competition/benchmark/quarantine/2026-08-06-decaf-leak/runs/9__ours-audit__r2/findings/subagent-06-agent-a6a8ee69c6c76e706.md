# subagent agent-a6a8ee69c6c76e706

I now have the full picture. Let me assess the cost of the new node-watching path.

## Analysis summary

I traced the four cost dimensions in the task:

**1. Poll loop in `newNodeManager` (node.go:87-104)** — Not a concern; in fact a win. The poll body calls `nodeLister.Get(nodeName)`, which reads the informer's in-memory cache, **not** the apiserver. Interval is 1s (prod), bounded by a 5-minute timeout (~300 iterations worst case), all against a local map. The old `getNodeIPs` did real `client.CoreV1().Nodes().Get()` apiserver calls with backoff, and `waitForPodCIDR` opened a separate ListWatch. The new path strictly reduces apiserver load.

**2. Informer count** — A win. `NewNodeManager` creates a single field-selected node informer; both `nodeConfig` and `nodeTopologyConfig` register handlers on that same shared informer (`s.NodeManager.NodeInformer()`). This replaces the former separate `currentNodeInformerFactory` plus the standalone `waitForPodCIDR` watch. One watch connection, shared.

**3. Topology-label filtering** — Correctly filtered. `handleNodeEvent` (config.go:648) extracts only `topology.kubernetes.io/zone`, and short-circuits via `reflect.DeepEqual` when the filtered label set is unchanged, so `OnTopologyChange` → proxier full resync fires **only** on actual zone-label changes, not on every node heartbeat. The per-event allocation (a 0-1 entry map) is trivial and the watch is a single node. Not a finding.

**4. Lock contention + the healthz read path** — This is where I found a real regression, below.

The one finding:

## Findings

```json
[
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 176,
    "severity": "Medium",
    "category": "performance",
    "issue": "[PERF_HOT_PATH] NodeEligible() regressed the /healthz probe path from an O(1) cached-bool read under RLock to a full v1.Node DeepCopy under an exclusive write lock, recomputed per request. healthzHandler.ServeHTTP calls NodeEligible() on every probe; it takes hs.lock.Lock() (exclusive) and calls nodeManager.Node() which does n.node.DeepCopy() of the entire Node (Status.Images, Conditions, Labels/Annotations, ManagedFields — hundreds of entries on a busy node) just to read DeletionTimestamp and iterate Spec.Taints. kube-proxy /healthz (:10256) is the node health check fanned-in by cloud load balancers fronting LoadBalancer Services; on a node backing many such Services this is probed at tens-to-hundreds/sec, so this is a large allocation per probe. Worse, hs.lock is now taken as a WRITE lock (was RLock) even though NodeEligible no longer touches any hs.lock-protected field — the exclusive lock is held across the whole DeepCopy and serializes every probe against Updated()/QueuedUpdate(), which each proxier sync calls on the data-plane path.",
    "fix": "Stop deep-copying and stop taking hs.lock in NodeEligible. Either (a) restore the cached-bool approach: have NodeManager compute an eligible bool inside OnNodeChange/OnNodeDelete (the rare write path) and expose a lightweight NodeEligible() bool accessor guarded only by nodeManager.mu; or (b) add a NodeManager method that reads DeletionTimestamp and Taints directly under nodeManager.mu without DeepCopy, and drop the now-spurious hs.lock.Lock() in the health server's NodeEligible().",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Poll loop hammering the apiserver (node.go:87)** — Dismissed; the poll reads `nodeLister.Get()` (local informer cache), not the apiserver. Net reduction versus the removed `getNodeIPs` Get-with-backoff and `waitForPodCIDR` ListWatch. A performance improvement, not a cost.
- **`handleNodeEvent` allocating a fresh `map[string]string` per node event (config.go:655)** — Bounded input: single field-selected node, and the map holds 0-1 entries. The `reflect.DeepEqual` short-circuit means downstream `OnTopologyChange` (and proxier full resync) only fire on real zone-label changes. Trivial cost; correctly filtered. This directly answers the task's question — yes, the path is filtered so needless full resyncs are avoided.
- **`OnNodeChange` calling `GetNodeHostIPs` twice + two `reflect.DeepEqual` per event (node.go:143-167)** — Single node, node-update frequency (heartbeats every ~10s), tiny slices. No felt cost.
- **Two informer configs (`nodeConfig` + `nodeTopologyConfig`) both registered on the same informer (server.go)** — Each node event runs both handler chains, but on one node with cheap handlers. Not a multiplication that hurts.
- **`nodeManager.mu` contention between `OnNodeChange` writer and `NodeIPs()`/`PodCIDRs()`/`Node()` readers (node.go)** — Writer holds the lock only to swap a pointer; the readers are startup-only (`NodeIPs`/`PodCIDRs` called once in `newProxyServer`) except `Node()`, whose sole hot caller is the healthz path already covered by the finding above. No separate finding.
- **Informer started with `wait.NeverStop` and never stopped (node.go:76)** — Intended process-lifetime singleton for a long-running daemon; not unbounded growth.

## Residual risks / notes for other reviewers (out of my lane)
- `NodeEligible()` calls `hs.nodeManager.Node()` with no nil guard; if a health server is ever constructed with a nil `NodeManager` (hollow-proxy wiring), this panics — a correctness concern for quick-reviewer/go-reviewer, not performance.
- The flush-then-exit change (`klog.Flush(); os.Exit(1)` vs `klog.FlushAndExit`) noted in the context is a correctness/robustness matter, not a cost one.

### Probe Requests
None required — all claims are verifiable from the source as read.
