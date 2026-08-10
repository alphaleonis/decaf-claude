# subagent agent-a58d1ff8b5eb4deca

## Silent-Failure / Error-Handling Review — kubernetes/kubernetes PR #130837

Scope: `pkg/proxy/node.go` (the new `NodeManager`), plus a scan of the rest of the diff for dropped/ignored error returns. Full post-PR file read at `/tmp/cr-pr-GDvNd7d4/pkg/proxy/node.go`.

### Finding 1 — `OnNodeChange` commits the new (possibly IP-less) node to state *before* validating it, then silently swallows the validation error, poisoning the "old" baseline used by the *next* call

`pkg/proxy/node.go:140-172`:

```go
func (n *NodeManager) OnNodeChange(node *v1.Node) {
	n.mu.Lock()
	oldNodeIPs, _ := utilnode.GetNodeHostIPs(n.node)   // line 144 — error ignored
	oldPodCIDRs := n.node.Spec.PodCIDRs
	n.node = node                                       // line 146 — state committed unconditionally
	n.mu.Unlock()

	... (PodCIDR exit check, unaffected) ...

	nodeIPs, err := utilnode.GetNodeHostIPs(node)
	if err != nil {
		klog.ErrorS(err, "Failed to retrieve NodeIPs")   // line 161 — log-and-continue
		return                                            // line 162 — no exitFunc, no state repair
	}

	if !reflect.DeepEqual(oldNodeIPs, nodeIPs) {
		...
		n.exitFunc(1)
	}
}
```

The type's own doc comment says `NodeManager` "crashes kube-proxy if there are any changes in NodeIPs or PodCIDRs" — i.e. the documented contract is fail-fast on anomalies. But when an incoming node update happens to have no valid host IP (`utilnode.GetNodeHostIPs` fails — e.g. a transient status wipe/resync race, a bad PATCH, or any window where `.status.addresses` is briefly absent), the code:

1. Has already overwritten `n.node` with the bad node (line 146, before the IP is even checked).
2. Logs the error via `klog.ErrorS` and returns — it does **not** call `exitFunc`, and does **not** revert `n.node` to the last-known-good value.

Two concrete consequences:
- Any caller of `NodeIPs()` (line 120-125, `nodeIPs, _ := utilnode.GetNodeHostIPs(n.node)`) after this point silently gets an empty IP slice with zero indication that anything is wrong, because that function *also* discards the error.
- On the **next** `OnNodeChange` call, `oldNodeIPs, _ := utilnode.GetNodeHostIPs(n.node)` (line 144) reads from the now-corrupted `n.node` and silently gets `nil` (error swallowed again). If the node's real IP subsequently reappears unchanged, `oldNodeIPs` (nil) will not `reflect.DeepEqual` the restored (non-nil) `nodeIPs`, so the code concludes "NodeIPs changed for the node" and calls `n.exitFunc(1)` — a spurious crash caused entirely by the earlier silently-swallowed error, not by an actual IP change.

This is the exact "ignored error corrupts stale baseline" pattern the review was asked to hunt for. The fix should validate the incoming node *before* committing it to `n.node` (or keep the last-known-good IPs separately), and must not let a `GetNodeHostIPs` failure be reduced to a log line when the rest of the function's design is "log at Info and then exit(1) on any detected change."

### Finding 2 — `newNodeManager`'s startup poll loop dropped all per-attempt diagnostic logging that existed in the code it replaced

`pkg/proxy/node.go:87-104`:

```go
pollErr := wait.PollUntilContextCancel(ctx, pollInterval, true, func(context.Context) (bool, error) {
	node, err = nodeLister.Get(nodeName)
	if err != nil {
		return false, nil          // no logging
	}
	_, err = utilnode.GetNodeHostIPs(node)
	if err != nil {
		return false, nil          // no logging
	}
	if watchPodCIDRs && len(node.Spec.PodCIDRs) == 0 {
		err = fmt.Errorf("node %q does not have any PodCIDR allocated", nodeName)
		return false, nil          // no logging
	}
	return true, nil
})
```

Compare with the pre-PR `getNodeIPs()` (deleted in `cmd/kube-proxy/app/server.go`, diff lines ~102-113), which logged on every failed attempt:

```go
node, err := client.CoreV1().Nodes().Get(ctx, name, metav1.GetOptions{})
if err != nil {
	logger.Error(err, "Failed to retrieve node info")
	return false, nil
}
nodeIPs, err = utilnode.GetNodeHostIPs(node)
if err != nil {
	logger.Error(err, "Failed to retrieve node IPs")
	return false, nil
}
```

The new poll loop retries for up to 5 minutes (`NewNodeManager` passes `5*time.Minute` as `pollTimeout`) with **zero** log output per attempt — only a single terminal error if the whole 5-minute window is exhausted, or a single success log ("Successfully retrieved NodeIPs" in `server.go`) if it eventually works. An operator watching `kubectl logs` on a kube-proxy pod stuck waiting for node registration / PodCIDR allocation during those minutes now sees nothing at all, where before they'd see repeated, actionable "Failed to retrieve node info" / "Failed to retrieve node IPs" lines explaining what kube-proxy was waiting on. This is a real observability regression introduced by the refactor, not a hypothetical.

### Finding 3 — On poll timeout, the surfaced error is always the last validation-failure reason, never `pollErr` itself, so a context cancellation during startup is misreported

`pkg/proxy/node.go:106-109`:

```go
// we return the actual error in case of poll timeout
if pollErr != nil {
	return nil, err   // returns the closure-captured `err`, discarding `pollErr`
}
```

`wait.PollUntilContextCancel` returns `ctx.Err()` (e.g. `context.Canceled`) immediately when the passed-in context is canceled from outside (confirmed via `staging/src/k8s.io/apimachinery/pkg/util/wait/loop.go:66-69,78-80` — cancellation is checked independently of the condition function and can fire between poll iterations). If kube-proxy's parent context is canceled while `NewNodeManager` is still waiting (e.g. a shutdown signal racing startup), `newNodeManager` will still return whatever business-logic error (`"node \"x\" does not have any PodCIDR allocated"`, `"host IP unknown..."`, etc.) was captured on the last executed poll iteration — not the fact that startup was interrupted by cancellation. An on-call engineer reading that error later would reasonably conclude there's a persistent node-config problem, when the real cause was an unrelated shutdown race. This is a narrower, lower-severity issue than Findings 1-2 (it never surfaces `nil, nil`, and normal timeout cases genuinely benefit from the specific business reason instead of a generic "context deadline exceeded"), but it's a real error-message-accuracy gap worth calling out.

### Not flagged
- `PodCIDRs()`/`Node()` dereferencing `n.node` (task's suggested lead): verified this is not reachable with a nil `n.node` — `newNodeManager` only ever returns a non-nil `NodeManager` after the poll loop has confirmed a non-nil `node`, and `OnNodeChange` always receives a non-nil `*v1.Node` from the informer. No nil-deref found here.
- `s.NodeManager` being nil for the hollow-proxy path (`pkg/proxy/kubemark/hollow_proxy.go`) is guarded correctly (`if s.NodeManager != nil` in `server.go` `Run()`, and hollow proxy never configures `HealthzBindAddress`, so `healthcheck.NewProxyHealthServer` — the only other consumer of `NodeManager` — is never constructed for it).
- Ignored error from `nodeInformer.Informer().AddEventHandlerWithResyncPeriod(...)` in both `NewNodeConfig` and the new `newNodeTopologyConfig` — pre-existing convention already used identically for `ServiceConfig`/`EndpointSliceConfig` elsewhere in this file; not a regression introduced by this PR.

```json-findings
[
  {
    "severity": "High",
    "confidence": 65,
    "category": "edge-case",
    "file": "pkg/proxy/node.go",
    "line": 146,
    "finding": "OnNodeChange() commits the incoming node to n.node (line 146) before validating that it has usable host IPs. When utilnode.GetNodeHostIPs(node) subsequently fails (line 159-163), the error is only klog.ErrorS-logged and the function returns — n.node is left pointing at the invalid node and exitFunc is never called, contradicting the type's documented contract ('crashes kube-proxy if there are any changes in NodeIPs or PodCIDRs'). Because NodeIPs() (line 123: `nodeIPs, _ := utilnode.GetNodeHostIPs(n.node)`) and the *next* OnNodeChange's oldNodeIPs computation (line 144: `oldNodeIPs, _ := utilnode.GetNodeHostIPs(n.node)`) both discard their errors too, the corrupted n.node silently poisons the baseline used for the next change-detection comparison.",
    "remediation": "Validate the incoming node's host IPs (and PodCIDRs) before assigning n.node = node; on failure, either exit(1) immediately (consistent with the rest of this type's fail-fast design) or keep the last-known-good IPs/PodCIDRs in separate fields so a bad update can't silently overwrite the comparison baseline. Also give NodeIPs()/PodCIDRs() a way to signal 'invalid state' instead of swallowing the error into an empty return value.",
    "failure_scenario": "A node update event arrives with Status.Addresses transiently empty/invalid (e.g. a status resync race). n.node is overwritten with this bad node and the error is only logged. When the node's real IP reappears unchanged on the following update, oldNodeIPs (computed from the now-corrupted n.node) comes back nil due to the swallowed error, differs from the restored valid IP, and OnNodeChange spuriously concludes 'NodeIPs changed' and calls n.exitFunc(1), crash-looping kube-proxy for no real reason."
  },
  {
    "severity": "Medium",
    "confidence": 80,
    "category": "observability",
    "file": "pkg/proxy/node.go",
    "line": 90,
    "finding": "The startup poll loop inside newNodeManager (lines 87-104) retries silently on every failure (`return false, nil` for lister-not-found, GetNodeHostIPs failure, and missing PodCIDRs) with no per-attempt logging at all, for up to the full 5-minute pollTimeout. The code it replaced (deleted getNodeIPs() in cmd/kube-proxy/app/server.go) called logger.Error(err, \"Failed to retrieve node info\") / logger.Error(err, \"Failed to retrieve node IPs\") on every failed attempt, giving operators live visibility into why kube-proxy startup was stalled.",
    "remediation": "Log each failed poll attempt (e.g. at V(2)/V(4) to avoid spamming, or throttled) with the specific error, mirroring the diagnostic behavior of the pre-PR getNodeIPs() implementation, so an operator watching pod logs during a slow node registration/PodCIDR allocation can see what kube-proxy is waiting on instead of a multi-minute blackout.",
    "failure_scenario": "A node takes 2 minutes to register or get a PodCIDR allocated (e.g. slow cloud-controller-manager). kube-proxy's log shows nothing during that window — no indication it's alive, retrying, or what it's blocked on — until it either succeeds silently or times out with a single terminal error, making live triage of slow-starting nodes much harder than before."
  },
  {
    "severity": "Low",
    "confidence": 50,
    "category": "observability",
    "file": "pkg/proxy/node.go",
    "line": 108,
    "finding": "On poll timeout, newNodeManager returns the closure-captured `err` (the last individual validation failure) rather than `pollErr` (the actual result of wait.PollUntilContextCancel, e.g. context.Canceled/DeadlineExceeded). If the caller's context is canceled from outside mid-wait (e.g. process shutdown racing startup), the returned error will misleadingly read as a persistent business-logic problem (\"node ... does not have any PodCIDR allocated\") rather than reflecting that startup was interrupted by cancellation.",
    "remediation": "When pollErr indicates context cancellation specifically (errors.Is(pollErr, context.Canceled)), prefer surfacing that (or wrap both: fmt.Errorf(\"%w: last observed error: %v\", pollErr, err)) so the caller/operator can distinguish 'startup was canceled' from 'the node genuinely never became ready'.",
    "failure_scenario": "kube-proxy receives SIGTERM while NewNodeManager is still polling for PodCIDR allocation. The process exits with an error log claiming the node lacks a PodCIDR, even though the real cause was a normal shutdown — misleading whoever reviews the exit log into thinking there's a cluster configuration problem."
  }
]
```
