# subagent agent-a1aa06b035fb682a8

Depth: deep — this changeset is well over 200 executable lines and sits squarely in a high-risk domain (process-lifecycle control via `os.Exit`, cluster bringup, health-server state, and informer/external-API integration). All four techniques applied, with cascade construction traced end to end.

I traced the new `NodeManager` (`pkg/proxy/node.go`), its wiring in `cmd/kube-proxy/app/server.go` (baseline captured at line 211 in `newProxyServer`, handler registered far later at lines 608-609 in `Run()`), the order-sensitive `GetNodeHostIPs` (`pkg/util/node/node.go:65`), and the health server (`pkg/proxy/healthcheck/proxy_health.go`).

```json
[
  {
    "file": "pkg/proxy/node.go",
    "line": 167,
    "severity": "Critical",
    "category": "error-handling",
    "issue": "[ADV_CASCADE] NodeManager baseline captured early with only kubelet's IPv4 → cloud-provider/CCM assigns IPv6 (or replaces the IP) after handler registration → OnNodeChange sees DeepEqual(oldNodeIPs,[v4]) != [v4,v6] → os.Exit(1) → DaemonSet pod restarts → address set is still settling → exit again → CrashLoopBackOff. Across a whole cluster during bringup this leaves kube-proxy down (exponential backoff up to 5m) exactly when new Service/Endpoint rules must be programmed, so new-workload networking is unprogrammed during creation. Old code never re-checked NodeIPs after startup, so this exit path is entirely new exposure.",
    "fix": "Do not treat every NodeIP delta as fatal during startup settling. Either (a) debounce/grace-window NodeIP changes before exiting, (b) compare IP *sets* not ordered slices and only exit on a genuine primary-IP change, or (c) attempt in-place reconfiguration instead of process exit. At minimum, gate the exit until the node has been observed stable for one resync period.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 167,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_ABUSE] GetNodeHostIPs (pkg/util/node/node.go:65) selects the primary IP by *positional order* of Node.Status.Addresses and returns an ordered slice; OnNodeChange compares with reflect.DeepEqual. A dual-stack node whose kubelet/cloud-provider republishes Status.Addresses with the InternalIP v4/v6 entries in swapped order (same IPs, different order) yields [v4,v6] vs [v6,v4] → DeepEqual false → os.Exit(1). If ordering flaps between syncs, kube-proxy exits on every flap → sustained CrashLoopBackOff with no actual IP change.",
    "fix": "Normalize before comparison: sort the IP slice (or compare as a set keyed by family) so a pure reordering of Status.Addresses does not register as a change. Only the identity of the per-family primary IP should matter.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 145,
    "severity": "High",
    "category": "error-handling",
    "issue": "[ADV_CASCADE] OnNodeChange writes n.node = node (line 145) BEFORE the GetNodeHostIPs error check (lines 159-163). Sequence: node transiently publishes empty Status.Addresses (kubelet status rebuild / cloud hiccup) → GetNodeHostIPs errors → function returns without exiting, but n.node is now the IP-less object so the stored baseline is nil-IP. Next event restores the SAME original IP [v4] → oldNodeIPs computed from the IP-less stored node = nil → DeepEqual(nil,[v4]) false → os.Exit(1), even though the IP never actually changed from the original baseline. A momentary address blip thus forces an unnecessary restart.",
    "fix": "Only overwrite n.node after a successful GetNodeHostIPs, or skip the comparison/baseline-update entirely when the new node yields no IPs (treat IP-less as 'no usable update' and retain the last good baseline).",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "pkg/proxy/node.go",
    "line": 60,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_ASSUMPTION] Fatal path uses default exitFunc = os.Exit (line 60), invoked as klog.Flush() then os.Exit(1) (lines 154/170-171, 178-179), replacing the prior klog.FlushAndExit(klog.ExitFlushTimeout, 1). [Inference/Unverified] klog.Flush() is a best-effort flush that does not wait for klog's flush daemon / buffered sinks the way FlushAndExit does; os.Exit then terminates immediately, so the very log line explaining WHY kube-proxy exited (NodeIPs/PodCIDRs changed / node deleted) can be lost. This matches the reported 'exiting early during bringup, logs not flushed' symptom — operators see a restart with no reason. [Inference] this is expected klog behavior, not a guarantee.",
    "fix": "Use klog.FlushAndExit(klog.ExitFlushTimeout, 1) on all three exit sites, or make exitFunc default to klog.FlushAndExit rather than os.Exit so the shutdown flush is bounded-wait rather than fire-and-forget.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "cmd/kube-proxy/app/server.go",
    "line": 608,
    "severity": "Medium",
    "category": "async",
    "issue": "[ADV_COMPOSITION] Baseline node is captured in newProxyServer at NewNodeManager (server.go:211) but the NodeManager handler is registered much later in Run() (server.go:608-609), and NewNodeConfig drops AddFunc (only UpdateFunc/DeleteFunc). Because the informer is already started+synced, client-go replays the current cache to the newly-registered handler as an Add event — which is swallowed (no AddFunc). Consequence: any NodeIP change occurring in the window between baseline capture and handler registration is never surfaced to OnNodeChange as such; it is only noticed on the NEXT unrelated Update, and if no further Update ever arrives, kube-proxy runs indefinitely with the stale poll-time NodeIPs (wrong masquerade/NodePort binding) while the real node has different IPs — a silent blackhole rather than the intended fail-fast restart.",
    "fix": "Capture the exit baseline at the moment of handler registration (or process the initial-list replay) rather than at a separate earlier poll, so the first observed state and the exit baseline are the same object and no change can slip through the gap.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Lock-ordering deadlock between ProxyHealthServer.NodeEligible (hs.lock) and NodeManager.Node() (n.mu)** — traced both directions. `NodeEligible` acquires `hs.lock.Lock()` then `n.mu` (via `Node()`); no `NodeManager` method ever calls back into the health server, so there is no reverse `n.mu → hs.lock` path. No cycle. Scenario fell apart at the "reverse acquisition" step. Only residual is minor: `NodeEligible` now holds the write lock (was RLock) across a `DeepCopy`, a small contention regression, not a failure.

- **Nil-pointer deref in NodeEligible when nodeManager is nil** — `hs.nodeManager.Node()` would panic if a `ProxyHealthServer` were built with a nil `NodeManager` (hollow-proxy sets `NodeManager = nil`). For real kube-proxy, `NodeManager` is always constructed before the health server, and hollow-proxy does not appear to start the healthz server, so I could not construct a reachable path. Left unflagged pending confirmation that hollow/kubemark never sets `HealthzBindAddress`.

- **Transient PodCIDR clearing → exit under watchPodCIDRs** — symmetric to the NodeIP-blip finding, but node `.spec.PodCIDRs` being cleared after assignment is far less plausible than a `.status.addresses` blip (spec is allocator-owned and stable), so I did not raise it separately; the same fix for baseline-overwrite ordering covers it.

- **Double exitFunc invocation (PodCIDR + NodeIP both changed in one event)** — with the real `os.Exit` the process dies on the first call, so the second is unreachable in production; only the test's no-op exitFunc continues. Not a runtime defect.
