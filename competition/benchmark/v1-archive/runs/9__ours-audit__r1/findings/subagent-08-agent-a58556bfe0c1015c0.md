# subagent agent-a58556bfe0c1015c0

```json
{
  "finding": "OnNodeChange advances the baseline node before validating NodeIPs, poisoning the baseline",
  "verdict": "confirmed",
  "reason": "Read pkg/proxy/node.go:140-172 directly. Line 145 (`n.node = node`) executes unconditionally under the lock before the NodeIPs error check at lines 159-163; on error the function returns without calling exitFunc, leaving n.node poisoned. GetNodeHostIPs (pkg/util/node/node.go:65-96) returns (nil, error) when Status.Addresses has no parseable NodeInternalIP/NodeExternalIP entry, so a transient empty/unparseable-address update is a real trigger. On the next event, oldNodeIPs is recomputed from the poisoned n.node (line 143, error discarded) yielding nil, and if that event restores the original IP A, reflect.DeepEqual(nil, [A]) is false, causing a spurious exitFunc(1) at line 171 even though the real IP never changed end-to-end (A -> poisoned -> A). Verified line numbers match the finding's citation exactly (140-172), and pkg/proxy/node_test.go's TestNodeManagerOnNodeChange only tests single-event transitions, not this three-event poison/restore sequence, so no existing guard prevents it.",
  "corrections": null
}
```
