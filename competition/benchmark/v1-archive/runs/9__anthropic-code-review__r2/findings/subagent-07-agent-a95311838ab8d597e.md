# subagent agent-a95311838ab8d597e

## Review findings — PR #130837 (kube-proxy NodeManager refactor)

I read the full diff (`gh pr diff 130837`) and, to verify the two findings below, pulled the post-merge blob of `pkg/proxy/config/config.go` and `pkg/proxy/kubemark/hollow_proxy.go` at the head SHA to confirm the surrounding (unshown) code — this was necessary to distinguish a real bug from a diff-only artifact. I did not check PR review comments for a discussion of finding 1 by name ("AddFunc"), which suggests it wasn't caught in human review.

### 1. `AddFunc` dropped when merging `handleAddNode`/`handleUpdateNode` into `handleChangeNode` — silently loses the "catch-up" replay for a late-joining listener

**File:** `pkg/proxy/config/config.go`, `NewNodeConfig` (diff hunk `@@ -307,8 +287,7 @@`, new lines ~288-293)

```go
handlerRegistration, _ := nodeInformer.Informer().AddEventHandlerWithResyncPeriod(
    cache.ResourceEventHandlerFuncs{
        UpdateFunc: func(_, newObj interface{}) { result.handleChangeNode(newObj) },
        DeleteFunc: result.handleDeleteNode,
    },
    resyncPeriod,
)
```

The old code had `AddFunc: result.handleAddNode`; the new code has no `AddFunc` at all (not even mapped to `handleChangeNode` like `UpdateFunc` was). `NodeHandler.OnNodeChange` is documented as "called whenever creation **or** modification of node object is observed" (see the interface doc in `pkg/proxy/config/config.go`), but the wiring only calls it on `UpdateFunc`.

**Why this is a real bug, concretely:** `NodeManager`'s own informer (`pkg/proxy/node.go`, `newNodeManager`) is created and `Start()`ed, and its cache is synced, during `NewNodeManager()` — which runs early in `newProxyServer()`. Much later, `ProxyServer.Run()` calls `config.NewNodeConfig(ctx, s.NodeManager.NodeInformer(), …)` and registers `s.NodeManager` as a handler on that **already-running, already-synced** informer. Per client-go's `sharedIndexInformer.AddEventHandlerWithResyncPeriod`, when a handler is added to an informer that has already started, it does a `List()` against the store and replays the current contents to the *new* listener as synthetic "Add" notifications (`isInInitialList: true`) — this is exactly the mechanism intended to bring a late-joining consumer up to date. Because `AddFunc` is now `nil`, `cache.ResourceEventHandlerFuncs.OnAdd` becomes a no-op, so this replay is silently dropped.

Concrete failure scenario: if the Node object changes (PodCIDR reassigned, NodeIP changed, taints applied) in the window between `NewNodeManager()`'s initial poll (inside `newProxyServer`) and `Run()` registering the handler (after proxier construction / iptables-nftables-conntrack setup, etc.), `NodeManager.node` never gets updated to that intermediate state — it will only catch up on the *next* genuine Update event. During that window: `NodeManager.Node()`/`NodeIPs()`/`PodCIDRs()` (used by `ProxyHealthServer.NodeEligible()` and by `iptables`/`ipvs`/`nftables` proxiers indirectly) serve stale data, and — more importantly — the entire point of this PR ("exit kube-proxy on unexpected NodeIP/PodCIDR change") fails to fire for that missed transition. This directly undermines the safety net the PR is introducing.

(By contrast, `NodeTopologyConfig`, added in the same file, correctly wires `AddFunc` to `handleNodeEvent`, so it does not have this gap — reinforcing that the omission in `NodeConfig` looks like an oversight rather than an intentional design choice.)

### 2. Missing nil-guard for `NodeManager` in `ProxyHealthServer.NodeEligible()` (latent, not currently reachable)

**File:** `pkg/proxy/healthcheck/proxy_health.go`, `NodeEligible()` (diff hunk `@@ -172,30 +171,22 @@`)

```go
func (hs *ProxyHealthServer) NodeEligible() bool {
	hs.lock.Lock()
	defer hs.lock.Unlock()

	node := hs.nodeManager.Node()   // <- no nil check on hs.nodeManager
	if !node.DeletionTimestamp.IsZero() {
		...
```

`Node()` on `*NodeManager` does `n.mu.Lock()` before anything else, so calling it on a nil `*NodeManager` receiver panics with a nil-pointer dereference. `cmd/kube-proxy/app/server.go`'s `Run()` explicitly guards the analogous case (`if s.NodeManager != nil { … }`) because the task description / code comment confirms `NodeManager` is nil for hollow-proxy. `healthcheck.NewProxyHealthServer` unconditionally stores whatever `nodeManager` it's given without a nil check.

**Verification / caveat:** I confirmed via the actual `hollow_proxy.go` blob that `HollowProxy` builds `ProxyServer` directly (not via `newProxyServer`) and never sets `HealthzServer`, so `NodeEligible()` is not reached today in the hollow-proxy path; and in the normal `newProxyServer()` path, `s.NodeManager` is always set (or the function returns early on error) before `NewProxyHealthServer(..., s.NodeManager)` is called, so it's also not nil there. So under the current call graph this is **not an active crash** — [Inference] it is a latent gap: any future caller that constructs a `ProxyHealthServer` with a nil `NodeManager` (which the codebase explicitly anticipates as a valid state elsewhere) and then serves a health/liveness request will panic. Flagging because the task explicitly called out NodeManager-nil-for-hollow-proxy as a risk area, and this is the one spot lacking the guard that exists everywhere else `NodeManager` is used.

### Not flagged (checked and ruled out)
- No swapped arguments in `CategorizeEndpoints(endpoints, svcInfo, nodeName, topologyLabels)` call sites (iptables/nftables) after the `nodeLabels`→`topologyLabels` rename.
- `metaproxier.OnTopologyChange` correctly forwards the same map to both v4/v6 sub-proxiers; it's read-only everywhere, so the shared reference isn't a mutation/aliasing hazard.
- `NodeManager.OnNodeChange`'s exit-on-PodCIDR-change vs exit-on-NodeIP-change conditions look correct (`watchPodCIDRs` gates only the PodCIDR check, as intended).
- `server.go`'s `if s.NodeManager != nil` guard around `nodeConfig`/`nodeTopologyConfig` construction in `Run()` is correct and necessary for hollow-proxy.
