# Code Review

**Mode**: mid (explicit) | **Reviewers**: quick, broad, go, test, knowledge, design, adversarial, consistency, performance | **Date**: 2026-07-14
**Source**: local changes — branch `batch/buffer-safety-watch-cleanup` (uncommitted)
**Scope**: 3 files changed, +30/-68 lines
**Spec**: none found
**Validation**: 3 confirmed, 0 refuted, 0 uncertain (0 waived, 0 unvalidated)

## Agent Selection Rationale

Mode was given explicitly (`mid`), so Step 2a.5 selection was skipped.

- `quick-reviewer` (always) — review floor
- `broad-reviewer` (always) — review floor
- `go-reviewer` — Go files in changeset (hard gate); owns the lock-discipline/channel/defer lanes central to this diff
- `test-reviewer` — test files in changeset (hard gate); owns the central "was coverage lost?" question
- `knowledge-reviewer` — substantive change; the diff *deletes documentation* along with code
- `design-reviewer` — exported `Core.Watch` removed; concurrency surface touched
- `adversarial-reviewer` — ~98 changed executable lines (≥50 gate)
- `consistency-reviewer` — substantive change with a large sibling test cluster to compare against
- `performance-reviewer` — async/concurrent code (`handleChanges`, fan-out) present in diff
- `security-reviewer`: skipped — no security-adjacent surface (pure callback removal; no auth/crypto/user input/secrets/network)
- `spec-compliance-reviewer`: skipped — no spec available (hard gate); no `plans/` or `docs/` dir, no `--spec`, no PR-linked item
- `data-migration` / `dotnet` / `typescript` / `cpp` / `rust`: skipped — domain absent (hard gate)
- `prior-feedback-reviewer`: skipped — not a PR (hard gate)

**Model tiering (mid)**: judgment agents (`knowledge`, `design`, `adversarial`) inherited the session model; volume agents (`quick`, `broad`, `go`, `test`, `consistency`, `performance`) and all three validators ran mid-tier (`sonnet`).

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 2 |
| 🟡 Medium | 1 |
| 🟢 Low | 0 |
| 🔵 Minor | 2 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts the reported-but-non-blocking findings. Pre-existing issues are listed separately and excluded from both.

**Verdict**: ❌ NEEDS_CHANGES

The mechanical removal itself is **clean and correct** — all nine reviewers independently confirmed the callback plumbing is genuinely dead, lock discipline is unchanged, and no test coverage was lost. Every primary finding is a **factual inaccuracy in the newly-authored `StartWatching` doc comment**. All three are one-line comment edits; no code change is required.

---

## Findings

### #1 🟠 High: New `StartWatching` doc says internal state is "reloaded"; the code updates incrementally, and the sibling doc 140 lines below says so explicitly

| | |
|---|---|
| **File** | `internal/nibcore/watcher.go:103` |
| **Category** | comment-code-mismatch |
| **Confidence** | 100 |
| **Found by** | knowledge-reviewer (SHOULD→High), consistency-reviewer (Medium) — *severity dissent noted; highest kept* |
| **Validation** | CONFIRMED |

**Issue:** `// Internal state is reloaded (after debouncing) whenever nibs are created, modified, or deleted` directly contradicts `handleChanges`' own doc comment 140 lines below at `:243`: *"processes only the files that changed, updating state incrementally."*

`handleChanges` (`:244-346`) takes a `map[string]fsnotify.Op` of only the debounced paths and does targeted `delete(c.nibs, id)` / `c.nibs[newNib.ID] = newNib`. It never clears the map and never walks the tree.

The package **reserves** load/reload vocabulary for the full-scan path — `Load` (`core.go:150`, "reads all nibs from disk into memory") and `loadFromDisk` (`core.go:158-159`), which does `c.nibs = make(map[string]*nib.Nib)` (`core.go:162`) and `filepath.WalkDir`s the whole tree (`core.go:176`). Applying "reloaded" to "internal state" wholesale borrows that stronger, established vocabulary incorrectly.

**Why it matters:** "Reloaded" implies a full re-read that self-heals missed events. It does not. `handleChanges` only ever touches paths present in the `changes` map, so a nib the watcher missed stays stale **indefinitely** until an explicit `Update`/`Load` — there is no periodic or triggered re-scan. This is also precisely the wording that invites a "fan out, then async reload" restructure, which would break the ordering contract in finding #3.

Violates CLAUDE.md: *"Comments state what the code does and why."*

**Validator note:** the identical misconception existed pre-diff in the deprecated `Watch` doc, but this diff **re-authors** the sentence onto the canonical, non-deprecated entry point — arguably worse, since it now sits on the primary recommended API immediately adjacent to a doc that says the opposite. `pre_existing: no` upheld.

**Fix:**
```go
// StartWatching starts watching the .nibs directory ... for
// changes. Internal state is updated incrementally (after debouncing), per
// changed nib. Use Subscribe() to receive the resulting nib change events ...
```

---

### #2 🟠 High: New `StartWatching` doc claims subdirectories are watched; the walk is best-effort and start-time-only

| | |
|---|---|
| **File** | `internal/nibcore/watcher.go:102` (doc claim) vs `:125-132` (`WalkDir`) |
| **Category** | comment-code-mismatch |
| **Confidence** | 100 |
| **Found by** | knowledge-reviewer (SHOULD→High) — single finder |
| **Validation** | CONFIRMED (validator independently re-derived every claim) |

**Issue:** *"starts watching the .nibs directory and its subdirectories"* is a new, flat, unqualified claim. The code qualifies it twice:

1. The `WalkDir` is explicitly `// Watch all subdirectories (best effort - don't fail if any can't be watched)` with `_ = watcher.Add(path)` swallowing errors.
2. It enumerates only subdirectories existing **at call time**. `watchLoop` filters every event through `strings.HasSuffix(event.Name, ".md")` (`:194`) *before* any other processing, so directory-create events are discarded and no dynamic `watcher.Add` exists anywhere in `watchLoop`/`handleChanges`.

**Why it matters — verified reachable:** `.nibs/archive/` is created lazily. `Archive()` (`core.go:1028`) is the **only** place that `MkdirAll`s it; `Core.Init()` (`core.go:1195`), package `Init()` (`core.go:1222`), and `loadFromDisk` (`core.go:160`) do not. `cmd/root.go:68` calls `core.Load()` before `cmd/serve.go:107` calls `StartWatching()`. So on a project where no nib has ever been archived, `archive/` is absent at watch-setup time and is **never watched for the process lifetime** — even after a later `ArchiveNib` creates it. Direct/external edits to files under `archive/` are then silently invisible to the web UI, which does surface archived nibs (`ArchiveNib` mutation, `ActiveNibView` archive menu, `RowContextMenu`).

The `WalkDir` code is unchanged by this diff — the mismatch is new because the **new doc overclaims old code**. The adjacent code comment at `:125` already says "best effort"; the doc doesn't carry that nuance forward.

**Fix:**
```go
// StartWatching starts watching the .nibs directory, plus any subdirectories
// that exist when it is called (best effort; subdirectories created later are
// not watched), for changes. ...
```

---

### #3 🟡 Medium: Read-after-event ordering guarantee deleted; now documented nowhere, while a production consumer depends on it

| | |
|---|---|
| **File** | `internal/nibcore/watcher.go:102-105` (new doc) · `:342-345` (`c.mu.Unlock()` → `c.fanOut(events)`) |
| **Category** | knowledge-preservation |
| **Confidence** | 100 |
| **Found by** | knowledge-reviewer (MUST→Critical) — single finder |
| **Validation** | CONFIRMED — *severity corrected Critical → Medium on validator evidence* |

**Issue:** The deleted `Watch` doc carried: *"The internal state is automatically reloaded before the callback is invoked."* That is an **ordering contract** — when a notification is delivered, `c.nibs` already reflects the change. The code still honors it (`handleChanges` mutates under `c.mu`, unlocks at `:342`, then `fanOut`s at `:345`), but nothing marks that `Unlock`→`fanOut` sequence as load-bearing rather than incidental.

The replacement doc says only *"Use Subscribe() to receive the **resulting** nib change events"* — causality, not a happens-before/visibility guarantee. `Subscribe()`'s own doc (`:56-59`) and `fanOut`'s (`:82-83`) never mention it. A repo-wide grep for `before the callback` / `reloaded before` / `already reflect` / `committed before` returns **zero hits** post-diff (validator re-verified independently).

**Why it matters — production dependency verified:** `internal/tui/real_backend.go:132` translates `[]NibEvent` → bare `chan struct{}`, **discarding the payload entirely**; `internal/tui/tui.go:302` handles `nibsChangedMsg` by calling `a.backend.GetNib(...)` + `a.list.loadNibs`. `Core.Get` (`core.go:596-598`) reads `c.nibs` from memory under `RLock` — no disk re-read. The TUI is a pure read-after-event consumer whose correctness rests entirely on this ordering. A maintainer restructuring `handleChanges` to emit events before applying state would break it silently and intermittently.

**Severity correction:** the finder rated this MUST (→Critical). The validator confirmed every fact but judged Critical overstated — *"a documentation-only gap with no live bug and a one-comment fix; Medium seems more defensible."* Applied.

**Validator nuance on `pre_existing`:** the deleted sentence lived on the deprecated `Watch` callback path, and `Subscribe()`'s docstring never stated this ordering before *or* after the diff — so for Subscribe-based consumers (the TUI) the gap was already partially undocumented. This diff's actual contribution is **deleting the last textual trace of the invariant anywhere in the repo** — a genuine regression, just narrower than "introduced from scratch". Kept as `pre_existing: no`.

**Fix:** Add to `Subscribe()`'s doc (`:56-59`):
```go
// Internal state is committed before events are delivered: when an event
// arrives, Get/List already reflect it.
```
And at `watcher.go:344`, replace `// Fan out to subscribers (outside lock)` with a comment naming the ordering as load-bearing (subscribers such as the TUI discard the payload and re-read via `Get`/`List`, so events must never be delivered before `c.nibs` reflects them).

---

## Pre-existing Issues

Informational only — excluded from the verdict and Summary counts. Neither is introduced by this diff, but both live in the lifecycle this diff touches and are worth pairing with the already-planned `Unwatch`/`StopWatching` follow-up nib.

### P1 🟡 Medium: `Unwatch()` → `StartWatching()` restart orphans the old `watchLoop`, which then reads the *new* `c.done` and never exits

| | |
|---|---|
| **File** | `internal/nibcore/watcher.go:182` |
| **Category** | async / watcher lifecycle |
| **Confidence** | 100 (mechanism empirically demonstrated) |
| **Found by** | adversarial-reviewer |

**Issue:** `watchLoop` selects on `c.done` by re-reading the **field**, not a captured local. After `Unwatch()` closes `c.done` and `StartWatching()` assigns a fresh one, the orphaned loop reads the new (open) channel, never exits, never closes its fsnotify watcher. Two live loops then both call `handleChanges` → subscribers receive every event **twice**, plus a goroutine and fd leak.

**Evidence:** the adversarial reviewer's race detector fired on 3/8 runs and duplicate batches were observed for a single file write (probe run on an isolated copy; working tree left byte-identical).

**Reachability:** no caller restarts a watcher today — rated Medium on that basis alone. But `StartWatching`/`Unwatch` are exported and `internal/tui/backend.go:53` exposes `StartWatching()`/`StopWatching()` as a public pair, so the first caller that restarts inherits duplicate events and a leaked fd.

**Fix:** capture `done` as a local in `StartWatching` and pass it: `go c.watchLoop(watcher, done)`, so each loop selects on its own channel.

### P2 🟠 High: `Subscribe()` documents neither its drop semantics, nor that `Unwatch`/`Close` close the channel, nor that it silently registers when nothing is watching

| | |
|---|---|
| **File** | `internal/nibcore/watcher.go:56-60` |
| **Category** | api-contract |
| **Confidence** | 75 |
| **Found by** | knowledge-reviewer (SHOULD→High), design-reviewer (Medium) — *dissent noted; highest kept* |

**Issue:** Three undocumented behaviors on what this diff makes the **sole** notification path:

1. **Drops**: `fanOut` does non-blocking sends into a 16-buffer and discards batches for slow subscribers — documented only on the *unexported* `fanOut` (`:82-83`), not on `Subscribe()`, the doc a caller reads. Reachable: `real_backend.go:135` does a **blocking** `ch <- struct{}{}`; a TUI that stops draining backs up into core's 16-slot buffer, after which batches are dropped and the UI stays stale with no signal.
2. **Closure**: `unwatchLocked` (`:161-167`) closes *every* subscriber channel. After any `Unwatch()`, a `Subscribe()` holder sees a closed channel indistinguishable from "no events", with nothing telling it to re-subscribe.
3. **No watcher**: `Subscribe()` never consults `c.watching`. `cmd/serve.go:107` treats a `StartWatching()` failure as non-fatal (warns, keeps serving), so on `fsnotify.NewWatcher()` error (e.g. `fs.inotify.max_user_instances` exhaustion) every subsequent GraphQL `nibChanged` subscription (`internal/graph/schema.resolvers.go:855`) registers a subscriber that can never fire.

**Fix:** document all three on `Subscribe()`; optionally return an error/ok flag when `c.watching` is false so the resolver can surface "live updates unavailable".

---

## Minor Findings

### Consistency

- `internal/nibcore/core_test.go:683` — Converted `TestWatch` (`:683`) and `TestWatchDeletedNib` (`:718`) use `t.Fatal` on the select-timeout branch; the surrounding cluster uses `t.Error` — `TestSubscribe` (`:808`), `TestEventTypes` ×2 (`:919`, `:944`), `TestMultipleChangesInDebounceWindow` (`:1035`), `TestInvalidFileIgnored` (`:1112`), `TestRapidUpdatesToSameFile` (`:1175`). Only `TestSubscribeMultiple` (`:850`) uses `t.Fatalf`. **Orchestrator-verified independently** (see note below). (consistency-reviewer)
- `internal/nibcore/core_test.go:652` — `TestWatch` and `TestWatchDeletedNib` are named after the deleted `Watch()` API; both now call `StartWatching()`+`Subscribe()` exclusively. Sibling tests name themselves after a live API (`TestSubscribe`, `TestUnsubscribe`, `TestUnwatchIdempotent`, `TestClose`). (consistency-reviewer)

**Note on the `t.Fatal` item — reviewers directly contradicted each other, and the orchestrator adjudicated.** test-reviewer asserted the change was *"consistent with every other timeout branch in this file that already used `t.Fatal`"*; consistency-reviewer asserted seven siblings use `t.Error`. A direct grep confirms **consistency-reviewer is correct and test-reviewer's claim is false**. However, consistency-reviewer's proposed *fix* (revert to `t.Error`) is the wrong direction: `t.Fatal` is genuinely better here — the old code fell through to assert `Get` after a timeout, producing a redundant second failure — and `mentions_test.go:583`/`:621` and `migrate_test.go:230` already use `t.Fatal`, indicating a newer convention. **Recommendation: keep `t.Fatal`; the siblings are what should eventually change.** Retained as Minor to record the drift, not to request a revert.

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| knowledge-reviewer | 4 | 2 |
| consistency-reviewer | 3 | 2 |
| adversarial-reviewer | 1 | 1 |
| design-reviewer | 1 | 0 |
| quick-reviewer | 0 | 0 |
| broad-reviewer | 0 | 0 |
| go-reviewer | 0 | 0 |
| test-reviewer | 0 | 0 |
| performance-reviewer | 0 | 0 |
| **Total** | **7** | |

Notes:
- **Issues Found**: Total findings attributed to this agent (including shared findings)
- **Unique Issues**: Findings reported ONLY by this agent and no other

---

## Specialist Notes

### The author's "strictly lossier duplicate" rationale is factually wrong — but the conclusion holds

Three reviewers (knowledge, design, adversarial) **independently** converged on the same correction. The caller asked for this claim to be probed adversarially; it does not survive:

1. **"`fanOut` runs unconditionally on the same code path"** — **false**. `fanOut` returns early at `len(events) == 0` (`watcher.go:85-87`); the callback was invoked regardless. Non-empty `changes` routinely yields zero `events`: an unparseable filename (`id == ""`), a Remove for an id not in `c.nibs`, a Remove where `c.fileExists(path)` is still true (rename-then-create), or a `loadNib` error hitting `continue` (`:307-311`). In every one of those the callback fired and `fanOut` delivered nothing. The callback signaled *"disk changed"*; `Subscribe` signals *"in-memory state changed"* — **different predicates**.
2. **"strictly lossier"** — **false**. `fanOut` does a non-blocking send into a 16-buffer and **drops** for slow subscribers (`:92-99`). The callback was a direct synchronous call and could not be dropped. So the callback was lossier *in payload* but **lossless in liveness**.

**The removal remains correct**, for a *stronger* reason than the one given: `StartWatching()` passed `onChange = nil`, so `if callback != nil` was **never true in production** — a dead branch, not a live capability. No caller ever existed, the marker dates to the initial commit (`6319331`), it is an `internal/` package, and CLAUDE.md waives Go-API compatibility. Retaining it would have been speculative generality.

**Why this matters beyond pedantry:** the "strict superset" framing shouldn't be reused as precedent for reasoning about `fanOut`'s delivery guarantees — it *is* lossy, and it *does* have a real consumer (`real_backend.go:132-145` is exactly a ping-only consumer). A future consumer needing guaranteed delivery must know `Subscribe()` does not offer it. This is the substance behind pre-existing finding P2.

### Test-conversion claim — verified TRUE (test-reviewer, corroborated by go-reviewer)

The caller's central claim — that `TestWatch`/`TestWatchDeletedNib` were converted rather than deleted to preserve **store-state convergence** assertions — **holds**:

- `TestEventTypes`' delete sub-test (`:923-946`) only checks `e.Nib == nil` on the event; it never calls `core.Get("evt1")` to confirm the map entry is gone.
- `TestSubscribe` (`:763-810`) never calls `core.Get("new1")`.
- `TestMultipleChangesInDebounceWindow` checks `Get` convergence, but only for created / created-then-deleted-in-window nibs — **not** for a nib that existed *before* watching started and is deleted externally (the `del1` scenario), a distinct path through `handleChanges`' `if _, exists := c.nibs[id]` branch.

**No coverage was lost.** The old callback carried no payload and was never asserted on for content. `TestUnwatchIdempotent`/`TestClose` passed `func() {}` no-ops that were never asserted on, so dropping the parameter changes nothing observable.

**The conversion is tighter, not merely different.** The ordering is sound: state mutation happens before `c.mu.Unlock()`, `fanOut` after — so when `<-ch` unblocks, `core.Get` is guaranteed to observe the mutated map. Empirical flake hunt: `go test -race -count=20 -run 'TestWatch|TestWatchDeletedNib|TestUnwatchIdempotent|TestClose' ./internal/nibcore/` passed all 20 iterations under `-race` (7.3s), no flakes.

### Explicitly probed and cleared

- **Dead plumbing**: `grep -rn "onChange"` / `"\.Watch("` repo-wide returns zero references (the `cmd/body.go` hits are unrelated `sectionChanged` locals). Confirmed by orchestrator, quick, broad, go, design.
- **Lock discipline**: `c.mu.Unlock()` still immediately precedes `c.fanOut(events)` at the same point. The removed `callback := c.onChange` hoist was a plain field read inside the existing critical section; the deleted invocation ran *after* `fanOut`, outside any lock. No critical section widened or narrowed. `subMu` is acquired only in `watcher.go` (`:61, :71, :89, :162`); ordering is consistently `mu → subMu` with no inversion possible.
- **`unwatchLocked` no longer nils `onChange`**: moot — the field is deleted outright and its only reader is deleted in the same change.
- **"Calling it while already watching is a no-op"**: verified accurate against `:107-111` (`if c.watching { c.mu.Unlock(); return nil }`).
- **Double-close on test teardown**: LIFO gives `unsub()` → `Unwatch()`; both are safe in either order because `unsubscribe` guards on map membership (`:73`) and `unwatchLocked` deletes as it closes (`:163-166`).
- **Comment hygiene (CLAUDE.md)**: the surviving doc comment was checked character by character by three reviewers — no `legacy`/`previously`/`was`/`collapsed from`, no nib/issue IDs, no trace of the removed API, American English throughout. **Passes.** (The findings above are about *accuracy*, not provenance.)
- **`sync` import**: `var mu sync.Mutex` removal does not orphan it — `sync.WaitGroup` still used at `core_test.go:613`.
- **Path assertions**: no hardcoded separators introduced; `filepath.Join` used throughout.
- **Performance**: pure subtraction of work from the watcher path. No new query, loop, allocation, or contention pattern. Dropping `onChange func()` shrinks `Core` by one word — immaterial (long-lived singleton).

### Considered But Not Flagged

**Suppressed by the confidence gate** (below anchor 75, not Critical) — 3 findings:

- `core_test.go:652` — *TestWatch duplicates TestSubscribe's create-event scenario* (quick-reviewer, anchor 50). **Also contested**: test-reviewer's detailed cross-check established the converted tests assert store convergence, which `TestSubscribe`/`TestEventTypes` do not — a materially different thing. Suppressed on both grounds.
- `watcher.go:96` — *backpressured websocket client → resolver blocks → 16-slot buffer fills → `fanOut` drops batches → web UI permanently stale with no resync signal* (adversarial-reviewer, anchor 50, pre-existing). The underlying documentation gap is captured in P2.
- `core.go:1211` — *`searchIndex.Close()` error → `Close()` returns early → `unwatchLocked` never runs → `watchLoop` survives `Close()` and keeps calling `IndexNib` on a closed index; `serve.go:46` discards the error via `_ =`* (adversarial-reviewer, anchor 50, pre-existing).

**Examined and dismissed with sound reasoning** (orchestrator concurs):

- **`c.watching` desynchronizing from the `watchLoop` goroutine** (design-reviewer, anchor 25) — `watchLoop` returns on `!ok` from `watcher.Events`/`Errors` without clearing `c.watching`. Traced fsnotify v1.9.0: those channels close only via paths gated on `watcher.Close()`, which only `watchLoop`'s own `defer` calls — circular, unreachable today. Recorded because the invariant "`c.watching == true` ⟺ a `watchLoop` is running" is not enforced by construction.
- **`real_backend.Subscribe` translation goroutine leak** (adversarial) — only reachable at TUI exit, when the process is terminating.
- **Debounce timer split** (adversarial) — `Stop()` returning false after the AfterFunc fired puts Create and Write in separate batches; both are non-empty and correctly ordered, `Get` after `<-ch` still holds.
- **`status: open` in `TestWatch`'s fixture is not a valid status** (draft/todo/in-progress/deferred/completed/scrapped) — pre-existing, untouched by this diff.
- **`defer func() { _ = core.Unwatch() }()` swallows the error the old code asserted on** (knowledge, broad) — `TestUnwatchIdempotent`/`TestClose` still assert `Unwatch`'s error paths directly; the new pattern matches the pre-existing idiom in `TestSubscribe`/`TestSubscribeMultiple`/`TestUnsubscribe` and is more robust against goroutine leaks on `t.Fatal`.
- **`core.go:97` `// Event subscribers (for channel-based API)`** — the "channel-based" qualifier existed to contrast with the deleted callback field and now reads as vestigial, but remains literally true and contradicts no code. Stylistic residue.
- **`.nibs directory` wording though `c.root` is configurable via `nibs.path`** — matches existing local convention (`Unwatch` doc, struct field comment); not drift introduced here.
- **Tests not table-driven (CLAUDE.md)** — these are sequential timing/lifecycle tests where a table adds nothing; the diff converts existing tests rather than introducing new non-tabular ones.
- **`Unwatch`/`StopWatching` naming asymmetry** — declared out of scope by the caller; a follow-up nib is planned. No reviewer found incoherence beyond the naming itself; `real_backend.go:128-130` wraps it cleanly. **P1 above is worth pairing with that nib**, since it touches this exact lifecycle.

---

## Recurring Findings

Strict file+category matching against prior reviews in `.decaf/code-reviews/` yields no exact recurrence for this diff's findings. One **thematic** recurrence is worth surfacing:

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `internal/nibcore/core.go` | knowledge / overstated docs | 2 | 2026-07-05 |
| `internal/nibcore/watcher.go` | knowledge / overstated docs (this review, #1 + #2) | 1 | 2026-07-14 |

`internal/nibcore` has now produced **overstated/inaccurate doc comments** in two separate files across three reviews (`core.go`'s etag docs on 2026-07-05; `watcher.go`'s `StartWatching` doc today). Both instances follow the same shape: a doc comment claiming a stronger guarantee than the code delivers. Worth a standing habit of diffing new doc comments against the function they describe — particularly against sibling docs in the same file, which is exactly what caught #1.

Separately, `internal/nibcore/watcher.go | async / watcher-path persistence | 2 | 2026-07-04` is a prior recurrence at `:312` — a different line and category from P1's watcher-lifecycle issue at `:182`, so not counted as a match.
