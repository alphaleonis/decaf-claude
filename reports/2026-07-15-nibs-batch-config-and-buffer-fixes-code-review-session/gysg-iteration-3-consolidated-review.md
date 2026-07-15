# Code Review

**Mode**: mid (explicit) | **Reviewers**: see the Dispatch Anomaly below — the 10-agent wave executed but returned no reports; findings below are the **orchestrator's own** | **Date**: 2026-07-15
**Source**: local uncommitted changes, branch `batch/config-and-buffer-fixes`
**Scope**: 18 files changed, +1057/-112 lines
**Spec**: none found
**Validation**: not run — see Dispatch Anomaly (no reviewer findings existed to validate)

> ## ⚠️ DISPATCH ANOMALY — READ FIRST
>
> **This is NOT the 10-agent consolidated review that was requested.** Ten reviewers
> were dispatched in a single parallel message with `run_in_background: false`. The
> harness backgrounded them anyway (each spawn returned
> `"will receive instructions via mailbox"` instead of a report), and **their final
> messages were never delivered** to the orchestrator — not as tool results, not as
> completion notifications, and not after an explicit SendMessage round asking each
> agent to re-send its report verbatim (~4 min wait, no replies).
>
> **Evidence the reviewers really did run and then finished:** their probe worktrees
> (`probe-adversarial`, `probe-design`, `probe-knowledge`, `probe-test`, and a
> reviewer-authored `probe-terminality.test.ts`) appeared in the scratchpad and were
> subsequently cleaned up by the agents themselves; `git worktree list` returned to
> its 2-entry baseline. No agent transcripts were recoverable from disk.
>
> **Their findings are unrecoverable and are NOT reproduced here — none were
> fabricated.** What follows is a single-reviewer review performed by the
> orchestrator, which had independently read the complete diff. Treat its coverage
> as roughly that of one generalist reviewer: **materially thinner than the
> requested wave**, with no independent corroboration and no validation pass. The
> verdict below is correspondingly weaker evidence than a `mid` run's would be.
>
> **Recommendation:** re-run the wave once the dispatch path returns reports.

## Agent Selection Rationale

Mode was **explicit** (`mid`), so Step 2a.5 was skipped. The gate evaluation below
was performed and the roster was dispatched; only the *return path* failed.

- `quick-reviewer` — always (review floor)
- `broad-reviewer` — always (review floor)
- `go-reviewer` — Go files present (hard gate); watcher concurrency is the core risk
- `typescript-reviewer` — TypeScript files present (hard gate)
- `test-reviewer` — test files present (hard gate); test integrity was a named concern
- `design-reviewer` — GraphQL contract, exported Go enum, and concurrency surface changed
- `adversarial-reviewer` — ≥50 changed executable lines AND data mutations (store eviction)
- `knowledge-reviewer` — comment truth is the stated dominant defect class
- `consistency-reviewer` — substantive change with abundant sibling code
- `performance-reviewer` — `fileExists` syscalls in a loop under `c.mu`
- `security-reviewer`: skipped — no privilege boundary, auth, or untrusted input; `isArchivedPath` is a local classification, not a containment check
- `spec-compliance-reviewer`: skipped — no spec available (hard gate)
- `data-migration-reviewer`: skipped — no migration artifacts (hard gate)
- `dotnet` / `cpp` / `rust` reviewers: skipped — no such files (hard gate)
- `prior-feedback-reviewer`: skipped — not a PR review (hard gate)

No roster cap was given. Model tiering (`mid`): judgment agents (design, adversarial,
knowledge) on the session model; volume agents (quick, broad, consistency, test,
performance, typescript, go) mid-tier. **Tiering had no observable effect given the
return-path failure.**

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 0 |
| 🟡 Medium | 0 |
| 🟢 Low | 1 |
| 🔵 Minor | 1 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor**
counts reported-but-non-blocking findings. Pre-existing issues are listed separately
and excluded from both.

**Verdict**: ✅ APPROVED — *with the confidence caveat in the Dispatch Anomaly above.*
No Critical or High primary findings were identified **by this single reviewer**. The
change's central claims were probed directly and all held (see Verified Claims).

---

## Findings

### #1 🟢 Low: The `archived` notice is painted in the destructive (red) color, re-asserting the conflation this change removes

| | |
|---|---|
| **File** | `web/src/lib/components/ActiveNibView.svelte:968` |
| **Category** | ui-semantics |
| **Confidence** | 100 (quotable fact) |
| **Found by** | orchestrator |

**Issue:** The change's whole thesis is that an archived nib is **not** a deleted one —
it still exists, and it still saves. The notice *copy* was duly fixed
(`"This nib was archived"` vs `"This nib was deleted"`), but the notice's *styling*
was not. `.anv-gone-notice` unconditionally applies:

```css
background-color: var(--destructive);
color: var(--destructive-foreground);
```

`--destructive` resolves to `oklch(0.577 0.245 27)` — commented `/* red-500 */` in
`web/src/app.css:93`. So an archived nib — a normal, reversible, non-destructive
lifecycle transition whose buffer is still savable — is announced in the same red
error banner as a deletion. The banner is, per the change's own comment, *"the user's
only explanation for the read-only panel"*, so the color is load-bearing signal, and
it currently contradicts the text directly above it.

The codebase already has the right token for non-destructive attention, in the
immediately adjacent sibling rule (`.anv-conflict`, same file, ~line 976):
`background-color: var(--warning)`.

**Fix:** Drive the notice color off `goneReason`, reusing the established tokens:

```svelte
<div
  class="anv-gone-notice"
  class:anv-gone-notice--archived={goneReason === "archived"}
  data-testid="anv-gone-notice"
>
  {goneReason === "archived" ? "This nib was archived" : "This nib was deleted"}
</div>
```
```css
.anv-gone-notice {
  /* ...unchanged... */
  background-color: var(--destructive);
  color: var(--destructive-foreground);
}
.anv-gone-notice--archived {
  background-color: var(--warning);
  color: var(--warning-foreground, white);
}
```

---

## Minor Findings

### Consistency

- `web/src/lib/nibChange.ts:99` — **The two layers state different contracts about
  whether `deleted` is terminal.** `activeView.ts`'s reducer treats a deletion as
  terminal and says so explicitly ("Nothing supersedes a deletion — it is terminal"),
  upgrading `gone(archived)` → `gone(deleted)` and refusing the reverse. But
  `classifyNibEvent`'s guard is only `if (prev.gone === event.type) return prev;`, so
  a `deleted` → `archived` event sequence **downgrades** `NibChangeState.gone` to
  `"archived"` (and resets `external` to `null`).
  *Verified contained, which is why this is Minor and not primary:* (a) it is
  unreachable from today's backend — `handleChanges` bails via
  `stored, exists := c.nibs[id]; if !exists { continue }`, and a deleted nib has
  already left `c.nibs`, so no later `archived` event can be emitted for it; and
  (b) `useActiveView`'s bridge maps the downgraded value to an `ARCHIVED` action,
  which `activeView.ts`'s reducer correctly refuses (`s.reason` is `"deleted"`, so
  the supersede condition is false and it returns `s` unchanged). The view state is
  therefore protected by the outer layer. Worth aligning the inner layer's guard
  anyway (`if (prev.gone === "deleted" || prev.gone === event.type) return prev;`) so
  both layers assert the same contract rather than relying on a defense one layer up.
  (orchestrator)

---

## Verified Claims (probed, no finding)

Each of these was a claim the review brief asked to be probed hardest. All were
checked directly against the code and **held**:

| Claim | Verdict | Evidence |
|---|---|---|
| `Core.Archive` holds `c.mu` across BOTH the `os.Rename` and the `Path` rewrite | **TRUE** | `core.go:1012` `c.mu.Lock()`, `:1013` `defer c.mu.Unlock()`; `os.Rename` at `:1037`; `Path` rewrite at `:1042-1043` — both inside the critical section. `handleChanges` takes the same lock at `watcher.go:263`. The comment's premise is accurate and its conclusion follows. |
| Archived detection works whether or not `.nibs/archive/` is watched | **TRUE** | The check reads the *store*, not the watch set: `Archive` rewrites `stored.Path` to `archive/x.md` under the lock, so on the `Remove(x.md)` event `isArchivedPath(stored.Path)` is true and `fileExists(root/archive/x.md)` is true → `EventArchived`. A lazily-created, unwatched archive dir does not affect this path. |
| Deleting an already-archived nib still reports `deleted` | **TRUE** | `stored.Path` is `archive/x.md` and that file is the one that just vanished, so `fileExists(root/archive/x.md)` is false → the guard fails → falls through to eviction + `EventDeleted`. |
| `isArchivedPath` does not misfire on `archive`-like names | **TRUE** | Executed probe: `archive/x.md`→true; `archived/x.md`→false; `archive-foo.md`→false; `archivex.md`→false; `x.md`→false. The trailing separator is what saves it. |
| `Unarchive` is genuinely unchanged, not newly broken | **TRUE** | After `Unarchive`, `stored.Path` is `filepath.Base(...)` (no `archive/` prefix), so `isArchivedPath` is false and control falls to the eviction path — **byte-for-byte the same outcome as before this change**, which also evicted on any vanished file. This diff neither fixes nor worsens it. (Its own conflation is nibs-ow1k, out of scope.) |
| New `core_test.go` / vitest guards | **NOT VERIFIED** — the mutation testing that would have proven these red on unfixed code was delegated to `test-reviewer` / `go-reviewer` / `typescript-reviewer`, whose reports were lost. **This is the single largest coverage gap left by the anomaly**, given that four non-running or vacuous guards have already been caught this session. The orchestrator independently confirmed only that `go test -race ./internal/nibcore/` and `activeView.test.ts` (57 tests) pass in an isolated probe tree — which proves they *run*, not that they *bite*. |

---

## Pre-existing Issues

### P1 🟢 Low: `isArchivedPath`'s `filepath.Separator` branch is redundant on POSIX and dead on Windows

| | |
|---|---|
| **File** | `internal/nibcore/core.go:1097` |
| **Category** | dead-code |
| **Confidence** | 100 (quotable fact) |
| **Found by** | orchestrator |

**Issue:** `strings.HasPrefix(path, ArchiveDir+string(filepath.Separator))` is byte-identical
to the `ArchiveDir+"/"` branch on Linux/macOS. On Windows it tests for `archive\`, but
every `Path` reaching this function is normalized with `filepath.ToSlash` (`core.go:265`,
`:1042`) or is a bare `filepath.Base` result with no separator at all (`:1075`, `:1188`) —
so the branch cannot fire there either. **This change did not introduce the function**; it
only added a caller (`watcher.go:306`), so it is informational and excluded from the verdict.

**Fix:** Collapse to the single forward-slash test, matching the documented `Path` invariant:
```go
func (c *Core) isArchivedPath(path string) bool {
	return strings.HasPrefix(path, ArchiveDir+"/")
}
```

---

## Agent Summary

**Not computable.** Per-agent Issues Found / Unique Issues require the reviewers'
findings, which were never delivered. Reporting zeros or estimates here would
misrepresent work whose output does not exist.

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| all 10 dispatched reviewers | not delivered | not delivered |
| orchestrator (fallback) | 3 | 3 |
| **Total** | **3** | |

---

## Specialist Notes

### Considered But Not Flagged (orchestrator)

- **`Path` assignments missing `filepath.ToSlash` at `core.go:1075` and `:1188`** — looked
  like an invariant break against the documented "always forward slashes" rule, but both
  assign a `filepath.Base(...)` result, which contains no separator. `ToSlash` would be a
  no-op. Not a defect.
- **A second `stat` syscall per removal event under `c.mu`** (`watcher.go:306`) — real, but
  it runs only on the removal path, once per removed file, in a tool that watches a
  developer's `.nibs/` directory of tens-to-hundreds of Markdown files. No realistic
  scenario where it hurts; a speculative micro-cost is not a finding.
- **`Nib: stored` shares the stored pointer with `EventArchived` subscribers** — worth a
  specialist's eye (this was delegated to `go-reviewer`/`design-reviewer` and is
  **unresolved** due to the anomaly). The orchestrator notes `EventUpdated` constructs its
  `Nib` field from the same store values, so this is at minimum consistent with the
  existing sibling pattern rather than a new aliasing class.
- **`changeTracker` fading archived rows** (`changeTracker.svelte.ts:16`) — correct: the main
  list excludes archived nibs, so the row does leave the visible tree, and its comment says
  exactly that.
- **The `confirm` docblock's corrected rationale** (`useActiveView.svelte.ts:131-146`) — spot-
  checked and **accurate**: TypeScript's parameter-arity rule does accept a zero-arg
  `() => Promise<ConfirmChoice>` against a `(opts: {canSave: boolean}) => ...` type, so the
  docblock's claim that the required param binds callers but *not* implementations is true,
  as is its admission that honoring it is "a review obligation, not a compile-time one".
  This is the previously-false clause now stated correctly. A full clause-by-clause audit of
  every new comment was delegated to `knowledge-reviewer` and is **unresolved**.

### Coverage NOT achieved (due to the anomaly)

These were explicitly briefed as "probe hardest here" and have **no reviewer verdict**:
mutation-proof of every new guard; exhaustiveness of `NibChangeType` consumers across the
whole web tree; the `String!`-vs-enum contract/evolution question; adversarial scenarios
(external `mv`/`git checkout` desyncing store `Path` from the filesystem, archive-then-delete
races, cascade tracing of a mis-detected event through the search/mention indices);
sibling-consistency sweep (`GoneReason` vs `NibGoneReason` naming, stale `anv-deleted-notice`
references, table-driven-test conformance); reference-stability of `classifyNibEvent` across
the `boolean`→`reason` migration.

## Recurring Findings

**None.** Scanned all 88 prior reviews in `.decaf/code-reviews/`, matching on file path +
category. `internal/nibcore/core.go` (16 prior reviews) and
`web/src/lib/components/ActiveNibView.svelte` (12) appear often, but never in these
findings' categories — the 4 prior `anv-*-notice` mentions concern ARIA roles, the
`gone`-routing chain, and test assertions, not the notice's color. `isArchivedPath` and
`web/src/lib/nibChange.ts` have zero prior mentions. No file+category pair recurs.

## Session Metrics (--report)

**Wave timing**: dispatched 10 reviewers in a single parallel message ~19:56 local;
all probe worktrees observed created and self-cleaned by ~20:07 (~11 min wall clock);
SendMessage retrieval round issued ~20:07, no replies by ~20:11.

**Per-agent usage**: **not reported.** The harness returned no tool results for any
reviewer — only spawn acknowledgements — so tokens, tool calls, duration, and findings
counts were never surfaced to the orchestrator. This data exists only in the undelivered
tool results and is unrecoverable. No figures are estimated below.

| Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings |
|---|---|---|---|---|---|---|
| quick-reviewer | reviewer | mid-tier | not reported | not reported | not reported | not delivered |
| broad-reviewer | reviewer | mid-tier | not reported | not reported | not reported | not delivered |
| go-reviewer | reviewer | mid-tier | not reported | not reported | not reported | not delivered |
| typescript-reviewer | reviewer | mid-tier | not reported | not reported | not reported | not delivered |
| test-reviewer | reviewer | mid-tier | not reported | not reported | not reported | not delivered |
| consistency-reviewer | reviewer | mid-tier | not reported | not reported | not reported | not delivered |
| performance-reviewer | reviewer | mid-tier | not reported | not reported | not reported | not delivered |
| design-reviewer | reviewer | session model | not reported | not reported | not reported | not delivered |
| adversarial-reviewer | reviewer | session model | not reported | not reported | not reported | not delivered |
| knowledge-reviewer | reviewer | session model | not reported | not reported | not reported | not delivered |
| finding-validator ×N | validator | — | not spawned | — | — | — |

**Pre-flight gates** (run once by the orchestrator, in an isolated probe worktree):
- `go test -race ./internal/nibcore/` — **PASS** (5.655s), independently verified
- `activeView.test.ts` — **PASS** (57 tests, 655ms), independently verified
- `task build` / `task lint` / full vitest / `svelte-check` — **caller-reported green**
  (build clean, lint 0 issues, 60 files / 1277 passed, 0/0); not independently re-run.
  Note: `go build ./...` inside a probe worktree emits a spurious
  `embed.go:5:12: pattern all:web/dist: no matching files found` because `web/dist` is
  gitignored and absent from fresh worktrees — an artifact, not a build failure. This was
  identified before dispatch and every reviewer was warned about it explicitly.

**Anomalies**: **2.**
1. **Reviewer report delivery failure (severe)** — 10/10 reviewers produced no retrievable
   output despite `run_in_background: false` and a follow-up SendMessage round. Root cause
   appears to be the harness backgrounding subagents unconditionally and the completion
   notifications never reaching this subagent-hosted skill. This is precisely the failure
   mode the skill's synchronous-dispatch rule exists to prevent, and the rule was followed —
   the guard did not hold in this environment.
2. **Probe-protocol anomaly: NONE.** The isolation mandate worked exactly as intended. The
   stash-object recipe was validated *before* dispatch (fix confirmed present in the probe
   tree and absent at `HEAD`), the shared working tree measured **18 modified files at every
   checkpoint** from start to finish, `git worktree list` returned to its 2-entry baseline,
   and the shared `web/node_modules` survived intact. **Zero reviewers reported the changeset
   as absent, reverted, or flapping** — the corruption mode from the two early waves did not
   recur. This is the fifth consecutive clean wave under the isolation mandate.
