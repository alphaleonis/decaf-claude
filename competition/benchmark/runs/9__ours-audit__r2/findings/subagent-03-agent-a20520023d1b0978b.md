# subagent agent-a20520023d1b0978b

I have enough to complete the analysis. Let me verify my reasoning on the poll-vs-API-load question by confirming the poll reads the lister (cache), not the API server — which I can see in node.go (line 88: `nodeLister.Get(nodeName)` on the informer's lister). Confirmed.

## Performance Review — PR #130837 (kube-proxy node manager)

I traced the four candidates. Only one is a reportable cost; the rest are provably trivial or actually reduce load. Findings as JSON:

```json
[
  {
    "file": "pkg/proxy/healthcheck/proxy_health.go",
    "line": 180,
    "severity": "Low",
    "category": "performance",
    "issue": "[PERF_HOT_PATH] NodeEligible() regressed from an RLock + single bool read to an exclusive hs.lock.Lock() plus a full Node DeepCopy on every /healthz request. The DeepCopy cost is proportional to the whole Node object (dominated by Status.Images, which on a busy node can be hundreds of entries) yet the function reads only DeletionTimestamp and Spec.Taints. The exclusive hs.lock now also guards no ProxyHealthServer state (the nodeEligible field it used to protect was removed), so it needlessly serializes /healthz against Health()/Updated()/QueuedUpdate(). Multiplication: per /healthz request served (cloud LBs poll :10256/healthz per node).",
    "fix": "Drop hs.lock in NodeEligible() (it protects no hs field). Avoid the DeepCopy: add a NodeManager method that evaluates eligibility under n.mu reading only node.DeletionTimestamp and node.Spec.Taints, or returns just those two fields, instead of returning n.node.DeepCopy().",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`OnNodeChange` calling `GetNodeHostIPs` + `reflect.DeepEqual` per event (pkg/proxy/node.go:140)** — The NodeManager informer is field-selected to `metadata.name == nodeName`, so this fires for exactly one Node, only on that node's watch updates plus the ConfigSyncPeriod resync (default 15 min). `GetNodeHostIPs` walks the small `Status.Addresses` slice and `DeepEqual` compares tiny `[]net.IP`/`[]string` slices. Cost is O(1) per event on a single object — no multiplication at scale. The prior per-proxier `OnNodeAdd/OnNodeUpdate` did the same `reflect.DeepEqual` over the full `node.Labels` map, so this is equal or cheaper. Not a cost regression.

- **`NodeTopologyConfig.handleNodeEvent` `reflect.DeepEqual` on topology labels (pkg/proxy/config/config.go:661)** — Compares a map of 0–1 entries (only `LabelTopologyZone` is copied in). Per single-node watch event. Trivial; the DeepEqual short-circuits redundant `OnTopologyChange` calls, so it net-reduces downstream `Sync()` work versus the old full-label comparison. Not a finding.

- **Per-node informer factory overhead** — Both `nodeConfig` and `nodeTopologyConfig` are wired to the *same* `s.NodeManager.NodeInformer()` (server.go), and it is the same single field-selected Node informer the old `currentNodeInformerFactory` provided. One LIST+WATCH on one Node object, same as before. No added watch/informer count, no added API-server load.

- **Removed exponential-backoff `Get` loop vs. new 1s poll — API-server load** — Not an amplification. The old `getNodeIPs` issued *direct* `client.CoreV1().Nodes().Get()` calls against the API server (up to 6, backing off). The new poll (node.go:87) runs `nodeLister.Get(nodeName)` against the **in-memory informer cache** every 1s; it does not touch the API server. The only API traffic is the informer's initial LIST + ongoing WATCH — standard, and strictly less than repeated GETs. The 1s cadence for up to 5 min is in-process cache reads (cheap). This change reduces, not increases, startup API-server load. No finding.

- **NodeEligible DeepCopy at scale / process memory** — I kept the one finding above at **Low/anchor-75** rather than higher: `/healthz` is polled by load balancers at low QPS (seconds-scale intervals), so even a node-size-proportional DeepCopy per call does not saturate CPU or the process — the impact is "measurable but minor waste, easy win," not a felt-at-scale cost. The copies are short-lived and GC'd, so there is no retention/unbounded-growth concern. Reported only because it is a concrete, per-request, clearly-unnecessary allocation-plus-exclusive-lock regression introduced by this diff with a trivial fix.

### Probe Requests
None. The one finding is grounded in a direct source read (DeepCopy in `NodeManager.Node()` invoked unconditionally by `NodeEligible()` on the `/healthz` path) and needs no runtime probe.
