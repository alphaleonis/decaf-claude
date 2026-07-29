# subagent agent-a0e33d9366e54cf47

## Summary

I reviewed PR #130837's node-handling consolidation against the git history of `pkg/proxy/node.go`, `cmd/kube-proxy/app/server*.go`, and `pkg/proxy/config/config.go` (fetched via `gh api repos/kubernetes/kubernetes/commits?path=...` since this local clone is a 3-commit shallow clone with no real history). Three history-grounded regressions found, reported via `ReportFindings`:

1. **`pkg/proxy/config/config.go:288`** — `NewNodeConfig` only wires `UpdateFunc`/`DeleteFunc`, no `AddFunc`. Since `NodeManager`'s informer (`pkg/proxy/node.go:56-117`) is already started and synced by the time `Run()` registers `NodeConfig` on it (`cmd/kube-proxy/app/server.go:607-611`), client-go's "late join" replay of the existing store as synthetic Adds is silently dropped (no-op `OnAdd` when `AddFunc` is nil). Any Node change between the initial poll and this later registration is lost — reintroducing exactly the startup race commit `26801d6541af414f213b1bbacac08c9052ff9af3` ("kube-proxy avoid race condition using LocalModeNodeCIDR") was written to close. The `https://issues.k8s.io/111321` comment anchoring that concern was also deleted with no replacement.

2. **`pkg/proxy/node.go:176`** — `NodeManager.OnNodeDelete` now calls `exitFunc(1)`, crashing the process on Node deletion. Commit `a38b9363` ("kube-proxy handle node PodCIDR changs", 2022) deliberately made this log-only, stating explicitly it would "keep working, since it may break graceful shutdowns of the node" — behavior preserved unchanged through the entire subsequent history until this PR. The new crash-on-delete is intentional and tested (`TestNodeManagerOnNodeDelete`), but no rationale is given for discarding the documented graceful-shutdown concern.

3. **`pkg/proxy/node.go:87-104`** — the consolidated startup poll in `newNodeManager()` never checks `node.DeletionTimestamp`, unlike the old `waitForPodCIDR` watch condition, which commit `75913e9949a2e59bacbebbb833c6ea07c2048dba` ("kube-proxy wait for cluster cidr skip delete events") explicitly taught to skip Delete events and keep waiting on a Node marked for deletion. Without it, a doomed/being-replaced Node object with stale IPs/PodCIDRs can now satisfy the startup poll instead of the code waiting for the real replacement Node.

All three are corroborated by the fact that no existing or new test in `pkg/proxy/node_test.go` / `pkg/proxy/config/config_test.go` exercises late handler registration or a Node with a set `DeletionTimestamp`.
