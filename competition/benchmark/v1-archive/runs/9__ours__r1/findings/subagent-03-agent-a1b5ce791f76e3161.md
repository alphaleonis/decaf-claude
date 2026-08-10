# subagent agent-a1b5ce791f76e3161

# Sibling-Consistency Review — kubernetes/kubernetes PR #130837

**Scope**: `OnTopologyChange` re-implementation across iptables/ipvs/nftables/winkernel/metaproxier, plus the `OnNodeAdd+OnNodeUpdate → OnNodeChange` merge in `pkg/proxy/config/config.go` and its tombstone handling.

## Sibling Census

- **`OnTopologyChange` doc-comment wording**: `pkg/proxy/iptables/proxier.go:625`, `pkg/proxy/ipvs/proxier.go:852`, `pkg/proxy/nftables/proxier.go:843` — all three carry the **identical** sentence: `"OnTopologyChange is called whenever this node's proxy relevant topology-related labels change."` This is the established 3-way convention.
- **Informer-handler wiring** (`pkg/proxy/config/config.go`): `NewServiceConfig` (174-191), `NewEndpointSliceConfig` (80-97), `NewServiceCIDRConfig` (376-400) each wire `AddFunc` + `UpdateFunc` + `DeleteFunc`.
- **Tombstone (`cache.DeletedFinalStateUnknown`) handling placement**: `handleDeleteService` (241-258), `handleDeleteEndpointSlice` (147-164), and `NodeConfig.handleDeleteNode` (339-356) all place the tombstone fallback only in the *Delete* handler. The matching Add/Update handlers — `handleAddService`/`handleUpdateService` (212-239), `handleAddEndpointSlice`/`handleUpdateEndpointSlice` (118-145) — do a plain type assertion with no tombstone fallback.
- `needFullSync`: present in `iptables`/`nftables` Proxier structs, entirely absent from `ipvs/proxier.go` (`grep -c needFullSync` → 0 occurrences anywhere in the file) — this is a pre-existing architectural difference (ipvs never had the incremental-full-sync concept), not something introduced by this PR.

## Findings

```json
[
  {
    "file": "pkg/proxy/config/config.go",
    "line": 288,
    "severity": "High",
    "category": "design",
    "issue": "[CONS_SYMMETRY] NewNodeConfig's cache.ResourceEventHandlerFuncs wires only UpdateFunc and DeleteFunc, omitting AddFunc entirely; every sibling Config type in this file wires all three (NewServiceConfig config.go:181-183, NewEndpointSliceConfig config.go:87-89, NewServiceCIDRConfig config.go:384-390). Because ResourceEventHandlerFuncs.OnAdd is a no-op when AddFunc is nil (staging/src/k8s.io/client-go/tools/cache/controller.go:257-261), any Add event delivered to a NodeConfig-registered handler — including the initial replay of the already-cached Node when NodeConfig.Run() attaches its handler after NodeManager's informer has already synced — is silently dropped and never reaches OnNodeChange. This directly contradicts the NodeHandler.OnNodeChange doc comment ('is called whenever creation or modification of node object is observed', config.go:263-265) and the commit's own stated intent to merge Add+Update handling rather than drop Add.",
    "fix": "Add `AddFunc: func(obj interface{}) { result.handleChangeNode(obj) }` to the ResourceEventHandlerFuncs in NewNodeConfig, matching the Add+Update+Delete wiring every sibling Config uses.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 320,
    "severity": "Medium",
    "category": "design",
    "issue": "[CONS_SYMMETRY] handleChangeNode (the merged Add+Update handler) contains a DeletedFinalStateUnknown tombstone fallback (config.go:323-331), but every sibling Add/Update handler in this file — handleAddService/handleUpdateService (config.go:212-239) and handleAddEndpointSlice/handleUpdateEndpointSlice (config.go:118-145) — does a plain type assertion with no tombstone branch. Across this codebase (and in NodeConfig's own handleDeleteNode, config.go:339-356), the tombstone fallback is reserved for Delete handlers, since client-go only ever delivers DeletedFinalStateUnknown on delete deltas; an Update callback's newObj is never a tombstone. The branch appears to have been carried over from handleDeleteNode when Add+Update were merged, producing an unreachable code path that diverges from how every other handler in the file is written.",
    "fix": "Drop the tombstone fallback from handleChangeNode and use a plain `node, ok := obj.(*v1.Node)` assertion (mirroring handleAddService/handleUpdateService), keeping the tombstone handling exclusively in handleDeleteNode.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/winkernel/proxier.go",
    "line": 1098,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_COMMENT] The TODO names the method 'OnTopologyChanged' ('TODO(imroc): implement OnTopologyChanged for winkernel proxier.') but the method it sits directly above is OnTopologyChange (winkernel/proxier.go:1103) — no trailing 'd'. The comment misnames the identifier it documents.",
    "fix": "Fix the TODO to say 'OnTopologyChange' to match the actual method name.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/winkernel/proxier.go",
    "line": 1099,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_COMMENT] winkernel's OnTopologyChange doc reads 'OnTopologyChange is called whenever node topology labels are changed.' — this diverges in wording from the identical sentence used by all three other real implementations: iptables/proxier.go:625, ipvs/proxier.go:852, nftables/proxier.go:843 ('OnTopologyChange is called whenever this node's proxy relevant topology-related labels change.').",
    "fix": "Reuse the established sentence from iptables/ipvs/nftables verbatim for consistency (adjusting only the no-op caveat that follows).",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/metaproxier/meta_proxier.go",
    "line": 131,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_COMMENT] metaProxier's OnTopologyChange doc reads 'OnTopologyChange is called whenever change in proxy relevant topology labels is observed.' — different phrasing from the identical convention shared by iptables/proxier.go:625, ipvs/proxier.go:852, and nftables/proxier.go:843 ('OnTopologyChange is called whenever this node's proxy relevant topology-related labels change.').",
    "fix": "Align the wording with the iptables/ipvs/nftables convention (or leave it, but note it's the third distinct phrasing among five implementers for the same method).",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`needFullSync` absent from `ipvs.OnTopologyChange`**: confirmed pre-existing — `ipvs/proxier.go` has zero occurrences of `needFullSync` anywhere in the file (it's an iptables/nftables-only incremental-sync concept); ipvs's old `OnNodeAdd`/`OnNodeUpdate` never set it either. Not a deviation introduced by this diff.
- **`topologyLabels` vs. old `nodeLabels` naming**: renamed uniformly and consistently across iptables, ipvs, nftables, `topology.go`'s `CategorizeEndpoints` parameter, and the config-layer type — no drift.
- **Interface doc-comment wording** (`NodeTopologyHandler.OnTopologyChange`, config.go:459-461) vs. the three matching implementers' identical wording: they don't match each other verbatim, but that's normal Go practice (interface doc vs. implementer doc commonly diverge) and not itself inconsistent — the real, flaggable convention is the 3-way agreement among the concrete implementers, which is what's cited above.
- **metaProxier's `OnTopologyChange` fan-out** (ipv4Proxier then ipv6Proxier, no switch/case): matches the exact fan-out pattern of every other simple (non-address-family-specific) handler in the same file — `OnServiceAdd`/`OnServiceUpdate`/`OnServiceDelete`/`OnServiceSynced`/`OnEndpointSlicesSynced`/`OnServiceCIDRsChanged` (meta_proxier.go:58-83, 124-142) — all call ipv4 then ipv6 with no extra locking. No deviation.
- **No `NoopNodeTopologyHandler` replacement for the removed `NoopNodeHandler`**: winkernel and `hollow_proxy.go`'s `FakeProxier` both implement `OnTopologyChange` as a direct empty method rather than embedding a shared no-op type. There's no sibling "Noop" type left anywhere in the package to compare against (the only prior one, `NoopNodeHandler`, was deleted in this same PR), so this is first-of-kind — not flaggable as drift.
- **`v1.LabelTopologyZone` literal duplication**: searched for a hardcoded `"topology.kubernetes.io/zone"` string anywhere in `pkg/proxy/` — none found; every reference (`config.go` handleNodeEvent, `topology.go`) uses the symbolic constant. No duplicated literal.
- **Double space typo in `topology.go`'s new comment** ("modify the logic over here to  watch") — a plain typo, not a sibling-comparison finding (no convention source to quote); belongs to quick-reviewer if flagged at all.

## Probe Requests

- **Test**: none currently exists exercising `NewNodeConfig`'s actual informer wiring end-to-end (unlike `TestNewNodeTopologyConfig` in `pkg/proxy/config/config_test.go:214-324`, which uses a `fakeWatch` + `nodeInformer` to prove Add/Update dispatch). A new test — a `nodeHandlerMock` implementing `config.NodeHandler`, registered via `config.NewNodeConfig(...).RegisterEventHandler(...)`, then `fakeWatch.Add(&v1.Node{...})` — would concretely demonstrate finding #1 (`OnNodeChange` is never invoked for a fresh Add, only for Update/Delete). This requires adding to `pkg/proxy/config/config_test.go`, which is why it's nominated here rather than written directly.
