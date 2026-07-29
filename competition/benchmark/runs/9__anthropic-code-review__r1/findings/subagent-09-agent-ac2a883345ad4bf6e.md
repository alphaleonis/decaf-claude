# subagent agent-ac2a883345ad4bf6e

Based on my verification:

**Finding confirmed:**

1. **PR #125382** explicitly added a DeletionTimestamp check during node polling with the comment: "don't consider the node if is going to be deleted and keep waiting"

2. **PR #130837** removed this check — the old `getNodeIPs()` and `waitForPodCIDR()` functions that contained `if !node.DeletionTimestamp.IsZero() { return false, nil }` were replaced with a new `NodeManager` that lacks this guard in its `newNodeManager()` polling loop

3. **PR #133059** (the "take 2" redo) also lacks the check in its `getNodeInfo()` helper, confirming this is a still-open gap

**Risk assessment:**

The new code captures whatever node is returned by the lister without checking if it's marked for deletion. While `OnNodeDelete()` will react and exit when the deletion event fires, there's a window where kube-proxy could baseline its IPs/PodCIDRs to a dying node. This is exactly the scenario PR #125382 was added to prevent. Both the poll and watch may encounter this: the poll during startup, the watch if the node is deleted after startup.

However, the scenario requires timing alignment (node marked for deletion within the poll window), and fallback handling exists via OnNodeDelete. Both new PRs lack explicit comments explaining the removal.

**Score: 65**

This is a real, verified regression from an explicit prior bug fix, but the narrow timing window and existing fallbacks prevent higher confidence. The issue affects correctness (wrong node baseline) rather than crashing behavior, and maintainers may have intentionally shifted from preventive to reactive deletion handling without documenting why.
