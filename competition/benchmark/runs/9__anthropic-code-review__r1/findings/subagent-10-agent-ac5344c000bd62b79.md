# subagent agent-ac5344c000bd62b79

## Code-comment compliance review — PR #130837 (kube-proxy node manager)

I read the diff (`gh pr diff 130837`) and the current state of every listed file at HEAD `46e2c22f`, then cross-checked the doc comments against the vendored `client-go` informer implementation (`staging/src/k8s.io/client-go/tools/cache/shared_informer.go`, `controller.go`) to verify runtime behavior rather than just eyeballing it. Two real mismatches survived verification; several other candidates (Provider interface, metaproxier, winkernel stub, topology.go note, `NodeManager.Node()`/`NodeIPs()`/`PodCIDRs()` docs) checked out fine and are not included.

### Finding 1 (high confidence) — `OnNodeChange`'s "creation" contract is never actually fulfilled

**Comments claiming the contract:**
- `pkg/proxy/config/config.go:263-265` (interface doc):
  ```go
  // OnNodeChange is called whenever creation or modification
  // of node object is observed.
  OnNodeChange(node *v1.Node)
  ```
- `pkg/proxy/config/config.go:301`: `// RegisterEventHandler registers a handler which is called on every node change.`
- `pkg/proxy/node.go:41-43` (struct doc): `// NodeManager handles the life cycle of kube-proxy based on the NodeIPs and PodCIDRs handles / node watch events and crashes kube-proxy if there are any changes in NodeIPs or PodCIDRs.`
- `pkg/proxy/node.go:139`: `// OnNodeChange is a handler for Node creation and update.`

**Conflicting code:** `pkg/proxy/config/config.go:288-294`
```go
handlerRegistration, _ := nodeInformer.Informer().AddEventHandlerWithResyncPeriod(
    cache.ResourceEventHandlerFuncs{
        UpdateFunc: func(_, newObj interface{}) { result.handleChangeNode(newObj) },
        DeleteFunc: result.handleDeleteNode,
    },
    resyncPeriod,
)
```
There is no `AddFunc`. `cache.ResourceEventHandlerFuncs.OnAdd` (`staging/.../tools/cache/controller.go:257-261`) is a no-op when `AddFunc == nil`, so any Add notification delivered to this handler is silently dropped.

**Why this matters here specifically:** in the old code, `NewNodeConfig`'s handlers were registered *before* the node informer factory was started (`server.go` had an explicit comment: "This has to start after the calls to NewNodeConfig because that must configure the shared informer event handler first."), so the informer's real initial-list Add event reached `OnNodeAdd`. This PR inverted that ordering: `s.NodeManager.NodeInformer()` (`cmd/kube-proxy/app/server.go:211-215`) is created, started, and cache-synced inside `NewNodeManager()`/`newNodeManager()` (`pkg/proxy/node.go:76-79`) long before `Run()` later does:
```go
// cmd/kube-proxy/app/server.go:607-611
nodeConfig := config.NewNodeConfig(ctx, s.NodeManager.NodeInformer(), s.Config.ConfigSyncPeriod.Duration)
nodeConfig.RegisterEventHandler(s.NodeManager)
```
Because the informer is already running when this handler joins, client-go's "late join" path fires (`sharedIndexInformer.AddEventHandlerWithOptions`, `shared_informer.go:697-721`): it synthesizes an Add notification from the current cache for the new listener ("in order to safely join... 3. send synthetic 'Add' events to the new handler"). Since `NewNodeConfig` registers no `AddFunc`, that synthetic Add — carrying whatever Node state the informer already has — is thrown away instead of reaching `NodeManager.OnNodeChange`.

Net effect: any drift in NodeIPs/PodCIDRs that occurs between `NewNodeManager()`'s initial poll and `Run()`'s handler registration (or any genuine Node re-creation event) is silently missed instead of triggering the documented "crashes kube-proxy if there are any changes" safety behavior. This is a regression introduced by this PR's refactor, not a pre-existing issue — the previous ordering guaranteed delivery; the new one relies on a replay path the new code doesn't wire up. (As corroborating evidence of the oversight: `handleChangeNode`, `config.go:320-337`, still contains a `cache.DeletedFinalStateUnknown` tombstone-unwrapping branch that is dead code given it's only ever invoked from `UpdateFunc` — a leftover suggesting the function was written to double as an Add handler but never got registered as one.)

No test exercises the actual production sequencing (`config_test.go`'s `TestNewNodeTopologyConfig` registers its handler *before* starting the informer, so it never exercises the late-join replay path either), so this gap isn't caught by CI.

### Finding 2 (lower severity) — stale "sync node status" doc line

**Comment:** `pkg/proxy/healthcheck/proxy_health.go:62-68`
```go
// ProxyHealthServer allows callers to:
//  1. run a http server with /healthz and /livez endpoint handlers.
//  2. update healthz timestamps before and after synchronizing dataplane.
//  3. sync node status, for reporting unhealthy /healthz response
//     if the node is marked for deletion by autoscaler.
//  4. get proxy health by verifying that the delay between QueuedUpdate()
//     calls and Updated() calls exceeded healthTimeout or not.
```

**Conflicting code:** `SyncNode(node *v1.Node)` — the method item 3 refers to — was deleted by this PR. `NodeEligible()` (`proxy_health.go:176-190`) now computes eligibility on demand by pulling a fresh copy from `hs.nodeManager.Node()` each call:
```go
func (hs *ProxyHealthServer) NodeEligible() bool {
    hs.lock.Lock()
    defer hs.lock.Unlock()
    node := hs.nodeManager.Node()
    ...
}
```
There is no longer any "sync" step or cached `nodeEligible` field to sync into — the struct doc still describes the old push/cache design (`SyncNode` writes a field, `NodeEligible` reads it) even though the PR replaced it with a pull model. A maintainer reading this struct-level contract will look for a `SyncNode`-style entry point that no longer exists. Minor/maintenance-only (no functional break), but worth updating to describe the current on-demand-query behavior.

### Checked and found consistent (no issue)
- `pkg/proxy/types.go:28-32` (`Provider` embedding `config.NodeTopologyHandler` instead of `NodeHandler`) matches that every proxier (`iptables`, `ipvs`, `nftables`, `winkernel`, `metaproxier`) now implements only `OnTopologyChange`.
- `pkg/proxy/topology.go:45-47`'s note that `NodeTopologyConfig.handleNodeEvent` must be kept in sync with `CategorizeEndpoints`' label usage is accurate — both only look at `v1.LabelTopologyZone`.
- `pkg/proxy/node.go:186-189` `Node()` really does return a deep copy, as documented.
- `pkg/proxy/kubemark/hollow_proxy.go` — comment "we don't create nodeManager for hollow-proxy" (`server.go:606`) is accurate; `HollowProxy` never sets `NodeManager`.
- `winkernel/proxier.go:1098-1103` TODO stub is honestly labeled as unimplemented (harmless naming nit: `OnTopologyChanged` vs. actual method `OnTopologyChange`, not worth flagging as a contract violation).
- No leftover references to removed types (`NodePodCIDRHandler`, `NodeEligibleHandler`, `NoopNodeHandler`, `waitForPodCIDR`, `getNodeIPs`, `SyncNode`) remain anywhere in non-test `pkg/proxy`/`cmd/kube-proxy` source.
