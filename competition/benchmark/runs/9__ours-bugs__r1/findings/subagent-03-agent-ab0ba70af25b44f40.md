# subagent agent-ab0ba70af25b44f40

I have enough to construct the scenarios. Let me verify one mechanical detail: that the reused informer is already started/synced before the two configs register handlers (confirming replay-as-Add semantics apply).

The chain is confirmed from the code already read: `NewNodeManager` calls `thisNodeInformerFactory.Start` + `WaitForNamedCacheSync` (node.go:76-79) and returns the same `nodeInformer` (node.go:135-137), which server.go:608/610 then hands to `NewNodeConfig`/`NewNodeTopologyConfig`, both of which call `AddEventHandlerWithResyncPeriod` on an already-synced informer.

Depth: deep — node.go is a ~200-line rewrite introducing process self-termination on node events; high-risk (concurrent informer lifecycle + os.Exit). All four techniques applied, focus on exit-semantics and initial-vs-event state consistency per instructions.

Findings:

```json
[
  {
    "file": "pkg/proxy/config/config.go",
    "line": 290,
    "severity": "Medium",
    "category": "async",
    "issue": "[ADV_COMPOSITION] node IP changes during the startup window are silently dropped → kube-proxy runs with stale NodeIPs. Sequence: (1) NewNodeManager starts+syncs the informer and polls, capturing node V1 with InternalIP 10.0.0.5 (node.go:76-104); (2) newProxyServer builds the proxier from that captured IP (server.go:217); (3) BEFORE server.go:608-609 registers NodeManager as a handler, kubelet updates the node to InternalIP 10.0.0.6 — this Update lands in the shared informer cache but NodeManager is not yet a handler, so OnNodeChange never sees it; (4) when NewNodeConfig finally registers the handler on the ALREADY-synced informer, client-go replays the current object (V2) as an Add, but NodeConfig registers only UpdateFunc/DeleteFunc — no AddFunc — so the replay is discarded and n.node stays V1. Result: the proxier programs rules with the stale 10.0.0.5 (wrong NodePort/masquerade IP) and NodeManager's stored 'old' also equals 10.0.0.5, so the change is invisible. It only self-heals when the next unrelated node Update arrives (comparing new 10.0.0.6 vs stale 10.0.0.5 → os.Exit), which under lease-based heartbeats can be up to nodeStatusReportFrequency (~5m) away.",
    "fix": "After registering the NodeManager handler, re-read the current node from the lister and reconcile against the captured node (or register an AddFunc that routes to OnNodeChange), so an IP change that occurred between poll capture and handler registration is detected immediately rather than waiting for the next Update.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 167,
    "severity": "Medium",
    "category": "async",
    "issue": "[ADV_ABUSE] address reordering with no real IP change triggers a spurious os.Exit(1) — a crash the pre-change code never had (old code captured NodeIPs once and never re-checked). GetNodeHostIPs derives the primary IP from the ORDER of node.Status.Addresses (node.go/util: InternalIPs in listed order, primary = first) and picks the dual-stack secondary as the first address of the other family. For a dual-stack node with InternalIPs [10.0.0.5, fd00::5], a node Update that merely re-lists them as [fd00::5, 10.0.0.5] (same set, different order / flipped primary family) makes reflect.DeepEqual(oldNodeIPs, nodeIPs) false → n.exitFunc(1). The node's actual reachable IPs are unchanged, but kube-proxy restarts. Under a flapping ordering this becomes a restart loop.",
    "fix": "Compare NodeIPs as an order-insensitive set (or compare only the primary-family membership that actually matters) before deciding to exit, so pure reordering of equal address sets does not terminate the process.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **NodeTopologyConfig has no `Run`/`HasSynced` and `nodeTopologyConfig.Run(...)` is never called (server.go:610-613).** Attempted: "initial topology labels never delivered → topology-aware routing broken at startup." Fell apart: the handler is registered on an already-synced shared informer (synced inside `NewNodeManager`), so client-go replays the current node as an Add → `handleNodeEvent` → `OnTopologyChange` delivers initial state. No Run is needed. Not a defect.

- **Lock scope in `OnNodeChange` — exit decision computed on values read before `mu` is unlocked (node.go:142-172).** Attempted: "concurrent OnNodeChange reads torn old state → wrong exit decision." Fell apart: shared-informer handler callbacks for a single registration are delivered serially by one goroutine, so `OnNodeChange` never overlaps itself; `mu` only guards against concurrent `Node()`/`NodeIPs()`/`PodCIDRs()` readers, which each take the lock and see a consistent swap. No race in the exit path.

- **`PodCIDRs()`/`NodeIPs()` return slices aliasing the shared informer-cache object (node.go:123-131), stored into `s.podCIDRs` (server.go:218).** Attempted: "caller mutates slice → corrupts shared informer cache seen by other handlers." Fell apart: every consumer (`server.go:293`, `badCIDRs` at 343) reads only; no append/mutation of `s.podCIDRs`. Latent aliasing hazard, not a triggered defect. Low, not flagged.

- **Nil `nodeManager` deref in `NodeEligible` → `hs.nodeManager.Node()` (proxy_health.go:180).** Attempted: hollow-proxy / healthz path with nil NodeManager. Fell apart: healthz server is created only when `HealthzBindAddress` is set (server.go:243), hollow-proxy sets no HealthzBindAddress, and in the real path `NewNodeManager` errors abort `newProxyServer` before the healthz server is built — so `nodeManager` is always non-nil where `NodeEligible` runs, and `n.node` is guaranteed set by the poll. No nil deref.

### Probe Requests
- `go test -race ./pkg/proxy/config/ ./pkg/proxy/ -run 'Node' -count=1` — confirm the existing NodeManager/NodeConfig tests exercise (or miss) the poll-vs-registration window; I did not run it to keep to read-only scope.
