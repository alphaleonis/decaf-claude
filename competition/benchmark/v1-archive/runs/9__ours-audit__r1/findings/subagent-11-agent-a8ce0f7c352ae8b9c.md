# subagent agent-a8ce0f7c352ae8b9c

```json
{
  "finding": "#NodeTopologyConfig-listerSynced",
  "verdict": "confirmed",
  "reason": "Direct grep of pkg/proxy/config/config.go confirms listerSynced is written (line 503) in newNodeTopologyConfig but never read anywhere in the file — no Run() method exists for NodeTopologyConfig (only RegisterEventHandler and handleNodeEvent), and all four sibling configs (EndpointSliceConfig, ServiceConfig, NodeConfig, ServiceCIDRConfig) have a Run() that calls cache.WaitForNamedCacheSync against their own listerSynced (lines 108, 202, 310, 411). cmd/kube-proxy/app/server.go:607-614 confirms the asymmetry directly: nodeConfig gets `go nodeConfig.Run(wait.NeverStop)` at line 613, but nodeTopologyConfig only gets RegisterEventHandler at line 611 with no corresponding Run call anywhere in the file.",
  "corrections": {
    "pre_existing": false
  },
  "additional_context": "On the functional-consequence question: NodeManager (pkg/proxy/node.go:76-79) already starts and syncs the underlying shared node informer factory before NodeTopologyConfig is even constructed, so the informer's object store is already populated. However, NodeTopologyConfig registers its own NEW event handler (with AddFunc) on that already-running informer, and client-go delivers the initial replay of existing objects to a newly added handler asynchronously — it is not instantaneous. Since nothing waits for handlerRegistration.HasSynced, there is a genuine (if brief, self-correcting) startup race: `go s.Proxier.SyncLoop()` at server.go:619 can begin before the initial OnTopologyChange callback populates topology labels, unlike NodeConfig's handler which is gated behind Run()'s WaitForNamedCacheSync + explicit OnNodeSynced call. So this is not purely a harmless dead field — it is a real (narrow, eventually-consistent) missing-sync-gate plus an unambiguous dead-field/pattern-inconsistency, both directly verifiable from the code with no speculation."
}
```
