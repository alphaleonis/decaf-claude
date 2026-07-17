# Benchmark run: 9__tag1-comprehensive-review__r1

| field | value |
|---|---|
| tool | tag1-comprehensive-review |
| subject | 9 (go / large) — kubernetes/kubernetes#130837 |
| review diff | `0872760763d5877707b018a4eea870d1fc02e6a4^1..0872760763d5877707b018a4eea870d1fc02e6a4` (merge 0872760763d5877707b018a4eea870d1fc02e6a4) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 1340 |
| longest single subagent (s) | 668 |
| duration_ms (orchestrator self) | 1338616 |
| duration_api_ms (summed parallel API time, not wall) | 4600350 |
| num_turns | 29 |
| cost_usd | 20.25029445 |
| input_tokens | 32 |
| output_tokens | 54225 |
| cache_creation_tokens | 310206 |
| cache_read_tokens | 2035873 |
| total_tokens (orchestrator only) | 2400336 |
| **subagents** | 11 |
| **ws output_tokens** | 59205 |
| ws input_tokens | 242 |
| ws cache_creation | 1653839 |
| ws cache_read | 11070223 |
| ws total_tokens | 12783509 |
| session_id | d5c17aa4-fd9f-4db9-baf8-d113fb1da45b |
| findings (raw lines) | 45 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (1340s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a512029cf31d57a6a | 151 | 794687 | 264 |
| agent-a58d1ff8b5eb4deca | 177 | 869241 | 320 |
| agent-a7a4a97193460d09b | 37 | 986519 | 330 |
| agent-a85c2e102f4d6fde2 | 199 | 1512468 | 541 |
| agent-a8a71d21c09a76783 | 314 | 921790 | 389 |
| agent-a906e444994f385b4 | 315 | 2574836 | 668 |
| agent-ab8f5f055930ee315 | 13 | 186446 | 41 |
| agent-abc2605935bf70ba2 | 127 | 1358691 | 493 |
| agent-aea7d0e5cb7f542c4 | 25 | 497987 | 207 |
| agent-aef15d6c80d79a878 | 12 | 284732 | 260 |
| agent-af6c4475074550cfc | 3610 | 395776 | 600 |

## Findings (final result text)

```
Review complete. Everything was displayed locally; nothing was posted to GitHub.

## Output file

`.decaf/tag1-review-130837.md` (25 KB) — full Block A (summary + walkthrough) and Block B (findings).

## Findings by severity

| Severity | Count | Key items |
|----------|-------|-----------|
| **Critical** | 0 | — |
| **High** | 2 | **H1** `NewNodeConfig` drops `AddFunc` → startup-window node changes bypass NodeManager's crash-on-change safety (converged by 5 reviewers). **H2** no metric/Event before any `os.Exit(1)` → fleet-wide crashloops are operationally invisible. |
| **Medium** | 11 | Baseline poisoned before validation → spurious crash (M1); order-sensitive `DeepEqual` on NodeIPs → reorder → spurious crash (M2); undocumented broadened crash surface + no release note (M3); unconditional `s.podCIDRs` → spurious `checkBadIPConfig` warning (M4); new blocking-fatal 5-min startup in all modes (M5); `healthcheck`→`proxy` coupling (M6); lost startup diagnostic logging (M7); stale 5-min comment (M8); plus 3 test-gaps (M9–M11). |
| **Low** | 13 | Needless `hs.lock`, `PodCIDRs()` non-copy vs `Node()`, garbled doc comment, dead `listerSynced`/`nodeLister`/tombstone branch, missing `return` after exit, shared-map handoff, mis-surfaced poll-timeout error, and 3 more test-gaps. |

**Overall risk: High.** No security or data-loss issues — `security-reviewer` returned a *reasoned* NONE (crash surface is per-node-scoped and RBAC/NodeRestriction-gated; it's an availability tradeoff, not a security hole). The two High findings both concern the correctness/operability of the new crash-on-change mechanism at the heart of the PR.

## Notes
- **PR is MERGED** — reviewed retrospectively from the authoritative `gh pr diff` (18 files, +757/−803) against a worktree at the PR head (local clone is shallow, depth 3).
- Agents run: 11. **Skipped:** issue-linker (`--pr`/`--local`), CVE check (no dependency manifests changed), all static analyzers (binaries absent).
- Suppression: 9 rules loaded, none matched (no version/dependency findings). Novelty pass skipped (claude-mem offline). Secret redaction: nothing to redact.
- **Confidence filter:** default `--min-confidence 75`. Because `--local` means "display everything," sub-threshold findings (M4, M2, several Lows) are **shown and labeled** rather than dropped.
- Worktree removed; temp files cleaned.

## Token utilization

| Agent | Model | Tokens | Tools | Est. cost |
|-------|-------|-------:|------:|----------:|
| pr-summarizer | Sonnet | 92,873 | 3 | ~$0.84 |
| code-reviewer | Sonnet | 167,270 | 25 | ~$1.51 |
| architecture-reviewer | Opus | 109,906 | 5 | ~$4.95 |
| security-reviewer | Opus | 111,539 | 9 | ~$5.02 |
| adversarial-general | Opus | 125,917 | 15 | ~$5.67 |
| blind-hunter | Sonnet | 158,835 | 3 | ~$1.43 |
| edge-case-hunter | Sonnet | 148,159 | 15 | ~$1.33 |
| silent-failure-hunter | Sonnet | 128,345 | 13 | ~$1.16 |
| pr-test-analyzer | Sonnet | 132,457 | 14 | ~$1.19 |
| comment-analyzer | Sonnet | 105,247 | 10 | ~$0.95 |
| type-design-analyzer | Sonnet | 147,542 | 16 | ~$1.33 |
| **Agents total** | | **~1.43M** | | **~$25.38** |
| Orchestrator (est.) | Opus | — | — | — see `/cost` |

Blended-rate estimates (Opus ~$45/M, Sonnet ~$9/M); run `/cost` for exact figures. No agent exceeded its 25-call budget (code-reviewer hit exactly 25).

⚠ **Address the two High findings (H1 `AddFunc` gap, H2 exit observability) before relying on this in production** — both are noted in the report's prioritized Recommended Actions.
```
