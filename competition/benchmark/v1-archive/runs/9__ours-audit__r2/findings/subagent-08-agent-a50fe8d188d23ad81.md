# subagent agent-a50fe8d188d23ad81

I have the complete picture from `node.go` and the full diff. I've traced the exit paths, the informer wiring, the old-vs-new behavior, and the health-server refactor. No further reads needed.

## Threat-model analysis

The central change: `NodeManager.OnNodeChange` / `OnNodeDelete` (`pkg/proxy/node.go:140-180`) call `n.exitFunc(1)` (prod: `os.Exit`, wired at line 60) whenever this node's NodeIPs change, PodCIDRs change (only if `watchPodCIDRs`), or the Node object is deleted. I compared this against the pre-change behavior to isolate what is genuinely new attack surface.

**Old behavior (for contrast):**
- NodeIP was read once at startup via `getNodeIPs` (exponential backoff, log-and-retry, no watch, never fatal on change).
- Node deletion: `NodeEligibleHandler.OnNodeDelete` → `SyncNode` marked the node ineligible (health 503); proxiers cleared labels and re-synced. **Neither exited.**
- PodCIDR change: `NodePodCIDRHandler` already exited, but only in `LocalModeNodeCIDR`.

**New behavior adds two always-on self-termination triggers** (NodeIP change; Node deletion) that did not exist before, and there is no debounce, backoff, rate-limit, or self-restart metric on any of the three exit paths.

Here is my report.

```json
[
  {
    "file": "pkg/proxy/node.go",
    "line": 167,
    "severity": "High",
    "category": "security",
    "issue": "[THREAT_ATTACK_SURFACE] kube-proxy now self-terminates (os.Exit(1)) on any observed change to this node's Status.Addresses (NodeIPs) or on Node deletion, with no debounce/backoff/rate-limit. This converts a Node-object write — a privilege held by the node's own kubelet (for its Node, via NodeRestriction) and cluster-wide by node-lifecycle/cloud controllers and any principal with `nodes` update/delete RBAC — into a dataplane restart. A flapping or maliciously-toggled node status produces a kube-proxy crashloop, during which this node's Service networking stops being reconciled. Blast radius is cluster-wide for any credential with cluster-scoped `nodes` update/delete. This is net-new surface: pre-change, NodeIP was read once at startup (never fatal on change) and Node deletion did not exit.",
    "fix": "Do not treat an attacker/kubelet-influenced field change as unconditionally fatal. Prefer reconciling NodeIP changes in place, or gate self-exit behind a debounce + restart rate-limiter (e.g. exit only after the change persists across N observations / a cooldown window) and surface it via CrashLoopBackoff-aware handling so a single actor cannot drive an unbounded restart loop of the node dataplane.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 179,
    "severity": "Medium",
    "category": "security",
    "issue": "[THREAT_AUDIT] The three self-induced exit paths (NodeIPs changed, PodCIDRs changed, Node deleted) emit only an Info-level log line immediately before os.Exit(1). There is no metric, event, or counter distinguishing an intentional NodeManager-driven restart from an ordinary crash. An incident responder cannot detect or attribute a restart-loop abuse (Finding 1's scenario) because the signal is indistinguishable from normal churn and is lost once the process dies. This is an observability/detection gap on a security-relevant availability control.",
    "fix": "Increment a dedicated counter metric (e.g. a labeled `kubeproxy_node_manager_restart_total{reason=...}`) and/or emit a Kubernetes Event before exiting, so restart-loop patterns are observable and alertable independent of the process lifetime.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Log injection via node fields** (`OnNodeChange`/`OnNodeDelete` log `klog.KObj(node)`, NodeIPs, PodCIDRs): `klog.KObj` emits only namespace/name (Node names are RFC1123-constrained, no newlines), IPs are parsed `net.IP`, PodCIDRs are validated CIDR strings, and klog structured KV output quotes string values. No practical forged-log-line vector. Not flagged.
- **Nil-pointer / panic robustness** in `Node()`, `PodCIDRs()`, `NodeIPs()` dereferencing `n.node`: `n.node` is guaranteed non-nil after successful construction and is only ever reassigned to a non-nil informer object. Not a security gap (and would be quick/go-reviewer's lane anyway).
- **Removed `node.Name != proxier.nodeName` guard** in the proxiers: the guard is now redundant because both `NodeManager` and `NodeTopologyConfig` consume a field-selected (`metadata.name=nodeName`) informer, so only this node's events are delivered. Loss of defense-in-depth is minor; not flagged.
- **Informer resync causing spurious exit**: resync re-delivers the same object as an Update; `OnNodeChange` compares against the stored `n.node` (same values) → `DeepEqual` true → no exit. Verified safe.
- **os.Exit skipping deferred cleanup**: matches prior semantics (old code used `klog.FlushAndExit`); `klog.Flush()` precedes exit. Not a new gap.
- **Health-server lock change** (`NodeEligible` now takes `hs.lock.Lock()` and reads `nodeManager.Node()`): lock ordering is consistent, no cross-lock cycle with `OnNodeChange`. Not flagged.

## Threat Model Notes

- **Trust boundary**: kube-proxy consumes the Node object from the API server. The writers of the fields that now decide process life-or-death are: this node's kubelet (constrained to its own Node by the NodeRestriction admission plugin) for `Status.Addresses`; the PodCIDR allocator / node-ipam controller for `Spec.PodCIDRs`; and node-lifecycle / cloud-controller-manager (plus any `nodes` update/delete grantee) for deletion. The change moves an availability decision onto data controlled at these boundaries.
- **Data sensitivity**: no PII/secrets/crypto in scope. The sensitivity here is *availability* — kube-proxy is the node's Service dataplane reconciler.
- **Attack-surface change**: two new always-on self-exit triggers (NodeIP change, Node deletion) added; PodCIDR-change exit narrowed/retained behind `watchPodCIDRs`. Removed: startup exponential-backoff retry for NodeIP acquisition (replaced by a 5-min bounded poll in `NewNodeManager`, which returns an error → container restart rather than looping in-process — acceptable, but shifts robustness from in-process retry to pod restart).
- **Privilege/blast radius**: a compromised kubelet can only affect its *own* node's kube-proxy (NodeRestriction) — bounded. A compromised cluster-scoped `nodes`-writer (cloud-controller-manager, node-lifecycle controller, an over-broad operator SA) can now flap every node's kube-proxy — the meaningful escalation of this change.
- **Residual risk / mitigating factor**: while kube-proxy is down, previously-programmed iptables/nftables/ipvs rules persist in the kernel, so existing Service connectivity is not immediately severed — only reconciliation of *new* changes stops. This is why Finding 1 is High, not Critical.
- **Assumption**: prod `exitFunc` is `os.Exit` (line 60) and the DaemonSet/pod restart policy will restart the container, making repeated exits a CrashLoopBackoff rather than a permanent outage. Debounce/rate-limiting is the missing architectural control.

### Probe Requests
None. Findings are grounded in source read from disk (behavior is directly observable in `OnNodeChange`/`OnNodeDelete`); no regression probe needed.
