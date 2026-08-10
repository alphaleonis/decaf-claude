# subagent agent-aaba28b590657b710

I have enough to construct the scenarios. Key structural facts confirmed:

- `NewNodeConfig` wires only `UpdateFunc`/`DeleteFunc` — no `AddFunc` (config.go). `NewNodeTopologyConfig` DOES wire `AddFunc`. The informer is created+started inside `newNodeManager`, but `NodeManager` is registered as an event handler much later in `Run()`.
- `OnNodeChange` swaps `n.node` before the IP-error check and swallows a missing-IP node without exiting.
- `WaitForNamedCacheSync` in `newNodeManager` uses the parent `ctx` (the 5-min timeout ctx is created afterward).
- Hollow proxy builds `ProxyServer` directly with nil `HealthzServer` and nil `NodeManager`, so the nil-`nodeManager` `NodeEligible()` panic is not reachable in practice.

Depth: **deep** — new `NodeManager` owns process-exit control (data-mutation/lifecycle domain), ~2200-line diff, >200 executable lines; all four techniques applied.

Here is my report.

```json
[
  {
    "file": "pkg/proxy/config/config.go",
    "line": 289,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_COMPOSITION] NodeManager baseline captured at newProxyServer time -> NodeConfig registered later in Run() with no AddFunc -> node IP/PodCIDR change landing in that registration gap is replayed only as a synthetic Add (dropped) -> no exit(1), kube-proxy keeps stale rules with no self-heal.",
    "fix": "Wire an AddFunc on NewNodeConfig's handler (mirror NodeTopologyConfig, which does register AddFunc) so the informer's initial synthetic Add for the pre-existing node is routed to OnNodeChange, letting NodeManager reconcile its startup baseline against current cache state.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 159,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_CASCADE] Node status briefly loses all addresses (kubelet re-register / not-ready blip): OnNodeChange sets n.node = IP-less node then GetNodeHostIPs errors and returns WITHOUT exit, corrupting the baseline to empty IPs -> next event restores IPs -> DeepEqual(nil, restoredIPs) is false -> exit(1). A transient flap where the final IP equals the original still forces a needless kube-proxy restart.",
    "fix": "On GetNodeHostIPs error, do not overwrite the good baseline n.node with the IP-less node (or skip the update entirely and keep prior IPs); only advance the baseline once the node has valid NodeIPs, so a transient empty-address blip cannot manufacture a spurious IP-change exit.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 77,
    "severity": "Medium",
    "category": "resource-management",
    "issue": "[ADV_ASSUMPTION] newNodeManager runs WaitForNamedCacheSync against the parent ctx.Done() (the 5-min timeout ctx is only created afterward at line 85). If the API server is unreachable at startup, cache never syncs and NewNodeManager blocks until process signal, not 5 minutes as the comment claims -> newProxyServer never returns -> kube-proxy hangs before serving livez, defeating the old bounded getNodeIPs backoff it replaced.",
    "fix": "Apply the poll timeout (or a dedicated cache-sync deadline) to the context passed to WaitForNamedCacheSync so startup is bounded on an unreachable API server, and correct the 'at most 5 minutes' comment to reflect that it does not cover the cache-sync wait.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Cluster-wide restart storm from exit-on-NodeIP-change.** Each kube-proxy's informer uses a `metadata.name` field selector for its own node only, so a single node's IP/PodCIDR change cannot correlate exits across the fleet. No amplifying trigger found — scenario fell apart at the "correlated event" step.
- **NodeTopologyConfig no-op DeleteFunc leaving stale topology after node delete.** On the same shared informer, NodeConfig's DeleteFunc -> OnNodeDelete -> `os.Exit(1)` terminates the process, so stale `topologyLabels` in the proxier is never observed. Ordering verified: the exit wins regardless of handler order.
- **Resync (ConfigSyncPeriod) re-delivering an unchanged node as Update.** Resync passes the same cached object; `OnNodeChange` compares `GetNodeHostIPs(n.node)` against the identical node -> `reflect.DeepEqual` true -> no exit. Guard holds; no spurious exit.
- **Tombstone (DeletedFinalStateUnknown) on the UpdateFunc path.** `handleChangeNode` defensively handles tombstones, but informers only emit tombstones via DeleteFunc, so that branch is dead on the Update path. Harmless dead code, not a failure.
- **Double `exitFunc(1)` in OnNodeChange (PodCIDR branch then NodeIP branch).** Latent only if `exitFunc` returns; production `os.Exit` never returns, so a single exit occurs. Real only under a non-terminating injected exitFunc (tests). No production impact.
- **Nil `nodeManager` panic in `NodeEligible()`.** Reachable only if a `ProxyHealthServer` is built with nil nodeManager; the sole such caller (hollow proxy) leaves `HealthzServer` nil entirely, so `NodeEligible()` is never invoked there. Not reachable.
- **`NodeEligible()` write-lock + per-probe `Node()` DeepCopy.** Cost-only, no failure chain -> performance-reviewer's lane. Lock ordering checked (hs.lock -> n.mu, never the reverse); no deadlock.

### Probe Requests
None — all findings are grounded in source read from disk; no working-tree mutation needed to demonstrate them.
