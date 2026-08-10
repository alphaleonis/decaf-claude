# Benchmark run: 9__pr-review-toolkit__r1

| field | value |
|---|---|
| tool | pr-review-toolkit |
| subject | 9 (go / large) — kubernetes/kubernetes#130837 |
| review diff | `0872760763d5877707b018a4eea870d1fc02e6a4^1..0872760763d5877707b018a4eea870d1fc02e6a4` (merge 0872760763d5877707b018a4eea870d1fc02e6a4) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 682 |
| longest single subagent (s) | 496 |
| duration_ms (orchestrator self) | 139959 |
| duration_api_ms (summed parallel API time, not wall) | 1882361 |
| num_turns | 1 |
| cost_usd | 9.25743975 |
| input_tokens | 2 |
| output_tokens | 12636 |
| cache_creation_tokens | 3875 |
| cache_read_tokens | 81666 |
| total_tokens (orchestrator only) | 98179 |
| **subagents** | 5 |
| **ws output_tokens** | 19856 |
| ws input_tokens | 89 |
| ws cache_creation | 635739 |
| ws cache_read | 3177252 |
| ws total_tokens | 3832936 |
| session_id | e8114b18-9e57-41f9-a408-abc69bf50da3 |
| findings (raw lines) | 173 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (682s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a65e1c4201cd79e1b | 17 | 395919 | 279 |
| agent-acc4816d5f3a55d7c | 32 | 883716 | 361 |
| agent-adec4c2f957ece7b7 | 22 | 524539 | 275 |
| agent-ae86c8bb9aaa387e7 | 130 | 1074142 | 496 |
| agent-af1254d2c88bc2cfb | 27 | 361329 | 228 |

## Findings (final result text)

```
All five pr-review-toolkit agents have completed. Nothing was posted anywhere — this is a read-only review of PR #130837's diff plus the merged working-tree source. Below is each agent's complete findings.

---

# PR #130837 Review — "Kube proxy node manager" (Daman Arora)

/kind cleanup · MERGED · 18 files · +757 / −803 · base `master`, head `kube-proxy-node-manager`

**Convergent headline finding (flagged independently by 4 of 5 agents):** the node informer is now started inside `NewNodeManager` (`pkg/proxy/node.go:76`) **before** the proxier's topology handler is registered (`cmd/kube-proxy/app/server.go:610-611`). This is both a **data race** on `NodeTopologyConfig.eventHandlers`/`topologyLabels` and a **latent correctness bug**: the replayed synthetic ADD can be processed with zero handlers registered, recording the zone into `topologyLabels`, after which the `reflect.DeepEqual` dedup (`config.go:528`) permanently suppresses re-delivery — leaving the proxier with `nil` topology labels and topology-aware routing silently disabled for the life of the process. The PR removed the very comment that used to enforce "register handlers before starting the informer."

---

## 1. code-reviewer

**Important (confidence 85) — Node informer started before its event handlers are registered → data race on `NodeTopologyConfig.eventHandlers` + possible permanent loss of the proxier's initial topology labels**
- Primary: `cmd/kube-proxy/app/server.go:607-614` combined with `pkg/proxy/node.go:76` and `pkg/proxy/config/config.go:485-506, 508-511, 515-537`.
- `NewNodeManager` eagerly calls `thisNodeInformerFactory.Start(wait.NeverStop)` (`node.go:76`) and blocks until synced. Much later in `ProxyServer.Run`, handlers are attached to that already-running informer: `NewNodeTopologyConfig(...)` then `nodeTopologyConfig.RegisterEventHandler(s.Proxier)` (`server.go:610-611`).
- Because the informer is already synced, `AddEventHandlerWithResyncPeriod` schedules an async replay of the cached node as a synthetic ADD, delivered by the processor goroutine concurrently with the following `RegisterEventHandler`. `NodeTopologyConfig` has no mutex: `handleNodeEvent` does `for i := range n.eventHandlers` (`config.go:533`) while `RegisterEventHandler` does `n.eventHandlers = append(...)` (`config.go:510`) — a data race under the Go memory model (would trip `go test -race`). Same for unsynchronized `n.topologyLabels`.
- Correctness: if the replayed ADD runs before the proxier is appended, `handleNodeEvent` sets `topologyLabels={zone:X}` but notifies zero handlers; every later update recomputes the same map and is filtered by the `DeepEqual` guard (`config.go:528`), so `OnTopologyChange` is *never* called — `proxier.topologyLabels` stays `nil`, disabling zone hints / `PreferClose`.
- Violates an invariant documented twice in the same function: `server.go:578-581` ("the initial update … may be lost if no handlers are registered yet") and `server.go:601-602`. The old code started the node informer *after* handler registration; this PR inverted it.
- Usually not observed because the slice-append almost always wins the race, and `TestNewNodeTopologyConfig` registers its handler *before* `sharedInformers.Start`, never exercising production ordering.
- **Fix:** register downstream handlers before the informer delivers to them — add a mutex guarding `eventHandlers`/`topologyLabels`, and/or restore the documented ordering (defer `factory.Start()` until after `RegisterEventHandler`, or attach the `NodeConfig`/`NodeTopologyConfig` handlers inside `NewNodeManager` before `Start`).

**Additional observations (below the reporting bar):**
- **A. `newNodeManager` can return `(nil, nil)` if the parent ctx is already canceled at startup (~65)** — `pkg/proxy/node.go:87-109`. Relies on "`pollErr != nil` ⇒ `err != nil`"; if `ctx` is canceled before the first condition eval, poll returns the ctx error while captured `err` is still `nil` → `(nil, nil)`, and caller derefs `s.NodeManager.NodeIPs()` (`server.go:211-217`) → nil panic. Realistically unreachable; a defensive `if pollErr != nil { if err == nil { err = pollErr }; return nil, err }` removes it.
- **B. Dead/misleading tombstone handling in `handleChangeNode` (~55)** — `pkg/proxy/config/config.go:320-337`. Wired only to `UpdateFunc` (`config.go:290`) yet handles `cache.DeletedFinalStateUnknown` (only delivered to `DeleteFunc`) — unreachable branch; doc comment ("creation or modification") no longer matches (ADD is intentionally not handled). Trim the branch and fix the comment.
- **C. `NodeEligible()` takes the write lock and hard-depends on non-nil `nodeManager` (~50)** — `pkg/proxy/healthcheck/proxy_health.go:176-190`. Acquires `hs.lock.Lock()` (was `RLock`) but reads none of `hs`'s guarded fields (only `hs.nodeManager.Node()`, independently locked) — superfluous; also panics if `nodeManager` is nil (safe today, more fragile than the old self-contained `nodeEligible` bool).

**Explicitly checked and OK:** proxier `topologyLabels` reads in `syncProxyRules` are under `proxier.mu` (iptables `proxier.go:736,938`) with map-replace (not mutate); `NodeManager.node` consistently guarded by `n.mu`, `Node()` deep-copies, handlers serialized by the informer's single goroutine; dropping `AddFunc` from `NodeConfig` is correct (initial state from poll); hollow-proxy path safe (nil `NodeManager`, guarded block, no health server); zone-only filtering matches the only label `CategorizeEndpoints` consumes (`topology.go:58`).

---

## 2. silent-failure-hunter

**Finding 1 — MEDIUM — `OnNodeChange` logs the NodeIP lookup failure and returns *after* already overwriting the tracked node → stale/degraded state behind a log line**
- `pkg/proxy/node.go:145` and `:159-163`. `n.node = node` (line 145) runs *before* validating; if the new node has no usable host IP, `GetNodeHostIPs` fails and the handler logs + `return`s, skipping the NodeIP-change/`exitFunc(1)` logic (lines 167-172). `NodeManager` now holds an IP-less node; `NodeIPs()` returns `nil`; kube-proxy neither restarts nor reverts to the last-good node.
- Masks: node genuinely losing its usable host IP (addresses cleared / only invalid addresses remain). Collapses all `GetNodeHostIPs` errors into one silent log-and-continue.
- **Fix:** validate before mutating shared state — compute `nodeIPs` from the incoming node first; on error, log and return *without* replacing `n.node` (preserve last-good), or treat unresolvable IPs as restart-worthy. At minimum move `n.node = node` to after IP validation.

**Finding 2 — MEDIUM — `newNodeManager` discards the poll's own timeout/context error and returns a side-channel `err`; a `(nil, nil)` return would nil-panic the caller**
- `pkg/proxy/node.go:87-109` (esp. `:107-108`); caller `cmd/kube-proxy/app/server.go:217`. The poll condition always returns `(false, nil)` on failure, stashing the reason in an outer `err`; on timeout the function returns that side-channel value, discarding `pollErr`.
- (1) Diagnostic loss: `context deadline exceeded` after the 5-min wait is thrown away; the old `waitForPodCIDR` produced an explicit "timeout waiting for PodCIDR allocation…" message. (2) Fragile `(nil, nil)`: guarantee depends on "every `return false, nil` first sets `err`"; any future forgetful early-return makes it return `(nil, nil)` and the caller nil-derefs `NodeIPs()` at `server.go:217`.
- **Fix:** `if pollErr != nil { return nil, fmt.Errorf("timed out waiting for node %q: %w (last error: %v)", nodeName, pollErr, err) }`; never return `(nil, nil)`. Prefer carrying the error through the poll condition rather than a captured outer variable.

**Finding 3 — LOW–MEDIUM — Ignored `GetNodeHostIPs` errors via `_`**
- `pkg/proxy/node.go:143` (`oldNodeIPs, _ := ...`) and `:123` (`NodeIPs()`). Line 143: if the previously-tracked node ever lacked resolvable IPs, `oldNodeIPs` silently becomes `nil`, so a later valid node diffs as a change and triggers a spurious `exitFunc(1)` with invisible root cause. Line 123: `NodeIPs()` can't distinguish "no IPs" from "lookup failed" — both `nil`.
- **Fix:** handle the error explicitly (log with context or propagate); for `NodeIPs()` return `([]net.IP, error)` or log on failure.

**Finding 4 — LOW–MEDIUM — `NodeTopologyConfig` has an empty `DeleteFunc`; node-delete signal silently dropped, leaving zone routing stale**
- `pkg/proxy/config/config.go:499` (`DeleteFunc: func(_ interface{}) {}`). On node deletion the proxier's `topologyLabels` (and zone categorization in `CategorizeEndpoints`) is never cleared. Masked today only because the sibling `NodeManager.OnNodeDelete` (`node.go:176-180`) calls `exitFunc(1)` — but the two handlers are independent with no ordering guarantee; if exit-on-delete is softened or the topology event is delivered first, the proxier routes on a deleted node's stale zone label with no signal.
- **Fix:** clear topology labels and notify handlers on delete (mirror Add/Update), or at minimum comment the intentional reliance on `OnNodeDelete` exiting.

**Finding 5 — LOW–MEDIUM — `NodeEligible()` unconditionally derefs `hs.nodeManager` (new nil-deref landmine; old code was nil-safe)**
- `pkg/proxy/healthcheck/proxy_health.go:180`. The old self-contained `nodeEligible bool` defaulted to `true` (always safe); now `Node()` is pulled live with no nil check and the constructor accepts a nil `*proxy.NodeManager`. Not reachable today (sole caller `server.go:244` passes non-nil; hollow-proxy leaves `HealthzServer` nil, guarded at `server.go:437`).
- **Fix:** `if hs.nodeManager == nil { return true }`, or reject nil in the constructor.

**Finding 6 — LOW — `NewNodeConfig` drops `AddFunc`; initial "Add" silently not delivered to `OnNodeChange`; `handleChangeNode` carries an unreachable tombstone branch**
- `pkg/proxy/config/config.go:288-294` and `:320-337`. Handlers attach to an already-synced informer, so client-go replays the node as an ADD — dropped. Baseline is instead captured out-of-band by the `NewNodeManager` poll: works, but an undocumented load-bearing coupling. The tombstone branch is dead on the update path.
- **Fix:** comment that Add is intentionally omitted (baseline from `NewNodeManager`); drop the unreachable tombstone branch.

**Verified non-issues:** zone-only filtering is sound — `CategorizeEndpoints`/`topologyModeFromHints`/`availableForTopology` read only `topologyLabels[v1.LabelTopologyZone]` (`topology.go:58`), sole writer `config.go:524`; `nodeTopologyConfig` never `.Run()` is fine (no `Run`/`OnSynced`); `OnNodeDelete` exiting is intentional loudness; `OnNodeChange` continuing past the PodCIDR `exitFunc(1)` (no `return`, `node.go:155`) is correct today (relies on `os.Exit` never returning) but worth a one-line comment.

---

## 3. pr-test-analyzer

Overall the new code is reasonably well covered (`NewNodeManager` polling, `OnNodeChange` IP/PodCIDR restart, `OnNodeDelete`, `NodeTopologyConfig` zone-filtering), and the deleted tests (`Test_getNodeIPs`, `Test_waitForPodCIDR`, `TestProxyServer_platformSetup`) tracked deleted production functions, so those removals are justified. Gaps concentrate in the config dispatch seam, concurrency, and weak negative assertions. Note: every exit test injects a fake `exitFunc` that *returns*, whereas prod `os.Exit` doesn't — so post-`exitFunc(1)` code runs in tests but is dead in prod.

**Gap A — severity 7 — `NodeConfig.handleChangeNode` / `handleDeleteNode` completely untested**
- `pkg/proxy/config/config.go:320-356`. `config_test.go` has no reference to `NodeConfig`/`NewNodeConfig`/`handleChangeNode`/`handleDeleteNode`/`OnNodeChange` (grep-verified). All `NodeManager` tests call `OnNodeChange`/`OnNodeDelete` directly, bypassing the config layer that wires the informer in production (`server.go:603` region). Sub-issues: unreachable tombstone branch at `config.go:323-331` (registered only as `UpdateFunc` at `:290`); `!ok` error paths (`:325,329,344,349`) untested.
- **Test:** build `NodeConfig` over a fake informer + recording `NodeHandler` mock; drive `fakeWatch.Modify/Delete`; feed `DeletedFinalStateUnknown{Obj: node}` through the delete path and a garbage-typed object through the error path.

**Gap B — severity 6 — No concurrency test for `NodeManager`'s shared `node`**
- `pkg/proxy/node.go:44-51,140-190`. `node` is written by the informer goroutine (`OnNodeChange`) and read concurrently from the healthz handler via `NodeEligible()`→`Node()` (`proxy_health.go:180`) and `NodeIPs()`/`PodCIDRs()`. The mutex + `Node()` deep copy exist precisely for this, yet no `-race` test runs `OnNodeChange` concurrently with the readers. A dropped lock or shared-pointer return passes every current test.
- **Test:** N goroutines `OnNodeChange` vs M goroutines `Node()`/`NodeIPs()`/`NodeEligible()` under `-race`.

**Gap C — severity 6 — Weak negative assertions in `TestNewNodeTopologyConfig` (false-positive risk)**
- `pkg/proxy/config/config_test.go:464-596`. The mock (`nodeTopologyHandlerMock`, `:464-470`) records only the *last* map, not a call count. So "no notification" cases can't detect a spurious call whose payload equals prior state: `:525/:540` (`require.Empty`) still pass if code erroneously calls `OnTopologyChange(emptyMap)`; `:595` (`require.Len(...,1)`, no value assertion) is trivially true whether or not a spurious same-map notification fired.
- **Fix:** add `invocationCount` to the mock; assert it's unchanged across each no-op and +1 on each real change.

**Gap D — severity 6 — `OnNodeChange` "node loses all NodeIPs" path untested**
- `pkg/proxy/node.go:159-172`. If the updated node has no usable addresses, `GetNodeHostIPs` errors and the function returns early *without* `exitFunc` (`:160-163`) — a node going from "has IP" → "no IP" silently doesn't restart kube-proxy. `TestNodeManagerOnNodeChange` (`node_test.go:231-294`) only supplies non-empty `updatedNodeIPs`.
- **Test:** `initialNodeIPs:["192.168.1.1"]`, `updatedNodeIPs:[]`; assert intended behavior (documents the decision, may surface a bug).

**Gap E — severity 5 — Zone-label *removal* untested in `NodeTopologyConfig`**
- `pkg/proxy/config/config.go:515-537`. Tests only add/change the zone label, never remove it (node had `LabelTopologyZone`, then loses it → empty map, proxier notified to drop zone routing). **Test:** after establishing a zone, `Add` a node with the label removed; assert notification with empty map (needs the Gap C call-count mock).

**Gap F — severity 5 — Healthcheck tests wire the real `os.Exit` into `NodeManager`**
- `pkg/proxy/healthcheck/healthcheck_test.go:481,561`. Built via public `proxy.NewNodeManager(...)`, which hardcodes `os.Exit` (`node.go:60`). Safe today only because `makeNode()` always yields the same IP `192.168.0.1` and the tweaks don't change it. A latent landmine: any future tweak changing the node IP into one of these `OnNodeChange` calls will `os.Exit(1)` mid-test. **Fix:** expose an internal constructor accepting `exitFunc` (like `newNodeManager`) so tests inject a no-op.

**Gap G — severity 4 — `watchPodCIDRs=false` + PodCIDR change (must NOT exit) untested**
- `pkg/proxy/node.go:150-157`. No case with `watchPodCIDRs:false` and differing PodCIDRs. **Test:** `watchPodCIDRs:false`, `initialPodCIDRs:["10.0.0.0/8"]`, `updatedPodCIDRs:["172.16.0.0/12"]`, same NodeIPs → `expectedExitCode:nil`.

**Gap H — severity 4 — Lost adversarial cases from deleted server tests not carried into `TestNewNodeManager`**
- Deleted `Test_getNodeIPs` covered a malformed address (`"invalid-ip"`); deleted `Test_waitForPodCIDR` covered a delete event during the wait. `GetNodeHostIPs` silently skips unparseable addresses, so a node whose only address is malformed behaves like "no IP." `TestNewNodeManager` (`node_test.go:74-229`) never supplies a malformed address. **Test:** a case with a single invalid `NodeInternalIP` then later a valid one; assert the poll waits.

**Test-quality issues:** non-counting topology mock (root cause of Gap C weak negatives); `TestNodeManagerNode` (`node_test.go:311-327`) never mutates the returned `*v1.Node` to confirm `Node()` (`node.go:186-190`) returns an isolated copy — a regression to returning `n.node` directly would pass; direct-call tests bypass the informer→`NodeConfig`→`NodeManager` wiring.

**Positives:** `TestNewNodeManager` is thorough on the startup poll (node-absent / no-IP / IP-after-delay × all `watchPodCIDRs` permutations); `TestNewNodeTopologyConfig` uses a per-event callback to avoid sleep-flakiness and asserts exact zone values on positives; `OnTopologyChange` consumption covered from the other side by `TestCategorizeEndpoints` (`topology_test.go:48+`); no proxier-level node-handler tests were deleted (none existed); `TestHealthzServer`/`TestLivezServer` drive real 200/503 HTTP through `OnNodeChange` for tainted/`ToBeDeletedTaint`/deleted nodes.

---

## 4. comment-analyzer

New exported symbols in `node.go`/`config.go` are all documented (no Go doc-comment omissions); the proxier `OnTopologyChange` comments are accurate. Issues are comment-vs-code mismatches, copy-paste carryovers, and stale pre-existing comments.

**Critical (factually incorrect / misleading):**

**1. `pkg/proxy/config/config.go:513-514` — `handleNodeEvent` doc claims to handle Delete, but Delete is a no-op.** `NewNodeTopologyConfig` (`:485-502`) wires only `AddFunc`/`UpdateFunc` to `handleNodeEvent`; `DeleteFunc` is `func(_ interface{}) {}`. Wording is copy-pasted from `ServiceCIDRConfig.handleServiceCIDREvent` (`:417`), which does handle all three. → "handle Add and Update events … Node deletions are ignored, since a deleted node's topology labels are no longer relevant."

**2. `pkg/proxy/config/config.go:263-264` and `pkg/proxy/node.go:139` — docs claim `OnNodeChange` fires on node *creation*, but `NodeConfig` registers no `AddFunc`.** `NewNodeConfig` (`config.go:288-294`) registers only `UpdateFunc`/`DeleteFunc`; the informer replays the pre-existing node as an ADD, which is dropped, so `OnNodeChange` is not invoked for creation. [Inference] Either stale comment (creation intentionally dropped, initial state from the `NewNodeManager` poll) or a missing `AddFunc` — worth author confirmation, then align comments.

**3. `pkg/proxy/node.go:182` — `OnNodeSynced` comment says "all pre-existing Nodes have been reported," which the wiring contradicts.** The informer is field-selected to a single node (`metadata.name == nodeName`), so "Nodes" (plural) is misleading; and with no `AddFunc`, pre-existing nodes are precisely *not* reported before `OnNodeSynced` runs. → "OnNodeSynced is called once the node informer cache has synced."

**Improvement opportunities:**

**4. `pkg/proxy/node.go:41-43` — `NodeManager` type doc is a run-on and omits the delete-triggered exit.** "...based on the NodeIPs and PodCIDRs handles node watch events..." lacks a sentence break; `OnNodeDelete` (`:176`) calls `exitFunc(1)` unconditionally, not mentioned. → rewrite naming all exit triggers (NodeIP change, delete, PodCIDR change when `watchPodCIDRs`).

**5. `pkg/proxy/node.go:119` and `:127` — `NodeIPs()`/`PodCIDRs()` docs say the value was "polled in NewNodeManager()", but the methods return the *current* node's data.** Both read `n.node`, which `OnNodeChange` reassigns (`:145`). Literally inaccurate before the process exits (e.g. tests with a no-op exit). → "returns the host IPs / PodCIDRs of the current node object."

**6. `pkg/proxy/healthcheck/proxy_health.go:62-66` — `ProxyHealthServer` doc item 3 ("sync node status") describes the removed push model.** The PR deleted `SyncNode`; eligibility is now computed on demand via `NodeEligible()` reading `hs.nodeManager.Node()` (`:176-190`). → "report an unhealthy /healthz response when the node is marked for deletion by the autoscaler or has been deleted (determined from the NodeManager)."

**7. `pkg/proxy/topology.go:45-48` — new cross-reference note has a typo and garbled wording.** The `NodeTopologyConfig.handleNodeEvent` reference is valuable, but "to  watch" has a double space and "watch other endpoint types or labels" is confusing (`CategorizeEndpoints` consumes node topology labels, doesn't "watch"). → "If you change this function to consume node topology labels other than the zone label, update the filtering in NodeTopologyConfig.handleNodeEvent accordingly."

**8. `pkg/proxy/winkernel/proxier.go:1098-1103` — TODO names a method that doesn't exist, and the doc describes behavior for a no-op body.** TODO says `OnTopologyChanged` but the method is `OnTopologyChange`; the descriptive lines assert active behavior ("is called whenever… this guarantees…") while the body is `{}`, and the TODO is the leading godoc line for an unimplemented stub. → "OnTopologyChange is a no-op on the winkernel proxier. TODO(imroc): implement topology-aware routing for winkernel."

**Stale (pre-existing, worsened by this PR):**

**9. `pkg/proxy/config/config.go:274-275` — `NodeConfig` struct comment describes a channel-based design that doesn't exist and references a removed "add" operation.** "accepts 'set', 'add' and 'remove' operations of node via channels" — `NodeConfig` is informer-driven, not channel-driven (already inaccurate pre-PR), and the PR removed the `AddFunc`/`handleAddNode` path. → "NodeConfig watches the node object for changes and invokes registered NodeHandlers on update and delete."

**Positives:** iptables/ipvs/nftables/metaproxier `OnTopologyChange` docs are accurate; all new exported symbols carry doc comments (minor: `ProxyServer.NodeManager` at `server.go:176` lacks one, but so do sibling exported fields — consistent with local convention); `newNodeTopologyConfig`'s test-only `callback` param is documented; the `CurrentTime`/`LastUpdated` backward-compat comments remain accurate. (Flagged for awareness: findings 2/3 hinge on the missing `AddFunc` — a behavioral gap if initial delivery was intended; `handleChangeNode` tombstone branch is unreachable.)

---

## 5. type-design-analyzer

The PR splits the old "node handler" concept into a lifecycle owner (`NodeManager`) and a topology-label fan-out (`NodeTopologyConfig`/`NodeTopologyHandler`), narrowing each proxier's interface. Direction is good; debt concentrates in `NodeTopologyConfig`'s construction-time invariants.

**`NodeManager` (`pkg/proxy/node.go:44-190`)** — Encapsulation 7/10, Invariant Expression 6/10, Usefulness 8/10, Enforcement 7/10.
- Fields private + lock-guarded; `Node()` deep-copies (`:186-190`). Two leaks: `NodeInformer()` (`:135-137`) hands out the raw shared informer; `PodCIDRs()` (`:128-132`) returns `n.node.Spec.PodCIDRs` directly (aliases the informer-cache slice), whereas `NodeIPs()` builds a fresh slice and `Node()` deep-copies — inconsistent defensive-copy story, safe only by the unstated "informer objects are read-only" assumption.
- "Immutable node identity, else crash" is expressed only via imperative `reflect.DeepEqual`+`exitFunc` blocks (`:150-172`), not the type shape; doc (`:41-43`) omits the type's role as live-node source for the health server.
- Genuinely replaces `getNodeIPs` + `waitForPodCIDR` + `NodePodCIDRHandler` + eligibility plumbing with one cohesive owner; construction blocks until valid (removes a class of "node not ready" bugs).
- **Recs:** `slices.Clone` in `PodCIDRs()` for parity; add `return` after each `exitFunc(1)` in `OnNodeChange` so test/prod flow agree; expand the doc to name the health-server-provider role.

**`NodeTopologyConfig` + `NodeTopologyHandler` (`pkg/proxy/config/config.go:456-537`)** — Encapsulation 6/10, Invariant Expression 5/10, Usefulness 8/10, **Enforcement 3/10** (the weak point).
- **Primary — initial-topology delivery race / no sync barrier:** the informer is started in `newNodeManager` (`node.go:76-79`) before the proxier handler is registered (`server.go:610-611`); the synthetic ADD can be consumed with zero handlers, recording the zone into `n.topologyLabels` (`config.go:532`) and permanently deduping it (`:528`), leaving the proxier with empty labels until the next real zone change (which may never come) → topology routing silently disabled. The PR *removed* the old comment that enforced "start the node informer after handler registration," inverting the ordering. No `Run()`/`WaitForNamedCacheSync`/`OnTopologySynced` barrier before `SyncLoop()` (`server.go:619`).
- **Dead state:** `listerSynced cache.InformerSynced` (`:466`) is written (`:503`) but never read — the type imitates its siblings' shape without a `Run()`, falsely implying a sync barrier.
- **Implicit contract:** `handleNodeEvent` dispatches the retained `n.topologyLabels` map to every handler (`:535`); cross-goroutine sharing is safe only by an unenforced never-mutate-after-publish rule — a future in-place `n.topologyLabels[k]=v` would race every proxier's read with no compiler complaint.
- Secondary: `DeleteFunc` no-op (`:499`) means topology is never cleared on delete — correct today only because `NodeManager.OnNodeDelete` crashes first (implicit cross-type dependency).
- **Recs:** register the handler before starting the informer, or add `Run(stopCh)` that waits on `listerSynced` and seeds current labels into new handlers (also gives the field a purpose); else delete `listerSynced`; document the copy-on-write map ownership or clone per handler.

**`NodeHandler` + `NodeConfig` (`config.go:260-356`)** — Encapsulation 8/10, Expression 7/10, Usefulness 7/10, Enforcement 6/10. Collapsing `OnNodeAdd`+`OnNodeUpdate` into `OnNodeChange` is sound (every impl treated them identically). Under-documented: `NewNodeConfig` wires no `AddFunc` (`:288-294`), silently relying on the sole consumer capturing initial state at construction — a trap for future handlers. Unreachable `DeletedFinalStateUnknown` branch in `handleChangeNode` (`:322-332`). **Recs:** comment the intentional Add omission; drop the dead branch.

**`ProxyHealthServer` (`proxy_health.go:69-189`)** — Encapsulation 6/10, Expression 7/10, Usefulness 8/10, **Enforcement 4/10.** Removing the cached `nodeEligible bool` + `SyncNode` in favor of on-demand `nodeManager.Node()` (`:176-189`) is a real invariant improvement (eliminates a divergeable optimistically-`true` flag). But it introduces concrete-type coupling (`nodeManager *proxy.NodeManager`, `:74`; new `healthcheck → proxy` import edge). **Lock-hygiene regression:** `NodeEligible()` takes `hs.lock.Lock()` (write, `:177`) but writes nothing and reads none of the fields that lock guards (`lastUpdatedMap`/`oldestPendingQueuedMap`, `:79-81`) — spurious, serializes against `Health()`/`Updated()`/`QueuedUpdate()`. **Recs:** depend on a one-method interface (`interface{ Node() *v1.Node }`) — also lightens the tests that now spin up a real `NewNodeManager`; remove the `hs.lock` acquisition (or downgrade to `RLock`).

**`Proxier` topology field + `Provider` interface (iptables/ipvs/nftables)** — Encapsulation 8/10, Expression 8/10, Usefulness 8/10, Enforcement 6/10. Renaming `nodeLabels` → `topologyLabels` + receiving a pre-filtered map shrinks stored state to only what `CategorizeEndpoints` consumes (the zone, `topology.go:59`), under `proxier.mu`. `Provider` now embeds `config.NodeTopologyHandler` instead of full `config.NodeHandler` (`types.go:31`) — clean interface segregation; removes ~180 lines of duplicated per-proxier node-diffing and the `NoopNodeHandler` hack. Concern: two independent sources of "current node" now exist (`NodeManager.node` and `NodeTopologyConfig.topologyLabels`), derived from the same informer via separate registrations — transiently inconsistent but feed disjoint consumers; worth a design comment. winkernel `OnTopologyChange` is an intentional no-op; iptables/nftables set `needFullSync=true` while ipvs doesn't (consistent with prior behavior, discoverable only by reading all three).

**Cross-cutting priority order:** (1) initial-topology delivery race / no sync barrier; (2) dead `listerSynced` field; (3) spurious write lock in `NodeEligible()`; (4) concrete-type coupling in `ProxyHealthServer`; (5) implicit shared-map ownership; (6) minor `NodeManager` items (`PodCIDRs()` aliasing, missing `return` after `exitFunc`, doc); (7) minor `NodeConfig` items (undocumented Add omission, dead tombstone branch).

---

## Cross-agent synthesis

**Highest-confidence, multi-agent issues** (worth acting on first):
1. **Startup-ordering race in `NodeTopologyConfig`** (`server.go:610-611` + `node.go:76`) — flagged by code-reviewer (85), type-design-analyzer (primary), silent-failure-hunter (Finding 4, related), and pr-test-analyzer (Gap C exposes why the test suite misses it). Both a `go test -race` data race and a latent "topology routing silently disabled" correctness bug.
2. **`OnNodeChange` overwrites `n.node` before validating IPs, then swallows the error** (`node.go:145,159-163`) — silent-failure-hunter Finding 1 + pr-test-analyzer Gap D (the untested branch).
3. **`newNodeManager` discards `pollErr` / fragile `(nil, nil)`** (`node.go:87-109`) — silent-failure-hunter Finding 2 + code-reviewer Obs. A.
4. **Spurious write lock + concrete-type/nil coupling in `NodeEligible()`** (`proxy_health.go:176-190`) — code-reviewer Obs. C, silent-failure-hunter Finding 5, type-design-analyzer.
5. **Missing `AddFunc` + unreachable tombstone branch + stale comments in `NodeConfig`** (`config.go:288-294,320-337`) — flagged by all five agents in some form.

**Test follow-ups that would have caught the above:** a `-race` concurrency test on `NodeManager` (Gap B), a `config_test.go` test exercising the informer→`NodeConfig` seam (Gap A), the call-counting topology mock (Gap C), and the "node loses all NodeIPs" case (Gap D).

Nothing was posted to GitHub and no files were modified.
```
