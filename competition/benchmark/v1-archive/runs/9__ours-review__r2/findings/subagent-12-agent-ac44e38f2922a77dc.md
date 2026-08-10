# subagent agent-ac44e38f2922a77dc

## Findings

```json
[
  {
    "file": "cmd/kube-proxy/app/server.go",
    "line": 606,
    "severity": "Medium",
    "category": "correctness",
    "issue": "[BUG_LOGIC] Node-change detection window: NodeManager's informer is started and synced early inside NewNodeManager() (called from newProxyServer(), before the proxier is even created), but NodeManager is only registered as a NodeConfig event handler much later in Run(). Because NodeConfig's cache.ResourceEventHandlerFuncs (pkg/proxy/config/config.go NewNodeConfig) only sets UpdateFunc/DeleteFunc (no AddFunc), and client-go's late-handler-registration replay for an already-synced informer delivers only a synthetic Add (staging/src/k8s.io/client-go/tools/cache/shared_informer.go:701-721, 'send synthetic Add events to the new handler'), any real Node update that happens between the initial poll snapshot in newNodeManager() and this later RegisterEventHandler call is silently dropped (ResourceEventHandlerFuncs.OnAdd is a no-op when AddFunc is nil, staging/.../controller.go:257-261). The pre-PR code avoided this by creating and starting the node-specific informer fresh inside Run(), strictly after handler registration (git show 08727607^1:cmd/kube-proxy/app/server.go, currentNodeInformerFactory), so no such gap existed before this refactor.",
    "fix": "Register NodeManager (and start any node-specific processing) before the shared node informer is first started/synced, or explicitly reconcile NodeManager's in-memory node against the informer's current cache state at registration time (e.g. add an AddFunc to NodeConfig that also calls OnNodeChange, or have Run() call s.NodeManager.OnNodeChange with the informer's current object right after registering).",
    "confidence": 75,
    "pre_existing": false
  }
]
```

Note on the finding above: this gap is bounded, not permanent — `NodeConfig`'s informer periodic resync (interval = `--config-sync-period`, default 15 minutes) will eventually redeliver the node as an `UpdateFunc` call (client-go `processDeltas`, `Sync` delta type → `handler.OnUpdate(old, obj)`), which does reach `NodeManager.OnNodeChange` and would still trigger the crash-on-change fail-fast. So the practical effect is: a Node IP/PodCIDR change (or delete-then-recreate racing startup) that lands in the narrow window between the initial poll in `newNodeManager()` and `Run()`'s `nodeConfig.RegisterEventHandler(s.NodeManager)` call is not detected immediately as designed, but only after up to one `ConfigSyncPeriod`. I verified this end-to-end by reading the vendored `client-go` `shared_informer.go`/`controller.go` in this repo rather than relying on recollection.

## Considered But Not Flagged

- `pkg/proxy/node.go` `NodeManager.OnNodeChange`/`OnNodeDelete`/locking: correct — old/new state compared and swapped under `n.mu`, no races found.
- `pkg/proxy/node.go` `newNodeManager` storing the raw pointer from `nodeLister.Get()`/event `newObj` as `n.node` without deep-copying: matches existing kube-proxy/client-go idiom (informer objects are replaced, not mutated, on update); `Node()` accessor does `DeepCopy()` before exposing externally. Not a bug (confidence 0).
- `pkg/proxy/config/config.go` `NodeTopologyConfig` having no `DeleteFunc`/no `Run()`: intentional — topology labels only need Add/Update, and the handler is wired directly via `AddEventHandlerWithResyncPeriod` in the constructor rather than needing a separate `Run()` to wait for sync (confidence 0, by design).
- `pkg/proxy/healthcheck/proxy_health.go` `NodeEligible()` dereferencing `hs.nodeManager.Node()` with no nil check: `hs.nodeManager` is nil only for `HollowProxy`, which never sets `HealthzServer` either, so `NodeEligible()`/`Health()` handlers are never reached in that path (confidence 25, verified via `pkg/proxy/kubemark/hollow_proxy.go` — `HealthzServer` field left unset).
- `pkg/proxy/ipvs/proxier.go` `OnTopologyChange` not setting `needFullSync = true` (unlike iptables/nftables): matches pre-existing behavior — the old `OnNodeAdd/OnNodeUpdate/OnNodeDelete` in ipvs never set `needFullSync` either (verified in the diff), so this is a preserved, pre-existing asymmetry rather than a regression (pre_existing, not reported per severity threshold — not Critical/High and not newly introduced).
- `pkg/proxy/config/config.go` `NodeTopologyConfig.handleNodeEvent` passing the same `n.topologyLabels` map instance by reference to every registered handler (metaproxier's ipv4/ipv6 sub-proxiers, single proxier): safe today since no consumer mutates the map, only reads `topologyLabels[v1.LabelTopologyZone]` (confidence 25, speculative future-mutation risk only).
- `pkg/proxy/node.go` `newNodeManager` returning `err` (last loop iteration's error) instead of `pollErr` on timeout: intentional per the inline comment ("we return the actual error in case of poll timeout") to surface a more specific message than a generic context-deadline error; `err` is guaranteed set by the first (immediate) poll iteration given `pollTimeout` defaults to 5 minutes (confidence 25).
- Removed `waitForPodCIDR`'s `n.Spec.PodCIDR != "" && len(n.Spec.PodCIDRs) > 0` condition vs. new poll's `len(node.Spec.PodCIDRs) == 0` (dropping the deprecated singular `PodCIDR` check): consistent with `PodCIDR` being deprecated/redundant with `PodCIDRs`; not flagged as a behavior regression of concern.
