# Code Review

**Mode**: mid (explicit) · roster cap 6 — 2 gate-matched agents dropped | **Reviewers**: quick, broad, typescript, test, design, knowledge | **Date**: 2026-07-15
**Source**: local changes — branch `batch/config-and-buffer-fixes` (uncommitted)
**Scope**: 6 files changed, +291/-12 lines (22 executable production lines; 228 added test lines)
**Spec**: none found (Step 1.5: no `--spec`, not a PR; the prior review `CODE_REVIEW_2026-07-15_17-49-25.md` is a review, not a spec — `spec-compliance-reviewer` hard-gated out)
**Validation**: 2 confirmed, 0 refuted, 0 uncertain, 1 waived (corroborated ×3), 0 unvalidated

## Agent Selection Rationale

Mode was **explicit** (`mid6`) — Step 2a.5 skipped. Roster cap **6** parsed and applied (Step 2b.5).

Changeset classification: **22 executable production lines** (the remainder of the production diff is comments — this is largely a *documentation* round, which the prior review's two findings asked for) plus **228 added test lines** across TypeScript and Svelte 5. Substantive, not mechanical. Data-mutation domain (the change gates whether a persistence mutation dispatches). API/contract surface changed (`ActiveViewDeps.confirm` signature; `ActiveView.save()` return contract). No untrusted-input parsing.

| Agent | Decision |
|-------|----------|
| `quick-reviewer` | included — always (floor) |
| `broad-reviewer` | included — always (floor) |
| `typescript-reviewer` | included — TS/JS files present (hard gate); ranked 1st by rule 1 (stack reviewer, dominant language) and owns the contravariance question |
| `test-reviewer` | included — test files present (hard gate); ranked 2nd by rule 2 (228 of 250 added lines are tests; test integrity was a named probe target) |
| `design-reviewer` | included — ranked 3rd by rule 2: the round's primary risk dimension is a contract change on a public interface, plus await-across-prompt concurrency |
| `knowledge-reviewer` | included — ranked 4th; normally last by rule 3, but elevated because this round **wrote a new interface contract** and comment truth is the stated dominant defect class (five knowledge-preservation findings in two days) |
| `adversarial-reviewer` | **dropped — roster cap (mid6)**: gate matched (data-mutation domain) but ranked 5th. Its ≥50-executable-line trigger did **not** fire (22 lines). ⚠️ **Coverage traded**: its lane is the "boundary inputs BETWEEN pinned cases" probe; that mandate was folded explicitly into `design` and `broad`, both of which returned a boundary matrix (see Considered But Not Flagged). |
| `consistency-reviewer` | **dropped — roster cap (mid6)**: gate matched but ranked 6th (rule 3 — lane overlaps `broad` most) |
| `security-reviewer` | skipped — no security-adjacent surface |
| `performance-reviewer` | skipped — no DB/ORM queries, loops with I/O, or caching logic |
| `spec-compliance-reviewer` | skipped — no spec available (hard gate) |
| `data-migration-reviewer` | skipped — no migration artifacts (hard gate) |
| `go` / `dotnet` / `cpp` / `rust` reviewers | skipped — no such files (hard gate) |
| `prior-feedback-reviewer` | skipped — not a PR (hard gate) |

**Model tiering (Step 2d, `mid` policy)**: judgment agents on the session model (`design`, `knowledge`); volume agents and both validators mid-tier `sonnet` (`quick`, `broad`, `typescript`, `test`).

**Natural ablation note**: the cap dropped `adversarial`, whose lane was explicitly reassigned. `design` and `broad` both returned boundary matrices covering the named cases (`gone→viewing` mid-await, `creating`, `closed`, concurrent `requestClose`), and `design` produced finding #3 from that lane. No evidence the drop cost a finding.

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 1 |
| 🟡 Medium | 2 |
| 🟢 Low | 0 |
| 🔵 Minor | 2 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts reported-but-non-blocking findings. Pre-existing issues are listed separately and excluded from both.

**Verdict**: ❌ NEEDS_CHANGES (one High among primary findings)

**The round's behavior is sound; its two enforcement mechanisms are not what the comments say they are.** Every claim about the `save()` gate held up under independent probing — both callers behave correctly, the `undefined` conflation is safe, nothing double-reports, and both mutation probes the implementer reported were reproduced exactly. The findings are: (#1) the `canSave` docblock asserts a compile-time guarantee TypeScript does not provide — verified false by three independent toolchain probes; (#2) the new render assertion cannot fail on the regression its comment names; and (#3) the round's savability predicate rests on a premise (`gone` ⟹ the nib no longer exists) that is false for the *archived* cause, foreclosing a save that previously succeeded.

---

## Findings

### #1 🟠 High: `confirm` docblock claims a compile-time guarantee TypeScript does not provide

| | |
|---|---|
| **File** | `web/src/lib/composables/useActiveView.svelte.ts:133-135` |
| **Category** | knowledge-preservation / false-contract (RULE 0) |
| **Confidence** | 100 (deterministic-claim safety net — doc-vs-code contradiction; corroborated ×3, validation waived) |
| **Found by** | knowledge-reviewer (MUST → Critical), typescript-reviewer (Medium) — **dissent noted below** |

**Issue:** The new docblock states:

> *"Required: an implementation that omitted the flag would silently offer the dead-end Save it exists to withdraw, **so the omission is a compile error**."*

The premise is true; the conclusion is false. **A required parameter binds callers, not implementations.** Via TypeScript's parameter-arity assignability rule, a zero-arg function is assignable to `(opts: { canSave: boolean }) => Promise<ConfirmChoice>`.

This was verified **three times, independently, via two toolchains, each with a negative control proving the checker was live**:

| Probe | Method | Result |
|---|---|---|
| knowledge-reviewer | `svelte-check` in an isolated worktree | impl omits param → **0 errors**; impl declares `{canSave: boolean}` and ignores it → **0 errors**; caller omits arg → `Expected 1 arguments, but got 0` |
| typescript-reviewer | `tsc --strict` + `@ts-expect-error` control | zero-arg impl type-checks cleanly; only omitting the `confirm` property entirely errors |
| orchestrator (this review) | `tsc --strict --noEmit` with **dual** `@ts-expect-error` controls | all three ignoring/omitting impls compile clean; both controls fired (exit 0) |

The only case the required param rejects is the one that **cannot occur today**: `guarded()` is the single caller, sits in the same file, and always passes the flag. The case the comment names — an implementation ignoring the flag — compiles clean.

**Why this is High rather than a nit:** the comment *retires the reader's vigilance*. The round's own rationale is that a fail-open default is a trap because a future implementer stumbles into it. This comment tells that future implementer the compiler is the backstop. Someone writing a second `confirm` implementation (test harness, Storybook stub, alternate host, or a refactor of `App.svelte`) reads "the omission is a compile error", writes `confirm: () => showMyDialog()`, and ships green through `svelte-check` and all 1249 tests — reinstating exactly the dead-end Save this round exists to withdraw. The real enforcement is the `toHaveBeenCalledWith({ canSave })` tests plus manual review; the comment actively suppresses that knowledge.

**Severity dissent (recorded, not resolved silently):** `knowledge-reviewer` filed this MUST (→ Critical under the normalization table); `typescript-reviewer` — the specialist whose domain the type system *is* — rated it Medium. Both agree completely on the underlying **fact**; they differ on stakes. Consolidated to **High**: it is a false safety claim on a public contract in this codebase's dominant defect class and should be fixed before merge, but it has **no runtime impact today** and marking it Critical would misrepresent it as a merge-blocking behavioral defect. Both ratings yield NEEDS_CHANGES regardless.

**Fix:** Replace the final clause with the enforcement boundary that actually holds:

```ts
 *  The required param binds CALLERS only (`confirm()` is a compile error), and
 *  guarantees an implementation that declares the param sees a defined boolean.
 *  It does NOT bind implementations: TypeScript accepts a zero-arg
 *  `() => Promise<ConfirmChoice>` here, so an implementation that ignores
 *  `canSave` compiles clean and silently offers the dead-end Save this flag
 *  exists to withdraw. Honoring it is a review obligation, not a compile-time one.
```

---

### #2 🟡 Medium: New `anv-editor-container` assertion is a false guard — it cannot fail on the regression its comment names

| | |
|---|---|
| **File** | `web/src/lib/components/ActiveNibView.svelte.test.ts:734` |
| **Category** | test-integrity / false-positive-test |
| **Confidence** | 100 |
| **Found by** | test-reviewer (Medium) · **validated: confirmed** (mutation probe independently reproduced) |

**Issue:** The 5-line addition asserts the editor never mounts on a `gone` buffer, and its comment claims this is "what keeps a save off a deleted nib at the render layer." The assertion is literally true but **passes for an unrelated reason**, so it cannot detect removal of the mechanism it documents.

`bodyModeEffective` is `disabled ? "preview" : bodyMode` (`ActiveNibView.svelte:157`); `bodyMode` initializes to `"preview"` for a non-create buffer (`:167-173`). The test uses `makeEditForm({ dirty: true })` (mode `"edit"`, so `isCreating` is false) and **never clicks `anv-edit-toggle`** — so `bodyMode` is `"preview"` throughout, wholly independent of `isGone`/`disabled`.

**Mutation evidence (reproduced twice — test-reviewer, then the validator independently):** mutating `bodyModeEffective` to `loadingUnseeded ? "preview" : bodyMode` — dropping **only** the `isGone` half, i.e. exactly the regression the surrounding comment warns about — leaves **all 52 tests passing**, including this assertion.

This is the session's fourth "guard that could never run." Per the consolidation rules a false-positive test is a defect, not a coverage gap, so it stays primary. `broad-reviewer` independently observed the same structural fact (anchor 50) but left it unflagged — a Step 5.5 cross-reference that corroborates the mechanics.

**Fix:** Toggle into edit mode *before* the buffer renders as `gone`, so the assertion actually exercises the override — e.g. render `viewing`, click `anv-edit-toggle`, then flip to `kind: "gone"` and assert the editor container disappears. Otherwise remove the assertion and its comment: as written it adds no coverage beyond the adjacent disabled-control assertions, while claiming to.

---

### #3 🟡 Medium: `gone` conflates DELETED and ARCHIVED — the round newly forecloses a save that previously succeeded

| | |
|---|---|
| **File** | `web/src/lib/composables/useActiveView.svelte.ts:433` (new `save()` gate) · `:325`/`:340-343` (`canSave: viewState.kind !== "gone"`) · `:127-135`, `:190` (docblocks) |
| **Category** | design / data-model |
| **Confidence** | 100 (deterministic-claim safety net — the contract's stated premise is contradicted by code; filed at anchor 50, **validated: confirmed** with a full independent re-derivation) |
| **Found by** | design-reviewer (Medium) — single finder |

**Issue:** The `gone` ViewState is a lossy union of at least two causes — **deleted** and **archived** — and this round newly promotes it to a *savability predicate* on a public contract. The gate, the `canSave` computation, and the docblocks all assert **gone ⟹ unsavable**:

> *"`canSave: false` means the buffer's nib no longer exists"* · *"a save against a deleted nib can only fail"*

**That premise is false for the archived cause**, and the validator re-derived the entire chain from code rather than accepting the finder's account:

- **The gate is net-new this round.** `git diff HEAD` confirms `save()` gained the `gone` refusal, `guarded()` gained the `canSave` threading, and `App.svelte`'s `confirmDiscard` changed from *unconditionally* including `saveLabel`/`saveAction` to omitting them. **Before this round, Save was always offered and always attempted.**
- **Reachable.** The Archive menu item's `disabled` binding is `isGone || loadingUnseeded` (`ActiveNibView.svelte:105`) — **not gated on `dirty`**. A user can archive a nib whose buffer is dirty. `handleArchive` then calls `view.requestClose()` on success → `guarded({type:"CLOSE"})` → dirty → the confirm dialog.
- **The backend accepts it.** `Core.Archive` (`internal/nibcore/core.go:1011-1044`) keeps the entry in `c.nibs` and only rewrites `Path`; `Core.Update` (`:866`) checks presence only, with no archived-state check; `saveToDisk` (`:933`) writes to the archive path successfully; the GraphQL `UpdateNib` resolver (`internal/graph/schema.resolvers.go:148`) has no archived rejection either. **A save against a just-archived nib is a real, technically-successful write path that this round forecloses.**
- The round's own new test comment (*"a dirty buffer's Archive/Delete succeeds and the handler calls requestClose()"*) treats Archive and Delete as the same cascade — corroborating both reachability and intent.

**Consequence:** for the Archive flow, the Save button is now structurally withdrawn and `save()` refuses, so **the only forward option destroys the user's unsaved edits** — where before they would have been saved successfully.

**Note on severity (transparency):** filed Medium at anchor 50, and per Step 5.6 a validator may not raise severity — so Medium stands. But the anchor-50 self-rating reflected *uncertainty in the chain*, and the validator resolved that uncertainty end-to-end. **Medium likely understates this**: a confirmed data-loss path on a reachable flow, newly introduced. The operator should weigh it above its rating.

**Contrary evidence against an established item (flagged as invited, not re-litigated):** reviewers were told *"the 'This nib was deleted' copy shown for an archived nib — known pre-existing."* The **copy** bug is indeed pre-existing. The finder's claim — upheld by the validator — is that this round extends the same conflation **from wrong copy to withheld behavior**. `pre_existing: false` was explicitly checked and confirmed correct.

**Fix:** Make savability an explicit property of the state rather than inferred from the `gone` tag. Either (a) carry the cause — `{ kind: "gone"; reason: "deleted" | "archived"; … }` — and derive `canSave` from `reason`, so an archived buffer keeps its Save and only a genuinely deleted one withdraws it; or (b) if archived buffers are *intentionally* unsavable, say so in the contract (`gone` = "not editable at its current location", not "no longer exists") and stop the docblocks from claiming deletion. Today the flag names a capability while `App.svelte` renders it as a cause.

---

## Minor Findings

### Consistency

- `web/src/App.test.ts:1025` — comment "Cancel out so the pending guard promise settles rather than leaking" misdescribes the real reason (test-reviewer, Low, anchor 75). `@testing-library/svelte`'s per-test unmount discards the App closure and any unresolved `pendingDiscardResolve` regardless; nothing awaits that promise, so a "leaked" one would simply be garbage-collected. The click itself is good practice — it closes the dialog deterministically during the test rather than at teardown, which is friendlier to the documented bits-ui deferred-timer hazard (`test-setup.ts`'s `afterAll`). Only the stated rationale is wrong. Suggested: *"Cancel out to close the dialog before the test ends, rather than leaving it open at teardown."*
- `web/src/lib/composables/useActiveView.svelte.test.ts:57` — the `confirm` mock is still typed `vi.fn<() => Promise<ConfirmChoice>>(...)`, a zero-arg signature that has now drifted from `ActiveViewDeps.confirm`'s `(opts: { canSave: boolean }) => …`. Promoted from dismissed items (Step 5.5): **four** agents independently noticed it (quick, broad, typescript, design) and all four dismissed it as cosmetic — correctly, on the merits (it type-checks via the same arity rule as finding #1; `vi.fn` records actual arguments regardless of declared arity, so `toHaveBeenCalledWith({ canSave: false })` genuinely asserts). Kept as Minor rather than dropped because it is a quotable fact and is directly downstream of the contract this round changed — and because it is the living proof of finding #1: the stub *should* have been updated, and nothing made it. Fix alongside #1.

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| quick-reviewer | 1 | 0 |
| broad-reviewer | 1 | 0 |
| typescript-reviewer | 2 | 0 |
| test-reviewer | 2 | 2 |
| design-reviewer | 2 | 1 |
| knowledge-reviewer | 1 | 0 |
| **Total** | **5** | |

Notes:
- **Issues Found**: total findings attributed to this agent (including shared findings and Minor).
- **Unique Issues**: findings reported ONLY by this agent.
- `quick` and `broad` each returned **zero primary findings** — assurance work, not idleness. Between them they independently cleared: the `undefined` conflation across both callers (no TOCTOU gap — the `gone` check and the `save()` call are synchronous with no intervening await); `useConfirmDialog.svelte.ts:54-56` fully replacing `saveLabel`/`saveAction` each call (no stale Save button can leak from a prior `canSave: true` invocation); the full comment-truth audit of the `App.svelte`/`ConfirmDialog` claims; and the boundary matrix. `broad` also produced the anchor-50 observation that corroborates #2.
- Verdict-driver concentration: the High came from `knowledge` + `typescript` jointly; both Mediums were single-finder (`test`, `design`) and both survived validation.

---

## Specialist Notes

### Considered But Not Flagged (all agents)

**`save()`'s overloaded `undefined` return — cleared by four agents independently.** The round's own "probe hardest here" item. `guarded()` checks `viewState.kind === "gone"` synchronously *after* `await deps.confirm(...)` resolves (`:340`) and returns `false` with `notifyError` **before** calling `save()`; no await separates the check from the call, so there is no race window. `handleSave` (`ActiveNibView.svelte:295`) gates on `isGone` before calling `view.save()`, likewise with no intervening await. Both sub-cases of `undefined` ("no buffer" / "gone") share one coherent meaning — *nothing was dispatched, the buffer is unchanged* — and every caller wants the identical response to both, so discriminating them would only be to re-merge them. `save()` never returns `undefined` for a genuine save failure (those return `{kind: "error"}`), so there is no conflation with real failures, no double-report (the single `notifyError` is pinned at `toHaveBeenCalledTimes(1)`), and no swallowed failure.

**Is the silent refusal a trap of the same shape as the fail-open default? No — the shapes are inverted.** (`design`, `broad`, concurring.) The `canSave` default failed **open**: omission produced an *active wrong action* (a real mutation at a deleted nib, stranded panel). `save()`'s refusal fails **closed**: it produces *inaction*; `undefined` is already in the declared return type so TypeScript forces every caller to confront it; and it only fires in a state where the UI already renders the form read-only behind a visible "This nib was deleted" notice, so a future caller's no-op is contextually explained on screen rather than mysterious. A future caller that skips the precheck loses a toast, not correctness. Anchor 25 — a plausible ergonomics critique, adequately documented, not a defect. *(Finding #3 is the real limit on that safety — not the silence, but the premise.)*

**Comment-truth audit — every other clause held.** Verified independently by `knowledge` and `broad`: "Both callers gate on `gone` before they get here" — **true**, grep confirms exactly two callers, both gated. "callers already treat as 'did not attempt' and abort on" — **true** of both. "a caller that must explain the dead end checks `state.kind === 'gone'` itself" — real and discoverable (`state` is on the public interface; `guarded()` is the worked example). "showConfirm nulls both, and ConfirmDialog gates its Save button on `onsave`" — **true** (`useConfirmDialog.svelte.ts:54-55`; `ConfirmDialog.svelte:58` `{#if onsave}`). "the same shape Delete/Archive confirms use" — **true**. `ActiveNibView.handleSave`'s "rendered controls that reach here are already gone-disabled" — **true of both paths** (Save button `:643` via `disabled = isGone || loadingUnseeded` at `:105`; the editor's `onsave` at `:793` mounts only when `bodyModeEffective === "edit"`, and `:157` forces `"preview"` whenever `disabled`). `guarded()`'s post-await cascade narrative — **reachable and accurate**. The `handleSave` comment is **honest about its own unreachability** — it scopes itself to a future path rather than implying live coverage.

**"pre-await" vs "AFTER the await" naming the same check.** `save()`'s docblock calls the guard's `gone` check "pre-await" (`:432`) while `guarded()`'s own comment calls it "Re-check `gone` AFTER the await" (`:329`). Opposite adjectives, same check — each correct in local context (before `await save()`; after `await deps.confirm()`), and the guard has exactly one `gone` check that calls `notifyError`, so the referent is unambiguous. Fails the durable-relevance gate — no wrong edit follows.

**Boundary matrix (the dropped `adversarial-reviewer`'s reassigned lane).** Pinned by new tests: pristine `gone`, dirty `gone`, `viewing→gone` mid-await. Cleared analytically: `closed` is covered by `save()`'s pre-existing `if (!f) return undefined` (a mid-await pristine `noteMissing`→CLOSE nulls `form`); a post-save buffer swap is covered by the pre-existing `if (form !== saved) return false`; `creating`/`viewing` correctly yield `canSave: true`; `closed` can never reach the prompt (`abandonsBuffer` requires `hasBuffer`). **`gone→viewing` mid-await** is structurally reachable through the reducer (`OPEN` on the same nibId is not an abandon and preserves the `edit:<id>` buffer key, so dirty edits survive) but needs an `open`/`syncTo` that the modal dialog blocks (`blocksHistoryNav` is true while dirty, freezing popstate); the outcome — a stale Discard-only prompt the user can still Cancel — honors intent. Nibs has no undelete/restore feature, so it is not reachable through any real product flow. Anchor 25. Concurrent `requestClose` → nibs-an5d, out of scope.

**Mid-prompt-vanish test determinism** (`useActiveView.svelte.test.ts:864`) — **not racy.** The `mockImplementationOnce` body has no internal `await`, so the synchronous `deleted = true` + `flushSync()` (driving the `$effect` bridge to `gone`) completes fully before the returned promise resolves and before `guarded()`'s continuation runs. Single-threaded JS guarantees the ordering.

**`openDirtyGone` helper's embedded assertions** — acceptable. `expect(view.noteMissing("n1")).toBe("kept")` inside a shared setup helper is a precondition/fail-fast check, not a silent-failure risk; a helper assertion failure surfaces as a normal test failure attributed via stack trace to the calling `it` block.

**`toHaveBeenCalledWith({ canSave: false })` — behavior, not implementation detail.** It tests the documented dependency-injection contract of `ActiveViewDeps.confirm` — the composable's sole channel for communicating savability to the host — which is appropriate given `confirm` is stubbed in composable unit tests.

**Both implementer mutation claims reproduced exactly** (test-reviewer, isolated worktree): `canSave` reverted to optional-defaulting-to-savable → **exactly 1 failure of 142** (`App.test.ts > "closing a dirty buffer whose nib vanished prompts Discard-only, then closes"`), and `svelte-check` reports **0 errors** on that broken implementation — proving the new `App.test.ts` coverage is *not* redundant with compile-time safety and catches a gap the stubbed-`confirm` composable tests structurally cannot see. `save()` gate removed → **exactly 1 failure of 56** (`"save() itself refuses a gone buffer…"`). A third, unrequested probe confirmed genuine defense-in-depth: removing `guarded()`'s own post-await branch (independent of `save()`'s gate) fails `"never fires a save against a gone buffer…"` specifically at its `notifyError` assertion — so the two gates are not redundant.

**Pre-existing, not flagged:** fire-and-forget `view.requestClose()` call sites (`ActiveNibView.svelte:374`, `:390`, `:605` — `onclick={() => view.requestClose()}` with no `.catch`) would surface a `deps.confirm()` rejection as an unhandled rejection, but this pattern predates the diff and this round adds no new throw path to `confirm()`. Same class as nibs-mpo4.

**Suppressed by the confidence gate:** 0 findings. (Two anchor-25 items — the silent-refusal ergonomics critique and `gone→viewing` mid-await — are recorded above as Considered But Not Flagged rather than suppressed findings.)

## Session Metrics (--report)

**Wave timing**: pre-flight gates 18:04:08 → reviewer wave dispatched ~18:06:00 [Estimate — derived from pre-flight completion plus recipe validation; the harness does not report dispatch wall-clock] → last reviewer returned ~18:15:30 [Estimate — dispatch + the longest reported reviewer duration, 571s] → consolidated ~18:17:00 → validation wave dispatched ~18:18:00 → validation done ~18:22:40 [Estimate — dispatch + longest validator duration, 278s] → file written 18:25:43 (measured)

| Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings submitted |
|-------|------|-----------|--------|-----------|----------|--------------------|
| quick-reviewer | reviewer | sonnet (mid) | 91,326 | 17 | 256.8s | 0 |
| broad-reviewer | reviewer | sonnet (mid) | 146,569 | 23 | 377.5s | 0 |
| typescript-reviewer | reviewer | sonnet (mid) | 117,247 | 24 | 349.8s | 1 |
| test-reviewer | reviewer | sonnet (mid) | 145,615 | 48 | 571.5s | 2 |
| design-reviewer | reviewer | session model (opus) | 119,109 | 35 | 477.9s | 1 |
| knowledge-reviewer | reviewer | session model (opus) | 117,800 | 15 | 296.6s | 1 |
| finding-validator (#2 editor-container) | validator | sonnet (mid) | 58,288 | 11 | 110.0s | verdict: confirmed |
| finding-validator (#3 archived/gone) | validator | sonnet (mid) | 103,143 | 32 | 278.1s | verdict: confirmed |

Reviewer subtotal: **737,666** tokens / 162 tool calls. Validator subtotal: **161,431** tokens / 43 tool calls. Wave total: **899,097** tokens / 205 tool calls.
*[Unverified] whether a subagent's reported token figure includes its own children — this caveat applies to every row and to both subtotals.* Orchestrator's own usage: not reported by the harness. Finding #1 consumed a third verification (orchestrator-run `tsc` probe) whose cost is not separately metered.

**Pre-flight gates**: `cd web && npx vitest run --reporter=agent` → **60 files / 1249 tests passed**; `cd web && npx svelte-check` → **0 errors, 0 warnings**. Both match the state the caller reported. Go gates not run — changeset is web-only (the Go layer was read by the #3 validator for evidence only).

**Anomalies**: **none.** No probe-protocol anomaly occurred. All six reviewers and both validators used isolated worktrees built from `git stash create`; each explicitly reported the shared tree intact; none observed the changeset as absent, reverted, or flapping. The shared working tree was byte-identical at review start and finish (6 files, +291/−12), and `git worktree list` shows no leaked probe directories. No dispatch retries, no unusable returns, no injected-content flags. Two orchestrator-side notes, neither an anomaly: (1) the caller named 5 files but the diff contains **6** — `ActiveNibView.svelte.test.ts` (+5) was also modified and was included in scope, and it is where finding #2 landed; (2) the changeset being uncommitted meant the naive `git worktree add … HEAD` recipe would have handed every reviewer the **pre-fix** tree — the known trigger for the "changeset is unimplemented" corruption seen in earlier waves. The orchestrator validated a `git stash create`-based recipe end-to-end (fix present, 56 tests green, shared tree untouched) **before** dispatch and issued it to every agent with a unique probe directory. Zero collisions.

---

## Recurring Findings

Matched on file path + category against the 30 prior reviews in `.decaf/code-reviews/`.

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `web/src/lib/composables/useActiveView.svelte.ts` | false contract on a public interface (comprehension-risk / knowledge-preservation) | 3 | 2026-07-14 |

**This is the third false-contract finding in this one file**, and the pattern is tightening rather than dispersing:

| Review | Location | Finding |
|---|---|---|
| `CODE_REVIEW_2026-07-14_21-58-30.md` | `useActiveView.svelte.ts:185-186` | comprehension-risk / false contract on a public interface |
| `CODE_REVIEW_2026-07-14_23-02-10.md` | `useActiveView.svelte.ts:323-325` | comprehension-risk / false contract |
| **this review** | `useActiveView.svelte.ts:133-135` | knowledge-preservation / false-contract (RULE 0) — finding #1 |

Note the recursion worth naming: the 07-14 finding sat at `:185-186` — the **`save()` interface declaration region that this very round was tasked with documenting** (prior-review finding #1, "`save()` is advertised as the shared save chokepoint but silently requires every caller to pre-check `gone`"). The round documented that contract correctly (every clause of the `save()` docblock was independently verified true — see Considered But Not Flagged) and introduced a *new* false contract 50 lines above it, on the sibling dep in the same interface. The defect class is not being retired by fixing instances of it; `ActiveViewDeps`/`ActiveView` docblocks are where this codebase's contract claims go wrong, and claims of *compile-time enforcement* deserve a probe before they are written, not after.

**Category-level pattern (not a strict file match, reported for completeness):** `false-positive-test` — a test that cannot fail on the regression it names — now has **4** occurrences across the web suite (`App.test.ts:182` on 2026-07-07; `useActiveView.svelte.test.ts:463` on 2026-07-14; `MarkdownEditor.test.ts:191` on 2026-07-14; `ActiveNibView.svelte.test.ts:734` today, finding #2). Different files each time, so it does not match the file+category rule, but four instances in nine days across four files is a suite-wide habit rather than four coincidences. Both of this review's non-contract findings (#2 and the `App.test.ts:1025` Minor) are assertions or comments that claim more than they establish.
