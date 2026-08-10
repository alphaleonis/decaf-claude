# subagent agent-a6521b471507cd75f

Analysis complete. The full multi-commit diff, the merged `config.go`, `node.go`, `proxy_health.go`, and `topology.go` are all traced.

---

Depth: deep — ~270 executable lines across node lifecycle/crash management, health eligibility, and endpoint topology routing; external-API (informer/watch) integration and process-lifecycle mutation touched.

## Findings

The central emergent issue is a composition failure introduced by commit 5 (`OnNodeAdd`/`OnNodeUpdate` → `OnNodeChange`): `NewNodeConfig` wires only `UpdateFunc` and `DeleteFunc`, with **no `AddFunc`**, while the `NodeManager` it drives is registered on an informer that was already `Start()`ed and cache-synced back in `newProxyServer` (server.go:211), long before the handler is attached in `Run()` (server.go:608).

```json
[
  {
    "file": "pkg/proxy/config/config.go",
    "line": 290,
    "severity": "Medium",
    "category": "async",
    "issue": "[ADV_COMPOSITION] node field changes in the startup window are delivered to NodeManager only as a replayed Add, which NewNodeConfig drops (no AddFunc) → stale NodeIPs/eligibility served until next Update/resync",
    "fix": "Add `AddFunc: func(obj interface{}) { result.handleChangeNode(obj) }` to the ResourceEventHandlerFuncs in NewNodeConfig so creation/initial-list events reach OnNodeChange, matching the interface contract ('OnNodeChange is called whenever creation or modification ... is observed').",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 323,
    "severity": "Low",
    "category": "error-handling",
    "issue": "[ADV_ASSUMPTION] handleChangeNode's DeletedFinalStateUnknown/tombstone branch is unreachable — it is wired only to UpdateFunc, and tombstones arrive exclusively via DeleteFunc, so the recovery path can never execute",
    "fix": "Drop the tombstone branch from handleChangeNode (it belongs only in handleDeleteNode), or wire handleChangeNode to AddFunc where an initial-list object is a plain *v1.Node and no tombstone is possible — either way the current code implies a code path that cannot run.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

### Finding 1 detail — the constructed scenario

Forward path (every step verifiable from the diff):
1. `newProxyServer` calls `NewNodeManager` (server.go:211). It `Start()`s the single-node informer, cache-syncs, polls until the node exists with an IP, and captures `n.node` (IP=A). The informer keeps running and updating its cache.
2. Startup then does `platformSetup`, `createProxier`, etc. — a real multi-step window.
3. During that window the node object changes on the API server — e.g. `InternalIP` A→B, or a `ToBeDeletedTaint` is added. The informer cache absorbs it; no handler is attached to `NodeManager` yet.
4. `Run()` (server.go:608) calls `NewNodeConfig(...)` and `RegisterEventHandler(s.NodeManager)`. Adding a handler to an already-synced sharedIndexInformer replays the current cache item as an **Add** (`isInInitialList: true`).
5. `NewNodeConfig`'s `ResourceEventHandlerFuncs` has no `AddFunc` → the replay is silently discarded. `NodeManager.OnNodeChange` is never called for it.

Outcome: two divergent consequences from the same drop:
- **NodeIP path:** `n.node`/detected NodeIPs stay at A. The proxier's `s.NodeIPs` are fixed at startup and only ever refreshed by crashing on a detected change — so kube-proxy keeps programming rules (NodePort bind, masquerade) for the stale IP A instead of exiting to pick up B. It self-heals only when the next real `Update` or resync (`ConfigSyncPeriod`, default 15m) fires an `OnNodeChange` that finally observes the delta and exits.
- **Eligibility path:** `ProxyHealthServer.NodeEligible()` (proxy_health.go) now reads `nodeManager.Node()` live; with `n.node` stale it reports the draining/tainted node as eligible, so load balancers keep steering traffic at it until the same delayed refresh.

Backward check: for the bad outcome, the field change must land in the poll→register window (step 3) and no subsequent `Update` must arrive before it matters — both plausible but unconfirmable from code alone, hence confidence 50 (the drop mechanism itself is 100 constructible). Before commit 5, `NewNodeConfig` had `AddFunc: result.handleAddNode`, so the replay was delivered and the change caught immediately; the change introduced the gap.

## Considered But Not Flagged

- **Node delete unconditionally crashes kube-proxy** (`NodeManager.OnNodeDelete` → `exitFunc(1)`). This is a deliberate, documented design change ("crashes kube-proxy") — old `NodeEligibleHandler`/`NodePodCIDRHandler` only logged/marked-ineligible. Behavior shift with crashloop potential under node-object churn, but intended; design-reviewer scope, not an emergent defect.
- **5-minute blocking startup now applies to all modes.** `NewNodeManager` uses a 5m `pollTimeout` and hard-fails startup (returns error → process exits) if the node has no IP; the old `getNodeIPs` did ~63s of non-fatal backoff. New hard dependency on "kubelet sets node IPs within 5m," else crashloop. Self-healing and matches the PR's stated "block on startup" intent — falls apart as a defect because the failure is the designed behavior.
- **`newNodeManager` nil-manager/nil-error return** (would nil-deref at `s.NodeManager.NodeIPs()`). Fell apart under construction: `PollUntilContextCancel(immediate=true)` always runs the closure at least once, so on timeout the outer `err` is always set non-nil whenever `pollErr` is non-nil; the nil-nil path is unreachable.
- **Shared topology-label map mutation race.** Fell apart: `handleNodeEvent` allocates a fresh map per event and never mutates a published one; informer handlers are serialized; proxier read/write of `topologyLabels` is under `proxier.mu`. No race.
- **Topology filter drops a needed label.** Checked `CategorizeEndpoints`/`topologyModeFromHints`/`availableForTopology` — only `LabelTopologyZone` is consumed (PreferSameNode keys off `nodeName`, not a label), so filtering to zone-only is consistent with the added guard comment.

### Probe Requests
- Run `go test -race ./pkg/proxy/config/... ./pkg/proxy/...` targeting `TestNewNodeConfig`-adjacent and `TestNewNodeManager`/`TestNodeManagerNode` to confirm no handler-registration race under the detector (optional; does not exercise the dropped-Add window).
