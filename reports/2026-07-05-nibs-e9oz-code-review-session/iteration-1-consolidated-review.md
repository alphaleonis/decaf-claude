# Code Review

**Mode**: mid (explicit) | **Reviewers**: quick, broad, knowledge, consistency, design, test, adversarial, go, performance (9) | **Date**: 2026-07-05
**Source**: local uncommitted changes (nib e9oz — auto-activation stale-etag fix)
**Scope**: 2 files changed, +120/-3 lines (`internal/graph/resolver.go`, `internal/graph/schema.resolvers_test.go`)
**Spec**: none found
**Validation**: 2 confirmed, 0 refuted, 0 uncertain (1 reclassified pre-existing)

## Agent Selection Rationale

Mode `mid` was given explicitly (not second-guessed). Roster = floor + every gate-matched specialist:

- **quick-reviewer** (always — floor)
- **broad-reviewer** (always — floor)
- **knowledge-reviewer** — substantive change; ~35-line doc comment encodes the etag/clone decision that must survive
- **consistency-reviewer** — sibling mutation paths (`close`, blocking add/remove) exist to compare against
- **design-reviewer** — optimistic-concurrency contract, etag semantics, internal auto-transition boundary
- **test-reviewer** — test file present (hard gate)
- **adversarial-reviewer** — data-mutation domain + >50 changed executable lines; TOCTOU / composition surface
- **go-reviewer** — Go files present (hard gate); caller explicitly asked for Go-idiom scrutiny
- **performance-reviewer** — parent-chain loop performs file I/O per iteration; the fix adds a read per level
- **security-reviewer**: skipped — no security-adjacent surface (no auth/crypto/user-input/network/secrets); internal data-integrity concurrency only
- **spec-compliance-reviewer**: skipped — no spec available (hard gate)
- **data-migration / dotnet / typescript / cpp / rust / prior-feedback**: skipped — domain absent (hard gates)

**Model tiering (mid):** judgment agents (knowledge, design, adversarial) ran on the session model; volume agents (quick, broad, consistency, test, go, performance) and both validators ran mid-tier (`sonnet`). Pre-flight gates ran once: `go build ./...` PASS, `go test ./internal/graph -run TestAutoActivation` PASS, `golangci-lint run ./internal/graph/...` 0 issues, `go vet` clean.

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 1 |
| 🟠 High | 0 |
| 🟡 Medium | 0 |
| 🟢 Low | 1 |
| 🔵 Minor | 6 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts reported-but-non-blocking findings. Pre-existing issues are listed separately and excluded from both.

**Verdict**: ❌ NEEDS_CHANGES

The fix correctly repairs the reported bug (auto-activation now succeeds when the in-memory render has drifted from the on-disk bytes, under `RequireIfMatch` on/off), and the clone-instead-of-shared-pointer change is sound in isolation. But the way it repairs it — re-reading a *fresh* canonical etag while writing a *stale* in-memory clone — introduces a silent data-loss regression when the on-disk content genuinely diverges from the in-memory snapshot. Independently confirmed by a validator, and the new test actually locks the data-loss behavior in.

---

## Findings

### #1 🔴 Critical: Auto-activation silently overwrites divergent on-disk content (lost update / data loss)

| | |
|---|---|
| **File** | `internal/graph/resolver.go:210-232` |
| **Category** | concurrency / data-loss |
| **Confidence** | 100 (validated: confirmed) |
| **Found by** | broad-reviewer (Critical), adversarial-reviewer (Critical), quick-reviewer (High), design-reviewer (High) |

**Issue:** `activateParentChain` now performs three *independent* locked operations per parent, and the data it writes comes from a different instant than the etag it validates against:

1. `parent, _ := r.Reader.Get(parentID)` returns the **shared** `c.nibs[id]` pointer — a snapshot at T1.
2. `currentETag, _ := r.Reader.CurrentETag(parentID)` re-reads and hashes the parent's **raw on-disk bytes** at T2 (a fresh, separate RLock).
3. `updated := parent.Clone()` clones the **T1 snapshot**, sets `Status`, and `Writer.Update(updated, &currentETag)` re-validates via `computeStoredETag` (the same disk-bytes hash) at T3.

Because the if-match token (`currentETag`) is drawn from the *same on-disk source* that `Update` re-checks against, the check is **self-referential**: it passes by construction whenever disk is stable between T2 and T3. But the payload (`updated`) is a clone of the *stale T1 render* with only `Status` flipped. So when the parent's on-disk content has genuinely diverged from the in-memory render — an external edit that fsnotify hasn't reloaded yet, or a concurrent `nibs serve` mutation that landed after T1 — `Update` re-renders and overwrites the file with the stale clone, **silently discarding the divergent on-disk content with no error**.

This is a **regression** relative to the pre-fix code. The old `parentETag := parent.ETag()` derived the if-match from the in-memory *render*; any real on-disk divergence made that render-hash differ from `computeStoredETag`, so `Update` returned `ETagMismatchError` and aborted — spuriously failing the activation, but *preserving* the on-disk content. The fix trades a fail-safe spurious failure for a fail-open silent overwrite.

The new test `TestAutoActivationSucceedsWhenParentETagStale` **demonstrates and locks in** this behavior: it appends `\n<!-- external edit -->\n` to the parent file, drives activation, then asserts only `got.Status == "in-progress"`. It never asserts the appended comment survived — and it does not survive (`saveToDisk` re-renders the stale clone). The test therefore encodes the data-loss as expected behavior.

**Reachability (validator-confirmed):** real, not contrived. `nibs serve` (`cmd/serve.go`) dispatches GraphQL mutations goroutine-per-request against one in-process `Core`, and each of `Get`/`CurrentETag`/`Update` takes and releases `c.mu` independently — so a concurrent writer landing between steps is a live window in server mode. Single-process, a direct external file edit not yet reloaded by fsnotify reproduces the same loss (a supported workflow given the file-based design).

**Fix:** Note that broad-reviewer's `GetWithETag` (read nib + etag under one lock) is **insufficient** — the validator confirmed it only closes the narrower T1→T2 concurrent-writer race; a nib that diverged from disk *before* activation starts still passes an atomically-read if-match and still gets overwritten, because `computeStoredETag` never compares against the in-memory render. Options that actually address the root cause:

- **Preferred — fix the etag layer, not the call site.** This is the same root cause the prior review (`CODE_REVIEW_2026-07-04_21-36-03.md`, finding on `computeStoredETag`) already flagged: `computeStoredETag`/`CurrentETag` hash raw disk bytes while `ETag()` hashes the canonical render, so the two domains diverge on benign round-trip drift. Making the stored-etag hash the parsed-and-rendered canonical form (or persisting normalization at load) eliminates the divergence, so `parent.ETag()` becomes a valid if-match again and no per-call-site workaround (or clone-from-stale-snapshot) is needed. This fix removes the reason `activateParentChain` had to diverge at all.
- **If keeping a call-site fix:** re-read the parent's *current on-disk content* (re-parse) immediately before mutation and apply `Status` onto that fresh content, rather than cloning the stale in-memory snapshot; or compare render-hash vs disk-hash and abort/merge on real (non-formatting) drift instead of blindly proceeding.

Whichever path is chosen, the regression test must additionally assert that pre-existing on-disk content survives activation (not just that status flips).

---

### #2 🟢 Low: Two error paths emit identical, indistinguishable warning text

| | |
|---|---|
| **File** | `internal/graph/resolver.go:224, 233` |
| **Category** | error-handling / duplication |
| **Confidence** | 100 |
| **Found by** | quick-reviewer (Low), broad-reviewer (Low) |

**Issue:** The `CurrentETag`-failure path (L224) and the `Update`-failure path (L233) print the byte-identical `"warning: failed to activate parent %s (from %s): %v\n"`. Only the wrapped `%v` differs, so an operator scanning stderr cannot tell whether the *etag read* failed (e.g. parent deleted mid-chain) or the *write* was rejected (e.g. etag mismatch) without parsing the error text.

**Fix:** Differentiate the messages (e.g. `"warning: failed to read current etag for parent %s ..."` vs `"warning: failed to activate parent %s ..."`), and/or hoist a small `warn(err)` closure to remove the duplication.

---

## Pre-existing Issues

### P1 🟠 High: Sibling mutation sites still use `ETag()` + shared-pointer mutation before a fallible `Update`

| | |
|---|---|
| **File** | `internal/graph/resolver.go:128, 144`; `internal/graph/schema.resolvers.go:~413, ~435`; `cmd/close.go:~108` |
| **Category** | concurrency |
| **Found by** | quick-reviewer, consistency-reviewer, broad-reviewer (deferred) |

**Issue:** `validateAndAddBlocking`, `removeBlockingRelationships`, `AddBlocking`, `RemoveBlocking`, and `cmd/close.go`'s parent update all derive the if-match from `target.ETag()` on the shared `Get` pointer and mutate that shared pointer in place before a write that can fail — the same shape the fix removes from `activateParentChain`. These sites are untouched by this diff.

**Important caveat — do not blindly propagate the fixed pattern.** The `ETag()`-based if-match at these sites is actually the *concurrency-safe* choice: it aborts on real on-disk drift, avoiding exactly the data-loss described in finding #1. Naively rewriting them to the `CurrentETag`+clone pattern would spread that bug. The correct follow-up is to fix the etag-domain divergence at the source (see #1's preferred fix) and only then revisit the shared-pointer-mutation hygiene. Recommend a follow-up nib per CLAUDE.md's defer-large-findings convention.

### P2 🟡 Medium: Etag mismatch mid-walk silently aborts activation part-way up the chain

| | |
|---|---|
| **File** | `internal/graph/resolver.go:222-235` |
| **Category** | async / error-handling |
| **Confidence** | 75 (validated: confirmed, reclassified pre-existing) |
| **Found by** | adversarial-reviewer |

**Issue:** If a concurrent write to an ancestor lands between `CurrentETag` and `Update`, `Update` fails, the loop warns to stderr and returns — abandoning the rest of the upward walk and leaving an in-progress descendant under a still-todo grandparent, surfaced only as an unobserved stderr warning. The validator confirmed the mechanism **but** determined the warn-and-stop-mid-chain behavior predates this diff (the old code did `warn; return` on any `Update` error too); this diff only adds one more early-return path (`CurrentETag` error) and widens the race window marginally. Documented "best-effort ... stops on any error (same pattern as close)." Informational; consider surfacing partial-activation outcomes rather than stderr-only if this posture is revisited.

---

## Minor Findings

### Consistency

- `internal/graph/interfaces.go:20` — `CurrentETag`'s doc comment says "Used by bulk-reorder pre-validation," but this diff adds a second caller (`activateParentChain`); the comment now understates its call sites. (consistency-reviewer, confidence 100)
- `internal/graph/schema.resolvers_test.go:4033` — test comment says "reproduces nib e9oz," dropping the configured `nibs-` prefix; every sibling bug reference in the file uses the full prefixed ID (`nibs-d44y`, `nibs-j7ez`, ...). (consistency-reviewer, confidence 100)
- `internal/graph/schema.resolvers_test.go:4075` — the new `mustCreate` literals hand-write `Slug: "parent-epic"` / `"child-task"`, where every other `mustCreate` literal in the file omits `Slug` (or derives it via `nib.Slugify`). (consistency-reviewer, confidence 100)

### Testing Gaps

- `internal/graph/schema.resolvers_test.go:~4090` — the reload-only assertion does not isolate the clone-vs-shared-pointer half of the fix: a partial regression that keeps `CurrentETag` but drops `Clone()` would pass silently (test-reviewer traced this). Compounded by finding #1 — the test asserts only status, not content survival. Add a case that forces `Update` to fail *after* the fresh etag read and asserts the live (non-reloaded) `core.Get` still reports `todo`, plus a content-survival assertion. (test-reviewer)
- `internal/graph/schema.resolvers_test.go` — the two table cases (`requireIfMatch` on/off) exercise the same `Update` etag-mismatch branch (which is not gated by `requireIfMatch`), so the split adds marginal independent coverage over the parent-activation path. (test-reviewer, Low)

### Residual Risks

- `internal/graph/resolver.go:222` — each parent file is read + FNV-hashed twice per level (once in `CurrentETag`, again in `Update`'s `computeStoredETag`) across two separate lock acquisitions; bounded by hierarchy depth so not a felt regression, but a clean redundancy the single-critical-section fix in #1 would also remove. (performance-reviewer, confidence 100)

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| quick-reviewer | 3 | 0 |
| broad-reviewer | 3 | 0 |
| consistency-reviewer | 4 | 3 |
| adversarial-reviewer | 2 | 1 |
| design-reviewer | 1 | 0 |
| test-reviewer | 2 | 2 |
| performance-reviewer | 1 | 1 |
| knowledge-reviewer | 0 | 0 |
| go-reviewer | 0 | 0 |
| **Total** | **10** | |

Notes:
- **Issues Found**: total findings attributed to this agent (including shared findings).
- **Unique Issues**: findings reported ONLY by this agent.

---

## Specialist Notes

### Considered But Not Flagged (all agents)

- **`Clone()` correctness** (broad, quick, go, design): verified deep-copies `Tags`/`BlockedBy`/`Blocking`/`Documents`/`CreatedAt`/`UpdatedAt` and clears the load-boundary-only `priorityMigrated` flag; no aliasing between `updated` and `parent`. Cloning-before-mutate is the right call in isolation — the residual issue is only that the clone source (T1 snapshot) is stale, folded into #1.
- **Go idioms** (go-reviewer — no findings): `currentETag, err :=` legally reuses the outer `err` while declaring a new var; the inner `if err := Update(...)` shadow is idiomatic; `&currentETag` is a fresh per-iteration loop-local (`:=` inside the loop body) and `Update` dereferences it synchronously under lock without retaining it — no escape/aliasing hazard. Clean under golangci-lint.
- **Knowledge preservation** (knowledge-reviewer — PASS): the doc comment and test comment accurately and durably capture the render-hash-vs-disk-bytes decision and the clone invariant; no comment contradicts the code. (Note: the comment does not mention the concurrency non-guarantee behind #1 — see design-reviewer's API-contract angle, folded into #1.)
- **Cycle / infinite-walk, prefix-resolution mismatch, cross-iteration aliasing, concurrent same-parent activation** (adversarial): all constructed and fell apart — cycle detection upstream + the status guard terminate the walk; `Get` and `CurrentETag` share identical prefix-resolution; the write targets the clone so no ancestor aliasing.
- **TOCTOU between `CurrentETag`'s RUnlock and `Update`'s Lock** (quick, broad, design): the narrow gap itself fails safe (`Update` re-validates); the real defect is the mismatched *source* of etag vs. clone (#1), not the gap's existence.
- **Suppressed / self-referential-if-match as a standalone Medium** (design-reviewer, API_CONTRACT, anchor 75): merged into #1 as its mechanism rather than reported separately.

## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| etag stored-hash (`computeStoredETag`/`CurrentETag` raw-bytes vs `Render()`) | optimistic-concurrency | 2 | 2026-07-04 |

The prior review (`CODE_REVIEW_2026-07-04_21-36-03.md`) already flagged the underlying etag-domain divergence — `computeStoredETag`/`CurrentETag` hash raw disk bytes while `ETag()` hashes the canonical render — as a correctness/optimistic-concurrency defect, recommending it be fixed *in the etag layer* (canonicalize the stored hash or persist normalization at load). This fix worked around the same divergence at one call site instead, which is what opened finding #1. Addressing the root cause per the prior recommendation would resolve both.

## Session Metrics (--report)

Wave dispatched 9 reviewers in parallel (single message, synchronous), then 2 validators in parallel. Pre-flight gates ran once before the wave.

| Agent | Kind | Model tier | Tokens | Tool calls | Duration (ms) | Findings |
|-------|------|-----------|-------:|-----------:|--------------:|---------:|
| quick-reviewer | reviewer | mid (sonnet) | 85,445 | 19 | 301,281 | 3 |
| broad-reviewer | reviewer | mid (sonnet) | 116,597 | 15 | 409,965 | 2 |
| knowledge-reviewer | reviewer | session (opus) | 86,043 | 9 | 119,683 | 0 |
| consistency-reviewer | reviewer | mid (sonnet) | 111,052 | 34 | 390,078 | 4 |
| design-reviewer | reviewer | session (opus) | 55,293 | 5 | 169,877 | 2 |
| test-reviewer | reviewer | mid (sonnet) | 86,138 | 17 | 308,332 | 2 |
| adversarial-reviewer | reviewer | session (opus) | 60,077 | 9 | 163,774 | 2 |
| go-reviewer | reviewer | mid (sonnet) | 65,666 | 9 | 122,314 | 0 |
| performance-reviewer | reviewer | mid (sonnet) | 59,710 | 9 | 112,608 | 1 |
| finding-validator #1 (Critical) | validator | mid (sonnet) | 60,962 | 9 | 101,854 | confirmed |
| finding-validator #2 (mid-walk) | validator | mid (sonnet) | 58,639 | 12 | 109,743 | confirmed (→ pre-existing) |

- **Pre-flight gates**: `go build ./...` PASS · `go test ./internal/graph -run TestAutoActivation` PASS · `golangci-lint run ./internal/graph/...` 0 issues · `go vet ./internal/graph` clean.
- **Validation**: 2 dispatched, 2 confirmed, 0 refuted, 0 uncertain; 0 waived (corroborated), 0 over budget. Finding #1's Critical severity upheld; finding P2 reattributed pre-existing per validator.
- **Anomalies**: none. All figures are harness-reported verbatim.
