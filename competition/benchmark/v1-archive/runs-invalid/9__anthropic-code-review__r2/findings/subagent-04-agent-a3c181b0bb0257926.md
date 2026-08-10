# subagent agent-a3c181b0bb0257926

Depth: deep — node.go fully rewritten (~150 exec lines) plus config.go NodeTopologyConfig (~80) and health/server/proxier wiring; well over 200 executable lines, and it introduces process-lifecycle control (os.Exit on node watch events) — an operationally high-risk domain. All four techniques applied.

I have enough to construct the scenarios. Key mechanical facts verified:
- `GetNodeHostIPs` (pkg/util/node/node.go:65) is order-sensitive to `node.Status.Addresses` and returns `nil,err` when no InternalIP/ExternalIP parses.
- `OnNodeChange` (node.go:140) sets `n.node = node` before the IP error check and compares `oldNodeIPs` (re-derived from the stored node) to the new IPs with `reflect.DeepEqual`, calling `os.Exit(1)` on any difference.
- `NodeConfig` (config.go:288) registers only `UpdateFunc`+`DeleteFunc`; the informer's replayed initial ADD to this late-registered handler is dropped.
- Exit-on-NodeIP-change is entirely NEW behavior; the pre-PR code read node IPs once at startup and never crashed on IP change.

```json
[
  {
    "file": "pkg/proxy/node.go",
    "line": 167,
    "severity": "Critical",
    "category": "resource-management",
    "issue": "[ADV_CASCADE] Cloud/kubelet flaps node InternalIP order or transiently drops it across many nodes → every kube-proxy OnNodeChange sees a changed IP slice → os.Exit(1) fleet-wide → DaemonSet restarts all pods → each restart re-LISTs Nodes/Services/EndpointSlices from apiserver simultaneously (thundering herd) while NewNodeManager blocks up to 5m if addresses are still churning → dataplane goes stale cluster-wide and the apiserver load worsens the control-plane instability that caused the churn, amplifying the outage.",
    "fix": "Do not os.Exit on every observed NodeIP difference. Compare a normalized (family-keyed, order-independent) primary-IP set and exit only on a genuine primary-IP change; require the change to persist across a re-read (debounce) before exiting; add randomized startup jitter to the informer LIST to avoid synchronized re-list storms. Reconsider blocking startup for all detect-local modes (previously only LocalModeNodeCIDR failed startup).",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 145,
    "severity": "High",
    "category": "error-handling",
    "issue": "[ADV_COMPOSITION] OnNodeChange stores n.node=node BEFORE the GetNodeHostIPs error check, poisoning the comparison baseline. Sequence: (1) an update arrives whose Status.Addresses has no parseable InternalIP/ExternalIP (transient loss / hostname-only) → n.node is overwritten with the IP-less node, GetNodeHostIPs(node) errors → function returns without exit; (2) the next update restores the SAME IP A → oldNodeIPs is re-derived from the stored IP-less node = nil, new = [A], reflect.DeepEqual(nil,[A]) = false → os.Exit(1). The node's effective IP never changed (A → none → A) yet kube-proxy crashes — a spurious restart, and the concrete per-node trigger feeding the fleet cascade above.",
    "fix": "Only advance the IP comparison baseline when the incoming node yields valid IPs. Move `n.node = node` (or keep a separate lastGoodNodeIPs field) after the GetNodeHostIPs(node) success check, so a transient IP-less update does not become the baseline and a same-IP restore compares equal instead of exiting.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 290,
    "severity": "Medium",
    "category": "async",
    "issue": "[ADV_COMPOSITION] NodeConfig registers only UpdateFunc/DeleteFunc (no AddFunc), but it is wired onto an already-synced informer in ProxyServer.Run — after NewNodeManager already polled the lister snapshot in newProxyServer. client-go replays the current node to the newly-registered handler as an ADD, which is dropped. If the node's NodeIP or PodCIDR changes in the window between NewNodeManager's lister read and this handler registration, that delta arrives only in the dropped ADD; n.node/NodeIPs()/PodCIDRs() (already consumed to configure the proxier) stay stale and kube-proxy programs the dataplane with the old IP until some later unrelated node update fires OnNodeChange.",
    "fix": "Register an AddFunc routing to handleChangeNode/OnNodeChange (idempotent: equal IPs → no exit, changed IPs → intended restart), or have NodeManager reconcile its stored node against the informer once handlers are registered, so an in-window IP/PodCIDR change is observed rather than silently dropped.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Startup `return nil, err` yielding `(nil, nil)` → caller `s.NodeManager.NodeIPs()` nil-panic** (node.go:107-109): fell apart under backward check. `pollErr` is non-nil only on ctx timeout/cancel, and every `return false, nil` path in the condition first assigns `err` (Get error, GetNodeHostIPs error, or the PodCIDR error); the only `return true` path makes `pollErr` nil. `wait.PollUntilContextCancel(immediate=true)` guarantees ≥1 condition run, and a `select` that picks `doneCh` still leaves `err` holding the prior false-run's non-nil value. So `err` is non-nil whenever `pollErr` is non-nil — `(nil, nil)` is unreachable and the caller never sees a nil NodeManager with nil error.

- **Health eligibility race: `NodeEligible()` reads `nodeManager.Node()` while `OnNodeChange` may os.Exit** (proxy_health.go:180, node.go:140): no defect. `n.node` access is mutex-protected in both; `n.node` is non-nil from construction onward (poll succeeded) and each event sets it to the non-nil event object, so `Node().DeepCopy()` cannot nil-panic. A momentarily-stale eligibility read immediately before `os.Exit` is harmless (process is terminating). Informer handler callbacks are serialized, so no concurrent OnNodeChange.

- **Resync re-delivering the same object** (config.go:290 → node.go:167): resync fires UpdateFunc(old,new) with new==stored node; oldNodeIPs==nodeIPs → DeepEqual true → no exit. Not a spurious-exit source on its own.

- **Delete/recreate coalescing** (node.go:176): OnNodeDelete → os.Exit(1) is the intended contract; a coalesced delete+recreate still surfaces a delete and exiting-then-restarting is the designed behavior, not an emergent defect.

- **Dual-stack / same-family address reordering** as a standalone finding: reordering `Status.Addresses` changes which IP `GetNodeHostIPs` selects as primary, so exiting is arguably the intended "primary IP changed" response rather than clearly spurious. Folded into the fleet-cascade finding (A) as one realistic flap source rather than reported separately.
