# subagent agent-acbde9aae09501858

Confirmed: default resync is 15 min. Depth assessment complete.

---

## Adversarial Review — kube-proxy NodeManager refactor (PR #130837)

**Depth: deep** — ~340 changed executable lines; touches external-API integration (node informer/watch) and process-lifecycle control (every code path in `NodeManager.OnNodeChange`/`OnNodeDelete` can call `os.Exit(1)` on a running kube-proxy). All four techniques applied; multi-step chains traced end to end.

### Assumption inventory (reference frame)
1. `GetNodeHostIPs(node)` produces an **order-stable** slice across successive Node updates (used by `reflect.DeepEqual` to decide whether to exit).
2. The Node always has retrievable host IPs on every watch event (`OnNodeChange` early-returns on the error path *after* mutating baseline state).
3. NodeIP/PodCIDR changes are only ever observed as informer **Update** events (no `AddFunc` registered for `NodeManager`).
4. The node object exists and has valid host IPs within 5 min of kube-proxy start, or the process should fail entirely.
5. A NodeIP change is a rare, deliberate, per-node event (not a synchronized fleet-wide one).

The scenarios below break assumptions 1–4 and exploit the blast radius of 5.

```json
[
  {
    "file": "pkg/proxy/node.go",
    "line": 167,
    "severity": "High",
    "category": "resource-management",
    "issue": "[ADV_CASCADE] Benign same-family address reorder in Node.Status.Addresses → GetNodeHostIPs returns a differently-ordered slice → reflect.DeepEqual false → os.Exit(1); a controller rolling the change across the fleet trips every kube-proxy at once → cluster-wide CrashLoopBackOff and dataplane sync gaps.",
    "fix": "Compare NodeIPs as an order-independent set (sort or use sets.New) before deciding to exit, and/or debounce/rate-limit the self-terminate so a single upstream event cannot synchronously kill every kube-proxy. At minimum, only exit when the primary IP set actually differs, not its ordering.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 145,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_COMPOSITION] OnNodeChange sets n.node = node BEFORE validating IPs; a transient update whose Status.Addresses has no parseable InternalIP/ExternalIP hits the GetNodeHostIPs error path and returns after corrupting the baseline (oldNodeIPs now derives from the IP-less node = nil). The very next event restoring the original IP compares nil vs [IP] → spurious os.Exit(1) even though the real NodeIP never changed.",
    "fix": "Only advance n.node after successfully deriving nodeIPs; on the GetNodeHostIPs error path, leave the previous baseline intact (compute nodeIPs first, update n.node last).",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 289,
    "severity": "Medium",
    "category": "async",
    "issue": "[ADV_COMPOSITION] NodeConfig registers only UpdateFunc/DeleteFunc (no AddFunc) for NodeManager. NewNodeManager polls the node (baseline IP1) during newProxyServer; the UpdateFunc handler is only registered much later in Run(). A NodeIP change in that window is folded into the informer cache and re-delivered to the late handler as a replay Add — which is dropped — so NodeManager keeps baseline IP1 while kube-proxy has already programmed rules with the stale IP. Detection is deferred to the next resync-driven Update (ConfigSyncPeriod, default 15m), i.e. up to 15 minutes serving traffic on stale NodeIPs before the delayed crash.",
    "fix": "Either register an AddFunc that routes to handleChangeNode, or re-seed NodeManager's baseline from the lister at handler-registration time so an in-window change is caught immediately rather than at the next resync.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 107,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_ASSUMPTION] NewNodeManager now hard-fails startup (returns err → newProxyServer returns err → kube-proxy exits) if the node lacks retrievable host IPs after a 5-minute poll. The removed getNodeIPs used a ~63s non-fatal backoff and returned nil, letting detectNodeIPs fall back to BindAddress so kube-proxy still started degraded. On nodes where the cloud provider/kubelet publishes the InternalIP later than 5 min (slow bare-metal/cloud bring-up), kube-proxy now CrashLoopBackOffs at boot instead of starting.",
    "fix": "Confirm this stricter contract is intended for all DetectLocalModes (not just NodeCIDR); if degraded-start via BindAddress fallback should be preserved, don't treat missing NodeIPs as a fatal NewNodeManager error outside watchPodCIDRs mode. Document the behavior change in the PR/release notes.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`ProxyHealthServer.NodeEligible()` nil-deref on `hs.nodeManager.Node()`** — construction is gated in `newProxyServer` (NodeManager set before HealthzServer), and the hollow-proxy path builds no HealthzServer and no NodeManager, so `Run()`'s `if s.NodeManager != nil` and the nil HealthzServer both avoid the call. No production path reaches a non-nil health server with a nil nodeManager. Fell apart on the backward check.
- **Import cycle (healthcheck→proxy, proxy→healthcheck)** — `node.go` dropped its healthcheck import and the code merged/compiles; couldn't construct a cycle from the tree.
- **`NodeTopologyConfig.listerSynced` set but never consulted** (no `Run`, handlers fire directly off the informer) — dead field / minor, no failure chain; topology init still works via the replay-Add because NodeTopologyConfig *does* register AddFunc.
- **`PodCIDRs()` returns `n.node.Spec.PodCIDRs` without deep-copy (aliases shared informer cache slice)** — only consumer (`server.go`) reads it; no mutation constructed, so no concrete bad outcome.
- **Fleet-wide crash on a *genuine* NodeIP change being by-design** — the PR intends to exit on real NodeIP/PodCIDR change; only the *spurious* reorder trigger (F1) and the window/baseline mechanics (F2, F3) are emergent defects, so I did not flag the intended-crash path itself.

### Probe Requests
- **File/test:** `pkg/proxy/node_test.go` — add a case to `TestNodeManagerOnNodeChange`: initial NodeIPs `["192.168.1.1","fd00::1"]`, updated NodeIPs `["fd00::1","192.168.1.1"]` (same set, reordered). **Expected with fix absent:** `expectedExitCode: ptr.To(1)` (confirms F1 — a pure reorder self-terminates). This isolates whether ordering alone trips the exit.
- **File/test:** `pkg/proxy/node_test.go` — sequence on one NodeManager: `OnNodeChange(makeNode(tweakNodeIPs()))` (no addresses) then `OnNodeChange(makeNode(tweakNodeIPs("192.168.1.1")))` where `192.168.1.1` equals the initial baseline. **Expected with F2 present:** second call exits(1) despite the effective NodeIP being unchanged from the original baseline (confirms baseline corruption on the error path).
