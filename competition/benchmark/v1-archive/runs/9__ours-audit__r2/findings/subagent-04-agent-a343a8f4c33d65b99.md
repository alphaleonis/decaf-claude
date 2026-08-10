# subagent agent-a343a8f4c33d65b99

```json
{
  "finding": "OnNodeChange overwrites n.node baseline before checking new node's IP validity",
  "verdict": "confirmed",
  "reason": "Traced pkg/proxy/node.go lines 140-173 directly. At line 143, oldNodeIPs is computed from n.node (the PRE-update baseline) with the error discarded via `_`. At line 145, n.node = node is assigned unconditionally, BEFORE any validation of the new node's addresses. Only afterward, at lines 159-163, does the code call GetNodeHostIPs(node) and, on error, log and return early WITHOUT calling exitFunc — but n.node has already been overwritten with the IP-less node. Confirmed via pkg/util/node/node.go GetNodeHostIPs (line 84-85): when node.Status.Addresses yields zero parseable IPs, it explicitly returns (nil, error), so oldNodeIPs on the SUBSEQUENT OnNodeChange call (line 143) will be exactly nil. When addresses are later restored (even to their original values), line 167's reflect.DeepEqual(nil, restoredIPs) is false, triggering n.exitFunc(1) at line 171 — a spurious restart. The mechanical chain (assign-before-validate -> discarded error -> nil baseline -> false DeepEqual on restore) is fully re-derivable from the code as written; there is no lock re-check, no guard on the discarded error, and no rollback of n.node on the early-return path.",
  "corrections": {
    "pre_existing": null
  }
}
```

Note on scope I could not fully resolve: the repo is a shallow/grafted clone (commit 46e2c22f has no fetchable parent, `git fetch --unshallow` failed with no network access), so I could not verify whether this exact ordering (assign n.node before validating IPs) is newly introduced by "kube-proxy: merge OnNodeAdd and OnNodeUpdate into OnNodeChange" or was already present in the separate `OnNodeAdd`/`OnNodeUpdate` handlers it replaced. [Unverified] on attribution/pre-existing status — this does not affect the mechanical confirmation above, only whether the finding should be flagged as pre-existing. I did not correct `pre_existing` since I could not verify it either way.

On reachability (the review's point 3): whether a real informer/apiserver ever delivers a Node update with zero `Status.Addresses` is plausible but not something I can verify with certainty from the code alone — normal kubelet status reporting rarely clears addresses to empty, but external actors (cloud-controller-manager address sync, apiserver/etcd anomalies, racing patches) could produce such an intermediate state. This is consistent with the original Medium/conf50 rating rather than grounds to raise or lower it further.
