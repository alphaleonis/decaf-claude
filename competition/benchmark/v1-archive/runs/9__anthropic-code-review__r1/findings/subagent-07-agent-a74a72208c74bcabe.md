# subagent agent-a74a72208c74bcabe

Fetched the diff via `gh pr diff 130837 --repo kubernetes/kubernetes` and read it in full (~2200 lines). I cross-checked exact line numbers against the actual file contents at the head SHA. Two large, verifiable correctness bugs stood out; everything else I traced (NodeTopologyConfig wiring, healthcheck refactor, proxier renames, hollow-proxy/winkernel/metaproxier interface updates) was internally consistent.

## Issue 1: `NodeConfig`'s merged handler is never wired to node creation — contradicts its own doc comment

**File:** `pkg/proxy/config/config.go`, lines 262-264 (interface doc) and lines 288-292 (wiring)

```go
// OnNodeChange is called whenever creation or modification
// of node object is observed.
OnNodeChange(node *v1.Node)
```
```go
handlerRegistration, _ := nodeInformer.Informer().AddEventHandlerWithResyncPeriod(
    cache.ResourceEventHandlerFuncs{
        UpdateFunc: func(_, newObj interface{}) { result.handleChangeNode(newObj) },
        DeleteFunc: result.handleDeleteNode,
    },
    resyncPeriod,
)
```

**Why it's a bug:** The old code registered both `AddFunc: result.handleAddNode` and `UpdateFunc: result.handleUpdateNode`. The merge into `OnNodeChange` dropped `AddFunc` entirely instead of wiring it to the same `handleChangeNode` callback — even though the interface's own doc comment explicitly promises `OnNodeChange` fires "whenever creation **or modification**... is observed." Contrast this with the new `NodeTopologyConfig` added in the same file (lines ~485-499), which correctly wires both `AddFunc` and `UpdateFunc` to its equivalent combined handler — showing the intended pattern was known but not applied to `NodeConfig`.

Concretely, `NodeManager` is registered as this config's only `NodeHandler` (`nodeConfig.RegisterEventHandler(s.NodeManager)` in `cmd/kube-proxy/app/server.go`), against an informer that was already started and synced earlier inside `NewNodeManager()`. When `AddEventHandlerWithResyncPeriod` attaches a new handler to an already-synced shared informer, client-go replays the current store contents as synthetic "Add" notifications to that new handler — which are silently swallowed here because `AddFunc` is nil. [Inference, based on documented client-go SharedIndexInformer semantics, not something shown directly in the diff] The practical effect: if the node object changes between `NewNodeManager()`'s initial poll (in `newProxyServer()`) and `NodeConfig`'s registration (later, in `Run()`), that transition is delivered only as this dropped synthetic Add and is never seen by `NodeManager.OnNodeChange` — meaning `NodeManager`'s cached node/IP/PodCIDR baseline can go stale relative to the informer's actual store, and it will never crash on a real change that happened in that window. Any future `NodeHandler` implementer relying on the documented "fires on creation" contract would also silently miss create events.

## Issue 2: `NodeManager.OnNodeChange` commits the new node as the baseline before verifying it's usable, enabling spurious `exit(1)` on the next update

**File:** `pkg/proxy/node.go`, lines 140-166

```go
func (n *NodeManager) OnNodeChange(node *v1.Node) {
	// update the node object
	n.mu.Lock()
	oldNodeIPs, _ := utilnode.GetNodeHostIPs(n.node)
	oldPodCIDRs := n.node.Spec.PodCIDRs
	n.node = node
	n.mu.Unlock()

	// We exit whenever there is a change in PodCIDRs detected initially, and PodCIDRs received
	// on node watch event if the node manager is configured with watchPodCIDRs.
	if n.watchPodCIDRs {
		if !reflect.DeepEqual(oldPodCIDRs, node.Spec.PodCIDRs) {
			klog.InfoS("PodCIDRs changed for the node", ...)
			klog.Flush()
			n.exitFunc(1)
		}
	}

	nodeIPs, err := utilnode.GetNodeHostIPs(node)
	if err != nil {
		klog.ErrorS(err, "Failed to retrieve NodeIPs")
		return
	}

	// We exit whenever there is a change in NodeIPs detected initially, and NodeIPs received
	// on node watch event.
	if !reflect.DeepEqual(oldNodeIPs, nodeIPs) {
		klog.InfoS("NodeIPs changed for the node", ...)
		klog.Flush()
		n.exitFunc(1)
	}
}
```

**Why it's a bug:** `n.node = node` happens unconditionally, *before* the code even checks whether `utilnode.GetNodeHostIPs(node)` succeeds. If a node-update event arrives where the node momentarily has no resolvable host IP (e.g. `Status.Addresses` transiently empty/incomplete — a real-world node-status flap, not merely hypothetical [Inference]), `GetNodeHostIPs` errors, the function logs and `return`s without exiting — but it has *already* overwritten `n.node` with this IP-less node, so this bad state becomes the new "old" baseline.

On the very next update — even one that simply restores the node's original, unchanged IP — the code computes `oldNodeIPs, _ := utilnode.GetNodeHostIPs(n.node)` from that corrupted baseline (yielding `nil`, since the error is discarded), compares it to the freshly-restored real IPs, finds them unequal, and calls `n.exitFunc(1)` — a **false-positive crash** even though the node's actual IP never truly changed across the blip. Since `exitFunc` is `os.Exit` in production (`NewNodeManager` passes `os.Exit`), this directly triggers an unwarranted kube-proxy process exit/restart from a transient, self-healing node-status hiccup, which is exactly the "exit(1) fires incorrectly on equivalent states" failure mode called out as a risk for this kind of change. The same overwrite-before-validate ordering also applies to the `PodCIDRs` comparison directly above it (`oldPodCIDRs` is read from `n.node` after it's already been reassigned only in the sense that both reads happen under one lock before the unconditional write — but a transient/incomplete `PodCIDRs` update would poison the next comparison the same way, since there is no validity check for `PodCIDRs` at all before treating it as the new baseline).

No other comparably large issues were found in the reviewed diff (node/topology label plumbing through `NodeTopologyConfig`, the iptables/ipvs/nftables/winkernel/metaproxier/hollow-proxy interface updates, and the healthcheck server's pull-based `NodeEligible()` refactor all traced through cleanly and consistently).
