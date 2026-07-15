# Code Review

**Mode**: mid (explicit) · roster cap 3 — 5 gate-matched agents dropped | **Reviewers**: quick-reviewer, broad-reviewer, knowledge-reviewer | **Date**: 2026-07-14
**Source**: local changes — uncommitted working tree on `batch/buffer-safety-watch-cleanup`
**Scope**: 3 files reviewed (`web/src/App.svelte`, `web/src/lib/composables/useActiveView.svelte.ts`, `web/src/lib/composables/useActiveView.svelte.test.ts`), +287/-14 lines of the 7-file / +355/-21 working-tree diff
**Spec**: none found
**Validation**: 2 confirmed, 1 refuted, 0 uncertain, 0 waived, 0 unvalidated (over budget)
**Review round**: third-pass regression check on the newest delta (not fresh discovery)

## Agent Selection Rationale

Mode was **explicit** (`mid3`) — not second-guessed.

- **quick-reviewer** (always — review floor) [mid-tier `sonnet`]
- **broad-reviewer** (always — review floor) [mid-tier `sonnet`]
- **knowledge-reviewer** — took the single specialist slot. Generic ranking (Step 2b.5 rule 3) ranks knowledge/consistency *last*, but rule 2 assigns the first specialist slot to the changeset's **primary risk dimension**, and the caller supplied evidence-backed direction that the recurring defect class here is *comments asserting false invariants* (two prior rounds: every High was a false comment on mechanically correct code; round 2's fixes for round 1's false comments were themselves false). That is squarely this agent's lane, and as a judgment agent it inherits the session model — the top tier, which this trace-heavy mandate needs. [session model]

Dropped to the roster cap (all had **matching** gates — they lost slots, they were not skipped):

- **typescript-reviewer**: dropped — roster cap (mid3). **Hard-gate domain IS present** (TS/Svelte is the dominant changed language); coverage traded away for the cap. Mitigating: the TS-idiom surface in this delta is thin (one discarded return value, one `queueMicrotask`), and both floor agents cover it.
- **test-reviewer**: dropped — roster cap (mid3). **Hard-gate domain IS present** (162 of 355 diff lines are tests); coverage traded away for the cap. Mitigating: the caller established that every new test was revert-probed and confirmed load-bearing, which is most of what this agent would have re-derived.
- **adversarial-reviewer**: dropped — roster cap (mid3): gate matched (≥50 executable lines) but ranked below knowledge-reviewer. Mitigating: the data-safety claim was already verified by six adversarial runtime probes across two prior rounds.
- **design-reviewer**: dropped — roster cap (mid3): gate matched (the `ActiveView` interface gained `noteMissing` + an exported `MissingNibOutcome` type) but ranked below knowledge-reviewer.
- **consistency-reviewer**: dropped — roster cap (mid3): gate matched; its comment-code-mismatch lane overlaps knowledge-reviewer's, which won the slot on model tier.

Skipped on gates (not cap-related): security-reviewer (no security-adjacent surface), performance-reviewer (no DB/loops/caching), spec-compliance-reviewer (no spec — hard gate), data-migration-reviewer (no migration artifacts — hard gate), prior-feedback-reviewer (not a PR — hard gate).

**Model tiering (mid)**: knowledge-reviewer on the session model; quick-reviewer, broad-reviewer, and all three validators mid-tier (`sonnet`).

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 0 |
| 🟡 Medium | 1 |
| 🟢 Low | 0 |
| 🔵 Minor | 2 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts the reported-but-non-blocking findings. Pre-existing issues are listed separately and excluded from both.

**Verdict**: ✅ APPROVED

No primary Critical or High findings. The delta's central claims held up: **no path was found on which a dirty buffer can be silently destroyed**, and the `noteMissing` boundary matrix (`gone(other)`, `viewing(other)`, `closed`, `creating`, same-id vs different-id, and the `gone → viewing → gone` bounce) was traced exhaustively by all three agents with no behavioral defect found. The recurring false-comment defect class dropped from **3 Highs (round 2) to 1 confirmed Medium** — and the round's two headline fixes (#3's `gone → "kept"` branch and #5's fallback-drives-the-machine rewiring) were independently confirmed correct, including under the live-bridge race.

---

## Findings

### #1 🟡 Medium: the fallback's "noteMissing routes it to `gone`" is false when the live bridge won the race

| | |
|---|---|
| **File** | `web/src/lib/composables/useActiveView.svelte.ts:479-481` |
| **Category** | comprehension-risk / comment-code mismatch |
| **Confidence** | 75 |
| **Found by** | knowledge-reviewer (COULD → Medium) |
| **Validation** | CONFIRMED (`pre_existing` corrected to **false** — authored by this delta) |

**Issue:** The comment on the fallback's resolved-null branch asserts a mechanism that is true for only one of two reachable sub-cases:

> `canSurface()` held, so the buffer is still `f` and dirty: noteMissing **routes it to** `gone`

When the live subscription's ungated `DELETED` fires during the save/fetch round-trip, the state is **already** `gone(f.id)` by the time the fallback resolves. The race is genuinely reachable — three independent facts, each verified:

1. `bufferKey()` (`useActiveView.svelte.ts:246-249`) maps **both** `viewing` and `gone` to the same `edit:<id>` key, so `reconcileBuffer()` short-circuits on the `viewing → gone` transition and `form` keeps its identity.
2. `classifyNibEvent`'s deleted branch (`nibChange.ts:89-91`) returns `{ deleted: true, external: null, … }` — a deletion **never** populates `external`, so `f.externalChange` stays `null`.
3. Therefore `canSurface()` (`form === f && f.dirty && f.externalChange === null`) still holds — so the fallback does **not** bail, and reaches `noteMissing(f.id)`.

At that point `noteMissing` takes its **first** branch (`:367`, `s.kind === "gone" && s.nibId === nibId → "kept"`) and applies **nothing**. It does not route.

**Why Medium, not High:** the comment's *conclusion* survives — the buffer does end in `gone` and the deleted notice does report the deletion. There is no behavioral defect and no maintainer decision that goes wrong as a result: a maintainer who believed "always routes" and inlined `apply({type:"DELETED"})` would still be correct, because `DELETED` from `gone` is a reducer no-op (`activeView.ts:84-86`). This is precisely the "true-only-for-some-sub-cases" mechanism claim the round set out to eliminate, caught on its own new code.

**Fix:** replace the mechanism claim with one that covers both sub-cases:

```typescript
// ... `canSurface()` held, so the buffer is still `f` and dirty: noteMissing
// lands it in `gone` — routing it there, or agreeing with the live bridge if
// that already did — where the view's deleted notice reports the deletion and
// the rejected save stops being silent.
```

---

## Pre-existing Issues

Informational only; excluded from the verdict and Summary counts.

### P1 🟠 High: the guard's Save-branch comment promises a resolver that the deleted path never surfaces

| | |
|---|---|
| **File** | `web/src/lib/composables/useActiveView.svelte.ts:323-325` |
| **Category** | comprehension-risk / false contract |
| **Confidence** | 100 |
| **Found by** | knowledge-reviewer (SHOULD → High) |
| **Validation** | CONFIRMED — `pre_existing: true` upheld against an explicit `git show HEAD:` check |

**Issue:** The comment justifying `if (!outcome || outcome.kind === "conflict") return false;` reads *"save() has surfaced the resolver; the user resolves it and re-navigates manually."* On the proven-deletion path this is concretely false: `f.noteExternalChange` is never called (only the `if (snapshot)` branch calls it), and `ActiveNibView.svelte:673` gates the resolver on `{#if !isGone && … && form.externalChange && …}` — **doubly** false here (`isGone` is true AND `externalChange` is null). No resolver appears, and there is nothing to resolve: Load-theirs / Overwrite are meaningless against a proven deletion. The promised "resolve and re-navigate manually" recovery does not exist.

**Why pre-existing (and why that attribution was contested and then upheld):** this was the one finding whose attribution could have flipped the verdict, so it was validated specifically on that question. The validator diffed the pre-delta file: the comment text at old `:293-294` is **byte-identical** to current `:323-324` (a pure context line, untouched this round), and the pre-delta `runNullRemoteConflictFallback` had `if (snapshot) {…} else if (loadFailed) {…}` with **no trailing `else`** — so on a resolved-null fetch the old code did *nothing at all*, meaning the comment was **already false** for this exact sub-case. This round changed the falsity's *character* (silent omission → a `gone` state where the resolver is structurally gated out) but did not introduce it.

**Note:** the `gone` + dirty stranding itself is out of scope (already filed). This finding is narrowly about the comment.

**Fix:** split the two conflict sub-cases at `:323-325`:

```typescript
// Conflict → ABORT the navigation and leave the buffer intact. Two sub-cases,
// both of which make proceeding wrong: a resolvable conflict (save() surfaced
// the inline Load-theirs/Overwrite resolver — the user resolves it and
// re-navigates), or a proven deletion (the null-remote fallback routed the
// buffer to `gone`; no resolver is surfaced there, and the deleted notice
// reports it instead).
```

---

## Minor Findings

### Consistency

- `web/src/App.test.ts:977` — the exact false claim this round fixed at `App.svelte:264` survives verbatim in the delta's own test file: *"view.syncTo(selection.selectedNibId) — **the sole guard-bypass**"*. Disproved by the same grep that justified fix #5: `syncTo` has 4 production call sites (`App.svelte:257,269`, `TreeTable.svelte:462,465`) and `noteMissing` bypasses the guard too. **Pre-existing context line, and outside the named 3-file scope** — reported because it makes fix #5 incomplete rather than wrong, and a one-word grep closes it. (broad-reviewer, corroborated by orchestrator grep)

### Residual Risks

- `web/src/lib/composables/useActiveView.svelte.ts:482` — the fallback discards `noteMissing`'s return value. Safe **today** by an unenforced emergent invariant: `canSurface()` pins `form === f && f.dirty`, and the branches between `:463` and `:482` are synchronous, so only `"kept"` is reachable — `"closed"` (whose contract says *"the caller owns healing the URL and reporting the deletion"*) cannot fire. If a future change relaxed `canSurface()` to admit pristine buffers, the ignored return would silently reintroduce the zero-feedback bug this round fixed, with no type error and no test to catch it. knowledge-reviewer examined the same code and rated it safe-not-a-defect; the two agents agree on the facts and differ only on whether latent fragility is reportable. Anchor 50, no current consequence. (broad-reviewer)

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| quick-reviewer | 0 | 0 |
| broad-reviewer | 2 | 2 |
| knowledge-reviewer | 2 | 2 |
| **Total** | **4** | |

Refuted findings are excluded. Zero findings were found by more than one agent — no corroboration was available, which is why all three primaries went to validators rather than being waived.

---

## Specialist Notes

### Considered But Not Flagged (all agents)

**Refuted by validator (removed from findings):**

- **`syncTo`'s "the only transition that may ABANDON a dirty buffer without a confirm" is disproved by the SAVED hand-off** (`useActiveView.svelte.ts:188-190`, knowledge-reviewer, SHOULD → High, confidence 75). This would have flipped the verdict to NEEDS_CHANGES, so it drew close scrutiny. The finder's mechanical facts were all correct — from `creating` with `dirty === true`, `save()` applies SAVED, `form` swaps, `confirm` is called 0 times — but the conclusion does not follow, on **either** reading of "abandon":
  - *Term of art*: `abandonsBuffer`'s own contract (`activeView.ts:93-97`) reads "true when applying `a` to `s` would discard an **unsaved** working-copy buffer". SAVED runs only after `f.save()` returned `outcome.kind === "created"` — the content is already on the server, so there is no unsaved buffer to discard.
  - *Plain English ("is real work lost?")*: independently verified — `EditForm`'s constructor (`nibForm.svelte.ts:401-408`) does `this.setFields(init); this.rebaseline(init);` from the `pendingCreateSeed` snapshot, so the successor form is **pristine from the instant it exists**. The discarded `CreateForm`'s stale `dirty === true` describes an object whose content already reached the server — structurally the same as `EditForm.save()` rebaselining in place after a successful write, which nobody here calls an "abandon".
  
  This is the reviewer-over-reads-a-term-of-art false positive the project has been burned by, and the validation wave caught it. The claim stands as written.

**Examined and cleared — every comment claim in the delta was individually traced** (the explicit probe mandate). Cleared claims, each with the evidence that cleared it:

- `:190` **"`noteMissing` bypasses the guard only where it provably cannot fire"** — TRUE, both branches. `DELETED` → `abandonsBuffer` `default` → `false`; the `CLOSE` branch runs only when `!form?.dirty`. Both conjuncts of `abandonsBuffer(s,a) && form?.dirty` are provably false, and there is no `await` between `noteMissing`'s and `guarded`'s reads of `form?.dirty`.
- `:58` **"`gone` renders the form read-only"** — defensible, not a `readonly`/`disabled` conflation. It is the established local vocabulary: `ActiveNibView.svelte:105` is literally `const disabled = $derived(isGone || loadingUnseeded); // gone / still-loading -> read-only`, and `:671` says "a deleted nib is read-only". Sibling-consistent.
- `:59` **"not savable"** — verified. Save's `disabled` (`:639`) ORs in `disabled` (= `isGone`); the only other `handleSave` caller (`:789`) sits inside `{#if !isGone …}` (`:673`).
- `App.svelte:285-291` **latch / early-return reasoning** — TRUE. Every state a report can produce (`gone`, `closed`) early-returns; "getting back to `viewing` on the same still-missing id takes an OPEN" verified exhaustively — `OPEN` is the only action reaching `viewing` from `gone`/`closed` (`SAVED` requires `creating`), and its only sites are `open()` and `syncTo()`.
- `App.svelte:307-313` **the `"stale"` enumeration** — `gone(other)` is a fourth `"stale"` producer the three-case list does not name, but "it moved to another nib" fairly covers a view targeting n2, and the branch's conclusion holds for all four producers. The type-level contract ("Any other state → `stale`") is exhaustive and precise.
- **Is `creating` safe to no-op on?** — traced. `startCreate` calls neither `nav.*` nor `selection.*`, so `?nib=<deleted id>` and `selection.selectedNibId` both persist through `creating`, healing on the next `requestClose()` or reload. No hazard — and strictly better than the pre-delta code, which would have destroyed the dirty create buffer outright via `syncTo(null)`.
- `App.svelte:276-281` **live-bridge asymmetry** — adequately captured. The pristine disagreement (bridge → `gone`; this effect → `closed`) is derivable from the comment as written, and the `"whichever signal arrives first agrees"` claim at `:199` is correctly **scoped to a dirty buffer**, where the two paths genuinely do agree.
- **All new/changed test comments** — audited individually; all accurate.

**Boundary matrix — traced by all three agents, no defect found:** `gone(other)`, `viewing(other)`, `closed`, `creating` → all correctly `"stale"`; `gone(same)` dirty and pristine → `"kept"`; the `gone → viewing → gone` bounce converges in one hop with no loop, form identity preserved via the shared `edit:<id>` buffer key.

**Fallback vs. live-bridge race — no double-report, no fighting:** both orderings land on `gone` with the buffer intact; the second `noteMissing` is an idempotent `"kept"` no-op, and neither path toasts on `"kept"`.

**Suppressed by the confidence gate:** none. (broad-reviewer's `:482` Low at anchor 50 was routed to Residual Risks rather than suppressed, since Step 5.5 cross-referencing showed knowledge-reviewer had examined the same code — the two agree on the facts and differ only on reportability.)

**Untested boundary inputs** (`gone(other)`, `closed`, `creating` → `"stale"`): noted by knowledge-reviewer; no undocumented assumption rides on them — the contract's catch-all is exhaustive and correct for all three.

**Out-of-scope observation:** `contexts.ts:99`'s stub returns `noteMissing: () => "closed"` — the one token that *instructs* the caller to act (close selection, heal URL, toast), where `"stale"` would be the honest no-op for a stub whose neighbors are documented no-ops. No live consequence (App constructs the real view; no component test routes `handleMissingNib` through the stub). Outside the 3-file scope.

### Working-tree integrity

All agents were dispatched read-only with an explicit prohibition on `git checkout` / `restore` / `reset` / `stash` / `clean`. knowledge-reviewer ran four runtime probes (A–D) and reverted them. Verified after the review wave: `git diff HEAD --stat` returns exactly the original **7 files, 355 insertions, 21 deletions**, with no untracked strays.

### Pre-flight gates

Run once for the wave (agents instructed not to re-run):

- `cd web && npx vitest run --reporter=agent` → **1222 passed / 60 files**. PASS.
- `cd web && npx svelte-check` → **0 errors, 0 warnings**. PASS.

Both match the state the caller reported.

### CLAUDE.md rule enforcement (orchestrator-run, on added lines only)

- **American English** — clean (grepped `behaviour|colour|initialis|cancelled|normalis|synchronis|neighbour|centre|licence|grey|serialis|organis`).
- **No nib/issue IDs in comments** — clean. The round's removal of the `(MEDIUM #3)` reference in the test file is confirmed in the diff. Pre-existing label families (`(HIGH)`, `(L2)`, `F1:`, `F4:`) are context lines outside this delta.
- **No change-history narration** — clean on added lines.

---

## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `web/src/lib/composables/useActiveView.svelte.ts` | comprehension-risk / false comment | 3 | 2026-07-14 (round 1) |

The defect class is genuinely converging rather than merely relocating: **round 1** produced 3 Highs on this file (`syncTo`'s "SOLE guard-bypass", `noteMissing`'s `"kept"` collapse, the deleted pristine-divergence record); **round 2** produced 3 Highs + 2 Mediums (false "first signal" invariant, self-contradicting latch block, `"stale"` JSDoc documenting one of two disjuncts, plus the #5 delegation regression); **round 3** produces **1 confirmed Medium** on newly-authored text, with one attempted High refuted on validation. `App.svelte`, which carried 2 Highs in round 2, is clean this round.
