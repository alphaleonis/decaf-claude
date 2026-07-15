# Code Review

**Mode**: mid (explicit) | **Reviewers**: quick, broad, knowledge, design, adversarial, typescript, consistency, test | **Date**: 2026-07-15
**Source**: local changes — branch `batch/config-and-buffer-fixes` (uncommitted)
**Scope**: 5 files changed, +197/-12 lines
**Spec**: none found (Step 1.5: no `--spec`, not a PR; repo glob matched multiple plan nibs with no unambiguous owner for this change — `spec-compliance-reviewer` hard-gated out)
**Validation**: 2 confirmed, 0 refuted, 0 uncertain, 0 waived, 0 unvalidated

## Agent Selection Rationale

Mode was **explicit** (`mid`) — Step 2a.5 skipped, no roster cap given.

Changeset classification: ~62 executable production lines (+135 test lines) across TypeScript and Svelte 5; substantive (not mechanical); data-mutation surface (the change gates whether a persistence mutation dispatches); no untrusted-input parsing; API/contract surface changed (the `confirm` dep signature).

| Agent | Decision |
|-------|----------|
| `quick-reviewer` | included — always (floor) |
| `broad-reviewer` | included — always (floor) |
| `knowledge-reviewer` | included — substantive change; new comments encode load-bearing timing/behavioral decisions |
| `consistency-reviewer` | included — sibling code exists to compare against (`handleOverwrite`/`handleLoadTheirs`, Delete/Archive confirms) |
| `design-reviewer` | included — the `confirm` dep contract widened; concurrency surface (await-across-prompt) |
| `adversarial-reviewer` | included — ≥50 changed executable lines AND data-mutation domain |
| `typescript-reviewer` | included — TS/JS files present (hard gate) |
| `test-reviewer` | included — test files present (hard gate) |
| `security-reviewer` | skipped — no security-adjacent surface (no auth, crypto, network, secrets, serialization, privilege boundary) |
| `performance-reviewer` | skipped — no DB/ORM queries, no loops with I/O, no caching logic |
| `spec-compliance-reviewer` | skipped — no spec available (hard gate) |
| `data-migration-reviewer` | skipped — no migration artifacts (hard gate) |
| `go` / `dotnet` / `cpp` / `rust` reviewers | skipped — no such files (hard gate) |
| `prior-feedback-reviewer` | skipped — not a PR, no prior review threads (hard gate) |

**Model tiering (Step 2d, `mid` policy)**: judgment agents on the session model (`knowledge`, `design`, `adversarial`); volume agents and both validators mid-tier `sonnet` (`quick`, `broad`, `consistency`, `typescript`, `test`).

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 1 |
| 🟡 Medium | 1 |
| 🟢 Low | 0 |
| 🔵 Minor | 4 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts reported-but-non-blocking findings. Pre-existing issues are listed separately and excluded from both.

**Verdict**: ❌ NEEDS_CHANGES (one High among primary findings)

**The fix itself is sound.** Every claim the implementer made was independently verified and held — the post-await re-check reads live state, the unreachability claim is correct, the load-bearing claim is empirically true, and all comment clauses are accurate (details under *Considered But Not Flagged*). Both findings below are about what the change leaves **undocumented** and **untested**, not about its behavior.

---

## Findings

### #1 🟠 High: `save()` is advertised as the shared save chokepoint but silently requires every caller to pre-check `gone`

| | |
|---|---|
| **File** | `web/src/lib/composables/useActiveView.svelte.ts:190` (interface decl) · `:405-413` (impl docblock) |
| **Category** | knowledge-preservation / assumption-unvalidated (RULE 0) |
| **Confidence** | 75 |
| **Found by** | knowledge-reviewer (SHOULD → High) |
| **Validation** | ✅ CONFIRMED — `pre_existing: no` upheld |

**Issue:** The fix places the `gone` gate at both *callers* of `save()` (`guarded()` at `:333`, `ActiveNibView.handleSave` at `:295`) rather than inside `save()` itself. `save()` has no `gone` gate, and its contract never states the precondition. Two things make this a trap rather than a neutral choice:

1. `save` is exposed on the public `ActiveView` interface at `:190` with **no doc comment at all**, while its neighbors (`savePending`, `syncTo`, `noteMissing`) each document their contracts in detail — so the one member carrying a hidden precondition is the one member documented least.
2. The impl docblock at `:405-408` **actively advertises reuse**: *"the SAME routine the Save control invokes. Extracted so the dirty-nav guard's 'Save' branch can reuse it without reimplementing the create hand-off / conflict routing."* That invites a third caller to reuse `save()` — which is precisely how the bug being fixed here reappears.

The validator confirmed the mechanism end-to-end: `save()` (`:414-445`) calls `f.save()` unconditionally, and `EditForm.save()` (`web/src/lib/nibForm.svelte.ts:482-541`) dispatches a real `updateNib` mutation with no gone-awareness — so the failure mode is real, not speculative. It also confirmed the precondition is **new**: at `HEAD`, neither `guarded()` nor `handleSave` checked `gone` at all. This changeset creates the precondition (as two caller-side gates) without centralizing or documenting it.

**Fix:** Document the precondition on `save()` at both the interface declaration (`:190`) and the impl docblock (`:405-413`):
```ts
/** Persist the active buffer through the create hand-off / conflict routing.
 *  PRECONDITION: callers must not invoke this while `viewState.kind === "gone"` —
 *  save() does NOT gate on it, and a save against a deleted nib can only fail.
 *  Both current callers (guarded()'s Save branch, ActiveNibView.handleSave) check first. */
save: () => Promise<...>;
```
(Alternatively, move the gate *into* `save()` so the invariant cannot be bypassed — but that is a design change beyond this fix's scope, and the caller-side gates are correctly placed for the view layer's own controls. Documenting is the minimal correct step.)

---

### #2 🟡 Medium: The new `canSave` dialog wiring in `App.svelte` has no test that exercises the real function

| | |
|---|---|
| **File** | `web/src/App.svelte:209` (function spans 205-235) |
| **Category** | test-coverage |
| **Confidence** | 100 (75 each finder, promoted on independent agreement) |
| **Found by** | broad-reviewer (Medium), test-reviewer (Medium) |
| **Validation** | ✅ CONFIRMED — line corrected to `:209` |

**Issue:** `confirmDiscard`'s `canSave` branching — which decides whether the rendered dialog offers Save at all, and which title/message pair to show — is a local (non-exported) closure inside `App.svelte`. Nothing tests it:

- `useActiveView.svelte.test.ts` stubs `deps.confirm` **entirely** — it verifies the composable *calls* `confirm({ canSave: ... })` with the right argument, never that App's real `confirmDiscard` reacts correctly.
- `ConfirmDialog.test.ts` verifies the child component's generic `onsave`-gating in isolation (pre-existing, unrelated to this diff).
- `App.test.ts` was **not touched** by this diff and has zero references to `confirmDiscard`, `canSave`, or the new copy. Its predecessor test at `:949` ("keeps a DIRTY buffer when the viewed nib vanishes…") stops right after the deleted notice appears, never clicking `anv-close`. All four `anv-close` click sites in `App.test.ts` (`:450`, `:818`, `:865`, `:891`) are on clean, non-deleted panels.

**This was proved, not argued.** The validator built an isolated worktree, applied the uncommitted changeset, then applied the exact regression the finding names — making `saveLabel`/`saveAction` unconditional, i.e. reintroducing the Save button on a deleted nib — and ran the suite: **60 files / 1246 tests passed, identical to baseline.** The regression that reopens this changeset's entire reason for existing is invisible to the test suite.

**Fix:** Add a case to `web/src/App.test.ts` driving the real dialog:
```ts
it("offers Discard-only (no Save) when closing a dirty gone buffer", async () => {
  const user = userEvent.setup();
  window.history.replaceState(null, "", "/?nib=nibs-vanish");
  render(App);

  const title = await screen.findByTestId("anv-title");
  await user.type(title, " edited");
  vanishNib();
  await waitFor(() => screen.getByTestId("anv-deleted-notice"));

  await user.click(screen.getByTestId("anv-close"));

  expect(screen.getByTestId("confirm-dialog-title")).toHaveTextContent("This nib was deleted");
  expect(screen.queryByTestId("confirm-dialog-save")).not.toBeInTheDocument();
});
```
Plus a `canSave: true` companion asserting the Save button *is* present for a live dirty buffer — that pins both sides of the boundary.

---

## Pre-existing Issues

Findings every finder marked `pre_existing`. Informational; excluded from the verdict and Summary counts. **P1 in particular deserves a follow-up nib** — it argues the changeset's `gone` predicate is fed from a source that can fail, leaving the original trap reachable by another route.

### P1 🟠 High: Live-subscription-down leaves the original stranded-panel trap fully reachable

| | |
|---|---|
| **File** | `web/src/lib/composables/useActiveView.svelte.ts:333` |
| **Category** | error-handling / cascade |
| **Confidence** | 75 |
| **Found by** | adversarial-reviewer (High) |

**Issue:** `gone` is a *subscription-derived* proxy for "deleted". If the live subscription is down, an in-app Delete of a dirty nib commits but nothing ever applies `DELETED` → the buffer stays `viewing` → `canSave` stays `true` → the post-await `gone` re-check never fires → `save()` hits `ErrNotFound` → `guarded()` returns false → **panel stranded, and every retry re-offers the same impossible Save.** This is the exact trap the fix targets, surviving via a state that never reaches `gone`.

**Fix (as proposed):** The app already *knows* the nib is deleted (`result.ok` from `deleteNibCmd`). Primary: in `ActiveNibView`'s `handleDelete`/`handleArchive`, call `view.noteMissing(id)` on `result.ok` **before** `view.requestClose()`, so the locally-proven deletion drives the state machine instead of waiting on a WS round-trip. Backstop: route a NOT_FOUND outcome in `guarded()`'s error branch (and/or `save()`) into `noteMissing(f.id)`, so a deletion from any source converges the buffer to `gone` and the retry gets Discard-only.

### P2 🟠 High: The confirm bridge is a single-slot resource with no re-entrancy discipline

| | |
|---|---|
| **File** | `web/src/App.svelte:200-213` |
| **Category** | design / concurrency (async) |
| **Confidence** | 75 |
| **Found by** | design-reviewer (High), adversarial-reviewer (Medium — dissent noted) |

**Issue:** `pendingDiscardResolve` is one module-level variable overwritten unconditionally at `:213`, and `confirmDialog` is a shared singleton whose `showConfirm` replaces dialog contents in place. `guarded()` has no re-entrancy guard, and the global shortcuts are gated only by `modalOpen()` = `view.isOpen && presentation === 'expanded'` (`useKeyboardShortcuts:49`) — which is **false for a docked buffer**. So with a docked dirty buffer and the guard prompt open, pressing `n`/`e` re-enters `guarded()` → `deps.confirm()` → overwrites the slot, **stranding the first await forever**. design-reviewer demonstrated this in an isolated scratch script:
```
first  guarded() await settled: false   ← leaked permanently
second guarded() await settled: true
```
adversarial-reviewer independently traced a user-visible consequence via the awaited `await view.requestClose()` in the pane `onCollapse` (`App.svelte:547`): the orphaned promise means the re-expand recovery never runs — the pane stays collapsed at 0 width while `dockOpen` is true, with Back/Forward frozen (`blocksHistoryNav` = dirty) and no way to bring it back. Same family as the stranded-panel bug this changeset fixes.

**Fix (as proposed):** In `confirmDiscard`, settle any in-flight resolver before claiming the slot (`resolveDiscard("cancel")` at the top) so a superseded guard unwinds deterministically instead of hanging; have `confirmDialog.close()` settle a pending guard promise so an in-place takeover cannot drop it. Better: make `guarded()` non-re-entrant, and extend the shortcut gate to include "a confirm dialog is open" rather than only the expanded presentation.

---

## Minor Findings

### Consistency

- `web/src/lib/components/ActiveNibView.svelte:289` — the new guard's comment says **"defense in depth"**, but every sibling describing this exact redundancy pattern says **"belt-and-braces"**: `handleLoadTheirs`'s own `isGone` guard two functions above (`:331` — *"the resolver is also hidden in that state — MEDIUM #3, belt-and-braces"*), plus `ActiveNibView.svelte.test.ts:839` and `ConfirmDialog.test.ts:142`. ("defense in depth" does appear at `markdown.test.ts`, but for an unrelated concept.) A second synonym for one concept. (consistency-reviewer, anchor 100)
- `web/src/lib/components/ActiveNibView.svelte:295` — the comment claims the guard **"Mirrors handleLoadTheirs/handleOverwrite"**, but the predicate order differs: `handleSave` checks `!f.dirty` before `f.saving`, while both cited siblings check `f.saving` before their final terminal condition (`handleOverwrite` `:343`: `isGone || !f || f.mode !== "edit" || f.saving || !f.dirty`; `handleLoadTheirs` `:332`: `… || f.saving || !f.externalChange`). The two siblings agree with each other; `handleSave` reverses it. No functional difference (independent boolean reads, no short-circuit side effects) — but the comment overstates the parity it claims. Either reorder to match, or soften the comment to "intent mirrors". (consistency-reviewer, anchor 100)
- `web/src/lib/composables/useActiveView.svelte.ts:133-135` — the `confirm` docblock justifies the optional param with a caller that does not exist: *"Optional (defaulting to savable) so callers that never face a `gone` buffer can ignore it."* `guarded()` at `:318` is the **sole** caller and **always** passes `{ canSave: … }`. The party that ignores it is an *implementation* of the dep (the test harness's fake), not a caller. The parenthetical also attributes the default to the contract, but `?? true` lives in one implementation (`App.svelte:210`), not the interface. Suggested: *"Optional so an implementation that never faces a gone buffer can ignore it; an implementation that omits it must treat the prompt as savable."* (knowledge-reviewer, quotable-fact re-anchor 100)
- `web/src/lib/composables/useActiveView.svelte.ts:334` — toast and dialog copy diverge for the same condition: the `notifyError` reads *"This nib no longer exists, so your changes can't be saved."* while the dialog at `App.svelte:217` reads *"…so your **unsaved** changes can't be saved. Discard them and continue?"* — same condition, two phrasings in one flow. **Dissent**: consistency-reviewer specifically investigated and declined to flag it (anchor 0), finding no convention to cite — "Save failed" is already independently duplicated at `ActiveNibView.svelte:305`, `:349`, and `useActiveView.svelte.ts:358`. Included per Step 5.5 (one agent flagged what another dismissed); cosmetic either way. (broad-reviewer Low)

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| quick-reviewer | 0 | 0 |
| broad-reviewer | 2 | 1 |
| knowledge-reviewer | 2 | 2 |
| consistency-reviewer | 2 | 2 |
| design-reviewer | 1 | 0 |
| adversarial-reviewer | 2 | 1 |
| typescript-reviewer | 0 | 0 |
| test-reviewer | 1 | 0 |
| **Total** | **8** | |

Notes:
- **Issues Found**: total consolidated findings attributed to this agent (including shared findings), across primary, minor, and pre-existing.
- **Unique Issues**: findings reported ONLY by this agent.
- **"Found 0 ≠ did nothing"**: `quick-reviewer` and `typescript-reviewer` returned clean, but both did substantive clearing work — see *Considered But Not Flagged*. `typescript-reviewer` in particular independently verified the `$state.raw` live-read semantics, the object-spread key-omission behavior across all three consuming layers, and the test-mock arity contravariance.

---

## Specialist Notes

### Considered But Not Flagged (all agents)

**The implementer's claims — all independently verified, all held:**

- **The post-await re-check reads live state (not stale).** Verified by quick, broad, adversarial, and typescript independently. `viewState` is a plain closure `let` reassigned wholesale by `apply()` (`$state.raw` at `:217`), so the `:333` read genuinely observes a mutation that landed during the `deps.confirm()` await.
- **Part 2 is load-bearing — verified empirically.** test-reviewer, in an isolated worktree with only part 1 applied: `2 failed | 53 passed`. Tests 1-2 (`canSave` assertions) passed; tests 3 and 4 failed specifically on `expect(f.save).not.toHaveBeenCalled()`. This confirms the implementer's claim and slightly *broadens* it (it holds for test 3 too, not just test 4). knowledge-reviewer corroborated: removing only the re-check fails 2 of the 5 new tests.
- **All 5 new tests genuinely fail on unfixed code — except the one honestly disclosed.** test-reviewer ran them against unfixed HEAD in an isolated worktree: `4 failed | 103 passed`. Tests 1-4 failed as expected; test 5 (`leaves a PRISTINE gone buffer unprompted`) passed — exactly as the implementer self-reported. Judged a genuine boundary-condition regression guard for the group's shared invariant, correctly disclosed and reasonably placed; its comment explains the invariant it protects rather than implying it distinguishes fixed from unfixed code. **No change needed.**
- **Part 3's unreachability claim is CORRECT** — verified independently by knowledge, test, design, and broad. `handleSave` has exactly two entry points: the Save button (`:644`, `disabled` = `isGone || loadingUnseeded`) and `MarkdownEditor`'s `onsave` (`:793`), which only mounts in the `{:else}` of `{#if bodyModeEffective === "preview"}` — and `bodyModeEffective = disabled ? "preview" : bodyMode` (`:157`) forces `"preview"` whenever `disabled`. No global Ctrl+S path exists. knowledge-reviewer confirmed removing the `isGone` term leaves all 52 ActiveNibView tests passing, corroborating "defense in depth for any future path". **No live hole, no missing test** — the comment is accurate and honestly hedged. The guard is correct to add given the planned relaxation of `:105`.
- **`contexts.ts` stub needs no change — CONFIRMED.** `confirm` is a dep of `createActiveView`, not a member of the `ActiveView` interface. The stub (`contexts.ts:79-101`) `satisfies ActiveView`; the widened dep signature is invisible to it. Consistent with the clean `svelte-check`.
- **Every comment clause verified TRUE** (knowledge-reviewer, clause by clause): "`abandonsBuffer` and the `canSave` offer … evaluated BEFORE it" — literally true; "the live bridge routes viewing → gone" — bridge confirmed at `:531-538`, an `$effect`, fires while the prompt is open; "the rule below — never navigate on a save that did not succeed" — genuinely exists below (`:344`, `:353`); "aborts once rather than trapping" — verified, and crucially the retry is *reachable* (`anv-close` at `:604` carries no `disabled` prop; Escape routes to `requestClose`). The described cascade is real: `handleArchive`/`handleDelete` (`:374`/`:390`) do `if (result.ok) view.requestClose()`. App.svelte's "showConfirm nulls both" / "ConfirmDialog gates on `onsave`" — **both halves true** (`useConfirmDialog.svelte.ts:54-55`; `ConfirmDialog.svelte:58`). "the same shape Delete/Archive confirms use" — true.
- **No change-history narration, no nib IDs, American English throughout** — confirmed by knowledge, consistency, and quick.

**Hypotheses constructed and REFUTED (the adversarial probes that came back clean):**

- **The `gone`→`viewing` bounce (the headline probe) — REFUTED at anchor 0.** adversarial-reviewer constructed it: `abandonsBuffer(gone, OPEN same-id)` is false, so `view.open(id)`/`syncTo(id)` flips `gone`→`viewing` unguarded with the dirty buffer intact, and `App.svelte:291` even documents "`gone` is not terminal". Predicted the live bridge would not re-fire `DELETED`. **The isolated-worktree probe failed that prediction: state healed straight back to `gone`.** Cause: `apply()` → `reduce(viewState, action)` reads `viewState` *inside* the bridge `$effect`, so the effect transitively tracks `viewState` and re-asserts `DELETED` on every bounce, synchronously within the flush — no user-interactive window. The bounce is closed. (Corollary: no re-entrancy loop — `reduce(gone, DELETED)` returns the same reference, which `$state.raw` dedups.)
- **Popstate buffer-swap during the prompt — REFUTED.** `blocksHistoryNav` = `Boolean(form?.dirty) || typePicker !== null` (`:636`), and the guard only prompts when `form?.dirty` — so `isBlocked()` is true for the whole prompt window and `handlePopState` refuses to navigate. `syncTo`'s guard-bypass is unreachable while a prompt is open. Enumerating every `apply()` site, the only transition reachable mid-prompt is the live bridge's `viewing → gone` — **the one transition `:333` checks.** Not a general check-after-await class; the design holds.
- **Sibling check-after-await holes in the save path — none found.** Traced the `await save()` continuation: conflict → abort, error → abort, `form !== saved` → abort. A delete landing *during* a successful save still resolves correctly.
- **Delete-event self-echo suppression — REFUTED.** Hypothesized `classifyNibEvent` might drop a `deleted` event when its etag matched the dirty buffer's baseline `selfEtag`. `nibChange.ts:89` short-circuits `type === "deleted"` before any selfEtag check. (This is why P1 requires the subscription to be genuinely down rather than merely racing.)
- **Stale `saveAction` resurrecting a Save button on a Discard-only prompt — REFUTED.** `useConfirmDialog.svelte.ts:54-55` uses `?? null` on every call; no stale Save can leak from a prior invocation.
- **Object-spread omitting keys vs. setting them `undefined` — no divergence.** All three layers agree (`?? null` at `:54-55`; `{#if onsave}` at `ConfirmDialog.svelte:58`; `App.svelte:622` only supplies `onsave` when `saveAction` is truthy).
- **`viewState` reaching `closed` mid-prompt** — traced: `save()` reads `const f = form` (null after the CLOSE reconcile) and returns `undefined`, which `if (!outcome …) return false` already aborts on. Safe by an existing invariant.
- **`creating` boundary** — `viewState.kind` can never be `"gone"` while `"creating"` (no reducer path connects them), so `canSave` is always `true` for create buffers. Correct.
- **Test mock arity** (`useActiveView.svelte.test.ts:57`, `vi.fn<() => Promise<ConfirmChoice>>` still zero-arg vs. the widened dep) — no type-safety consequence: TypeScript's parameter-count contravariance permits it, `svelte-check` passes, and `toHaveBeenCalledWith` is generically typed so it checks actual call args regardless. Cosmetic drift; flagged by no one as reportable.
- **`expect(view.noteMissing("n1")).toBe("kept")` in the `openDirtyGone` helper** — acceptable: a fail-fast precondition check (did the helper reach `gone` via the `noteMissing` path), materially different in purpose from a hidden production assertion.
- **The `anv-editor-container` assertion is genuine, not vacuous** — the testid exists at `ActiveNibView.svelte:782`; verified it passes even against unfixed HEAD, because it pins a *pre-existing* invariant (that both routes into `handleSave` are closed at render time) rather than the new fix. An honest substitute for the untestable part-3 guard.

**Suppressed by the confidence gate:**

- **1 finding suppressed at anchor 50** — design-reviewer, `useActiveView.svelte.ts:135`, Medium: *"the widened `confirm` seam is under-specified in both directions, and its optionality is unreachable."* Argues (a) `opts?` and `canSave ?? true` are dead today (one implementor, one invoker that always passes it), and since CLAUDE.md states there are no back-compat requirements, nothing is being preserved — what remains is a **fail-open default** where a future invoker that forgets `opts` silently gets the savable dialog, reintroducing this exact dead end; (b) the param names a **capability** (`canSave`) but App decodes it as a **reason**, hardcoding "This nib was deleted" on the false branch, so any second reason to withdraw Save (read-only, offline, permission) would make the dialog assert a deletion that did not happen. Proposed fix: make the param required — `confirm: (opts: { canSave: boolean })` — converting a silent fail-open into a compile error at zero cost; or pass `{ reason: 'dirty' | 'gone' }` and let the dialog own its copy. Below the 75 gate for non-Critical findings; the finder's own anchor was 50. **Recorded here rather than dropped** — it partially overlaps Minor finding 3 (the docblock justifying optionality with a caller that does not exist), and the two share a root: the optionality serves nobody today. Worth considering alongside #1's fix.

**Not flagged per explicit out-of-scope instruction:** `ActiveNibView.svelte:105`/`:157`/`:648` (gone-state read-only rendering); `nibForm.svelte.ts` `sameBody`; `MarkdownEditor.svelte` sync suppression; `TreeTable` title click; `internal/nibcore/watcher.go`; the "This nib was deleted" copy for archived nibs. On the last: knowledge-reviewer noted the new dialog title (`App.svelte:212`) **widens that known copy defect's reach** to a new surface — recorded, not flagged.

---

## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `web/src/lib/composables/useActiveView.svelte.ts` | knowledge-loss / api-contract | 2 | 2026-07-14 |
| `web/src/App.svelte` | test-coverage | 2 | 2026-07-13 |
| `web/src/lib/composables/useActiveView.svelte.ts` | comprehension-risk / comment-code mismatch | 2 | 2026-07-14 |

All three of this review's non-pre-existing findings land on ground already broken:

- **#1 repeats a pattern from `CODE_REVIEW_2026-07-14_21-32-40`**, which flagged `useActiveView.svelte.ts:172` — the *same `ActiveView` interface*, same knowledge-loss/api-contract category. Two undocumented contracts on one interface in two days.
- **#2 repeats `CODE_REVIEW_2026-07-13_20-40-24`**, which flagged `App.svelte:69-71` as test-coverage with the identical shape: *"missing test belongs in `web/src/App.test.ts`"*. `App.svelte`'s non-exported closures are systematically escaping coverage because the composable tests stub them out.
- **The comment-code mismatch category recurs** (`CODE_REVIEW_2026-07-14_23-02-10`, `useActiveView.svelte.ts:479-481`), matching the briefing's characterization of comment truth as this codebase's dominant defect class — though notably, this changeset's comments were **verified accurate**; the two mismatch findings here are a synonym choice and an overstated parity claim, both cosmetic.

The `App.svelte` test-coverage recurrence is the most actionable structural signal: it is not a one-off omission but the second instance in three days of new `App.svelte` glue logic shipping with coverage that only reaches it through a stub.

---

## Session Metrics (--report)

**Wave timing**: pre-flight completed 17:31:18 → reviewer wave dispatched ≈17:31:20 → last reviewer returned ≈17:42:21 → consolidated ≈17:44 → validation done ≈17:47 → file written 17:49:25

> [Estimate] Exact dispatch/return wall-clock timestamps were **not recorded** at dispatch time; the figures above are reconstructed from two measured anchors — vitest's reported `Start at 17:30:52` + `Duration 26.10s`, and the `date` call at file-creation (17:49:25) — combined with the harness-reported per-agent `duration_ms` below. The per-agent durations themselves are harness-reported and verbatim. Reviewers ran in parallel, so wave length ≈ the longest reviewer (adversarial, 660921 ms = 11m 1s).

| Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings submitted |
|-------|------|-----------|--------|-----------|----------|--------------------|
| quick-reviewer | reviewer | sonnet (mid) | 99527 | 22 | 179883 ms | 0 |
| broad-reviewer | reviewer | sonnet (mid) | 159003 | 28 | 445135 ms | 2 |
| knowledge-reviewer | reviewer | opus (session) | 101374 | 35 | 402784 ms | 2 |
| design-reviewer | reviewer | opus (session) | 94819 | 23 | 339354 ms | 2 |
| adversarial-reviewer | reviewer | opus (session) | 137313 | 30 | 660921 ms | 2 |
| typescript-reviewer | reviewer | sonnet (mid) | 119009 | 22 | 236858 ms | 0 |
| consistency-reviewer | reviewer | sonnet (mid) | 141876 | 28 | 324142 ms | 2 |
| test-reviewer | reviewer | sonnet (mid) | 121656 | 47 | 491577 ms | 1 |
| finding-validator (#1) | validator | sonnet (mid) | 69367 | 14 | 110265 ms | confirmed |
| finding-validator (#2) | validator | sonnet (mid) | 61262 | 17 | 129906 ms | confirmed |

**Totals**: reviewers 974577 tokens / 235 tool calls · validators 130629 tokens / 31 tool calls · **wave total 1105206 tokens / 266 tool calls**.

> [Unverified] Whether a subagent's reported token figure includes its own children. This caveat applies to every row and to all sums above. Orchestrator-side tokens (this context: context gathering, spec discovery, pre-flight, consolidation, report authoring) are **not reported** by the harness and are excluded from the totals.

**Pre-flight gates**:
- `cd web && npx svelte-check --threshold warning` → **PASS**: 4737 files, 0 errors, 0 warnings
- `cd web && npx vitest run --reporter=agent` → **PASS**: 60 test files, 1246 tests passed (26.10s)
- Go gates (`task build` / `task lint` / Go tests) **not run** — the changeset is web-only (5 files, all under `web/`); no Go source is implicated. Recorded as deliberately skipped, not as passing.

**Anomalies**: one benign, zero corrupting.
- **Benign**: `adversarial-reviewer` found `$SCRATCH/probe` already existing as a plain (unregistered) directory when it went to create its worktree — a path collision with `test-reviewer`'s probe directory, caused by the orchestrator assigning the same scratch path to both agents. adversarial correctly declined to reuse it, created its own `adv-probe` worktree, and removed it afterward. No data crossed between probes. **Tuning candidate**: the orchestrator should assign per-agent scratch subdirectories rather than one shared path.
- **Zero probe-protocol corruption.** No reviewer reported the changeset as absent, reverted, or flapping. Three agents (`test-reviewer`, `adversarial-reviewer`, `finding-validator #2`) ran genuine revert/mutation probes, all in isolated `git worktree`s, all removed afterward. `design-reviewer` ran its executable probe as a standalone scratchpad script. The shared tree was verified byte-identical before and after the wave (same 5 modified files, +197/-12, no stray worktrees). This is the third consecutive wave with the isolated-probe mandate and the third with zero corruption anomalies.
