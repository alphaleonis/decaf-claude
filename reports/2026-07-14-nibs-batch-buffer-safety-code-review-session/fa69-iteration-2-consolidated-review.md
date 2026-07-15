# Code Review

**Mode**: mid (explicit) · roster cap 6 — 2 gate-matched agents dropped | **Reviewers**: quick, broad, knowledge, consistency, adversarial, test | **Date**: 2026-07-14
**Source**: local changes — branch `batch/buffer-safety-watch-cleanup` (uncommitted)
**Scope**: 7 files changed, +242/-6 lines
**Spec**: none found
**Validation**: 3 confirmed, 1 refuted, 0 uncertain (2 findings waived — corroborated ×2 and ×3)

## Agent Selection Rationale

Mode was **explicit** (`mid6`) — not second-guessed. Roster cap **6**: floor (2) + 4 of 8 gate-matched specialists.

**Included:**
- `quick-reviewer` — always (review floor)
- `broad-reviewer` — always (review floor)
- `knowledge-reviewer` — **top-ranked specialist**. Comment accuracy is the caller's stated probe area *and* the defect class that produced 2 of 3 Highs (2 unique) in the prior round. Its lane is the round's primary deliverable.
- `adversarial-reviewer` — the `"stale"` token + latch-clearing is the only new *logic* (~10 executable lines); top unique producer last round (2 unique)
- `test-reviewer` — hard gate (test files present); 179 of 242 diff lines are tests — 4 new tests + a reworked hoisted mock
- `consistency-reviewer` — CLAUDE.md comment rules (no change-history narration, no nib IDs, American English) are quotable-fact checks the caller explicitly asked to enforce; it produced M1 last round, whose fix needed verifying

**Dropped to the roster cap (their gates MATCHED — they lost a slot, they were not skipped):**
- `design-reviewer` — **dropped — roster cap (mid6)**: ranked below the 4 kept. Produced 0 unique findings last round, and its main lane here (the return-union widening) is explicitly pre-litigated by the caller.
- `typescript-reviewer` — **dropped — roster cap (mid6)**: **hard-gate coverage traded away.** Normally a stack reviewer for the dominant changed language ranks highest under categorical coverage. Overridden on direct evidence: it returned **0 findings / 0 unique** on a *superset* of this diff in the prior round, and the new production code is ~10 lines of plain synchronous TS with no promises, casts, coercion, or event-loop surface. Its lane is genuinely empty here. *(If a future round adds async or type-level surface, restore it.)*

**Excluded by gate:**
- `security-reviewer`: skipped — no auth/crypto/user-input/network/file-I/O/secrets surface
- `performance-reviewer`: skipped — no DB queries, I/O loops, pipelines, or caching; the `queueMicrotask` is a scheduling deferral, not a throughput surface
- `spec-compliance-reviewer`: skipped — no spec available (hard gate). No `--spec`, no `plans/` or `docs/specs/`, not a PR. The prior review report was considered as a spec source and **rejected**: it is *feedback*, not a specification (the skill's lane for feedback is `prior-feedback-reviewer`), and "a wrong spec is worse than no spec." Matches the prior round's own determination. Its content was instead passed to every reviewer as context.
- `prior-feedback-reviewer`: skipped — local changes, not a PR (hard gate)
- `data-migration`, `dotnet`, `cpp`, `go`, `rust`: skipped — domains absent (hard gates)

**Model tiering** (mid policy): judgment agents (`knowledge`, `adversarial`) inherited the session model; volume agents (`quick`, `broad`, `consistency`, `test`) and all 4 validators ran mid-tier (`sonnet`).

**Wave note**: `adversarial-reviewer` terminated on a server-side 529 on first dispatch and was **re-dispatched**; the retry completed and its report is included. Because it owns the caller's #1 probe area, the retry was not optional.

**Pre-flight gates**: `task test` — **PASS**. Go: all packages ok. `svelte-check`: 4737 files / 0 errors / 0 warnings. `vitest`: 60 files / 1220 tests passed (up from 1219 — the round's new test #4). Ran once for the wave.

**Working-tree integrity**: multiple agents ran non-destructive revert-probes. Verified post-wave: `git status --porcelain -uall` shows only the 7 intended modified files and **no untracked probe files** (an improvement on the prior round, which leaked two); `git diff HEAD --stat` matches the original diff at +242/-6. Nothing leaked.

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 3 |
| 🟡 Medium | 2 |
| 🟢 Low | 0 |
| 🔵 Minor | 2 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts the reported-but-non-blocking findings. Pre-existing issues are listed separately and excluded from both.

**Verdict**: ❌ NEEDS_CHANGES

**The data-safety fix holds — again, and harder.** `adversarial-reviewer` ran six runtime probes at the presenter boundary (5× `gone`↔`viewing` bounce on a dirty buffer; reports arriving while `creating`/`closed`; the confirm-dialog window; `save`/`guarded()` composition) and **could not destroy a dirty buffer through any path in the new code**. `test-reviewer` revert-probed all four new tests and confirmed every one is load-bearing, not decorative. The core claim is now verified twice over.

**But the round repeated its own defect class.** The prior round's three Highs were all comments making false claims. This round's *replacement* comments make **three more** — including one that is structurally the same defect as prior finding #2: the round fixed `"kept"` collapsing two outcomes and, in the same edit, created `"stale"` collapsing two outcomes. All three Highs are again documentation, on mechanically sound code. One genuine logic regression (#5) was also found — the round silently broke a cross-module message delegation.

---

## Findings

### #1 🟠 High: `App.svelte`'s "Only reached when the detail query is the first signal" is false — and its conclusion with it

| | |
|---|---|
| **File** | `web/src/App.svelte:274` |
| **Category** | comprehension-risk / false-invariant |
| **Confidence** | 100 |
| **Found by** | knowledge-reviewer (High), adversarial-reviewer (confirmed by runtime probe) |
| **Validation** | corroborated ×2 (both judgment specialists, independent runtime confirmation) — validation waived |

**Issue:** The new comment block asserts:

```
// Only reached when the detail query is the first signal. A live-subscription
// deletion (useActiveView's bridge) applies DELETED with no dirty gate, so a
// PRISTINE nib deleted that way lands in `gone` instead of closing — the
// close/heal/toast below is not the only outcome for a missing nib.
```

The code contains **no mechanism that observes signal ordering**. The only gate is `if (s.kind !== "viewing")` (`:286`) plus the `reportedMissingFor` latch. The "first signal" claim silently rests on `gone` being terminal — which **this diff's own test #4 disproves** (`useActiveView.svelte.test.ts:441-470`): `syncTo(sameId)` bounces `gone -> viewing`.

`adversarial-reviewer` confirmed the counterexample at runtime (probe P1):
1. Live sub deletes `n1` → bridge applies `DELETED` → `gone(n1)`; the effect early-returns, no report. **Live was the first signal.**
2. Pristine ⇒ `blocksHistoryNav === false` → user opens `n2` (no confirm) → presses Back → `syncTo("n1")` → `viewing(n1)` with a rebuilt pristine form.
3. Detail refetches → `{nib: null}` → effect reports → `noteMissing("n1")` returns **`"closed"`** → close + heal + toast.

So the paragraph's conclusion is also wrong: a pristine live-deleted nib does **not** stay in `gone` "instead of closing" — it converges to close/heal/toast on the next sync. **The divergence is momentary, not terminal.**

This block's *sole purpose* is to record a correctness-relevant divergence (it exists because prior finding #3 asked for it), and the recorded invariant is false.

**Fix:** replace with the invariant the code actually enforces:
```
// Runs only while the view is `viewing` — a live-subscription deletion (useActiveView's
// bridge) applies DELETED with no dirty gate, so it reaches `gone` first and this effect
// stays silent. That is momentary, not terminal: a later syncTo re-anchors on the same
// id (gone -> viewing) and the decision below runs then, against the buffer's dirtiness
// at that moment. So a PRISTINE nib deleted via the live sub sits in `gone` until the
// next sync, then closes/heals/toasts like any other missing nib.
```

---

### #2 🟠 High: the latch comment block makes three false claims, one contradicting the paragraph above it

| | |
|---|---|
| **File** | `web/src/App.svelte:281-285` |
| **Category** | comprehension-risk / self-contradicting comment |
| **Confidence** | 100 |
| **Found by** | broad-reviewer (High), quick-reviewer (Medium), knowledge-reviewer (Medium) |
| **Validation** | corroborated ×3 (incl. specialist, all anchor 100) — validation waived |

**Issue:** Three independent reviewers each disproved a different claim in the same five-line block:

```ts
// Only a `viewing` nib can go missing. `gone` — the dirty-buffer outcome of a
// report already made — lands here too, which is what stops the effect from
// re-firing on the state it just produced. Clearing the latch is safe: the
// only way back to `viewing` on the same still-missing id is a fresh open,
// which re-runs the same decision against the buffer's current dirtiness.
```

1. **"`gone` — the dirty-buffer outcome of a report already made"** (quick, broad) — incomplete to the point of false. `gone` is *also* produced by the live-subscription bridge (`useActiveView.svelte.ts:463`, `if (l.deleted) apply({type:"DELETED"})`) with **no dirty gate at all**, so a *pristine* nib lands there with no report ever made. **The comment block four lines above says exactly this** — the two statements contradict each other *within the same block*.
2. **"which is what stops the effect from re-firing on the state it just produced"** (knowledge) — the effect **does** re-fire; `view.state` is its dependency and `gone` is a new value. What stops the *re-report* is the `return` on `:288`. Worse, the very next sentence ("Clearing the latch is safe") presupposes `:287` executed — i.e. that the effect re-fired. **The block asserts the effect does not re-fire, then reasons from the fact that it did.** A reader taking the first sentence at face value concludes the latch stays `=== id` after a `"kept"` outcome and that a later same-id report is latch-suppressed — the opposite of what happens.
3. **"the only way back to `viewing` on the same still-missing id is a fresh open"** (knowledge) — `syncTo` also produces `OPEN → viewing` (`useActiveView.svelte.ts:616`), and **the diff's own test #4 exercises exactly that**. In this file `open()` and `syncTo()` are deliberately distinct (`open` is guarded; `syncTo` is *the* guard-bypass), so "a fresh open" reads as `open()` and excludes the popstate path. The *conclusion* (clearing is safe) holds for both — only the premise is misnamed.

**Fix:**
```ts
// Only a `viewing` nib can go missing. `gone` and `closed` land here too and return
// early — that early return, not the latch, is what keeps a report from repeating on
// the state a report just produced. (`gone` is reached either from noteMissing's dirty
// branch or from the live bridge's ungated DELETED.) Clearing the latch here is safe:
// getting back to `viewing` on the same still-missing id takes a fresh OPEN (via `open`
// or the guard-bypassing `syncTo`), and either way the decision below re-runs against
// the buffer's dirtiness at that moment.
```

---

### #3 🟠 High: `noteMissing`'s `"stale"` JSDoc documents one of its two disjuncts — the same collapse the round set out to fix

| | |
|---|---|
| **File** | `web/src/lib/composables/useActiveView.svelte.ts:185-186` |
| **Category** | comprehension-risk / false contract on a public interface |
| **Confidence** | 75 |
| **Found by** | knowledge-reviewer (High), adversarial-reviewer (fact confirmed by runtime probe; **dissents on severity → Medium**) |
| **Validation** | ✅ **confirmed** — validator verified the fact and the absence of test coverage; **sided with the Medium reading on exploitability** |

**Issue:** The implemented guard is a two-disjunct test (`:622`):
```ts
if (s.kind !== "viewing" || s.nibId !== nibId) return "stale";
```
The JSDoc describes only the second:
```
*    - stale (the view already moved off `nibId`) -> "stale": no state change,
*      nothing preserved; the report says nothing about the buffer on screen.
```
For **`gone(nibId)`** — same id, different kind — the first disjunct short-circuits to `"stale"`, and all three clauses are false:
- *"the view already moved off `nibId`"* — the view is on `nibId`, in a different `kind`.
- *"nothing preserved"* — the dirty buffer for `nibId` **is** preserved (`bufferKey` maps both `viewing` and `gone` to `edit:<id>`).
- *"the report says nothing about the buffer on screen"* — the buffer on screen **is** `nibId`'s.

`adversarial-reviewer` confirmed at runtime (probe P2): `gone(n1)` + dirty → `noteMissing("n1")` returns `"stale"` while that dirty buffer is on screen. The validator independently confirmed, and further confirmed **no test calls `noteMissing` from a `gone` state** — the `"stale"` test (`:416-433`) exercises only the *other* disjunct, and test #4 always calls from `viewing`. The untrue half of the contract is entirely unexercised.

**Why this is the round's most significant finding:** prior finding #2 was *"`noteMissing`'s `"kept"` collapses two structurally different outcomes; the JSDoc documents only one."* The round fixed that by splitting `"kept"` — and **introduced the identical defect in the replacement**: `"stale"` now collapses two structurally different outcomes (*view moved elsewhere, nothing on screen* vs. *dirty buffer for this very id still on screen*), with the JSDoc documenting only one. This is precisely the caller's warning that "a wrong replacement comment re-introduces the exact defect class."

**Severity dissent (recorded, not resolved away):** `knowledge-reviewer` rated **High** — `noteMissing` is a public `ActiveView` method with three structural implementers, and a future caller trusting *"stale ⇒ nothing preserved, safe to close and heal"* would destroy unsaved edits against a dirty `gone`, reinstating the very bug this change fixes. `adversarial-reviewer` and the validator both judged **Medium** — the sole caller's `"stale"` branch only clears a latch, so no caller can act on it destructively *today*; a doc defect, not a live bug. **Held at High** per the consolidation rule (highest severity among finders, dissent noted) and on precedent: the identical defect shape was rated High in the prior round, and the whole point of a contract is the callers it will have.

**Fix:** rewrite the bullet to describe the disjunction, and add a test pinning the uncovered case.
```
*    - the view is not `viewing` `nibId` (moved to another target, closed, creating, or
*      already `gone` on this same id) -> "stale": noteMissing changes nothing. This does
*      NOT mean no buffer is on screen — a `gone` buffer for `nibId` may still hold unsaved
*      edits. Callers must not close or heal on "stale".
```
Add to the `createActiveView · missing nib` block: `noteMissing("n1")` from `gone` returns `"stale"` and leaves `view.form` intact.

---

### #4 🟡 Medium: the stale branch's stated reason is false for two of its three sub-cases

| | |
|---|---|
| **File** | `web/src/App.svelte:302` |
| **Category** | comprehension-risk / comment-code mismatch |
| **Confidence** | 100 |
| **Found by** | broad-reviewer (Medium), knowledge-reviewer (corroborating) |
| **Validation** | ✅ **confirmed** (line corrected to 302; `pre_existing: false` confirmed) |

**Issue:**
```ts
if (outcome === "stale") {
  // The view moved off `id` before this microtask ran, so nothing was
  // reported and the URL describes a different nib — healing it here would
  // close a view the report says nothing about. ...
```
`"stale"` covers three sub-cases: moved to a different nib B, `closed`, or `creating`. *"the URL describes a different nib"* holds only for the first. Validator traced both counterexamples in source:
- **`closed`** — `closePanel()` calls `history.pushState({nibId: null}, "", closeUrl())` and `replaceClosed()` calls `history.replaceState({nibId: null}, ...)`. Both **null out** the nib id; neither points at a different nib.
- **`creating`** — `startCreate` / `startCreateChild` / `chooseType` all route only through `guarded({type:"START_CREATE"})`, whose only side effects are `apply(action)` + `reconcileBuffer`. The file has exactly three `deps.nav.*` call sites (`open`'s `navigateToNib`, the create-save hand-off's `navigateToNib`, `requestClose`'s `closePanel`), **none reachable from `START_CREATE`**. The URL still shows `?nib=<id>` — the **same** now-missing id.

The behavior (do nothing) is correct in all three; only the stated reason is wrong. Medium because it misstates URL state for anyone later extending `"stale"` handling on the false premise that the URL already points elsewhere.

**Fix:**
```ts
// The view moved off `id` before this microtask ran (to another nib, "creating",
// or closed) — none of which this report may act on: it says nothing about
// whatever (or nothing) is on screen now, and none of those transitions leave
// `?nib=id` as something this handler owns to heal. Release the latch (only if
// it is still ours) so a later report for `id` is not suppressed.
```

---

### #5 🟡 Medium: the round silently broke the conflict fallback's message delegation — a rejected save on a deleted nib can now report nothing

| | |
|---|---|
| **File** | `web/src/lib/composables/useActiveView.svelte.ts:427` |
| **Category** | error-handling / silent failure |
| **Confidence** | 75 |
| **Found by** | adversarial-reviewer (Medium) — single finder |
| **Validation** | ✅ **confirmed** (`pre_existing: no` confirmed — this round caused it). Validator found the impact **worse than filed**. |

**Issue:** The one genuine *logic* regression of the round. The chain:
1. User saves a **dirty** buffer for a deleted nib → server 409 with `remote: null` → `runNullRemoteConflictFallback(f)` (`:377-379`).
2. The fallback's gate `canSurface = () => form === f && f.dirty && f.externalChange === null` (`:404`) **requires `f.dirty`**.
3. `fetchSnapshot(f.id)` **resolves null** (deleted, no throw) → `loadFailed` stays false.
4. Neither branch fires — not `noteExternalChange` (snapshot null), not `notifyError` (gated on `loadFailed`). The silence is justified by:
```
// NOT emitted for a deleted nib (snapshot === null, no throw):
// "please retry" is wrong advice when the nib is gone — the missing-nib
// path (App.svelte) owns that message.
```
5. **But** App's missing-nib path now toasts **only on `"closed"`** — i.e. only when **pristine**. The fallback runs only when **dirty**. The delegation target is **mutually exclusive with the delegating case**; the message can never fire for this chain.

This is a regression of *this* round: the validator confirmed via `git diff HEAD -- web/src/App.svelte` that the pre-change `handleMissingNib` ran `view.syncTo(null); selection.close(); nav.replaceClosed(); toast.error(...)` **unconditionally** — dirty or not. The dirty/pristine split this round introduced is what severed the delegation.

**Amplifying evidence from the validator (raises stakes, not severity):** the impact is worse than "the wrong subsystem reports it." The *only* route to `gone` (which renders the persistent `anv-deleted-notice`) is `apply({type:"DELETED"})` — fired by the live-subscription bridge or by `noteMissing`. But **the fallback's own comment concedes the live subscription "may be down/lagging" — that is its literal reason for existing** — and App's detail query uses a plain urql document `cacheExchange` (`web/src/lib/graphql.ts`) with no polling or normalized-cache invalidation for another client's out-of-band mutation, so `detailNib` will not spontaneously re-resolve to null either. **In the exact race the fallback exists to handle, the proven-deleted knowledge is discarded and there is a real, potentially unbounded window with zero user feedback.** Held at Medium per the rule that validation never raises severity — but weigh this when fixing.

> Note: this does **not** contradict the established "toast dropped on the dirty path is deliberate; `anv-deleted-notice` says it better." That rationale assumes the notice *appears*. On this chain, nothing drives the view to `gone`, so it does not.

**Fix:** the fallback has already **proven** the nib is deleted and throws that knowledge away. Have it drive the machine rather than delegate: on `snapshot === null && !loadFailed`, route through the presenter's own missing-nib path (`noteMissing(f.id)` / `apply({type:"DELETED"})`) so the buffer reaches `gone` and the persistent notice reports the deletion. Then correct the comment at `:426-428` **and** the rationale at `useActiveView.svelte.test.ts:1063-1065` — the validator confirmed that test's comment ("App's missing-nib effect owns telling the user... never toast") is asserted by a test that explicitly sets `f.dirty = true`, i.e. it documents exactly the dirty-path case App no longer covers, so it is now false as stated.

---

## Pre-existing Issues

Informational — excluded from the verdict and Summary counts.

### P1 🟡 Medium: the "sole guard-bypass" twin at `App.svelte:265` was left uncorrected

| | |
|---|---|
| **File** | `web/src/App.svelte:265` |
| **Category** | comprehension-risk / dead contract |
| **Confidence** | 100 |
| **Found by** | knowledge-reviewer (Medium, marked pre-existing) |

This round's deliverable #1 rewrote `syncTo`'s JSDoc from "The SOLE guard-bypass" to "A guard-bypass" because `noteMissing` now bypasses the guard too. `App.svelte:265` still reads `// ... the view then syncs to the resulting selection — the sole guard-bypass path.` and was not touched. It is false on two counts: `syncTo` has four call sites (`App.svelte:257`, `App.svelte:267`, `TreeTable.svelte:462`, `TreeTable.svelte:465`), and `noteMissing` (`App.svelte:300`) bypasses `guarded()` as well. `TreeTable.svelte:461` even calls its own site "the documented guard-bypass path".

Classified pre-existing (the text predates the diff and was already inaccurate), **but the diff created the direct contradiction by deliberately revising its twin** — the file now carries two contradicting statements about the same property. A maintainer auditing guard-bypass paths (the highest-risk category in this presenter — the only way to abandon a dirty buffer without a confirm) who trusts `:265` will enumerate one path and miss three. **Recommend fixing in this round**: it is a one-line edit, and leaving it defeats the purpose of finding #1's fix.

**Fix:** `// view then syncs to the resulting selection — one of the guard-bypass paths (see syncTo's JSDoc).`

### P2 🟡 Medium: an open type picker survives a missing-nib CLOSE and can then create a child of a deleted nib

| | |
|---|---|
| **File** | `web/src/lib/composables/useActiveView.svelte.ts:631` |
| **Category** | composition failure |
| **Confidence** | 100 |
| **Found by** | adversarial-reviewer (Medium, marked pre-existing) |

Add-child picker open on `n1` → `n1` is deleted → pristine `noteMissing` applies `CLOSE` → the view closes and `form` nulls, but `typePicker` lives **outside** the `ViewState` machine and is rendered by a top-level `{#if view.typePicker}` in App. The picker survives on a closed view, still freezes Back/Forward (`blocksHistoryNav` ORs it in), and `chooseType()` then runs an **unguarded** `START_CREATE` parented to the deleted nib (`abandonsBuffer(closed, START_CREATE)` is false, so nothing stops it).

Pre-existing: the pre-change code reached the same `CLOSE` via `syncTo(null)` with identical consequences. **Suggest filing as a nib** — it is a real composition gap, out of scope for this round.

**Fix:** clear the picker whenever the buffer it is anchored to disappears — set `typePicker = null` in `reconcileBuffer` when the new state has no buffer (or when `bufferNibId` changes away from `typePicker.parentId`).

---

## Minor Findings

Reported and counted; never verdict-driving.

### Consistency

- `web/src/lib/composables/useActiveView.svelte.ts:187` — the `"closed" | "kept" | "stale"` outcome union is declared inline while its direct sibling `ConfirmChoice` (`:48`) — also a payload-free tri-state outcome, also consumed across the same set of files — is a named exported type with documented members. The union now appears in the interface, the implementation, the caller's branches, three stubs, and the tests. Extract it as an exported type for parity with the cited convention source. (consistency-reviewer, anchor 100 — quotable-fact safety net.)

### Residual Risks

- `web/src/App.svelte:301-318` — `handleMissingNib` branches with two `if`s and an implicit trailing else rather than a discriminated `switch`. Correct today (all 3 union members handled), but a future 4th outcome literal would silently fall through to the `"closed"` branch (heal URL + toast) with no compiler error. A `switch` with a `never`-check default would fail loudly instead. (broad-reviewer)

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| knowledge-reviewer | 5 | 1 |
| adversarial-reviewer | 4 | 2 |
| broad-reviewer | 3 | 1 |
| quick-reviewer | 1 | 0 |
| consistency-reviewer | 1 | 1 |
| test-reviewer | 0 | 0 |
| **Total** | **9** | |

Notes:
- **Issues Found**: total findings attributed to this agent (including shared findings). Refuted findings excluded.
- **Unique Issues**: findings reported ONLY by this agent.
- `test-reviewer`'s sole finding was refuted by validation; its contribution to this wave was **negative-space verification** — revert-probing all four new tests to prove they are load-bearing. That is a real result, not an absence of one.
- The roster cap's ranking was vindicated: `knowledge` and `adversarial` (the two kept judgment agents) produced all 3 Highs and all 3 uniques among primary findings.

---

## Specialist Notes

### Adversarial depth tier

**deep** — data-loss / data-mutation domain (unsaved-buffer destruction); all four techniques, with runtime probes at the presenter boundary. Six probes run (all deleted afterward; tree verified byte-identical).

### Verified-accurate claims (knowledge-reviewer + adversarial-reviewer, each traced to code)

The round's comment rewrites were **not** uniformly wrong — these claims were checked and hold:
- **`syncTo:172-174` "The only transition that may ABANDON a dirty buffer without a confirm"** — TRUE. Every unguarded `apply` enumerated: `EXPAND`/`COLLAPSE` → `abandonsBuffer` false; `SAVED` → false (persists, does not abandon); bridge `DELETED` → false, same buffer key; `noteMissing`'s two branches → below. Only `syncTo`'s `OPEN`(other id)/`CLOSE` can abandon a dirty buffer.
- **"`noteMissing` ... bypasses the guard only where it provably cannot fire"** — TRUE for **both** branches, by different mechanisms: `DELETED` hits `abandonsBuffer`'s `default: return false`; `CLOSE` is reached only under `!form?.dirty`, the negation of the guard's second conjunct. Both synchronous, no `await`, no TOCTOU window.
- **`:623-626` "DELETED keeps the same buffer key (`edit:<id>`)"** — TRUE. `bufferKey` returns `edit:${s.nibId}` for both `viewing` and `gone`; `reconcileBuffer` early-returns on `key === currentKey`.
- **"the outcome the live-subscription deletion path also produces for a dirty buffer, so whichever signal arrives first agrees"** — TRUE. Correctly scoped to *dirty*, so the pristine divergence does not contradict it.
- **"`gone` renders the whole form read-only, so 'kept' means the edits are still VISIBLE — NOT that the user can retrieve or save them"** — TRUE. `ActiveNibView.svelte:105` `disabled = isGone || loadingUnseeded`, threaded to title, tags, status/type/priority/estimate, body toggle, add-child, Save, Discard; `bodyModeEffective` forces `preview` and `bodyHtml` derives from `form?.body`, so edits render. **The M2 hedge is the correct description of the nibs-mpo4 reality.**
- **Test #4's comment** — accurate: `useHistoryNav.svelte.ts:86-93` re-anchors on the same id when `isBlocked()`, and `App.onPopState:267` calls `syncTo` unconditionally.

### CLAUDE.md compliance (checked by knowledge, consistency, quick, broad, test — all clean)

- **American English** — all added lines scanned across five agents; **no violations**.
- **No change-history narration** — grepped for "was previously" / "now uses" / "changed from" / "ported from"; **none found**. The new text correctly adds no provenance, consistent with the four comment-audit commits (`git log --oneline -6`).
- **No nib/issue IDs in comments** — **none**. (`nibs-vanish` / `nibs-gone` are test-fixture ids following the file's established fixture-naming convention, not tracker refs.)
- **Sibling marker families** (`F1:`, `F4:`, `L2:`, `(HIGH)`) — new comments correctly add none.
- **No hardcoded path separators** — no new path assertions in this diff.

The findings above are a *different* defect class from the audit's target: not provenance narration, but internally **inaccurate** "why" claims.

### M1 realignment — verified sound (consistency-reviewer + test-reviewer, independently)

`await vi.hoisted(async () => {...})` is the only *async* `vi.hoisted` in the suite (the 5 cited siblings are synchronous), but **both agents independently cleared it as necessity, not drift**: Vitest physically hoists `vi.hoisted`/`vi.mock` above all `import` statements (confirmed in `node_modules/@vitest/mocker/dist/chunk-hoistMocks.js`), so a hoisted factory cannot reference a normally-imported `writable` binding — it must `await import(...)`. **This exact technique is already established in this same file** at the pre-existing `vi.mock("@urql/svelte", async () => { const { readable } = await import("svelte/store"); ... })` (`App.test.ts:60-61`, unchanged). The 5 siblings only share `vi.fn()`s and never needed a real store. First-of-kind necessity. **M1 is properly fixed.**

### Test verification (test-reviewer — non-destructive revert-probes, all restored byte-exactly)

All four new `useActiveView.svelte.test.ts` tests pin real invariants:
- Removing the `form?.dirty` gate → "routes a DIRTY buffer to gone" **and** "survives a same-id resync" both fail. ✅
- Removing the `s.nibId !== nibId` staleness check → "ignores a stale report" fails; the probe additionally revealed the removal would silently close the **wrong** buffer (n2) in a live app. ✅
- Diverging `bufferKey`'s `gone` case from `viewing`'s → test #4 **and** the pre-existing live-bridge DELETED test both fail, confirming test #4 genuinely pins the buffer-identity invariant it claims. ✅
- `h.editForms.get("n1")!.dirty = true` is an established convention used ~20+ times in this same file (including the directly analogous live-bridge test at `:813`), operating on the injected fake `EditForm` double — the correct seam for a presenter-level unit test. ✅
- `App.test.ts`'s integration test: assertions load-bearing; `anv-deleted-notice` renders only in `ActiveNibView.svelte`'s `isGone` branch; `waitFor` is justified by the real `queueMicrotask` deferral, not papering over a race. ✅
- `vanishingDetailData` leakage: `restoreVanishingNib()` runs unconditionally in `beforeEach` before any `render(App)`, regardless of prior test outcome or order; no other test references `nibs-vanish`. ✅

### Considered But Not Flagged

**Refuted by validation:**
- `App.svelte:304-306` — *"the identity-guarded latch clear has no test coverage"* (broad-reviewer Medium, test-reviewer Medium; test-reviewer's revert-probe showed all 32 `App.test.ts` tests pass with the guard stripped). **Refuted by validator**: the guard defends an **unreachable** interleaving, so the probe passing is the *expected* result, not a coverage gap. The validator checked Svelte 5.55.0's source directly (`internal/client/reactivity/batch.js`, `dom/task.js`) and confirmed the effect flush is scheduled exclusively through native `queueMicrotask` (`queue_micro_task`); `handleMissingNib`'s `queueMicrotask(M1)` is called synchronously from inside that flush, so M1 drains before any macrotask. Every path that could move `viewState` to a *different* viewing nib (`syncTo` at `App.svelte:257`/`:267`, `TreeTable.svelte:462`/`:465`, plus `guarded()`/`save()`) requires a real click or network round-trip — all macrotask-separated. The only same-flush mover is the live bridge's `DELETED`, which yields a non-`viewing` state that the effect's own unconditional clear already handles, making the identity check a no-op there too. **knowledge-reviewer's counterexample is a valid `ViewState` sequence but not reachable within the microtask window the guard defends.** *This is not a recommendation to remove the guard — it is sound defensive coding on a public API.*

**Dismissed with sound reasoning (cross-checked, not promoted):**
- **Same-tick `A→B→A` bounce racing a pending microtask** (quick, anchor 25) — independently investigated and refuted by adversarial on the same ordering grounds. Consistent.
- **Latch logic functional bug** (broad, anchor 25, after tracing) — consistent with adversarial's six probes and the validator. No path found where a dirty buffer is destroyed, where the guard clears a latch it shouldn't, or where it fails to clear one it should.
- **Live-bridge `DELETED` vs. detail-query `noteMissing` racing the same deletion** (quick) — both orderings converge cleanly; whichever fires first flips state off `viewing`, and the other observes `"stale"` or the already-`gone`/`closed` state and no-ops. No double toast, no double teardown.
- **`noteMissing`'s `"closed"` branch lacking the identity re-check that `"stale"` has** (quick) — intentional and correct: reaching `"closed"` implies `noteMissing` already verified `nibId` was the current `viewing` target.
- **Whether `"stale"` is reachable at all from `App.svelte`'s caller** (knowledge, deferred as a design question) — materially answered by the #6 refutation: it appears unreachable from this caller. Defensive coding on a public interface method with three structural implementers is defensible regardless, and the *contract wording* (#3) is what was flagged.
- **`gone`+dirty → `syncTo("n2")` destroys the buffer with no confirm** (adversarial probe P3 confirmed the presenter behavior) — **unreachable**: `blocksHistoryNav` is true whenever dirty, and `handlePopState` (`useHistoryNav.svelte.ts:86-93`) early-returns under `isBlocked()` leaving `selectedNibId` unchanged, so `onPopState` can only ever call `syncTo(sameId)`. Not a finding.
- **Report loop / re-report storm** — refuted by probe P4 and by `reduce(gone, DELETED)` returning the identical object reference, which `$state.raw` does not fire on.
- **`seededKey` never reset on CLOSE** (adversarial) — real but pre-existing, off-assignment, masked by App's synchronous `editForm` seed from the urql cache, and unreachable via `noteMissing`'s CLOSE specifically (that nib no longer exists to re-open).
- **False "missing" report from a freshly-created `queryStore` briefly reading `fetching:false, data:undefined`** (adversarial) — condition unconfirmed and unchanged by this diff; `App.test.ts`'s 32 passing deep-link tests imply `fetching: true` on init.
- **Microtask outliving unmount** (adversarial) — identical shape to the pre-change `syncTo(null)`; not a regression.
- **`noteMissing` returning a bare string synchronously vs. `save()`'s `Promise<Outcome>`** (consistency) — justified by necessity: no I/O, and its caller must branch on the result.
- **Module-level shared `writable` + `beforeEach` reset vs. `TreeTable.test.ts`'s per-test fresh store** (consistency) — not comparable; `App.test.ts`'s single `mockQueryStore.mockImplementation` already branches per-nib-id across multiple concurrent call sites, and the `nibs-vanish` branch extends its own pre-existing `nibs-gone` convention exactly.
- **Three `ActiveView` stubs' new `noteMissing` line** (consistency) — `contexts.ts:99` uses a plain arrow, the two test files use `vi.fn(...)`; each matches its own file's established idiom for every other stub method. Mutually consistent.
- **Out-of-scope items** (nibs-dsc8, nibs-1nqt, nibs-mpo4, nibs-gysg, Archive→"deleted" copy) — respected as filed; not re-flagged. Note #3 still checks the *accuracy of the JSDoc's description* of the nibs-mpo4 reality, which is in scope and passed.

---

## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `web/src/lib/composables/useActiveView.svelte.ts` | comprehension-risk / false contract | 2 | 2026-07-14 (21-32-40) |
| `web/src/App.svelte` | comprehension-risk / false comment | 2 | 2026-07-14 (21-32-40) |

**Both rounds on this change produced their entire High set from the same category: comments making false claims on mechanically correct code.** Round 1: 3 Highs (`useActiveView.svelte.ts:172`, `:178`, `App.svelte`). Round 2: 3 Highs (`App.svelte:274`, `:281`, `useActiveView.svelte.ts:185`). Finding #3 is structurally the *same defect* as round 1's #2, re-introduced in its own replacement text.

This is a signal about the change, not about the reviewers: the presenter's comment blocks are carrying load-bearing multi-path invariants that the code does not enforce, and each rewrite re-derives them by hand. Consider, for the next round, pinning the contested invariants as **tests** (as #3's fix proposes) rather than as prose — a test cannot drift from the code the way these paragraphs keep doing.
