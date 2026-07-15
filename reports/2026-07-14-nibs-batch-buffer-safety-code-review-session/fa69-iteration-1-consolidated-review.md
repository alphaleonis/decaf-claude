# Code Review

**Mode**: mid (explicit) | **Reviewers**: quick, broad, knowledge, consistency, design, adversarial, test, typescript | **Date**: 2026-07-14
**Source**: local changes — branch `batch/buffer-safety-watch-cleanup` (uncommitted)
**Scope**: 7 files changed, +168/-6 lines
**Spec**: none found
**Validation**: 4 confirmed, 0 refuted, 0 uncertain (1 finding corroborated ×2 — not selected; 2 suppressed at the confidence gate)

## Agent Selection Rationale

Mode was **explicit** (`mid`) — not second-guessed.

**Included:**
- `quick-reviewer` — always (review floor)
- `broad-reviewer` — always (review floor)
- `knowledge-reviewer` — substantive change; the new interface contract carries behavioral decisions in dense doc comments
- `consistency-reviewer` — substantive change with close siblings to compare against (`syncTo`, the live-bridge `DELETED` dispatch, three duplicated `ActiveView` stubs)
- `design-reviewer` — the public `ActiveView` interface gains a method with a new return contract
- `adversarial-reviewer` — data-safety domain (unsaved-buffer preservation) plus ≥50 changed executable lines
- `test-reviewer` — test files present (hard gate)
- `typescript-reviewer` — TypeScript/Svelte files present (hard gate)

**Excluded:**
- `security-reviewer`: skipped — no auth/crypto/user-input/network/file-I/O/secrets surface in the diff
- `performance-reviewer`: skipped — no DB queries, I/O loops, data pipelines, or caching logic; the `queueMicrotask` is a scheduling deferral, not a throughput surface
- `spec-compliance-reviewer`: skipped — no spec available (hard gate); no `--spec`, no `plans/` or `docs/` directory, no PR-linked work item
- `data-migration-reviewer`, `dotnet-reviewer`, `cpp-reviewer`, `go-reviewer`, `rust-reviewer`: skipped — domains absent from the changeset (hard gates)
- `prior-feedback-reviewer`: skipped — local changes, not a PR (hard gate)

**Model tiering** (mid policy): judgment agents (`knowledge`, `design`, `adversarial`) inherited the session model; volume agents (`quick`, `broad`, `consistency`, `test`, `typescript`) and all four validators ran mid-tier (`sonnet`).

**Pre-flight gates**: `task test` — PASS. Go tests all ok; `svelte-check` 4737 files / 0 errors / 0 warnings; vitest 60 files / 1219 tests passed. Ran once for the wave.

**Working-tree integrity**: the test-reviewer reported transient untracked probe files (`__tmp_review_probe.test.ts`, `zz_probe.svelte.test.ts`) appearing during the wave from sibling agents' non-destructive probes. Verified post-wave: `git status --porcelain -uall` shows only the 7 intended modified files, and `git diff HEAD --stat` matches the original diff byte-for-byte. Nothing leaked.

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 3 |
| 🟡 Medium | 1 |
| 🟢 Low | 0 |
| 🔵 Minor | 2 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts the reported-but-non-blocking findings. Pre-existing issues are listed separately and excluded from both.

**Verdict**: ❌ NEEDS_CHANGES

**The core data-safety claim holds.** Four reviewers independently attacked "the dirty buffer is preserved" — including a presenter-level runtime probe and a revert-probe of the dirty gate — and **none could destroy a dirty buffer through the new code**. All three High findings are documentation/contract defects on a mechanically correct fix. They are cheap to fix (three comment edits, optionally one extra return token).

---

## Findings

### #1 🟠 High: `syncTo`'s "SOLE guard-bypass" annotation is now a false contract

| | |
|---|---|
| **File** | `web/src/lib/composables/useActiveView.svelte.ts:172` |
| **Category** | knowledge-loss / api-contract |
| **Confidence** | 100 |
| **Validation** | CONFIRMED |
| **Found by** | broad-reviewer (High), consistency-reviewer (Medium), design-reviewer (Low) |

**Issue:** The `ActiveView` interface still documents `syncTo` as:

```ts
/** The SOLE guard-bypass: popstate / multi-select desync (history already moved). */
syncTo(nibId: string | null): void;
```

This is unchanged context in the diff. Immediately below it, the diff adds `noteMissing`, whose implementation dispatches `apply({ type: "DELETED" })` (line 623) and `apply({ type: "CLOSE" })` (line 626) — both bypassing `guarded()`. Its own inline comment says "Deliberately unguarded". Two comments in the same file now contradict each other, and the "SOLE" annotation — the audit anchor for enumerating bypass sites — no longer enumerates them truthfully.

The `syncTo` misuse this whole change exists to fix was itself enabled by treating that annotation as the authoritative bypass inventory. Leaving it false re-arms the same trap.

**Severity dissent, adjudicated:** design-reviewer rated this Low, arguing the bypass is *vacuous*: `abandonsBuffer(s, DELETED)` always hits `default: return false`, and the `CLOSE` branch only runs when `form?.dirty` is falsy — so routing either branch through `guarded()` would behave identically. The validator confirmed that mechanism is correct, **and** confirmed it is a severity mitigant rather than a refutation: line 626 dispatches `CLOSE` — an action that *is* in `abandonsBuffer`'s switch — through `apply()` directly, which is precisely what "SOLE" claims exists nowhere else.

The validator also checked and **rejected** a pre-existing reattribution: the live bridge's pre-existing `if (l.deleted) apply({ type: "DELETED" })` (line 458) does not falsify "SOLE", because `DELETED` is never a guardable action. `noteMissing`'s `CLOSE` dispatch is the first genuine second site, and it is wholly new in this diff.

**Fix:**
```ts
/** A guard-bypass: popstate / multi-select desync (history already moved). The
 *  only transition that may ABANDON a dirty buffer without a confirm — see also
 *  `noteMissing`, which bypasses the guard only where it provably cannot fire. */
syncTo(nibId: string | null): void;
```

---

### #2 🟠 High: `noteMissing`'s `"kept"` collapses two structurally different outcomes; the JSDoc documents only one

| | |
|---|---|
| **File** | `web/src/lib/composables/useActiveView.svelte.ts:174-182` (contract), impl at `:613-628` |
| **Category** | api-contract |
| **Confidence** | 100 |
| **Validation** | CONFIRMED |
| **Found by** | knowledge-reviewer (High), design-reviewer (Medium), broad-reviewer (Low) |

**Issue:** The return union has two tokens but three outcomes:

- pristine → `"closed"`
- dirty → `"kept"` (buffer genuinely preserved in `gone`)
- **stale report → `"kept"` (nothing kept, nothing touched, view is on a different nib)**

The JSDoc defines `"kept"` *exclusively* as the dirty case — "transition to `gone`, preserving the unsaved edits behind the read-only deleted notice" — then describes the stale case in a trailing sentence that **never states which token it returns**. A consumer reading the contract cannot determine the stale return value, and the stated meaning of `"kept"` is false for it.

The caller already reads the token through the wrong lens. `App.svelte:295-297` justifies its early-return with "A kept (dirty) buffer stays on screen with the user's edits, so the selection and `?nib=` URL still describe what is shown" — which is *not* why the stale case must skip healing. In the stale case the URL describes nib **B**, not `id`. Behavior is correct today only because both cases coincidentally want "do nothing". Any future work added to the `!== "closed"` branch — focus the deleted notice, log "edits preserved", offer to re-create the nib — fires wrongly for a stale report about a nib that is not on screen.

**On the latch-leak mechanism:** design-reviewer argued the stale branch returns `"kept"` without calling `apply`, so `viewState` never changes, so App's effect never re-runs, so `reportedMissingFor` stays pinned to an id whose report was dropped — permanently suppressing a needed report. The validator traced this and found the reducer path sound (`OPEN` goes `viewing(A) → viewing(B)` without passing through a latch-clearing non-`viewing` state) **but could not construct a realistic route into the effect-flush→microtask window** — matching adversarial-reviewer's independent finding, which dropped the same cascade at confidence 25. **Treat this as a documentation/contract defect, not a live bug.** The three-token fix closes the theoretical hole for free.

**Fix (either is sufficient):**

Minimal — make the stale case explicit and widen `"kept"`'s stated meaning:
```
 *    - stale (the view already moved off nibId) -> "kept": no state change.
 *  "kept" means only "the view was NOT closed" — do not read it as "unsaved
 *  edits for nibId are on screen"; that holds for the dirty case only.
```

Preferred — add the third token so the distinction is machine-checkable and the latch can be cleared on stale:
```ts
noteMissing(nibId: string): "closed" | "kept" | "stale";
```

---

### #3 🟠 High: the rewritten comment deletes the only record that the pristine live-deletion path still diverges

| | |
|---|---|
| **File** | `web/src/App.svelte:270-272` |
| **Category** | knowledge-loss |
| **Confidence** | 75 |
| **Validation** | CONFIRMED |
| **Found by** | knowledge-reviewer (High) — single finder |

**Issue:** The diff removes this sentence:

> *"Distinct from the deleted-while-viewing `gone` state, which keeps the (cached) nib on screen."*

That was the only place recording that two independent signals report the same real-world event with **different outcomes**. The change makes the two paths agree **only for a dirty buffer**; the pristine divergence is untouched and is now unrecorded anywhere:

- `useActiveView.svelte.ts:458` — `if (l.deleted) apply({ type: "DELETED" })` has **no dirty gate**, so pristine + live-deleted → `gone` (notice on screen, no toast, `?nib=` **not** healed).
- `noteMissing` pristine → `closed` + toast + healed URL.

The replacement prose points the reader the other way: "`view.noteMissing` owns the outcome" is true only of the effect's own path — when the live subscription wins, the effect early-returns on `s.kind !== "viewing"` and `noteMissing` is never called at all. The `noteMissing` JSDoc reinforces the false model with "Agrees with the live-subscription deletion path, so whichever signal arrives first yields the same outcome" — accurate, but scoped by indentation to the dirty bullet only.

**Competing assessment, adjudicated:** adversarial-reviewer examined the same divergence and declined to flag it, arguing the two signals never race because urql's document `cacheExchange` invalidates only on mutation results. The validator confirmed that reasoning is correct **but that it does not refute the finding**: it shows only that the two signals don't literally race for an out-of-band deletion. The divergence itself remains real and commonly reachable — a pristine nib being live-viewed while someone else deletes it routes through the bridge only and deterministically lands in `gone`, which is exactly the outcome the deleted sentence documented.

The validator also weighed the counter-argument that the removed sentence was *made wrong* by the change (`gone` is now an outcome **of** this path, not "distinct from" it) and concluded: the literal "Distinct from" framing is indeed stale, but the substantive fact it carried survives and needs re-recording in updated form.

**Fix:** Append to the `App.svelte:270-272` block:
```
// Only reached when the detail query is the first signal. A live-subscription
// deletion (useActiveView's bridge) applies DELETED with no dirty gate, so a
// PRISTINE nib deleted that way lands in "gone" instead of closing — the
// close/heal/toast below is not the only outcome for a missing nib.
```

Also consider un-scoping the `noteMissing` JSDoc's "Agrees with the live-subscription deletion path" so it states the agreement holds for the dirty case only.

---

### #4 🟡 Medium: the `gone` + `syncTo(sameId)` self-heal is documented but pinned by no test

| | |
|---|---|
| **File** | `web/src/lib/composables/useActiveView.svelte.test.ts` (gap); mechanism at `web/src/lib/composables/activeView.ts:67-68` |
| **Category** | test-coverage |
| **Confidence** | 75 (promoted on agreement) |
| **Validation** | corroborated ×2 — not selected for validation |
| **Found by** | broad-reviewer (Medium), test-reviewer (Medium) |

**Issue:** `reduce()`'s `OPEN` case does not special-case `s.kind === "gone"` — it unconditionally returns `{ kind: "viewing", ... }`. `App.svelte`'s `onPopState` calls `view.syncTo(selection.selectedNibId)` **unconditionally**, even when `nav.handlePopState` took the `isBlocked()` branch that intentionally leaves `selectedNibId` untouched so Back/Forward is a no-op while a dirty buffer blocks navigation. `blocksHistoryNav` is true for exactly the `gone` + dirty case this fix produces.

So: dirty `gone` buffer on screen → user presses Back → `isBlocked()` re-anchors on the same id (intending a no-op) → the following `syncTo(sameId)` still flips `gone → viewing`, momentarily un-marking the nib as deleted/read-only.

This self-heals: the missing-nib effect re-fires (the latch was reset to `null` on entering `gone`), re-detects the missing nib, and re-applies `DELETED` — all within the same microtask drain, before paint. Both adversarial-reviewer and design-reviewer independently traced the bounce and confirmed it converges in one cycle with the buffer intact (`bufferKey` is `edit:<id>` for both states, so `reconcileBuffer` never rebuilds the form). **No data loss, no visible flicker.**

The problem is that this convergence is asserted only in a code comment. No test — old or new — exercises `gone` + `syncTo(sameId)`. `App.test.ts:957` covers Back/Forward only for retargeting to a *different* nib. A future change to `bufferKey`, the latch-clearing logic, or the blocked-history-nav wiring could silently regress the invariant with nothing failing.

Note this is a route the **old** code lost the buffer on (`syncTo(null)`) — the diff fixes it. It deserves a test precisely because it is newly correct.

**Fix:** Add to `describe("createActiveView · missing nib")`:
```ts
it("survives a same-id resync while gone: keeps the buffer and re-converges", async () => {
  // open n1, dirty it, noteMissing("n1") -> gone
  // then view.syncTo("n1") — the blocked-popstate bypass shape
  // assert the form instance and its edits survive the gone -> viewing -> gone bounce
});
```

---

## Pre-existing Issues

Issues in code this change did not introduce. Informational only; excluded from the verdict and Summary counts.

### P1 🟡 Medium: Archive/Delete with a dirty buffer can strand the panel open on the just-deleted nib

| | |
|---|---|
| **File** | `web/src/lib/components/ActiveNibView.svelte:359-389` |
| **Category** | cascade / error-handling |
| **Confidence** | 75 |
| **Validation** | CONFIRMED — **reattributed to pre-existing** |
| **Found by** | adversarial-reviewer (Medium, originally claimed not-pre-existing) |

**Issue:** User has a dirty buffer → invokes Archive/Delete → the mutation **succeeds** → the handler calls `view.requestClose()`, which routes through `guarded()` and prompts "Unsaved changes" → the nib vanishes underneath → dirty routes to `gone` → user picks **Save** → `save()` errors ("not found") → `guarded()` returns false → `nav.closePanel()` never runs → the panel is stranded open on the nib the user just deleted, with Back/Forward frozen (`blocksHistoryNav` stays true while `form?.dirty`).

**Reattribution rationale (validator):** adversarial-reviewer marked this `pre_existing: false`, reasoning that the old code's unconditional `syncTo(null)` would have closed the panel. The validator refuted that: `ActiveNibView.svelte` is **not in this changeset's 7 touched files**, and the exact `gone` + dirty + refused-Save cascade was already fully reachable pre-diff via the unmodified live-subscription bridge (`useActiveView.svelte.ts:451-474`). `deleted` events are never self-echo-suppressed — `nibChange.ts`'s `classifyNibEvent` short-circuits on `selfEtag` only for `created`/`updated`, not `deleted` — so a user's **own** delete pushes a `deleted` event back through their own live subscription, flipping `viewing → gone` before the detail query ever reports. The old code's own comment documented this ("distinct from the deleted-while-viewing `gone` state") and its `if (s.kind !== "viewing") return` guard meant it never interfered once the bridge had already flipped the state.

This diff only converges a second, redundant detection path onto the **same** outcome the live path already produced. This is the scenario the review brief already carved out as pre-existing.

**Escape hatch:** the close X (line ~598) carries no `disabled` binding, so X → Discard always works. That makes it a nuisance rather than a trap — but a confusing one.

---

### P2 🟡 Medium: the preserved `gone` buffer is read-only to the point of being unrecoverable

| | |
|---|---|
| **File** | `web/src/lib/components/ActiveNibView.svelte:105` |
| **Category** | usability / data-recovery |
| **Confidence** | 75 |
| **Found by** | adversarial-reviewer (Medium, pre-existing) |

**Issue:** `noteMissing` preserves the dirty buffer into `gone`, but `disabled = $derived(isGone || loadingUnseeded)` makes every control read-only — including the Discard button (line 648) and the body, which `bodyModeEffective` (line 157) flips to rendered-markdown preview. So the preserved markdown source is **displayed but not recoverable**: it cannot be saved, cannot be selected out of the `disabled` title/tag/status inputs (HTML `disabled` blocks text selection; `readonly` would not), and cannot be reverted.

This is pre-existing — the `gone` state and its `disabled` gating predate the change, reachable via the live-subscription path. But the change **substantially widens the population** that lands here: `gone` + dirty is now an ordinary outcome of a stale deep link, not just a live-subscription race. Worth a follow-up nib.

**Fix:** Render `gone` with `readonly` rather than `disabled` on the text inputs (readonly permits selection/copy), keep the body reachable in raw markdown, or add an explicit "Copy body" action to the deleted notice — so the preserved edits have at least one exit path other than Discard.

---

### P3 🟢 Low: `gone` + dirty + `requestClose()` still offers a Save that cannot succeed

| | |
|---|---|
| **File** | `web/src/lib/composables/activeView.ts:98-110` (`abandonsBuffer`), `web/src/lib/components/ActiveNibView.svelte:337-339` |
| **Category** | error-handling |
| **Confidence** | 100 |
| **Found by** | broad-reviewer (Low, pre-existing) |

**Issue:** `abandonsBuffer(gone-state, CLOSE)` is `true` via `hasBuffer`, so `requestClose()` on a dirty `gone` buffer routes through `guarded()` and offers Save/Discard/Cancel — where Save cannot succeed against a deleted nib. Confirmed exactly as the review brief anticipated; recorded here for completeness. The caller indicated they will file this.

---

## Minor Findings

### Consistency

- `web/src/App.test.ts:153` — the new `__vanishNib` / `__restoreVanishingNib` module-export + `import * as urqlMock` + `as unknown as {...}` double-cast departs from this suite's established `vi.hoisted()` shared-mock-state convention, cited across 5 agreeing siblings (`RowContextMenu.test.ts:19`, `dispatcher.test.ts:16`, `clipboard.test.ts:3`, `ActiveNibView.svelte.test.ts:15,29`, `MarkdownEditor.test.ts:12`). No other test file in the repo re-imports a mocked module via `import * as X` to reach hidden test hooks. (consistency-reviewer, anchor 100 — quotable-fact safety net.) *Note: typescript-reviewer independently examined the double-cast and cleared it as a self-checking pattern that masks no real defect — the objection is convention drift, not type safety.*
- `web/src/lib/composables/useActiveView.svelte.ts:178` — "preserving the unsaved edits behind the read-only deleted notice" attaches *read-only* to the **notice** (trivially true of a `<div>`). The load-bearing fact is that the whole form goes read-only (`ActiveNibView.svelte:105`), with both recovery controls gated off on `isGone` (`:328`, `:339`). So `"kept"` means *displayed for copy-paste salvage*, not *recoverable* — and `disabled` inputs block even that (see P2). Suggest: "preserving the unsaved edits on screen. The gone state renders read-only, so the edits are salvageable by copy-paste only — `"kept"` is not `"recoverable"`." (knowledge-reviewer)

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| quick-reviewer | 0 | 0 |
| broad-reviewer | 3 | 1 |
| knowledge-reviewer | 3 | 2 |
| consistency-reviewer | 2 | 1 |
| design-reviewer | 2 | 0 |
| adversarial-reviewer | 2 | 2 |
| test-reviewer | 1 | 0 |
| typescript-reviewer | 0 | 0 |
| **Total** | **9** | |

Notes:
- **Issues Found**: total findings attributed to this agent (including shared findings)
- **Unique Issues**: findings reported ONLY by this agent

---

## Specialist Notes

### Adversarial depth tier: deep

All four techniques ran; cascade chains traced end-to-end and validated with a throwaway presenter-level probe (`createActiveView` + stubbed deps, since removed; tree verified byte-identical afterward).

**The central claim — "the dirty buffer is preserved" — holds on every route constructed.** No reviewer could destroy a dirty buffer through the new code:

- `gone` → re-entering `viewing` (via `open()` or the `syncTo` popstate bypass) keeps `bufferKey() === "edit:<id>"`, so `reconcileBuffer()` early-returns and the form instance survives (probe: `form preserved: true`). It re-reports and converges back to `gone` — no loop, no loss.
- A second `noteMissing` while already `gone` returns `"kept"` and is a no-op (probe confirmed).
- The `reportedMissingFor` latch reset on `gone` is safe — it only re-arms a report that reaches the same decision.
- The `queueMicrotask` window is not exploitable: verified in `node_modules/@urql/svelte/dist/urql-svelte.mjs` that `queryStore` delivers `fetching: true` on its **first** subscriber emission (the wonka `fromValue({fetching:true})` fires inside svelte's `writable` start fn, before `run(value)`), so a target swap or the create hand-off never produces a transient `(fetching:false, error:undefined, nib:null)` tick. The `pause:true` store *does* emit that signature, but only when `detailTargetId` is null (`closed`/`creating`), which `s.kind !== "viewing"` already excludes.
- `form?.dirty` cannot be sampled transiently-clean: every dirt-clearing call (`applyExternal` in the live bridge, the F1 effect, the detail seed) is itself gated on `!dirty`.
- The stale-report `"kept"` → caller-skips-heal path is correct, not a URL leak: the view is on B (or closed), and both of those already own their URL.

### Regression-guard verification (test-reviewer, empirical)

A revert-probe replaced `noteMissing`'s dirty gate with an unconditional `apply({type:"CLOSE"}); return "closed";` (stale check left intact), re-ran the affected suites, then restored the file to its exact original bytes (`git diff --stat` confirmed). Both new dirty-path tests failed exactly as intended:

- `useActiveView.svelte.test.ts > routes a DIRTY buffer to gone…` → `AssertionError: expected 'closed' to be 'kept'`
- `App.test.ts > keeps a DIRTY buffer when the viewed nib vanishes…` → timed out waiting for `anv-deleted-notice`

**Both are genuine regression guards, not false positives.** Also cleared: `expect(view.form).toBe(f)` identity is sufficient (no code path wipes the form's fields in place while keeping the reference, since `bufferKey` is unchanged across the transition); the `window.location.search` assertion is a real discriminator (without the fix, `nav.replaceClosed()` would clear `?nib=`); the module-level `vanishingDetailData` reset in `beforeEach` is correctly ordered and sufficient (no `.concurrent`/`.only` in the file); and the three hardcoded `noteMissing: () => "closed"` stubs pose no false-positive risk (neither `ActiveNibView.svelte` nor `RowContextMenu.svelte` ever calls `.noteMissing()`).

### Considered But Not Flagged

**Suppressed by the confidence gate (2 findings at anchor 50):**
- `syncTo(sameId)` bouncing a dirty `gone` buffer back to `viewing` **as a behavior defect** (broad-reviewer, Medium/50, marked pre-existing). Adversarial and design both traced it independently and concluded it converges in one cycle before paint with the buffer intact. Retained as a *test-coverage* finding (#4), where the two-finder agreement promoted it to 75.
- The `if (s.kind !== "viewing")` guard serving triple duty, coupling latch correctness to which internal state `noteMissing`'s dirty path targets (design-reviewer, Medium/50, EVOLUTION_READINESS). Proposed fix — move the report bookkeeping inside the presenter so the latch leaves `App.svelte` entirely — is a reasonable follow-up but architectural, not a defect.

**Examined and cleared:**
- **`form?.dirty` optional chaining** (typescript-reviewer): `dirty` is `readonly dirty: boolean` on the shared `NibFormFields` interface, implemented once as a plain non-`$derived` getter on `BaseForm` (`nibForm.svelte.ts:192-203`), inherited unmodified by both `CreateForm` and `EditForm`. Never `undefined` on a real form. The only `undefined` read is `form === null`, which `reconcileBuffer()` (synchronous, at the tail of every `apply()`) makes impossible whenever `viewState.kind === "viewing"`. **No data-loss path through the diff's most safety-critical expression.**
- **`$state.raw` reads from inside `queueMicrotask`, outside any `$effect`** (typescript-reviewer): `dirty` is an un-memoized getter, not `$derived`, so every read recomputes from live `$state` fields; no rune-tracking staleness window tied to reactive context. Precedent: `guarded()`, `canSurface()`, and `blocksHistoryNav` all already read `.dirty` synchronously outside effects.
- **`satisfies ActiveView` literal-type preservation** (typescript-reviewer): verified with an isolated `tsc --strict` probe on this project's `typescript@6.0.2` that the stub's arrow return type stays `"closed"`, not widened to `string`.
- **`s.nibId !== nibId` narrowing** (typescript-reviewer): `s.kind !== "viewing"` short-circuits the `||` before `s.nibId` is evaluated, so `gone` (which also carries `nibId`) is excluded by the first operand.
- **`form?.dirty` / `viewState` TOCTOU** (design-reviewer): both read synchronously with no intervening await; `apply()` calls `reconcileBuffer()` at its tail on every path. No TOCTOU.
- **Missing nib while `creating`** (design, broad, knowledge): structurally unreachable, doubly so — `detailTargetId` is `null` for `creating` (App.svelte:101-104), pausing the query, *and* the effect returns early on `s.kind !== "viewing"`. Notably the change **fixes** a real hazard here: the old unconditional `syncTo(null)` would have destroyed an in-progress create buffer on a report queued for a prior nib.
- **The A/B stale-close bug the change fixes** (broad, quick, design): verified real and verified fixed by the `s.nibId !== nibId` check, with direct unit coverage.
- **`"closed" | "kept"` bare union vs. tagged `kind` unions** (consistency): `ConfirmChoice` (`useActiveView.svelte.ts:48`) is an established bare 3-way string union with no payload; `CreateOutcome`/`EditOutcome` are tagged because they carry payloads. `noteMissing` correctly follows the no-payload precedent. Not a deviation.
- **`noteMissing` vs. `noteExternalChange` vocabulary** (consistency): only one prior `note*` method exists, so no second agreeing sibling establishes a "must return void" convention. Anchor ~25.
- **`handleMissingNib(id)` vs. `nibId`-named siblings** (consistency): a broader census found a competing, equally-established convention — when the function name already says "Nib" (`navigateToNib`, `handleMissingNib`), the param is bare `id`. Not a deviation.
- **Latch staleness across `viewing A → viewing B → viewing A`** (adversarial, confidence 25; re-checked by finding #2's validator): requires the view to move targets inside the effect-flush→microtask window. Neither the reviewer nor the validator could construct a concrete route — the only non-click path needs a confirm-dialog or save-in-flight continuation, whose human click latency arrives long after the in-flight detail query resolves.
- **`gone` + dirty leaves `selection.selectedNibId` on the deleted nib** (adversarial, Low/50): a keyboard Delete then acts on a phantom; consequence is a failed-mutation toast.
- **`runNullRemoteConflictFallback`'s deliberate silence on `snapshot === null`** (adversarial, confidence 25): its comment delegates the message to "the missing-nib path (App.svelte)", which this diff makes silent on the dirty path — but the contract is honored in substance since `gone` renders `anv-deleted-notice`.
- **Pre-existing `(F1)`/`(F4)`/`(HIGH)`/`MEDIUM #3` review-finding markers** in `useActiveView.svelte.ts` / `ActiveNibView.svelte` (knowledge): arguably issue IDs under CLAUDE.md's comment rule, but entirely outside this diff.

**Project rules (CLAUDE.md) — all clean:**
- **American English spelling**: swept by quick, knowledge, consistency, broad, adversarial. No British-spelling hits on targeted greps of added lines.
- **Comments state what/why, no change-history narration, no nib IDs**: swept by knowledge and consistency against the convention just established by the repo's own comment audit (commits `868bfec`, `515d768`, `fad6f7b`, `5d7258d`). No `was previously` / `now uses` / `changed from` / `formerly`, no nib IDs. The rewritten `App.svelte` block correctly states what and why without narrating the `syncTo(null)` → `noteMissing` transition. **Note:** findings #1-#3 are comment *accuracy* defects, not comment *rule* violations — the rules pass; the content is stale.
- **No hardcoded `/` or `\` in path assertions**: the new `App.test.ts` `/?nib=nibs-vanish` string is a URL query, not a filesystem path, consistent with sibling tests in the same file.
- **Test-name IDs**: new test names carry no nib IDs, matching the post-audit convention.

---

## Recurring Findings

Matched on file path + category against 20+ prior reviews in `.decaf/code-reviews/`.

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `web/src/lib/composables/useActiveView.svelte.ts` | api-contract | 3 (1 prior + #1, #2) | 2026-07-14 (`14-31-05`) |
| `web/src/lib/composables/useActiveView.svelte.test.ts` | test-coverage | 2 (1 prior + #4) | 2026-07-14 (`16-21-38`) |
| `web/src/lib/components/ActiveNibView.svelte` | error-handling | 2 (1 prior + P1) | 2026-07-14 (`04-06-16`) |

**Signal worth acting on:** `useActiveView.svelte.ts` is by far the most-reviewed file in this repo — 10 prior findings across 6 reviews today alone, clustered in `error-handling` (5), `race-condition` / `async` / `concurrency` (4), and now `api-contract` (3). The presenter is absorbing a lot of subtle correctness load, and reviews keep finding it. The recurring `api-contract` shape specifically is **doc comments asserting invariants the code has outgrown** (#1, #2, plus the prior `error-handling / api-contract` finding). Worth considering a convention: interface annotations claiming exclusivity ("SOLE", "the only…", "always") either carry a pointer to what enforces them, or get dropped.

This also lends weight to design-reviewer's suppressed suggestion (see Considered But Not Flagged) that the missing-nib report bookkeeping belongs inside the presenter rather than split across `App.svelte`'s latch — and, more broadly, to CLAUDE.md's own guidance to run `/decaf-experimental:improve-codebase-architecture` against this area before the next feature lands on it.
