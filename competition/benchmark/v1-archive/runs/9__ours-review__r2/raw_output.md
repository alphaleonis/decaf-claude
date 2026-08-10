Review complete. The only working-tree change is the new untracked review artifact under `.decaf/` — no tracked source was modified (both revert-probes restored byte-identical). No prior reviews existed, so the recurring-findings step was skipped. Nothing was posted to the PR (review-only).

✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-10_11-36-42.md`

**Findings by severity: 0 Critical · 3 High · 4 Medium · 1 Low · 14 Minor** (+1 pre-existing) — Verdict: ❌ NEEDS_CHANGES

The three High findings, all validator-confirmed:
1. **Missing `AddFunc` in `NodeConfig`** — a NodeIP/PodCIDR change during the startup window is dropped as a replayed Add, bypassing crash-on-change safety until the next resync.
2. **`NodeTopologyConfig` register-after-start** — unsynchronized `eventHandlers` data race plus a lost-initial-topology window (proxier can route with `zone=""`).
3. **`NodeEligible()` deep-copies the whole Node on every `/healthz` request**, under a lock that now guards nothing.
