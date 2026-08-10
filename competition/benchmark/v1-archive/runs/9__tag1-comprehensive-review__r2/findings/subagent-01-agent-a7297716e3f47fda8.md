# subagent agent-a7297716e3f47fda8

## Adversarial Review

### Summary
This PR does far more than the narrative ("consolidate `OnNodeAdd`/`OnNodeUpdate` into `OnNodeChange`") advertises: it introduces a `NodeManager` that watches NodeIPs and **crashes kube-proxy (`os.Exit(1)`) on any NodeIP change, PodCIDR change, or node deletion**, and it re-plumbs topology-label delivery to the proxiers. The most dangerous problem lives in the seam between the pre-started shared informer and late event-handler registration: the proxier can silently lose its initial topology (zone) labels via a registration race, and there is a concurrent unsynchronized read/append on `NodeTopologyConfig.eventHandlers`. Secondary gaps: the new crash-on-change behavior ships with zero metrics/events, and a startup-window NodeIP change is silently swallowed because `NodeConfig` no longer has an `AddFunc`.

### Findings

#### High

- **[edge-case]** Topology-config handler is registered on an already-started informer, racing the informer's synthetic Add — data race + lost initial zone labels — `cmd/kube-proxy/app/server.go:610` / `pkg/proxy/config/config.go:485,509,533`
  - **What's wrong/missing:** The node informer is started and synced inside `NewNodeManager` (`pkg/proxy/node.go:76`), long before `Run()` creates `NodeTopologyConfig` and calls `nodeTopologyConfig.RegisterEventHandler(s.Proxier)`. [Inference, based on client-go informer semantics] `AddEventHandlerWithResyncPeriod` on an already-started informer schedules an asynchronous synthetic `Add` replay of the current node. That replay runs `handleNodeEvent` on the informer's listener goroutine concurrently with `RegisterEventHandler(s.Proxier)` on the main goroutine. Two failures result:
    - (A) **Data race:** `handleNodeEvent` reads `n.topologyLabels` and iterates `n.eventHandlers` with no lock (`config.go:528-536`), while `RegisterEventHandler` appends to `n.eventHandlers` with no lock (`config.go:509-510`). `NodeTopologyConfig` has no mutex at all — unlike its sibling `ServiceCIDRConfig`, which guards the same pattern with `mu sync.Mutex`. This is a `-race`-detectable data race and undefined behavior on a map+slice.
    - (B) **Lost initial topology:** If the synthetic Add wins the race, `handleNodeEvent` sets `n.topologyLabels = {zone: X}` and notifies an *empty* handler list, then the proxier is registered afterward. Because the labels are now recorded, no later event (including periodic resync, which arrives as an Update whose computed labels `DeepEqual` the stored ones) will ever re-notify the proxier. The proxier runs indefinitely with `topologyLabels == nil`.
  - **Why it matters:** With `topologyLabels == nil`, `CategorizeEndpoints` sees `zone == ""` (`pkg/proxy/topology.go:58`) and topology-aware routing (topology hints / `TrafficDistribution: PreferClose`) silently does not apply — traffic that should stay zone-local is spread cluster-wide. Not a blackhole, but a silent, persistent cost/latency regression that defeats the feature this refactor is built around, and it manifests nondeterministically per-pod-restart. The data race is separately a correctness hazard.
  - **Fix:** Give `NodeTopologyConfig` a mutex covering `eventHandlers` and `topologyLabels`; register the proxier handler *before* the informer can deliver (e.g., add a `Run()`/priming step that replays current labels to newly registered handlers, mirroring `ServiceCIDRConfig.Run`'s `handleServiceCIDREvent(nil,nil)` priming), or register handlers before the informer is started. Add a regression test that registers the handler *after* `Start()` (see test-gap finding below).
  - **Confidence:** 85/100

#### Medium

- **[edge-case]** A NodeIP change during the startup window is silently swallowed — `NodeConfig` has no `AddFunc` — `pkg/proxy/config/config.go:288-294`
  - **What's wrong/missing:** `NodeConfig` registers only `UpdateFunc`/`DeleteFunc`; `AddFunc` is nil. `NodeManager` seeds its baseline `node` from a one-shot poll in `NewNodeManager` (called in `newProxyServer`), but the event handler is registered much later in `Run()` (after `platformSetup`, proxier creation, etc.). Any NodeIP change that occurs in that window is delivered only as the informer's synthetic *Add* replay — which is dropped because `AddFunc` is nil. `OnNodeChange` never fires, so the change is neither detected (no crash-and-restart) nor reflected in the already-computed `rawNodeIPs`.
  - **Why it matters:** The entire point of `NodeManager` is to catch NodeIP changes; this leaves a real, non-tiny hole precisely at startup, after which kube-proxy runs with stale NodeIPs baked into its rules until the next unrelated Update. There is no test for "IP changed between poll and handler registration."
  - **Fix:** Register the `NodeConfig` handler before the informer starts, or have `NodeManager` re-check current lister state against its polled baseline at registration time, or add an `AddFunc` that routes to `handleChangeNode`.
  - **Confidence:** 76/100

- **[observability]** New self-induced restart behavior ships with no metric or Event — `pkg/proxy/node.go:155,171,179`
  - **What's wrong/missing:** `OnNodeChange`/`OnNodeDelete` call `exitFunc(1)` on NodeIP change, PodCIDR change, or node deletion. There is only a `klog.InfoS` line before exit — no metric counter (e.g., `kubeproxy_node_restart_total{reason=...}`) and no Kubernetes Event on the node/pod. This is a brand-new operational behavior: previously NodeIPs were read once at startup and never triggered a restart.
  - **Why it matters:** A fleet-wide trigger (cloud migration re-IP, mass drain, address reordering) would produce kube-proxy restarts across the cluster with no aggregated signal — operators would have only scattered log lines to correlate. For a component this critical, self-induced restarts must be observable. `os.Exit(1)` also bypasses deferred cleanup.
  - **Fix:** Increment a dedicated metric (and ideally emit an Event) with a `reason` label before calling `exitFunc`; document the new restart triggers in the changelog.
  - **Confidence:** 80/100

- **[test-gap]** `TestNewNodeTopologyConfig` registers the handler *before* `Start()`, so it never exercises the production ordering — `pkg/proxy/config/config_test.go`
  - **What's wrong/missing:** The test does `newNodeTopologyConfig(...)` → `config.RegisterEventHandler(handler)` → `sharedInformers.Start(stopCh)`. Production (`server.go:610-611`) does the reverse: informer already started/synced, then config created, then handler registered. The test's safe ordering hides both the data race and the lost-initial-label race described in the High finding.
  - **Why it matters:** Gives false confidence that the topology path is correct; the exact failure mode is untested.
  - **Fix:** Add a test variant that starts and syncs the informer first, then registers the handler, and asserts the handler still receives the current zone label exactly once.
  - **Confidence:** 80/100

- **[other]** `NodeEligible()` now deep-copies the entire Node object under a write lock on every health/liveness probe — `pkg/proxy/healthcheck/proxy_health.go:176-190`
  - **What's wrong/missing:** Previously `NodeEligible()` was an `RLock` + return of a cached `bool`. It now takes `hs.lock.Lock()` (write) and calls `hs.nodeManager.Node()`, which performs `n.node.DeepCopy()`. It only reads `DeletionTimestamp` and `Taints`, but deep-copies the whole Node (including potentially large `.status.images`, labels, annotations, addresses).
  - **Why it matters:** `/healthz` and `/livez` are hit frequently by kubelet liveness and load balancers. A full Node deep-copy per probe is wasteful allocation on a hot path, and the RLock→Lock change serializes probes against `Health()` updates.
  - **Fix:** Add a `NodeManager` accessor that returns only eligibility (or the two needed fields) without a full deep-copy, and keep the health read on `RLock`.
  - **Confidence:** 78/100

#### Low

- **[docs]** Doc comments on `NodeIPs()`/`PodCIDRs()` are stale/misleading — `pkg/proxy/node.go:119,127`
  - **What's wrong/missing:** Both say "returns the ... polled in `NewNodeManager()`," but `OnNodeChange` overwrites `n.node` on every event (`node.go:145`), so these return the *latest* node's values, not the initially-polled ones.
  - **Why it matters:** A future caller could wrongly assume these are startup-stable snapshots. The `NodeManager` type comment (`node.go:41-42`) is also a broken run-on sentence that reads like a merge artifact.
  - **Fix:** Reword to "returns the current node's NodeIPs/PodCIDRs" and clean up the type doc.
  - **Confidence:** 80/100

- **[other]** Dead `DeletedFinalStateUnknown` branch in `handleChangeNode` — `pkg/proxy/config/config.go:320-332`
  - **What's wrong/missing:** `handleChangeNode` is wired only to `UpdateFunc` (`config.go:290`), where `newObj` is always a `*v1.Node`; a tombstone can never arrive here. The tombstone-handling branch is copy-pasted from `handleDeleteNode` and is unreachable.
  - **Why it matters:** Dead defensive code signals confusion about the event semantics of the consolidated handler and misleads the next reader into thinking Add/Delete are routed through this function.
  - **Fix:** Drop the tombstone branch from `handleChangeNode` (keep it only in `handleDeleteNode`).
  - **Confidence:** 78/100

### Findings below reporting confidence (surfaced for awareness, not in JSON)

- **[edge-case, ~55]** Spurious restart on equivalent-but-reordered NodeIPs: `OnNodeChange` uses `reflect.DeepEqual(oldNodeIPs, nodeIPs)` over the ordered slice returned by `GetNodeHostIPs`. If `node.status.addresses` is reported in a different order (same IP set), the derived primary IP per family can change and trigger an unnecessary `exit(1)`. Consider comparing as sets. [Inference — depends on `GetNodeHostIPs` ordering behavior.]
- **[other, ~55]** `NodeEligible()` dereferences `hs.nodeManager` with no nil guard (`proxy_health.go:180`). Currently guaranteed non-nil by construction in `newProxyServer`, so this is latent, not live — flagged only because the old code had no external dependency on the health path (per GOVERNANCE, not proposing defensive code for a currently-impossible case, just noting the new coupling).

### Most Critical Gap
The proxier can permanently lose its initial topology (zone) labels because `NodeTopologyConfig`'s handler is registered on an already-started informer with no synchronization and no priming — a composition failure in the seam between `NewNodeManager` (starts the informer) and `Run()` (registers the proxier). Fix the registration ordering/priming and add a mutex before merge; it is both a `-race` data race and a silent zone-routing regression.

### Positive Observations
- Consolidating `OnNodeAdd`/`OnNodeUpdate` and narrowing the proxier's interface to `NodeTopologyHandler` (only the labels it actually consumes) is a clean reduction of surface area.
- The forward-reference comment added to `CategorizeEndpoints` (`topology.go:44-48`) pointing at `NodeTopologyConfig.handleNodeEvent` is exactly the kind of coupling note that prevents future drift.
- `newNodeManager`/`newNodeTopologyConfig` expose injectable exit function, poll interval/timeout, and a completion callback for deterministic tests — good testability seams.

```json-findings
[
  {"severity":"High","confidence":85,"category":"edge-case","file":"cmd/kube-proxy/app/server.go","line":610,"finding":"NodeTopologyConfig registers the proxier handler on an already-started/synced shared informer (started earlier in NewNodeManager). The informer's asynchronous synthetic Add replay runs handleNodeEvent concurrently with RegisterEventHandler: (A) unsynchronized read/append of n.eventHandlers and read/write of n.topologyLabels (NodeTopologyConfig has no mutex, unlike ServiceCIDRConfig) is a data race; (B) if the Add wins the race it records topologyLabels and notifies an empty handler list, so the proxier never receives initial zone labels and runs with nil topologyLabels indefinitely, silently disabling topology-aware routing.","remediation":"Add a mutex to NodeTopologyConfig guarding eventHandlers/topologyLabels; prime newly registered handlers with current labels (mirror ServiceCIDRConfig.Run) or register handlers before the informer starts; add a regression test using the production ordering.","source":"adversarial-general"},
  {"severity":"Medium","confidence":76,"category":"edge-case","file":"pkg/proxy/config/config.go","line":288,"finding":"NodeConfig registers only UpdateFunc/DeleteFunc (no AddFunc). NodeManager seeds its baseline from a one-shot poll in NewNodeManager but the handler is registered much later in Run(); a NodeIP change occurring in that window is delivered only as the informer's synthetic Add replay, which is dropped, so OnNodeChange never fires and the change is neither detected (no restart) nor reflected in the already-computed NodeIPs.","remediation":"Register the NodeConfig handler before the informer starts, or re-check current lister state against the polled baseline at registration, or route AddFunc to handleChangeNode.","source":"adversarial-general"},
  {"severity":"Medium","confidence":80,"category":"observability","file":"pkg/proxy/node.go","line":171,"finding":"OnNodeChange/OnNodeDelete call exitFunc(1) on NodeIP change, PodCIDR change, or node deletion with only a klog line and no metric or Kubernetes Event. This is new behavior (NodeIPs were previously read once and never triggered a restart); a fleet-wide trigger would produce cluster-wide restarts with no aggregated signal, and os.Exit bypasses deferred cleanup.","remediation":"Increment a dedicated restart metric with a reason label (and emit an Event) before exiting; document the new restart triggers in the changelog.","source":"adversarial-general"},
  {"severity":"Medium","confidence":80,"category":"test-gap","file":"pkg/proxy/config/config_test.go","line":718,"finding":"TestNewNodeTopologyConfig registers the event handler before sharedInformers.Start(), the opposite of production ordering (informer started/synced in NewNodeManager, then handler registered in Run). The test therefore never exercises the data race or the lost-initial-label race and gives false confidence in the topology path.","remediation":"Add a test variant that starts and syncs the informer first, then registers the handler, asserting the handler still receives the current zone label exactly once.","source":"adversarial-general"},
  {"severity":"Medium","confidence":78,"category":"other","file":"pkg/proxy/healthcheck/proxy_health.go","line":180,"finding":"NodeEligible() switched from an RLock + cached bool to a write Lock plus hs.nodeManager.Node(), which deep-copies the entire Node object on every health/liveness probe, though only DeletionTimestamp and Taints are read. Node objects can be large (status.images, labels), making this wasteful allocation on a hot path and serializing probes against Health().","remediation":"Add a NodeManager accessor returning eligibility (or only the needed fields) without a full deep-copy, and keep the health read on RLock.","source":"adversarial-general"},
  {"severity":"Low","confidence":80,"category":"docs","file":"pkg/proxy/node.go","line":119,"finding":"Doc comments on NodeIPs() and PodCIDRs() say values are 'polled in NewNodeManager()', but OnNodeChange overwrites n.node on every event, so they return the current node's values, not the initial poll. The NodeManager type comment is also a broken run-on sentence.","remediation":"Reword to 'returns the current node's NodeIPs/PodCIDRs' and fix the type doc.","source":"adversarial-general"},
  {"severity":"Low","confidence":78,"category":"other","file":"pkg/proxy/config/config.go","line":320,"finding":"handleChangeNode contains a DeletedFinalStateUnknown tombstone branch, but it is wired only to UpdateFunc where newObj is always a *v1.Node; the branch is unreachable dead code copy-pasted from handleDeleteNode and misrepresents the handler's event routing.","remediation":"Remove the tombstone branch from handleChangeNode.","source":"adversarial-general"}
]
```
