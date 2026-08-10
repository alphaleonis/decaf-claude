# subagent agent-adc74a567afb693f3

## Edge Case Analysis

### Pass 1: Path Walk

Traced the `NodeHandler`/`NodeTopologyHandler` consolidation across `pkg/proxy/config/config.go`, `pkg/proxy/node.go`, and the six proxier implementations (iptables/ipvs/nftables/winkernel/metaproxier/kubemark). Found 9 branching constructs directly touched by the `OnNodeAdd`+`OnNodeUpdate`→`OnNodeChange` merge: the `cache.ResourceEventHandlerFuncs` literal in `NewNodeConfig`, the type-assertion/tombstone fallback in `handleChangeNode`, the `watchPodCIDRs` branch and NodeIPs-error branch in `NodeManager.OnNodeChange`, the topology-label filter in `NodeTopologyConfig.handleNodeEvent`, and the poll-timeout error path in `newNodeManager`. 3 candidates identified; 1 confirmed as a finding after Pass 2, 2 discarded (nil-old-node concern from the task hint is actually handled — `NodeManager.node` is always non-nil after construction; the double-`exitFunc` call without an early `return` is provably inert in production because `exitFunc` is `os.Exit`, which never returns).

### Pass 2: Validated Findings

#### High

- **Missing else/default — `AddFunc` omitted from `NodeConfig`'s event registration, so `OnNodeChange` is never invoked for Node creation** — `pkg/proxy/config/config.go:288-294`
  - **Unhandled path:** `NewNodeConfig` wires only `UpdateFunc` and `DeleteFunc` into `cache.ResourceEventHandlerFuncs{}` — no `AddFunc` field is set:
    ```go
    handlerRegistration, _ := nodeInformer.Informer().AddEventHandlerWithResyncPeriod(
        cache.ResourceEventHandlerFuncs{
            UpdateFunc: func(_, newObj interface{}) { result.handleChangeNode(newObj) },
            DeleteFunc: result.handleDeleteNode,
        },
        resyncPeriod,
    )
    ```
    `cache.ResourceEventHandlerFuncs.OnAdd` (`staging/src/k8s.io/client-go/tools/cache/controller.go:257-261`) is a no-op whenever `AddFunc == nil`, so every "Add" notification for this registration is silently swallowed. This directly contradicts the interface's own doc comment at `config.go:263-265` — "`OnNodeChange` is called whenever **creation** or modification of node object is observed" — and the caution already written above the sibling configs at `cmd/kube-proxy/app/server.go:579-581` ("the initial update ... may be lost if no handlers are registered yet").
    This is reachable in practice, not just at theoretical cold-start: `s.NodeManager` (the sole `NodeHandler`, registered at `server.go:609`) is attached to an informer that `NewNodeManager` already started and synced earlier, at `server.go:210-211`. Per `shared_informer.go:697-721`, a handler added to an already-started informer receives a synthetic **"Add" replay of the current store contents** to catch it up — this is exactly the kind of Add this registration drops. Any node mutation that lands between `NewNodeManager`'s last successful poll (`node.go:64-`, which sets the initial `n.node`) and `NodeConfig.RegisterEventHandler` running later in `server.go` (after building `serviceConfig`, `endpointSliceConfig`, `serviceCIDRConfig`, starting two informer factories, etc.) is delivered to `NodeManager.OnNodeChange` only as this dropped synthetic Add, never as an Update.
  - **Consequence:** `NodeManager.OnNodeChange` (`pkg/proxy/node.go:140`) exists specifically to crash-and-restart kube-proxy (`n.exitFunc(1)`) if NodeIPs or (when `watchPodCIDRs`) PodCIDRs drift from the values captured at startup — because `s.podCIDRs`/`rawNodeIPs` are captured once at `server.go:217-218` and never re-derived. If the drift-triggering change is delivered only via the dropped Add path, the safety check silently never fires: kube-proxy keeps running with stale `podCIDRs`/node IPs baked into local traffic detection and health-check binding, with no log, no error, and no self-correction unless a *later, distinct* genuine watch Update happens to arrive for the same node.
  - **Remediation:** Add `AddFunc: func(obj interface{}) { result.handleChangeNode(obj) }` alongside `UpdateFunc` in the `cache.ResourceEventHandlerFuncs{}` literal at `config.go:289-292`, mirroring how `NewNodeTopologyConfig` (added in the same diff, `config.go:485-499`) correctly wires both `AddFunc` and `UpdateFunc` to the same `handleNodeEvent`.
  - **Confidence:** 82/100

### Positive Observations

- `NodeManager.OnNodeChange`/`OnNodeDelete` never operate on a nil "old" node — `n.node` is populated synchronously inside `newNodeManager` (`pkg/proxy/node.go:64-`) before the struct is ever handed to a caller or registered as a handler, so the nil-old-state concern that motivated this review does not materialize.
- `handleChangeNode`'s type assertion correctly falls back to `cache.DeletedFinalStateUnknown` tombstone unwrapping (`config.go:320-332`), matching the pattern already used for delete handling elsewhere in the file.
- The new `NodeTopologyConfig` (`config.go:452-535`) correctly wires `AddFunc`, `UpdateFunc`, and a no-op `DeleteFunc`, and safely indexes into a possibly-nil `node.Labels` map (Go's nil-map read semantics make this safe) — no gaps found there.
- `metaProxier`, `iptables`/`ipvs`/`nftables`/`winkernel` proxiers, and `kubemark.FakeProxier` were all migrated consistently to `OnTopologyChange`; no stray references to the removed `OnNodeAdd`/`OnNodeUpdate`/`NoopNodeHandler` remain anywhere in `pkg/proxy` or `cmd/kube-proxy`.

```json-findings
[{"severity":"High","confidence":82,"category":"edge-case","file":"pkg/proxy/config/config.go","line":288,"finding":"NewNodeConfig's cache.ResourceEventHandlerFuncs literal registers only UpdateFunc and DeleteFunc, omitting AddFunc. Since cache.ResourceEventHandlerFuncs.OnAdd is a no-op when AddFunc is nil, Node \"Add\" notifications — including the synthetic catch-up replay client-go sends to handlers registered on an already-started/synced informer (which is exactly what happens here, since NodeManager's informer is started earlier in NewNodeManager, well before NodeConfig.RegisterEventHandler runs in server.go) — are silently dropped. This contradicts the NodeHandler.OnNodeChange doc comment (\"is called whenever creation or modification ... is observed\") and can cause NodeManager's IP/PodCIDR drift-detection safety check (which restarts kube-proxy via exitFunc) to silently never fire for changes delivered only via the dropped Add path, leaving kube-proxy running with stale podCIDRs/NodeIPs captured at server.go:217-218.","remediation":"Add AddFunc: func(obj interface{}) { result.handleChangeNode(obj) } to the cache.ResourceEventHandlerFuncs{} literal in NewNodeConfig, mirroring how NewNodeTopologyConfig wires both AddFunc and UpdateFunc to the same handler in the same diff.","source":"edge-case-hunter"}]
```
