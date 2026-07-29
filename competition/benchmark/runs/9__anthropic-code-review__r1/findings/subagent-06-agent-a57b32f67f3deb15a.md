# subagent agent-a57b32f67f3deb15a

## Summary

PR #130837 replaced kube-proxy's ad-hoc node/PodCIDR watching code with a consolidated `proxy.NodeManager`. Critically, **this exact PR was reverted in production** (revert PR [#132958](https://github.com/kubernetes/kubernetes/pull/132958), redone as [#133059](https://github.com/kubernetes/kubernetes/pull/133059) "kube-proxy node manager (take 2)") because of a regression it introduced. That gives concrete, non-speculative confirmation for two of the three findings below; all three trace back to review feedback on prior PRs touching these same files.

## Findings

### 1. Hard-blocking/erroring wait for NodeIPs regresses the old soft-timeout behavior — this is what caused the PR to be reverted

- **Prior feedback:** danwinship, reviewing this very PR (#130837), [comment on `cmd/kube-proxy/app/server.go`](https://github.com/kubernetes/kubernetes/pull/130837#discussion_r1996981966) (orig_line 705): *"this loses the timeout that the previous version had (about 30 seconds)."* The old `getNodeIPs()` used a ~30s exponential backoff and then just returned whatever it had (possibly empty), letting kube-proxy startup continue.
- **Current PR's code:** `pkg/proxy/node.go` — `NewNodeManager` (lines 56-61) delegates to `newNodeManager` with a single hardcoded `5*time.Minute` poll timeout for the *whole* wait (NodeIPs, and PodCIDRs if `watchPodCIDRs`). The poll callback (lines 87-104) only returns `true` once the node exists **and** has resolvable host IPs; if that never happens, `newNodeManager` returns an error (lines 106-109), which `newProxyServer` (`cmd/kube-proxy/app/server.go` lines 210-215) propagates as a hard failure of kube-proxy startup — no soft-fail/continue path remains.
- **Why it still applies:** This is exactly the regression that broke Cluster API Provider Azure (kubernetes-sigs/cloud-provider-azure#9266, "cloud-node-manager doesn't set Node IPs before kube-proxy expects them"): cloud-node-manager needs a working kube-proxy to reach the API server, but kube-proxy in this PR now blocks/errors until NodeIPs are set — a circular dependency deadlock. The maintainers themselves flagged this concern in review before merge (the comment above) but it wasn't fixed, the PR merged anyway, broke production, was reverted, and the redo (#133059) explicitly restored a short (~30s) soft timeout for NodeIPs specifically (falling back to "keep going even if we didn't find a node/IPs, for backward-compatibility") while only PodCIDRs kept the long hard timeout. aroradaman's own review note on the redo ([#133059 comment](https://github.com/kubernetes/kubernetes/pull/133059#discussion_r2216596291)) makes the mechanism explicit: *"For cloud-providers the IP will be nil on bootstrap, it will trigger a pod restart."*

### 2. `NodeConfig`'s merged handler drops the `AddFunc` wiring — confirmed as a real bug by maintainers in the redo, not just a hypothetical

- **Current PR's code:** `pkg/proxy/config/config.go`, `NewNodeConfig` (lines 282-299, part of commit `46e2c22f` "kube-proxy: merge OnNodeAdd and OnNodeUpdate into OnNodeChange" — the HEAD commit of this PR):
  ```go
  handlerRegistration, _ := nodeInformer.Informer().AddEventHandlerWithResyncPeriod(
      cache.ResourceEventHandlerFuncs{
          UpdateFunc: func(_, newObj interface{}) { result.handleChangeNode(newObj) },
          DeleteFunc: result.handleDeleteNode,
      },
      resyncPeriod,
  )
  ```
  Only `UpdateFunc`/`DeleteFunc` are wired to `OnNodeChange`; there is no `AddFunc`.
- **Prior feedback:** When this same code was re-reviewed in the redo (#133059), aojea flagged it directly: [*"you are removing the Add event handler, so is not really merging add an update"*](https://github.com/kubernetes/kubernetes/pull/133059#discussion_r2217986365) and [*"you only handle the new object on an Update, and presumably also for the Add..."*](https://github.com/kubernetes/kubernetes/pull/133059#discussion_r2217986540). danwinship then confirmed it empirically: [*"(confirmed that the version of this without the AddFunc fails the new unit test)"*](https://github.com/kubernetes/kubernetes/pull/133059#discussion_r2219405772).
- **Why it still applies:** The redo fixed this by wiring `AddFunc: func(obj interface{}) { result.handleChangeNode(obj) }` alongside `UpdateFunc`. The current PR's merged code (which this review covers) ships without that `AddFunc`, i.e., with the version the maintainers later proved (via a new unit test) to be broken.

### 3. Startup poll for the node no longer excludes a Node with `DeletionTimestamp` set — same class of bug aojea already fixed once in #125382

- **Prior feedback:** aojea, reviewing #125382's rewrite of `waitForPodCIDR` from a watch to a lister-based poll, wrote: [*"we need to recover this condition, as we had a bug because of this, and check the node object is not being deleted"*](https://github.com/kubernetes/kubernetes/pull/125382#discussion_r1631207022). That PR's `getNodeIPs`/`waitForPodCIDR` were subsequently fixed to include `if !node.DeletionTimestamp.IsZero() { ...keep waiting... }` before merging.
- **Current PR's code:** `pkg/proxy/node.go`, `newNodeManager`'s poll loop (lines 87-104):
  ```go
  pollErr := wait.PollUntilContextCancel(ctx, pollInterval, true, func(context.Context) (bool, error) {
      node, err = nodeLister.Get(nodeName)
      if err != nil { return false, nil }
      _, err = utilnode.GetNodeHostIPs(node)
      if err != nil { return false, nil }
      if watchPodCIDRs && len(node.Spec.PodCIDRs) == 0 { ...; return false, nil }
      return true, nil
  })
  ```
  There is no `DeletionTimestamp` check anywhere in this function (confirmed: `grep DeletionTimestamp` across `pkg/proxy/` only matches the unrelated `healthcheck/proxy_health.go` eligibility logic, which is pre-existing and orthogonal to this startup wait).
- **Why it still applies:** This is the same class of bug aojea previously identified and had fixed once already (the risk being that kube-proxy captures a dying, about-to-be-replaced Node's IPs/PodCIDRs as its baseline instead of waiting for the real one). It was consolidated into `NodeManager`'s new poll helper in this PR without carrying the check forward. Note for completeness: I did not find this check reinstated in the #133059 redo either (its equivalent `getNodeInfo` helper also lacks it), so this may be a still-open, lower-confidence gap rather than one proven to have caused an incident — flagging it since it directly matches previously-articulated, specific reviewer guidance that the changed lines don't honor.

## Not flagged (already addressed / not applicable)

- wojtek-t's "stale read vs. consistent Get" concern from #125382 — danwinship's rationale (kube-proxy exits on later node changes anyway) was reaffirmed in this PR's own review thread and is sound; no action needed.
- linxiulei/aojea's "informer starts before handler registration" ordering concern from #125382 — verified against `vendor`'d client-go (`shared_informer.go` `AddEventHandlerWithOptions`): late-joining handlers are replayed synthetic "Add" notifications from the store, so this ordering does not lose events in the current design.
- danwinship's "crash-loop on Node deleted-and-not-recreated" design concern (#125382 discussion r1669405761, re-raised in this PR's own thread) — explicitly deferred by reviewers as a known, pre-existing architectural gap, not a regression introduced by this PR.
