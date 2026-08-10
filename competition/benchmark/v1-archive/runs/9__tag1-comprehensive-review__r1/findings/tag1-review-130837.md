# Comprehensive Review — kubernetes/kubernetes PR #130837

> **Mode:** `--local` (display-only; nothing posted to GitHub). **PR state:** **MERGED** — this is a retrospective review of the PR diff on its merits.
> **Diff source:** authoritative GitHub PR diff (`gh pr diff 130837`), 18 files, **+757 / −803**. Local checkout is a shallow clone; the PR head (`46e2c22f`) was reviewed in a worktree.
> **Depth:** normal · **Tier:** medium (1560 changed lines) · **Language:** Go · **Agents run:** 11 (issue-linker skipped in `--pr`/`--local`; CVE + static analyzers skipped — no manifest changes, no analyzer binaries installed).

## Summary

This PR consolidates kube-proxy's several overlapping node-watching mechanisms — the `getNodeIPs` retry-poll, the Linux-only `waitForPodCIDR` watch, `NodePodCIDRHandler`, and `NodeEligibleHandler` — into a single `NodeManager` (`pkg/proxy/node.go`) that owns one node-scoped informer, blocks startup until the node's `NodeIPs` (and `PodCIDRs`, when configured) are available, and then `os.Exit(1)`s the process on any subsequent change to `NodeIPs`/`PodCIDRs` or on node deletion. It also splits the old combined `NodeHandler` (`OnNodeAdd`/`OnNodeUpdate`) into a merged `OnNodeChange` and a new lightweight `NodeTopologyConfig`/`OnTopologyChange` path, so the iptables/ipvs/nftables/winkernel proxiers are notified only when topology-zone labels actually change rather than on every node update. Carries work forward from PR #125382.

**Type:** refactor / cleanup **Effort:** 4/5 — architecture-level consolidation touching startup sequencing, the `NodeHandler`/`Provider` interfaces, and every proxier backend, applied mechanically and consistently.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| pkg/proxy/node.go | +141/−62 | Replaces `NodePodCIDRHandler`/`NodeEligibleHandler` with unified `NodeManager`: owns node informer, blocks in `NewNodeManager` until NodeIPs/PodCIDRs exist, `os.Exit(1)`s on NodeIP/PodCIDR change or node deletion. Injectable `exitFunc`/`pollInterval`/`pollTimeout`. |
| pkg/proxy/node_test.go | +266/−90 | Rewrites tests for `NewNodeManager`/`newNodeManager`, `OnNodeChange`, `OnNodeDelete`, `Node()` using an injected exit function. |
| cmd/kube-proxy/app/server.go | +21/−54 | Constructs `s.NodeManager`, derives NodeIPs/podCIDRs from it, passes it to the health server; removes `getNodeIPs` and the ad-hoc node-informer wiring; adds `NodeTopologyConfig`. |
| cmd/kube-proxy/app/server_linux.go | +0/−66 | Removes `waitForPodCIDR` and Linux-specific PodCIDR-wait from `platformSetup` (now handled by `NodeManager`). |
| cmd/kube-proxy/app/server_linux_test.go / server_test.go | −119 / −79 | Deletes `Test_waitForPodCIDR`, `TestProxyServer_platformSetup`, `Test_getNodeIPs` and helpers for the removed logic. |
| pkg/proxy/config/config.go | +100/−48 | Merges `OnNodeAdd`/`OnNodeUpdate` into `NodeHandler.OnNodeChange`; drops `NoopNodeHandler`; adds `NodeTopologyHandler`/`NodeTopologyConfig` firing `OnTopologyChange` only when zone labels change. |
| pkg/proxy/config/config_test.go | +137/−0 | New `TestNewNodeTopologyConfig` verifying zone-label change filtering. |
| pkg/proxy/types.go | +1/−1 | `Provider` now embeds `config.NodeTopologyHandler` instead of `config.NodeHandler`. |
| pkg/proxy/{iptables,ipvs,nftables}/proxier.go | +9/−72 (×3) | Replace `OnNodeAdd/Update/Delete/Synced` with a single `OnTopologyChange`; rename field `nodeLabels` → `topologyLabels`. |
| pkg/proxy/metaproxier/meta_proxier.go | +4/−26 | Replaces four forwarded node-handler methods with a single `OnTopologyChange` fan-out to both family proxiers. |
| pkg/proxy/winkernel/proxier.go / kubemark/hollow_proxy.go | +7/−3 / +2/−4 | Drop embedded `NoopNodeHandler`; add explicit no-op `OnTopologyChange` (winkernel has a TODO). |
| pkg/proxy/topology.go | +6/−2 | Renames `CategorizeEndpoints` param `nodeLabels` → `topologyLabels`; adds cross-reference comment to `NodeTopologyConfig`. |
| pkg/proxy/healthcheck/proxy_health.go | +14/−23 | `NewProxyHealthServer` now takes a `*proxy.NodeManager`; replaces cached `SyncNode`/`nodeEligible` with on-demand `NodeEligible()` computed from `nodeManager.Node()`. |
| pkg/proxy/healthcheck/healthcheck_test.go | +31/−15 | Drives eligibility through a real `NodeManager` + fake clientset instead of the removed `hs.SyncNode`. |

---

## Review Findings

**Overall Risk: High** — no data-loss or security-exploit findings, but two High-severity issues affect the correctness and operability of the new crash-on-change safety mechanism at the heart of the PR.

> **Confidence note:** the default `--min-confidence` is 75. Because `--local` requests "display everything," findings below that threshold are **retained and labeled** rather than dropped. Each finding shows its consolidated confidence and how many independent reviewers converged on it. At the default threshold, findings **M4, M9, and several Low items** would be filtered.

### Critical (0)

None.

### High (2)

- **[H1] `NewNodeConfig` drops `AddFunc` → the initial-state informer replay is silently discarded, so node changes in the startup window bypass NodeManager's crash-on-change safety.** — `pkg/proxy/config/config.go:288`
  `NewNodeConfig`'s `cache.ResourceEventHandlerFuncs` wires only `UpdateFunc` and `DeleteFunc`; `AddFunc` is `nil`, so `OnAdd` is a no-op. `NodeManager` now starts and syncs its informer inside `NewNodeManager` **before** `NodeConfig` registers this handler in `Run()` (the pre-PR code deliberately started the informer *after* registration — see the removed "This has to start after the calls to NewNodeConfig…" comment). client-go replays cached state to a late-registered handler as a synthetic **Add**, which is dropped here. Any change to the node's `NodeIPs`/`PodCIDRs` (or a delete/recreate) that lands between `NewNodeManager`'s construction poll and handler registration — a window spanning `platformSetup`, `checkBadConfig`, `createProxier`, etc. — is never delivered to `OnNodeChange`, so the crash-and-restart self-heal doesn't fire until the next genuine Update or periodic resync. The sibling `NodeTopologyConfig`, added in the same PR, **does** wire `AddFunc`, making this an asymmetry/oversight. The `OnNodeChange` doc ("called on creation or modification") is also inaccurate as a result.
  *Convergence: 5 reviewers (edge-case 78, architecture 76, type-design 65, code-review 55, comment-analysis 55). The missing-`AddFunc` fact is certain; impact is bounded by the resync backstop and by NodeManager capturing initial state via its own poll.*
  **Fix:** add `AddFunc: func(obj interface{}) { result.handleChangeNode(obj) }` to `NewNodeConfig`, mirroring `newNodeTopologyConfig`; or have `NodeManager` register itself on its own informer at construction so wiring can't be forgotten. Add an informer-level `NodeConfig` test that asserts `OnNodeChange` fires for the replayed Add.

- **[H2] All three `os.Exit(1)` paths emit no metric or Event before exiting → fleet-wide kube-proxy crashloops are operationally invisible.** — `pkg/proxy/node.go:155,171,179`
  `OnNodeChange` (NodeIP change, PodCIDR change) and `OnNodeDelete` call `n.exitFunc(1)` after only a `klog.InfoS` + `klog.Flush()` racing process teardown — no `kubeproxy_node_manager_exit_total{reason=...}` counter, no Kubernetes Event. A single correlated trigger (node-controller bug, stale/empty apiserver node status, mass taint/relist) can fire the same event on every node at once, crashlooping every kube-proxy simultaneously, with the only signal being process restarts that can't be attributed to a cause or distinguished from legitimate churn. Node-deletion and NodeIP-change are brand-new exit surfaces widening this blind spot.
  *Convergence: adversarial-general (85). Availability/operability, not security (see Security Analysis).*
  **Fix:** increment a `reason`-labeled counter (and ideally record an Event) immediately before `exitFunc(1)`. Rejected alternative — relying on the generic process-restart metric — can't attribute cause or separate churn from a crashloop.

### Medium (11)

- **[M1] `OnNodeChange` overwrites `n.node` *before* validating the new node's IPs; a transient IP-less update poisons the baseline and causes a later spurious crash.** — `pkg/proxy/node.go:145`
  The method sets `n.node = node` under lock, then calls `GetNodeHostIPs(node)`; on error it logs and returns without exiting and without reverting. The bad (IP-less) node is now the stored baseline, so the *next* update computes `oldNodeIPs` from it (error again swallowed → `nil`) and, mismatching the restored real IPs, concludes "NodeIPs changed" → `exitFunc(1)`. A momentary empty/unparseable `Status.Addresses` (resync race, bad PATCH) followed by any normal update crashes kube-proxy even though the IPs never actually changed. *Convergence: adversarial 76, silent-failure 65, type-design 70.* **Fix:** assign `n.node = node` only after successfully deriving `nodeIPs` (or keep last-known-good IPs separately); don't reduce a `GetNodeHostIPs` failure to a log line when the rest of the type is fail-fast.

- **[M2] NodeIP change detection uses order-sensitive `reflect.DeepEqual` on a derived slice → benign address reordering triggers a spurious crash.** — `pkg/proxy/node.go:167`
  `GetNodeHostIPs` preserves `Status.Addresses` ordering; a kubelet restart or cloud-controller resync that reports the same IP *set* in a different order flips the derived primary and exits, disrupting dataplane programming during the restart — no IP added or removed. No normalization/sort before comparison, and no test pins the intended behavior. *Convergence: adversarial 66, pr-test 65.* **Fix:** compare the IP set (sorted/as a set), or document that ordering is contractually stable and intentionally load-bearing.

- **[M3] Behavior change: node deletion and NodeIP change now `os.Exit(1)` in all modes (was: delete → 503 drain while serving; IP change ignored) — undocumented, no release note, and the type doc omits the delete-crash.** — `pkg/proxy/node.go:42,167,176`
  Pre-PR, node deletion only flipped the health server to 503 (proxy kept serving existing rules) and node IPs were read once at startup and never re-evaluated. The `NodeManager` doc lists only NodeIP/PodCIDR change as crash triggers and omits deletion entirely; this ships as `/kind cleanup` with an empty release-note block. Operators upgrading will see kube-proxy start dying on events it previously tolerated. *Convergence: architecture 78, adversarial 82, comment-analysis.* **Fix:** document all three exit conditions on `NodeManager`; add a release note calling out crash-on-NodeIP-change / crash-on-node-delete across all modes. Counter-argument acknowledged: crash-and-reload is a defensible strategy for kube-proxy — the ask is to make it explicit, not to revert it.

- **[M4] `s.podCIDRs` is now populated unconditionally → `checkBadIPConfig`'s podCIDR-family warning can fire for non-`LocalModeNodeCIDR` modes.** *(confidence 65 — below default threshold; single-source, well-reasoned)* — `cmd/kube-proxy/app/server.go:218`
  `s.podCIDRs = s.NodeManager.PodCIDRs()` runs in `newProxyServer` regardless of `DetectLocalMode`; previously it was set only under `LocalModeNodeCIDR`. `checkBadIPConfig` runs unconditionally and `badCIDRs(s.podCIDRs, badFamily)` is not gated (only the *fatal* escalation is still scoped to `LocalModeNodeCIDR`), so `ClusterCIDR`/`BridgeInterface`/`InterfaceNamePrefix` deployments can now log a misleading non-fatal "node.spec.podCIDRs contains only IPv{X} addresses" for a field their mode doesn't consume. The struct comment `podCIDRs []string // only used for LocalModeNodeCIDR` (line 175) is now false. *Convergence: code-review 65.* **Fix:** gate `s.podCIDRs` population (or the `badCIDRs(s.podCIDRs, …)` check) on `DetectLocalMode == LocalModeNodeCIDR`.

- **[M5] `NewNodeManager` now blocks startup up to a hardcoded 5 min and hard-fails (aborts kube-proxy) when NodeIPs aren't ready — in all detect-local modes (was best-effort start with fallback).** — `pkg/proxy/node.go:60,87-109` · `cmd/kube-proxy/app/server.go:211`
  The removed `getNodeIPs` used ~63s backoff and returned possibly-`nil` IPs *without* erroring (proxy started degraded on the bind address); the 5-min wait previously applied only to PodCIDR under `LocalModeNodeCIDR`. Now a single poll blocks up to `5*time.Minute` (a magic literal, not configurable) for node existence + usable host IPs in every mode, erroring out `newProxyServer` on timeout. A "start degraded and continue" path becomes "block, then crashloop until ready." *Convergence: architecture 76, adversarial 68.* **Fix:** confirm intended for non-`LocalModeNodeCIDR`; document the fatal path; consider making the timeout configurable and/or preserving a degraded-start fallback.

- **[M6] `healthcheck` now depends on the concrete `*proxy.NodeManager` but uses only `Node()` — inverts the package dependency direction and forces heavy test setup.** — `pkg/proxy/healthcheck/proxy_health.go:74` (import at `:29`)
  Adds a new `healthcheck → pkg/proxy` import (previously `proxy` depended on `healthcheck` via `NodeEligibleHandler`). The health server needs exactly one method yet takes the whole struct; `healthcheck_test.go` must now stand up a real `proxy.NewNodeManager` with a fake clientset (`:481`, `:561`) to exercise taint/deletion eligibility logic that's conceptually independent of node-watching. *Convergence: architecture 80.* **Fix:** define a one-method interface in `healthcheck` (`type nodeProvider interface { Node() *v1.Node }`) and accept that.

- **[M7] The startup poll loop dropped all per-attempt diagnostic logging → multi-minute silent startup stalls.** — `pkg/proxy/node.go:87-104`
  Each failure path (`nodeLister.Get`, `GetNodeHostIPs`, missing PodCIDR) returns `false, nil` with no logging, for up to the full 5-minute window. The replaced `getNodeIPs` logged `Failed to retrieve node info` / `Failed to retrieve node IPs` on every attempt. An operator watching a kube-proxy pod stuck waiting for node registration / PodCIDR allocation now sees nothing. *Convergence: silent-failure 80.* **Fix:** log each failed attempt (throttled or at V(2)/V(4)) with the specific reason.

- **[M8] `NewNodeManager`'s "5 minutes for PodCIDR" comment is now inaccurate.** — `pkg/proxy/node.go:59`
  The comment is carried over verbatim from the pre-PR PodCIDR-only timeout, but the same value is now the general `pollTimeout` covering node existence + NodeIP readiness and only conditionally PodCIDRs. A maintainer debugging a 5-min startup stall caused by missing NodeIPs would be misdirected toward CNI/PodCIDR allocators. *Convergence: comment-analysis 80.* **Fix:** reword to "wait at most 5 minutes for the node to exist and have NodeIPs, and (if watchPodCIDRs) PodCIDRs."

- **[M9] `config.NodeConfig`'s informer→handler dispatch has zero test coverage, before or after — and this PR changed it non-trivially.** *(test-gap)* — `pkg/proxy/config/config.go:320` · `pkg/proxy/config/config_test.go`
  `handleChangeNode` merged Add+Update, added a tombstone branch, and dropped `AddFunc` (H1) — none exercised; `node_test.go` calls `NodeManager`'s methods directly, bypassing the type-assertion/tombstone/wiring layer. *Convergence: pr-test 80, type-design 85.* **Fix:** add a `NodeConfig` test (like the existing `ServiceConfig`/`EndpointSliceConfig` ones) driving a fake informer through Add/Update/Delete (including a raw `DeletedFinalStateUnknown`) — this would also have caught H1.

- **[M10] `watchPodCIDRs=false` + PodCIDR change is never tested → a regression in the `if n.watchPodCIDRs` guard would crashloop every non-`LocalModeNodeCIDR` deployment undetected.** *(test-gap)* — `pkg/proxy/node_test.go:231`
  All `watchPodCIDRs:false` cases leave PodCIDRs empty, so the doc'd "only crashes on PodCIDR change when watchPodCIDRs is true" gate is unverified. *Convergence: pr-test 85.* **Fix:** add a `watchPodCIDRs:false`, non-empty→changed-PodCIDRs case asserting no exit.

- **[M11] `healthcheck_test.go` builds its `NodeManager` via the public `NewNodeManager`, which hard-wires the real `os.Exit` → a future test edit could kill the test binary instead of failing.** *(test-gap)* — `pkg/proxy/healthcheck/healthcheck_test.go:481,561`
  Unlike `node_test.go` (same package, uses the injectable unexported `newNodeManager`), `healthcheck_test.go` is in another package and can only reach the exported constructor, which passes `os.Exit`. A change to `makeNode`/`tweakTainted`/`tweakDeleted` altering `Status.Addresses` would make `OnNodeChange` call real `os.Exit(1)` mid-test. *Convergence: blind-hunter 76, pr-test.* **Fix:** export a test-only constructor / functional option to inject a no-op exit function.

### Low (13)

- **[L1] `NodeEligible()` takes the `hs.lock` write lock but no longer guards any state it protects** (the `nodeEligible` field it protected was removed; it now only reads `hs.nodeManager.Node()`, which has its own mutex). Needless contention with `Updated()`/`QueuedUpdate()`. — `pkg/proxy/healthcheck/proxy_health.go:177` *(type-design 80, blind-hunter 66)* — drop the lock (or downgrade; was `RLock` before).
- **[L2] `PodCIDRs()` returns the raw informer-owned slice without copying, while sibling `Node()` deliberately `DeepCopy()`s** — inconsistent encapsulation; a caller mutating the result could corrupt the comparison baseline or shared informer state. — `pkg/proxy/node.go:131` *(type-design 65)* — `return slices.Clone(n.node.Spec.PodCIDRs)`.
- **[L3] `NodeManager` type doc comment is grammatically garbled** ("…based on the NodeIPs and PodCIDRs **handles** node watch events…" — duplicated verb, merge artifact). — `pkg/proxy/node.go:41` *(comment-analysis 90)* — split into two sentences and enumerate all three crash conditions.
- **[L4] `NodeTopologyConfig.listerSynced` is assigned but never read** (no `Run` waits on it, unlike every sibling config type) — dead field inviting a false assumption that sync-gating exists. — `pkg/proxy/config/config.go:503` *(adversarial 85, blind-hunter 78)* — remove it or add a `Run` that waits on it.
- **[L5] `NodeManager.nodeLister` field is written at construction but never read afterward** — dead struct state. — `pkg/proxy/node.go:48` *(type-design 90)* — use a local in `newNodeManager` instead.
- **[L6] Dead `cache.DeletedFinalStateUnknown` tombstone branch in `handleChangeNode`** — the function is wired only to `UpdateFunc`, whose `newObj` is never a tombstone; harmless copy-paste. — `pkg/proxy/config/config.go:320` *(blind-hunter 82, adversarial 78)* — drop the branch.
- **[L7] No `return` after `exitFunc(1)` on the PodCIDR-change path** — harmless in production (`os.Exit` never returns) but with an injected non-terminating `exitFunc` (tests / future reuse) execution falls through and can call `exitFunc` twice. — `pkg/proxy/node.go:155` *(adversarial 72)* — add `return`.
- **[L8] `NodeTopologyConfig` hands its internal `topologyLabels` map to every handler by reference** (fanned out to both family proxiers via `metaProxier`) — safe today (map is replaced wholesale, never mutated in place) but relies on convention, not the type. — `pkg/proxy/config/config.go:535` *(type-design 70)* — document the read-only contract or defensively copy at handoff.
- **[L9] On poll timeout, `newNodeManager` returns the captured business `err`, not `pollErr`** — a context cancellation racing startup (SIGTERM during the wait) is misreported as a persistent node-config problem ("node … does not have any PodCIDR allocated"). — `pkg/proxy/node.go:108` *(silent-failure 50)* — surface `pollErr` when it's `context.Canceled`, or wrap both.
- **[L10] Cache-sync-failure path untested** — `newNodeManager`'s `"can not sync node informer"` branch has no test (pass an already-canceled context). *(test-gap)* — `pkg/proxy/node.go:77` *(pr-test 80)*.
- **[L11] Transient `GetNodeHostIPs` error path untested** — no `OnNodeChange` case sends an address-less update to confirm it doesn't crash (and, per M1, that it doesn't poison the baseline). *(test-gap)* — `pkg/proxy/node.go:159` *(pr-test 75)*.
- **[L12] Dual-stack PodCIDRs no longer explicitly tested** — the deleted `TestProxyServer_platformSetup` had a two-CIDR case; `TestNewNodeManager` only supplies a single CIDR. *(test-gap)* — `pkg/proxy/node_test.go:146` *(pr-test 60)*.
- **[L13] `OnNodeChange` doc says it fires on "creation and update," but only `UpdateFunc` is wired** (see H1) — creation is actually captured by `NewNodeManager`'s bootstrap poll. — `pkg/proxy/node.go:139` *(comment-analysis 55)* — clarify, or fix by adding `AddFunc` per H1.

### Security Analysis

`security-reviewer` (Opus) returned **NONE** after an explicit evaluation, and this is a substantive clean result rather than a skip:

- **Crash-on-change as a DoS surface:** the informer is scoped by `fields.OneTermEqualSelector("metadata.name", nodeName)`, so events fire only for the **local** node — a compromised kubelet on node X cannot crash kube-proxy on node Y (per-node isolation preserved). Triggering a crash requires mutating the local Node's `Status.Addresses`/`Spec.PodCIDRs` or deleting it — privileged operations gated by NodeRestriction/RBAC; an actor with those rights already controls that node. No privilege escalation, no cross-node blast radius. It is an **availability/robustness tradeoff** (covered by H2/M1/M2/M3), below the Medium security bar.
- **Field-selector scoping** correct; **Node fields** used only as structured data (`reflect.DeepEqual`, `GetNodeHostIPs`) — no injection sink; **log exposure** is network topology, not secrets/PII, and pre-existing. No new RBAC surface. No reachable nil-deref or data race (mutex correctly guards `n.node`; handlers invoked serially).

### Adversarial Analysis — Most Critical Gap

The `NodeManager` turns NodeIP change, PodCIDR change, and node deletion into unconditional `os.Exit(1)` with **no metric/Event before exit (H2)** and **no guard against transient or reordered node updates** (baseline replaced before validation — M1; order-sensitive comparison — M2). A single correlated bad node update can crashloop the entire kube-proxy fleet, and operators have no observability to detect or attribute it. Add a `reason`-labeled exit metric/Event and make change detection resilient to transient/malformed/reordered updates before relying on this in production.

### Positive Observations

- **Real consolidation:** four overlapping node-watch mechanisms (`getNodeIPs` backoff, `waitForPodCIDR` watch, `NodePodCIDRHandler`, `NodeEligibleHandler`) plus per-proxier `OnNodeAdd/Update/Delete/Synced` and `NoopNodeHandler` collapse into one `NodeManager` + focused `NodeTopologyConfig`; a single node-scoped informer replaces a second informer factory and two ad-hoc Get/watch loops, cutting apiserver load and eliminating duplicated field-selector logic.
- **Testability win:** `exitFunc`/`pollInterval`/`pollTimeout` (and `newNodeTopologyConfig`'s completion callback) are dependency-injected, replacing the old fragile `klog.OsExit`/`panic`-based exit testing with clean, table-driven, non-flaky tests.
- **Responsible topology narrowing:** `NodeTopologyConfig` filters to only `LabelTopologyZone` (the sole label `CategorizeEndpoints` consumes) and suppresses no-op notifications; `topology.go:44` adds a cross-package comment to keep the two in sync — good knowledge preservation for an easy-to-miss coupling.
- **Clean interface segregation:** splitting `NodeTopologyHandler` out of `NodeHandler` gives each `Proxier` a narrow `OnTopologyChange(map[string]string)` instead of the full node object; the refactor is threaded consistently across all five proxier backends with no stray `OnNodeAdd`/`nodeLabels` references left behind.
- **Correct concurrency & aliasing discipline** on the hot path: `Node()` deep-copies, `n.mu` consistently brackets reads/writes of `n.node`, and informer handlers run serially (no self-concurrency on `OnNodeChange`).

### Recommended Actions (priority order)

1. **H1** — restore `AddFunc` in `NewNodeConfig` (or self-register `NodeManager` on its own informer) and add a `NodeConfig` informer-level test (also closes **M9**).
2. **H2** — emit a `reason`-labeled exit counter/Event immediately before every `exitFunc(1)`.
3. **M1 + M2** — validate the incoming node before replacing the baseline; compare NodeIPs as a set, not an ordered slice (add tests **M10, L11, M2's reorder case**).
4. **M3 + M8 + L3** — document the broadened crash-on-change lifecycle (all three triggers) on `NodeManager`, fix the 5-minute comment, and add a release note.
5. **M4 / M5 / M7** — re-scope `s.podCIDRs` to `LocalModeNodeCIDR`; confirm/document (and consider making configurable) the new blocking-fatal startup; restore per-attempt startup logging.
6. **M6, M11, L1–L2, L4–L9** — decouple `healthcheck` via a one-method interface; fix the exit-injection test seam; clear the dead fields/branches/locks and encapsulation nits.
