# subagent agent-a2f6954ce12de5dd5

## Sibling-Consistency Review — PR #130837 (kube-proxy node manager)

Reviewed `pkg/proxy/config/config.go`, all five `OnTopologyChange` implementations, `pkg/proxy/node.go`, and `cmd/kube-proxy/app/server.go` against their siblings.

```json
[
  {
    "file": "pkg/proxy/config/config.go",
    "line": 464,
    "severity": "Medium",
    "category": "design",
    "issue": "[CONS_SYMMETRY] NodeTopologyConfig has no Run() method and is never started with WaitForNamedCacheSync; its `listerSynced` field (config.go:466, set at config.go:503) is written but never read. Every sibling Config type — EndpointSliceConfig (config.go:104-116, invoked via `go endpointSliceConfig.Run(...)` in server.go), ServiceConfig (config.go:198-210, `go serviceConfig.Run(...)`), NodeConfig (config.go:306-318, `go nodeConfig.Run(wait.NeverStop)` in server.go:613), and ServiceCIDRConfig (config.go:407-415, `go serviceCIDRConfig.Run(...)`) — exposes and invokes Run() to gate handler dispatch on cache sync. `nodeTopologyConfig` is constructed and has `RegisterEventHandler` called (server.go:609-611) but Run() is never called for it.",
    "fix": "Add a Run() method to NodeTopologyConfig that calls cache.WaitForNamedCacheSync using the stored listerSynced (matching the sibling pattern), and invoke it with `go nodeTopologyConfig.Run(...)` in server.go alongside nodeConfig.Run(), or explicitly document/justify why NodeTopologyConfig intentionally skips this (its interface has no Synced() method).",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/winkernel/proxier.go",
    "line": 1099,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_COMMENT] winkernel's OnTopologyChange doc comment reads \"OnTopologyChange is called whenever node topology labels are changed.\" while the three other real proxier implementations use identical wording: \"OnTopologyChange is called whenever this node's proxy relevant topology-related labels change.\" (pkg/proxy/iptables/proxier.go:625, pkg/proxy/ipvs/proxier.go:852, pkg/proxy/nftables/proxier.go:844).",
    "fix": "Align winkernel's leading doc sentence with the iptables/ipvs/nftables wording, keeping the additional field-selector explanation as a follow-up sentence.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/winkernel/proxier.go",
    "line": 1103,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_HELPER] winkernel's no-op `OnTopologyChange(topologyLabels map[string]string) {}` names its unused parameter, whereas every other no-op stub in this codebase uses `_` for an unused parameter: iptables/ipvs `OnServiceCIDRsChanged(_ []string) {}` (pkg/proxy/iptables/proxier.go:637, pkg/proxy/ipvs/proxier.go:863), winkernel's own `OnServiceCIDRsChanged(_ []string) {}` (pkg/proxy/winkernel/proxier.go:1096), and FakeProxier's `OnTopologyChange(_ map[string]string) {}` (pkg/proxy/kubemark/hollow_proxy.go:55).",
    "fix": "Rename the parameter to `_` to match the established no-op-stub convention.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 509,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_NAMING] NodeTopologyConfig.RegisterEventHandler's doc comment reads \"registers a handler which is called on Node object change,\" diverging from the \"registers a handler which is called on every X change\" phrasing shared by ServiceConfig (config.go:194), EndpointSliceConfig (config.go:100), NodeConfig (config.go:302), and ServiceCIDRConfig (config.go:403). It also mischaracterizes the behavior — the handler is called only when topology labels differ, not on every Node object change.",
    "fix": "Reword to \"registers a handler which is called on every topology label change\" to match sibling phrasing and accurately describe the dedup behavior.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 458,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_NAMING] NodeTopologyHandler's interface doc reads \"is an abstract interface for objects which receive notifications,\" while ServiceHandler (config.go:40), EndpointSliceHandler (config.go:57), and NodeHandler (config.go:262) all use \"is an abstract interface of objects which receive notifications.\"",
    "fix": "Change \"for objects\" to \"of objects\" to match the three sibling handler interfaces.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/config/config.go",
    "line": 275,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_COMMENT] NodeConfig's type doc still reads \"It accepts \\\"set\\\", \\\"add\\\" and \\\"remove\\\" operations of node via channels, and invokes registered handlers on change,\" but NodeConfig's construction (config.go:288-294, directly touched by this PR's OnNodeChange merge) uses `AddEventHandlerWithResyncPeriod`, not channels — matching the plain \"X tracks a set of Y configurations.\" doc style used by EndpointSliceConfig (config.go:73) and ServiceConfig (config.go:167), neither of which carries stale channel language.",
    "fix": "Drop the channel-based description from NodeConfig's doc comment; it no longer reflects the informer-based implementation.",
    "confidence": 100,
    "pre_existing": true
  }
]
```

## Considered But Not Flagged

- **metaproxier's OnTopologyChange doc wording** (`pkg/proxy/metaproxier/meta_proxier.go:131`, "is called whenever change in proxy relevant topology labels is observed") differs from the iptables/ipvs/nftables triple, but it's closer to the canonical `NodeTopologyHandler` interface doc phrasing and metaproxier is a structurally different (fan-out/composite) implementation — consistent with how its other pass-through methods (e.g. `OnServiceCIDRsChanged`) also mirror the interface doc rather than the concrete-proxier doc. Not clearly a deviation vs. a legitimate second convention.
- **ipvs's OnTopologyChange not setting `needFullSync`** — pre-existing structural difference; ipvs never had a `needFullSync` field/concept even before this PR (its former `OnNodeAdd`/`OnNodeUpdate` didn't set it either), so this isn't drift introduced by the change.
- **No `var _ config.NodeHandler = &NodeManager{}` compile-time assertion** in `pkg/proxy/node.go` — the two prior assertions of this kind (`NodePodCIDRHandler`, `NoopNodeHandler`) were deleted along with their types in this same PR, so there's no surviving sibling to compare against; not new drift, just an unreplaced pattern.
- **`handleNodeEvent` naming in NodeTopologyConfig** (config.go:515) combining Add/Update into one dispatcher — matches the established combined-handler pattern already used by `ServiceCIDRConfig.handleServiceCIDREvent` (config.go:419), so this is convention-following, not drift.
- **Double space typo** ("to  watch") in the `CategorizeEndpoints` cross-reference comment (`pkg/proxy/topology.go:46`) — a prose/comment-quality nit, not a sibling-consistency issue (quick-reviewer's domain).
- **NodeTopologyConfig lacking a mutex** around `topologyLabels`/`eventHandlers` — consistent with ServiceConfig/EndpointSliceConfig/NodeConfig, none of which lock either (informer callbacks run serially); no drift.
