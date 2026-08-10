# subagent agent-a769bca7c6cdeb8aa

## Review Findings — code comment mismatches (PR #130837, HEAD `46e2c22fd76643bc985f7e77c99e97c6b7d078fc`)

### 1. `pkg/proxy/config/config.go` — `OnNodeChange` is documented to fire on "creation" but the only production wiring never sends it an Add event

**Comment (interface doc), lines 260-265:**
```go
// NodeHandler is an abstract interface of objects which receive
// notifications about node object changes.
type NodeHandler interface {
	// OnNodeChange is called whenever creation or modification
	// of node object is observed.
	OnNodeChange(node *v1.Node)
```
Also `RegisterEventHandler`, line 301: `// RegisterEventHandler registers a handler which is called on every node change.`

And in `pkg/proxy/node.go`, line 139: `// OnNodeChange is a handler for Node creation and update.` (doc on `NodeManager.OnNodeChange`, the sole registrant of `NodeHandler` — see `cmd/kube-proxy/app/server.go:609`, `nodeConfig.RegisterEventHandler(s.NodeManager)`).

**Contradiction:** `NewNodeConfig` (config.go, lines 282-299) wires the informer as:
```go
handlerRegistration, _ := nodeInformer.Informer().AddEventHandlerWithResyncPeriod(
    cache.ResourceEventHandlerFuncs{
        UpdateFunc: func(_, newObj interface{}) { result.handleChangeNode(newObj) },
        DeleteFunc: result.handleDeleteNode,
    },
    resyncPeriod,
)
```
There is no `AddFunc`. Before this PR, `AddFunc: result.handleAddNode` existed and invoked `OnNodeAdd` on every registered handler; the OnNodeAdd/OnNodeUpdate→OnNodeChange merge dropped that wiring entirely rather than routing Add events into `handleChangeNode` too. Since `cache.ResourceEventHandlerFuncs.OnAdd` no-ops when `AddFunc` is nil, `OnNodeChange` is never invoked for the initial "creation"/Add event delivered by the shared informer (including the replay of pre-existing store contents that occurs when a handler is registered on an already-synced informer, which is exactly what happens here — `NewNodeConfig` registers on `s.NodeManager.NodeInformer()`, an informer that was already started and synced inside `NewNodeManager`). `OnNodeChange` will only actually fire on a genuine Update or on periodic resync — not on "creation," despite three separate doc comments promising it. (Tests don't catch this because `node_test.go` and `healthcheck_test.go` call `nodeManager.OnNodeChange(...)` directly, bypassing `NewNodeConfig`'s real wiring; `config_test.go` has no test for `NodeConfig`/`OnNodeChange` at all — `TestNewNodeTopologyConfig` only covers the separate `NodeTopologyConfig`, which does wire `AddFunc`.)

Reason: **code comment mismatch**.

---

### 2. `pkg/proxy/config/config.go` — `handleNodeEvent` doc claims to handle Delete events, but the wired `DeleteFunc` never calls it

**Comment, lines 513-515:**
```go
// handleNodeEvent is a helper function to handle Add, Update and Delete
// events on Node objects and call downstream event handlers.
func (n *NodeTopologyConfig) handleNodeEvent(obj interface{}) {
```

**Contradiction:** In `newNodeTopologyConfig` (lines 485-502):
```go
handlerRegistration, _ := nodeInformer.Informer().AddEventHandlerWithResyncPeriod(
    cache.ResourceEventHandlerFuncs{
        AddFunc: func(obj interface{}) {
            result.handleNodeEvent(obj)
            ...
        },
        UpdateFunc: func(_, newObj interface{}) {
            result.handleNodeEvent(newObj)
            ...
        },
        DeleteFunc: func(_ interface{}) {},   // <-- line 499, empty no-op
    },
    resyncPeriod,
)
```
`DeleteFunc` is a stub that does nothing — it never calls `handleNodeEvent`. So `handleNodeEvent` is only reachable from Add and Update events, never Delete, directly contradicting its own doc comment ("handle Add, Update and **Delete** events").

Reason: **code comment mismatch**.

---

### 3. `pkg/proxy/healthcheck/proxy_health.go` — type doc still advertises a "sync node status" caller capability that no longer exists

**Comment, lines 62-68:**
```go
// ProxyHealthServer allows callers to:
//  1. run a http server with /healthz and /livez endpoint handlers.
//  2. update healthz timestamps before and after synchronizing dataplane.
//  3. sync node status, for reporting unhealthy /healthz response
//     if the node is marked for deletion by autoscaler.
//  4. get proxy health by verifying that the delay between QueuedUpdate()
//     calls and Updated() calls exceeded healthTimeout or not.
type ProxyHealthServer struct {
```

**Contradiction:** The PR removes the public `SyncNode(node *v1.Node)` method (and the `NodeEligibleHandler` that used to push node updates into it via `OnNodeAdd`/`OnNodeUpdate`/`OnNodeDelete`) and replaces it with a pull-based `NodeEligible() bool` getter that reads `hs.nodeManager.Node()` on demand:
```go
// NodeEligible returns if node is eligible or not. Eligible is defined
// as being: not tainted by ToBeDeletedTaint and not deleted.
func (hs *ProxyHealthServer) NodeEligible() bool {
	...
	node := hs.nodeManager.Node()
	...
}
```
There is no longer any way for a caller to "sync node status" into `ProxyHealthServer` — that capability (item 3 in the type's own enumerated contract) was deleted; the server now derives eligibility itself from the injected `*proxy.NodeManager` rather than being synced by a caller.

Reason: **code comment mismatch** (lower confidence than #1/#2, since the externally observable `/healthz` behavior for a tainted/deleted node is preserved — only the "callers sync it" mechanism described in the doc is gone).

---

Files reviewed for surrounding-comment consistency (no further mismatches found): `pkg/proxy/types.go` (Provider interface / `NodeTopologyHandler` swap — consistent), `pkg/proxy/topology.go` (new note about `NodeTopologyConfig.handleNodeEvent` filtering — accurate), `pkg/proxy/iptables/proxier.go`, `pkg/proxy/ipvs/proxier.go`, `pkg/proxy/nftables/proxier.go`, `pkg/proxy/winkernel/proxier.go` (topologyLabels rename and `OnTopologyChange` docs — consistent; winkernel's `OnTopologyChange` TODO stub honestly discloses it's unimplemented, so not flagged), `pkg/proxy/metaproxier/meta_proxier.go`, `pkg/proxy/kubemark/hollow_proxy.go`, `cmd/kube-proxy/app/server.go`/`server_linux.go` (NodeManager field-selector claim in winkernel's `OnTopologyChange` comment verified true — the shared informer is field-selected to the local node name in `newNodeManager`).
