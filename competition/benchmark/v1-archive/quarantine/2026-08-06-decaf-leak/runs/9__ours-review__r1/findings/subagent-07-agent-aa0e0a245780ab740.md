# subagent agent-aa0e0a245780ab740

Depth: deep — node-watch lifecycle rewrite spanning ~250+ executable lines across `pkg/proxy/node.go` (full rewrite), `pkg/proxy/config/config.go`, and `pkg/proxy/healthcheck/proxy_health.go`; external informer integration plus process-lifecycle control (os.Exit). All four techniques applied.

I traced the NodeManager event flow, the informer handler wiring, and the healthz eligibility path. Findings below.

```json
[
  {
    "file": "pkg/proxy/node.go",
    "line": 179,
    "severity": "High",
    "category": "error-handling",
    "issue": "[ADV_CASCADE] Node object transiently deleted+recreated (etcd restore, node re-registration, node-controller churn) → informer DeleteFunc → OnNodeDelete → unconditional os.Exit(1) → kube-proxy restart → NewNodeManager blocks up to 5m polling for node to reappear with IPs → connectivity/proxy-rule gap; repeats on each churn = crash loop",
    "fix": "This is a behavior regression: the old NodePodCIDRHandler.OnNodeDelete only logged and NodeEligibleHandler marked the node ineligible (healthz 503) while the proxy kept running. Restore graceful degradation — on delete, drive NodeEligible()->false (503) rather than os.Exit(1), or only exit if the deletion is confirmed durable rather than a transient watch delete.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 159,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_CASCADE] Update arrives for a node whose Status.Addresses momentarily lack a parseable Internal/External IP → n.node is overwritten to the IP-less node (line 145) BEFORE the GetNodeHostIPs check, which then errors and returns early (line 161-162), leaving the corrupted baseline → next normal update restoring IP1 computes oldNodeIPs=nil from the bad baseline, newNodeIPs=[IP1], reflect.DeepEqual(nil,[IP1])=false → spurious os.Exit(1) even though the node IP never actually changed",
    "fix": "Validate the incoming node's host IPs BEFORE committing it as the baseline: if GetNodeHostIPs(node) errors, log and return WITHOUT overwriting n.node (treat as no-change), so a transient addressless update cannot poison the comparison baseline.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 290,
    "severity": "Medium",
    "category": "async",
    "issue": "[ADV_COMPOSITION] NodeConfig registers only UpdateFunc/DeleteFunc (no AddFunc) on the shared informer that NewNodeManager already started and synced. A real NodeIP change occurring in the window between NewNodeManager's initial poll (baseline captured, proxier configured from it) and this later handler registration is replayed to the new handler as an Add event → dropped → NodeManager keeps the stale baseline and kube-proxy runs with the wrong NodeIP (NodePort bind / masquerade) until some later unrelated Update triggers a (delayed) restart",
    "fix": "Add an AddFunc that also routes to handleChangeNode, or have NodeManager re-read the lister to re-seed its baseline at the point the node handler is registered, so an IP change during the startup registration window is not silently dropped.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Dead tombstone branch in `handleChangeNode` (config.go:323-331).** `cache.DeletedFinalStateUnknown` is only ever delivered through `DeleteFunc`, never `UpdateFunc`, so this branch is unreachable. Checked the concern that a real delete-final-state case is mishandled elsewhere: `handleDeleteNode` (config.go:342-350) handles the tombstone correctly, so no real delete is dropped. Harmless dead code, not a failure scenario.
- **Nested lock `hs.lock` → `NodeManager.mu` in `NodeEligible()` (proxy_health.go:177-180).** No deadlock: `NodeManager` never acquires `hs.lock`, so the lock order is globally consistent (one direction only). `Health()` and `NodeEligible()` are called sequentially in `ServeHTTP`, not nested. Fell apart under the backward check. The RLock→Lock change is a minor serialization regression (performance-reviewer scope), not a correctness defect.
- **`hs.nodeManager` nil-deref in `NodeEligible()`.** In `newProxyServer`, `NodeManager` is always set (line 211) before `HealthzServer` is built (line 244); hollow-proxy builds neither `NodeManager` nor `HealthzServer` and `serveHealthz` no-ops on a nil server. No production path reaches a nil deref.
- **Resync-driven spurious exit.** Every-`ConfigSyncPeriod` resync redelivers the identical cached node as an Update; `GetNodeHostIPs` and `PodCIDRs` compare equal → no exit. Safe; the scenario collapses.
- **`PodCIDRs()`/`NodeIPs()` returning informer-owned slices without deep copy.** Both are called only once at startup (server.go:217-218) single-threaded before any handler runs, so no concurrent-read race materializes.
