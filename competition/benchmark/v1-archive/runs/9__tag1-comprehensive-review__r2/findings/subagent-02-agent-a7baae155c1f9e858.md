# subagent agent-a7baae155c1f9e858

## Findings: kube-proxy Node Manager (PR #130837)

### Finding 1 — Missing `AddFunc` silently drops the informer's Add-replay catch-up event for `NodeManager`

**Location**: `pkg/proxy/config/config.go:288-294` (constructor `NewNodeConfig`), consumed from `cmd/kube-proxy/app/server.go:608-611`

**Severity**: HIGH

**Issue Description**

Before this PR, `NewNodeConfig` wired all three of `AddFunc`, `UpdateFunc`, `DeleteFunc`. After merging `OnNodeAdd`+`OnNodeUpdate` into `OnNodeChange`, the registration became:

```go
handlerRegistration, _ := nodeInformer.Informer().AddEventHandlerWithResyncPeriod(
    cache.ResourceEventHandlerFuncs{
        UpdateFunc: func(_, newObj interface{}) { result.handleChangeNode(newObj) },
        DeleteFunc: result.handleDeleteNode,
    },
    resyncPeriod,
)
```

`AddFunc` was dropped entirely — not merged into `handleChangeNode`, just gone.

This matters because the `nodeInformer` passed in (`s.NodeManager.NodeInformer()`) is **not a fresh informer**. It was already started and synced earlier, inside `newNodeManager` (`pkg/proxy/node.go:74-77`, called from `newProxyServer` in `cmd/kube-proxy/app/server.go:210-215`), well before `NodeConfig` registers its handler in `Run()` (`cmd/kube-proxy/app/server.go:607-612`).

I verified against the vendored client-go source (`staging/src/k8s.io/client-go/tools/cache/shared_informer.go:697-720`): when a handler is registered on an **already-started** `sharedIndexInformer`, client-go explicitly replays the currently-cached object(s) as synthetic `addNotification{..., isInInitialList: true}` events to the newly-joining listener ("in order to safely join... 3. send synthetic 'Add' events to the new handler"). This is the only mechanism that catches a late-joining handler up to current state.

That synthetic Add is delivered via `ResourceEventHandlerFuncs.OnAdd`, which (`staging/src/k8s.io/client-go/tools/cache/controller.go:257-261`) is a hard no-op when `AddFunc == nil`:
```go
func (r ResourceEventHandlerFuncs) OnAdd(obj interface{}, isInInitialList bool) {
	if r.AddFunc != nil {
		r.AddFunc(obj)
	}
}
```
So the event is swallowed with **zero logging, zero error, zero trace** — nothing observes it happened.

**Hidden Errors**

- Any Node drift (PodCIDR reassignment, NodeIP change) that occurs in the window between `newProxyServer()`'s initial `nodeLister.Get()` poll (which seeds `NodeManager.node`) and `Run()`'s `nodeConfig.RegisterEventHandler(s.NodeManager)` call is never re-delivered to `NodeManager.OnNodeChange` for its drift-detection/crash-restart safety check.
- The next chance to detect that drift is either a genuine subsequent watch `Update` to the Node object, or the per-handler periodic resync — which defaults to **15 minutes** (`pkg/proxy/apis/config/v1alpha1/defaults.go:122-123`, `ConfigSyncPeriod`). Since kubelet heartbeats are now carried by the separate `Lease` object (not Node-object updates) on any cluster with `NodeLease` enabled (stable since 1.17), a stable node's `.status`/`.spec` can legitimately go unchanged — and thus generate no watch event — for the full 15 minutes.

**User Impact**

The entire purpose of `NodeManager.OnNodeChange` for `watchPodCIDRs`/NodeIPs is to force kube-proxy to crash-restart rather than silently keep running with stale PodCIDR/NodeIP assumptions (https://issues.k8s.io/111321 — this is exactly the safety mechanism the old `NodePodCIDRHandler` existed to provide). This merge silently disables the "catch me up on current state at registration time" leg of that safety net, with no operator-visible signal that it happened. Debugging this would be extremely hard: nothing logs, nothing errors, the behavior only manifests as "kube-proxy didn't restart when it should have" sometime after the fact.

This is also confirmed **completely untested**: `TestNodeManagerOnNodeChange` (`pkg/proxy/node_test.go`) calls `nodeManager.OnNodeChange(...)` directly, bypassing `NodeConfig`/the informer pipeline entirely. `pkg/proxy/config/config_test.go` only gained a new test for `NodeTopologyConfig` (which correctly wires both `AddFunc` and `UpdateFunc`); there is no equivalent `TestNewNodeConfig` exercising the real informer registration path for `NodeManager`. Neither before nor after this PR did such a test exist, so this exact code path has zero coverage.

**Recommendation**

Restore `AddFunc` in `NewNodeConfig`, routing it through the same merged handler (mirroring what `NewNodeTopologyConfig` already does correctly):

```go
handlerRegistration, _ := nodeInformer.Informer().AddEventHandlerWithResyncPeriod(
    cache.ResourceEventHandlerFuncs{
        AddFunc:    func(obj interface{}) { result.handleChangeNode(obj) },
        UpdateFunc: func(_, newObj interface{}) { result.handleChangeNode(newObj) },
        DeleteFunc: result.handleDeleteNode,
    },
    resyncPeriod,
)
```

Add a regression test analogous to `TestNewNodeTopologyConfig` that registers `NodeConfig` against an already-synced informer and asserts `OnNodeChange` fires for the pre-existing Node object — this is precisely the scenario that would have caught the bug.

---

### Finding 2 (lower severity) — Swallowed error retrieving old NodeIPs in `OnNodeChange`

**Location**: `pkg/proxy/node.go:143` and `pkg/proxy/node.go:123`

```go
oldNodeIPs, _ := utilnode.GetNodeHostIPs(n.node)   // line 143, in OnNodeChange
...
nodeIPs, _ := utilnode.GetNodeHostIPs(n.node)      // line 123, in NodeIPs()
```

**Severity**: MEDIUM (currently low practical risk, but a discipline violation)

**Issue Description**: Both call sites discard the error from `GetNodeHostIPs`, contrary to the "every error return must be checked" rule. Note the asymmetry within `OnNodeChange` itself: the error for the **old** node is silently dropped (line 143) while the error for the **new** node a few lines later is checked and logged (line 159-163). Currently this is defensible because `newNodeManager`'s constructor poll loop (`pkg/proxy/node.go:88-93`) already guarantees `n.node` has valid addresses before `NodeManager` is ever returned — so `n.node` should never legitimately fail `GetNodeHostIPs` by the time `OnNodeChange`/`NodeIPs()` run. But that's an invariant enforced only by control flow in a different function; nothing near these two lines documents or asserts it, and if a future edit calls `OnNodeChange` before that invariant holds (or a Node update legitimately drops all its addresses transiently), the code goes on to compute a spurious `oldNodeIPs == nil` and could either miss a real IP change or falsely trigger `n.exitFunc(1)` for what is actually just a transient address-loss/-recovery pair — with no log entry pointing at the swallowed root cause.

**Recommendation**: At minimum, log the discarded error at low verbosity (e.g., `klog.V(4).ErrorS(err, "Could not determine previous NodeIPs")`) so a future investigator has a breadcrumb, or add a comment stating the invariant relied upon (`n.node` is guaranteed to have addresses by the constructor) at the call site so silence is a documented decision, not an oversight.

---

### Minor note (not filing as a separate finding) — fallthrough after `exitFunc(1)` in the PodCIDR branch

`pkg/proxy/node.go:150-157`: after detecting a PodCIDR drift and calling `n.exitFunc(1)`, there is no `return`; execution falls through into the NodeIPs comparison and potentially calls `n.exitFunc(1)` a second time. Harmless in production since `exitFunc` is `os.Exit` (never returns), but it's an implicit assumption baked into the control flow rather than an enforced one — worth a `return` for defensiveness given `exitFunc` is an injectable field.

---

**Files referenced**: `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/pkg/proxy/config/config.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/pkg/proxy/node.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/pkg/proxy/node_test.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/pkg/proxy/config/config_test.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/cmd/kube-proxy/app/server.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/staging/src/k8s.io/client-go/tools/cache/shared_informer.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/staging/src/k8s.io/client-go/tools/cache/controller.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/9/pkg/proxy/apis/config/v1alpha1/defaults.go`.
