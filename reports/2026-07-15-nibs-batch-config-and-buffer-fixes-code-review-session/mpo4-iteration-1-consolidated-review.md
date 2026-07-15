# Code Review

**Mode**: mid (explicit) | **Reviewers**: quick, broad, knowledge, consistency, design, test, spec-compliance, adversarial, typescript (9) | **Date**: 2026-07-15
**Source**: local uncommitted changes on `batch/config-and-buffer-fixes`
**Scope**: 4 files changed, +136/-8 lines
**Spec**: `.nibs/nibs-mpo4--the-gone-state-preserves-a-dirty-buffer-but-render.md` (inferred — discovered by repo search, severity capped at Medium)
**Validation**: 7 confirmed, 0 refuted, 0 uncertain, 0 waived, 0 unvalidated

## Agent Selection Rationale

Mode was given explicitly (`mid`), so Step 2a.5 selection was skipped. No roster cap given.

- **quick-reviewer** — always (floor)
- **broad-reviewer** — always (floor)
- **knowledge-reviewer** — substantive change; the diff is comment-dense and comment truth is this codebase's documented dominant defect class
- **consistency-reviewer** — rich sibling surface to compare against (`.anv-conflict` banner, `handleCopyId`, other `copyToClipboard` callers, sibling gone-state tests)
- **design-reviewer** — `copyToClipboard`'s shared signature gains an optional parameter: a contract change with existing callers
- **test-reviewer** — hard gate: test files present in changeset
- **spec-compliance-reviewer** — hard gate: a spec was discovered (`nibs-mpo4`)
- **adversarial-reviewer** — ≥50 changed executable lines; the pinned-state boundaries (gone+dirty, `loadingUnseeded`, archived vs deleted) are the stated risk surface
- **typescript-reviewer** — hard gate: `.ts`/`.svelte` files present in changeset
- **security-reviewer**: skipped — no security-adjacent surface; a clipboard write of the user's own buffer, no auth/crypto/network/untrusted-input parsing
- **performance-reviewer**: skipped — no DB/ORM queries, I/O loops, concurrency, or caching in the diff
- **data-migration-reviewer**: skipped — no migration artifacts in changeset (hard gate)
- **go / dotnet / cpp / rust-reviewer**: skipped — no such files in changeset (hard gate). Note Go files exist in the project but not in this diff.
- **prior-feedback-reviewer**: skipped — local changes, not a PR (hard gate)

**Model tiering (mid)**: judgment agents (knowledge, design, spec-compliance, adversarial) inherited the session model; volume agents (quick, broad, consistency, test, typescript) and all 7 validators ran mid-tier (`sonnet`).

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 3 |
| 🟡 Medium | 2 |
| 🟢 Low | 2 |
| 🔵 Minor | 5 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts reported-but-non-blocking findings. No pre-existing issues were reported.

**Verdict**: ❌ NEEDS_CHANGES (3 High)

The change's core design is sound and its test suite is genuinely strong — test-reviewer independently reproduced all 7 claimed mutations in an isolated worktree and found no eighth decorative guard. What fails the review is not the mechanism but its *justification*: two of the three Highs are false comments about platform behavior, in a changeset whose whole purpose was to correct a false claim about platform behavior. The third is a real contrast regression in the one shipped light theme.

---

## Findings

### #1 🟠 High: "Copy body" text and icon are invisible in the Daylight theme for a deleted nib

| | |
|---|---|
| **File** | `web/src/lib/components/ActiveNibView.svelte:701-712` |
| **Category** | production-reliability / contrast-accessibility |
| **Confidence** | 100 |
| **Found by** | broad-reviewer (High) |
| **Validation** | CONFIRMED — every premise independently re-derived, including a from-scratch OKLCH→sRGB WCAG recomputation |

**Issue:** The new `Copy body` Button (`variant="outline"`) is nested inside `.anv-gone-notice`, which sets `color: var(--destructive-foreground)` for the deleted case (`:1013-1014`). shadcn's `outline` variant (`web/src/lib/components/ui/button/button.svelte:11`) sets `bg-background` but **no resting-state text color** — only `hover:text-foreground`. Tailwind v4's preflight sets `button { color: inherit }` (`web/node_modules/tailwindcss/preflight.css:238-252`), so the button's label and its `Copy` icon (stroke=`currentColor`) inherit the notice's `--destructive-foreground` while the button paints its own `--background`. In the `daylight` palette those two tokens nearly coincide:

```
--background:             oklch(0.985 0.004 85)   /* app.css:299 */
--destructive-foreground: oklch(0.99  0.005 27)   /* app.css:314 */
```

Independent recomputation gives ≈`rgb(251,250,247)` on ≈`rgb(255,251,250)` — **≈1.01:1** contrast, against a ≥4.5:1 requirement. The same computation on the dark `:root` tokens gives 11.16:1, so only `daylight` is affected — the app's one shipped light theme (`dark: false`, `web/src/lib/types.ts:179-184`), which drops the `.dark` class and so disables the `dark:bg-input/30` override that would otherwise rescue it.

**Why it matters:** this button is the entire feature. In Daylight the control is present, bordered, hoverable and keyboard-reachable — but at rest gives no legible cue of what it is, so a user may never discover the recovery action the change exists to provide. This is **not** the already-tracked `--warning-foreground` fallback issue (that one is on the `archived`/warning path and is pre-existing via `.anv-conflict`); `--destructive-foreground` is a properly-defined token, and the defect is the new nesting interaction.

**Fix:** stop relying on inherited `color` + `bg-background`; track `currentColor` and keep the background transparent against the notice's own band:
```svelte
<Button
  variant="outline"
  size="sm"
  class="border-current bg-transparent text-current hover:bg-black/10 dark:hover:bg-white/10"
  data-testid="anv-gone-copy-body"
  title="Copy the description's markdown source"
  onclick={handleCopyBody}
>
```

---

### #2 🟠 High: The title comment blames `disabled` for the selects' unselectability — the real cause is a `select-none` class

| | |
|---|---|
| **File** | `web/src/lib/components/ActiveNibView.svelte:634-636` |
| **Category** | comment-truth / knowledge-preservation |
| **Confidence** | 100 |
| **Found by** | knowledge-reviewer (High), spec-compliance-reviewer (Low — same clause, framed as an unverified over-claim) |
| **Validation** | CONFIRMED |

**Issue:** The comment's final clause reads:

> This is NOT parity with the metadata band below — bits-ui's Select takes only `disabled` (it has no readonly concept), **so those values stay unselectable.**

The conclusion is true; the stated cause is false. The metadata values are unselectable because shadcn's Select trigger hard-codes `select-none` (→ `user-select: none`, which inherits to the value text) at `web/src/lib/components/ui/select/select-trigger.svelte:22` — **unconditionally**, not gated on `disabled`. The `disabled`-scoped classes on that same line touch only `cursor` and `opacity`, never `user-select`. `StatusSelect`, `TypeSelect` and `PrioritySelect` all render their value text as a direct child of that trigger, so the class reaches it; the consumer's `class="flex-1"` does not collide with `select-none` under the `tailwind-merge` config. `disabled` contributes nothing — and this session established empirically that `disabled` does not block selection in Chromium at all.

The comment is also self-refuting: three lines earlier it argues HTML "leaves selection of the control's text to the user agent, **so it is not a property this can rely on**" — then relies on exactly that property in the affirmative to assert the selects are unselectable.

**Why it matters:** it forecloses a real solution space with a wrong reason. A maintainer later asked to make gone-state metadata recoverable reads "bits-ui has no readonly concept, so those values stay unselectable", concludes the limitation is upstream and unfixable, and stops. The actual blocker is a local CSS class they control. The bits-ui half of the claim is accurate and worth keeping (verified: `bits-ui@2.16.3` Select has no `readonly` prop) — it is the causal "so" that is wrong.

**Fix:**
```
This is NOT parity with the metadata band below — bits-ui's Select takes only
`disabled` (it has no readonly concept), and its shadcn trigger sets
`select-none`, so those values are unselectable regardless.
```

---

### #3 🟠 High: Test comment asserts `disabled` makes the title "unrecoverable" — the premise this change exists to retire

| | |
|---|---|
| **File** | `web/src/lib/components/ActiveNibView.svelte.test.ts:730-731` |
| **Category** | comment-truth / knowledge-preservation |
| **Confidence** | 100 |
| **Found by** | knowledge-reviewer (High) |
| **Validation** | CONFIRMED |

**Issue:** The comment states that swapping the attribute back to `disabled` "reinstates the **unrecoverable title**" — i.e. `disabled` ⇒ not recoverable. That is false in the shipping browser: this session verified in real Chromium 145 that a `disabled` input's text is selectable and copyable (drag-select + triple-click + Ctrl+C recovers the full value, including when ellipsis-truncated). It is [Unverified] anywhere else, since no Firefox is available on this platform.

The comment cites "(see the input's comment)" while stating the opposite of what that comment carefully says. The component comment at `:630-633` deliberately rests on *"HTML … leaves selection … to the user agent, so it is not a property this can rely on"* — never on "`disabled` blocks selection". The two cannot both be right, and the test's version is the empirically wrong one.

The trailing disclaimer ("Whether the text is genuinely *selectable* is a rendering behavior jsdom cannot answer") does not cure this: it scopes what the **assertion** verifies, not what the **comment** claims. The validator weighed the charitable reading — "unrecoverable" as shorthand for "no longer reliably recoverable across UAs" — and judged it plausible but not what a maintainer skimming the line takes away.

**Why it matters:** this is precisely the false premise the component comment was written to avoid, reintroduced in the test that guards it. The nib itself exists because an earlier review asserted this same claim without testing it. A maintainer learns a wrong platform fact and propagates it; the real justification (selection is UA-defined under `disabled`, so it cannot be relied on; `readonly` is spec-guaranteed focusable) is lost.

**Fix:**
```ts
// Both halves are load-bearing: dropping the attribute makes the title
// editable, while swapping it back to `disabled` puts recovery back at the
// user agent's discretion.
```

---

### #4 🟡 Medium: `readonly={disabled}` also covers `loadingUnseeded`, opening a title-corruption path at the seed boundary

| | |
|---|---|
| **File** | `web/src/lib/components/ActiveNibView.svelte:646` (comment at `:627-636`) |
| **Category** | correctness / comprehension-risk |
| **Confidence** | 100 (promoted on agreement) |
| **Found by** | adversarial-reviewer (Medium — corruption cascade), broad-reviewer (Medium — comment scope; assessed as harmless). quick-reviewer examined and **dismissed** it as inert. |
| **Validation** | CONFIRMED — the validator sided with adversarial's reading and found the "harmless" framing understates it |

**Issue:** `disabled = $derived(isGone || loadingUnseeded)` (`:108`), so `readonly={disabled}` applies the swap to **both** states — but the new comment justifies it only for `gone`. `readonly` (unlike `disabled`) leaves the empty placeholder title focusable and caret-placeable during the detail fetch. The cascade:

1. User clicks a nib row, then clicks the visible empty title placeholder and types before the async detail fetch resolves.
2. Keystrokes are blocked by `readonly` — **no `input` event fires**, so `form.dirty` stays false.
3. That clean-buffer state is exactly what lets the seed effect fire: `useActiveView.svelte.ts:638-651` is guarded by `if (!f.dirty)` → `applyExternal` → `setFields`/`rebaseline` (`nibForm.svelte.ts:473-480`).
4. `loadingUnseeded` flips false in the same reactive flush, atomically removing `readonly`. The input is patched in place via `bind:value` (not remounted — it sits under the stable `{#if form}` at `:489`), so `document.activeElement` is unchanged and the caret lands at end-of-value.
5. Further keystrokes now insert into the **seeded** title → `form.dirty` becomes true → Save un-disables (`:668`) → a corrupted title is persistable.

Under the old `disabled` this was structurally impossible: the click could never focus the field, so no keystroke could land. The validator judged the trigger plausible rather than contrived, and noted the harm materializes **at the `loadingUnseeded → false` boundary**, not within the window — which is what quick-reviewer's and broad-reviewer's "nothing to focus, no observable harm" framing misses.

**Fix:** split the two states at the attribute, so `readonly` applies only where its justification does:
```svelte
readonly={isGone}
disabled={loadingUnseeded}
```
The `readonly` rationale (recovering unsaved edits by selecting text) applies only to `isGone`; an unseeded form is a blank placeholder with nothing to recover and should stay unfocusable. `.anv-title:read-write:hover` already excludes both. If both flags were ever true at once, `disabled` wins — the safe direction. Whichever way this is resolved, the comment must state what it does to `loadingUnseeded`.

---

### #5 🟡 Medium: "Copy body" is offered for `archived`, a buffer the app can still save

| | |
|---|---|
| **File** | `web/src/lib/components/ActiveNibView.svelte:701` |
| **Category** | correctness / composition |
| **Confidence** | 75 |
| **Found by** | adversarial-reviewer (Medium) |
| **Validation** | CONFIRMED, including `pre_existing: no` |

**Issue:** The panel and the close-guard disagree about `archived`, and the new button reinforces the wrong side:

- `disabled = isGone` (`:108`) greys **both** Save and Discard for archived and pins the body to preview.
- `canSaveState` (`web/src/lib/composables/activeView.ts:128-129`) returns **true** for archived, and the close-guard's confirm dialog (`App.svelte:212-236` via `guarded()`, `useActiveView.svelte.ts:334-357`) genuinely renders a working **Save** button for a dirty archived buffer.

So: nib archived under a dirty editor → the notice says "This nib was archived" beside a [Copy body] button → the user reasonably reads that as *these edits are unsavable, copy them out* → closes the panel → the guard offers Save → the user, already committed to the copy-out reading, picks Discard → **title edits are destroyed** (there is no Copy title) and the body survives only in the clipboard, to be re-pasted into a nib they must now find in the archive.

The `disabled = isGone` derivation is pre-existing (commit `36106d2` deliberately kept panel-level Save disabled for archived, documented as: *"an archived buffer is still saved through the dirty-nav guard's prompt, not through this panel"*). But no UI element invited a copy-this-out reading before this diff — and the new comment at `:691-692` states unqualified that *"the panel keeps the dirty buffer but can no longer save it"*, without scoping that to deleted. That is the same conflation the finding says a user will make, baked into the code. Hence the composition, and the comment, are new.

**Fix:** gate the button on savability rather than `isGone` — render only when `goneReason === "deleted"`. For `archived`, the honest affordance is the opposite one: either let Save stay enabled (derive from `canSaveState(viewState)` rather than `isGone`), or have the archived notice say the edits can still be saved on close. At minimum, scope the `:691-692` comment to the deleted case.

---

### #6 🟢 Low: `copyToClipboard` selects its toast branch by truthiness rather than presence

| | |
|---|---|
| **File** | `web/src/lib/clipboard.ts:18` |
| **Category** | design / api-contract |
| **Confidence** | 75 (promoted on agreement) |
| **Found by** | design-reviewer (Medium), typescript-reviewer (Low) |
| **Validation** | CONFIRMED, with a scoping correction — see note |

**Issue:** `toast.success(label ? ... : \`Copied "${text}" to clipboard\`)` tests **truthiness** on an optional string, so `copyToClipboard(text, "")` silently falls back to quoting the entire text — the empty label produces the *least* conservative output rather than the most. `label !== undefined` is the predicate the documented optional-parameter contract implies.

design-reviewer additionally argued the wider API shape is hazardous: the unbounded branch is the default and is guarded only by an unenforceable caller obligation ("Omit it for short values like an id"), and `(text: string, label?: string)` is an adjacent same-typed positional pair, so `copyToClipboard("body", f.body)` type-checks and toasts a whole document.

**Severity note (consolidation correction):** this was initially consolidated at Medium/75 by taking design's severity across the merge. The validator showed the two finders only overlap on the **truthiness predicate**; design's broader API-shape argument is single-finder and rests entirely on hypothetical future callers. All 3 call sites are enumerated and verified correct — `RowContextMenu.svelte:97` and `ActiveNibView.svelte:367` pass short ids with no label, `ActiveNibView.svelte:376` passes the string literal `"body"`. Neither the empty-string branch nor the transposition hazard is reachable today. Re-scoped to typescript-reviewer's narrower Low reading: real and deterministic, but not a live defect.

**Fix (minimal):**
```ts
toast.success(label !== undefined ? `Copied ${label} to clipboard` : `Copied "${text}" to clipboard`);
```
Optionally also cap the quoted branch (truncate past ~60 chars), which would demote `label` from a safety mechanism to a presentation nicety. The project has no back-compat requirement, so an options-object signature (`copyToClipboard(text, { label })`) remains cheap later if a third caller ever needs it.

---

### #7 🟢 Low: The newly-focusable title creates a dead keyboard zone in the very flow the change enables

| | |
|---|---|
| **File** | `web/src/lib/components/ActiveNibView.svelte:646` |
| **Category** | correctness / composition |
| **Confidence** | 100 |
| **Found by** | adversarial-reviewer (Low) |
| **Validation** | CONFIRMED |

**Issue:** `isInputFocused()` (`web/src/lib/composables/useKeyboardShortcuts.svelte.ts:18-24`) checks only `tagName` (`INPUT`/`TEXTAREA`/`SELECT`) and `isContentEditable` — never `readOnly`/`disabled`. It gates the `n`, `e`, `Delete` and `Backspace` handlers (`:108-139`; `$mod+n` is the sole ungated exception). So: gone nib → user selects the title text to copy their unsaved title (**the stated purpose of the swap**) → focus is now parked in the title → every one of those shortcuts returns early, while the readonly input silently swallows the same keystroke. The keypress does nothing at all, with no feedback.

The validator confirmed this is genuinely new: `disabled` blocks focus (spec-defined), and selection under `disabled` needs no focus — so the old code could not park focus there. It also confirmed the title is the only focusable control added to the gone panel (the selects still take plain `{disabled}`; TagEditor's input is unrendered via `{#if !disabled}`), and that no `stopPropagation` sits between the input and the window-level tinykeys listener.

Low because it is self-healing — click elsewhere and the shortcuts return.

**Fix:** let `isInputFocused()` ignore non-editable inputs, so a keystroke the field will discard falls through to the shortcut layer instead of vanishing between the two:
```ts
if (el instanceof HTMLInputElement && (el.readOnly || el.disabled)) return false;
```
Note the fix touches shared shortcut code and deserves its own thought: `Delete`/`Backspace` would then fire a nib action while the caret sits in a field the user may believe they are editing. If that trade is unwelcome, an alternative is to leave `isInputFocused()` alone and accept the papercut.

---

## Minor Findings

### Consistency

- `web/src/lib/components/ActiveNibView.svelte.test.ts:748` — British spelling "licence" in a new comment; CLAUDE.md requires American English in newly authored text ("license"). (broad-reviewer)
- `web/src/lib/components/ActiveNibView.svelte:1006` — `.anv-gone-notice` places its Button as a direct flex child, while every sibling action band wraps actions in a `*-actions` div (`.anv-conflict-actions:736`, `.anv-head-actions:650`, `.anv-mini-actions:788` — the last wraps even a single button). The new comment "Same shape as `.anv-conflict` below" asserts a DOM parity the markup lacks; only the outer flex properties match. A future second action would inherit the banner's larger gap. (consistency-reviewer)
- `web/src/lib/components/ActiveNibView.svelte:373` — "which is the only copy of those edits" overstates: `anv-prose` renders the same live dirty buffer (`:132` → `:823`) and is selectable. What is unique to `form.body` is the raw **markdown**, not the edits — as the comment's own preceding sentence gets right. Suggested: "the only verbatim copy of those edits — the prose pane shows them rendered, not as source." (knowledge-reviewer)
- `web/src/lib/components/ActiveNibView.svelte.test.ts:775` — `expect(writeText.mock.calls[0][0]).not.toContain("<h1")` cannot fail independently: the literal `raw` never contains `<h1`. Empirically verified — the `bodyHtml`-swap mutation fails at the preceding line 773 and never reaches 775. The test as a whole bites; only this assertion is decorative. (test-reviewer)
- `web/src/lib/components/ActiveNibView.svelte.test.ts:789` — `expect(mockToastSuccess).not.toHaveBeenCalledWith(expect.stringContaining(raw))` likewise cannot fail independently of line 788 under single-call semantics. Empirically verified: the label-dropped mutation fails at 788, never reaching 789. (test-reviewer)

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| quick-reviewer | 0 | 0 |
| broad-reviewer | 3 | 2 |
| knowledge-reviewer | 3 | 2 |
| consistency-reviewer | 1 | 1 |
| design-reviewer | 1 | 0 |
| test-reviewer | 2 | 2 |
| spec-compliance-reviewer | 1 | 0 |
| adversarial-reviewer | 3 | 2 |
| typescript-reviewer | 1 | 0 |
| **Total** | **12** | |

Notes:
- **Issues Found**: total findings attributed to this agent (including shared findings)
- **Unique Issues**: findings reported ONLY by this agent
- The three judgment agents on the session model (knowledge, adversarial, design) plus broad supplied all 3 Highs and both Mediums. quick-reviewer returned no findings but its "Considered But Not Flagged" section correctly identified the `loadingUnseeded` behavior change before dismissing it — the dismissal was overturned in Step 5.5.

---

## Specialist Notes

### Requirement Coverage Matrix (spec-compliance-reviewer)

Spec: `nibs-mpo4` (inferred → severities capped at Medium). **Verdict: compliant** — all six acceptance items met.

| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| R1 | Raw markdown of a preserved dirty buffer retrievable while `gone` | Covered | `:701-712` button → `:374-377` `handleCopyBody` → `copyToClipboard(f.body, "body")` |
| R2 | Test: "Copy body" copies `form.body` verbatim (vitest, clipboard stub) | Covered | `test:760-776` — stubs `writeText`, asserts on markdown containing `#`/`[]()`/`**` |
| R3 | Title uses `readonly` rather than `disabled` while `gone` | Covered | `:646`; pinned at `test:734-735` (both halves) and `test:747-758` |
| R4 | Relaxing `:105` does not re-enable Save for a gone nib (pin it) | Covered — see below | `:108` derivation unchanged; Save's `\|\| disabled` gate at `:668` intact; pinned by `test:743` |
| R5 | Record that the bits-ui selects cannot be made readonly | Deviated | `:634-636` — API half accurate, appended selectability clause is **Finding #2** |
| R6 | `task test` green | Covered | Orchestrator-verified: 60 files / 1285 tests |

**On R4 (the ordering constraint) — satisfied, not vacuous.** The criterion is a negative invariant ("does not re-enable Save for a gone nib"); the parenthetical about gysg's guard explains why it matters but is not itself the criterion. The implementer met it by never opening the hole: `disabled = $derived(isGone || loadingUnseeded)` is untouched and `readonly={disabled}` reuses that derivation on the title alone. Save's gate at `:668` is byte-for-byte unchanged. Both reviewers independently verified no new path into `handleSave` was opened by making the title focusable — the Save button is gated by `disabled`; `MarkdownEditor`'s `onsave` is unreachable because `bodyModeEffective` pins to preview while disabled (and its `Mod-s` is a CodeMirror keymap inside an unmounted editor); **no `<form>` element exists anywhere in `web/src`**, so a focusable readonly input opens no implicit-submission path; and `useKeyboardShortcuts` registers no save binding.

**What is overtaken is the nib's rationale, not its acceptance.** The nib states "That guard is unreachable today and becomes reachable here — so this nib is what exercises it." It does not become reachable; gysg's `handleSave` `isGone` guard remains dead code. That is a premise overtaken by a narrower implementation, not a code defect — and the guard's own comment is honest about its status ("belt-and-braces for any future path…"). **The implementer's decision not to ship a test for it is correct.** Worth noting only that if the team wants that guard exercised, no work item is currently positioned to do it.

### Test Mutation Verification (test-reviewer)

All 7 implementer-claimed mutations were **independently reproduced** in an isolated worktree (`probe-test`), with the fix's presence verified in the probe tree first and an intact baseline of 63/63 confirmed before and after. **No eighth decorative guard found.**

| # | Mutation | Claimed | Observed |
|---|---|---|---|
| 1 | title `readonly` attribute removed | 2 fail | CONFIRMED |
| 2 | title swapped back to `disabled` | 1 fails | CONFIRMED |
| 3 | copy `bodyHtml` instead of `form.body` | 1 fails | CONFIRMED |
| 4 | `label` argument dropped | 1 fails | CONFIRMED |
| 5 | empty-body gate removed | 1 fails | CONFIRMED |
| 6 | notice not gone-scoped | 2 fail | CONFIRMED |
| 7 | Save's `disabled` gate removed | 1 fails | CONFIRMED |

Two questions the orchestrator raised were settled empirically rather than by inspection:
- **`await user.type(title, "XYZ")` on a readonly input is NOT vacuous** — mutation 1 makes that exact test fail (`'Preserved titleXYZ'` received), proving jsdom/testing-library respect the `readonly` attribute.
- **"does not offer Copy body outside the gone state" passes for the right reason** — `makeView()`'s `kind` defaults to `"viewing"` (`test:211`), and mutation 6 makes the test fail.

Bonus: mutating `clipboard.ts`'s own label branch is caught independently at **two** layers (`clipboard.test.ts:41` and the ActiveNibView toast-naming test) — genuine non-overlapping coverage.

### Considered But Not Flagged (all agents)

**Suppressed by the confidence gate (anchor 50, no Critical):**
- Unrestored `navigator.clipboard` stub in the new ActiveNibView tests (test-reviewer 50, typescript-reviewer 50 — the latter marked it `pre_existing`). **Refuted in substance by consistency-reviewer**, which showed the inline `Object.defineProperty` pattern is the established convention for *component* tests that consume `copyToClipboard` (the pre-existing Copy ID test at `test:658-659` and `RowContextMenu.test.ts:586-592` use it identically); `clipboard.test.ts`'s `stubClipboard()` is a private helper local to that file. Vitest isolates `navigator` per test file, so no cross-file leak is possible. Latent within-file risk only.
- `{#if form.body}` treats a whitespace-only body as truthy (typescript-reviewer 50). Dismissed by quick-reviewer (mirrors the file's existing truthy-gate pattern for the prose/preview panes) and knowledge-reviewer (a whitespace-only string *is* a non-empty body, so the comment matches the guard).

**Examined and dismissed with reasoning judged sound:**
- **quick-reviewer**: icon size 14 vs 15 between "Copy body" and "Copy ID" — independently dismissed by consistency-reviewer, which found no same-kind sibling (`Button size="sm"` with icon+text) anywhere in `web/src/lib/components/` to establish a convention either way.
- **knowledge-reviewer**: verified TRUE clause-by-clause and did not flag — "`bodyModeEffective` pins the body to preview" (`:160`/`:108`); "a `readonly` input stays focusable with its text selectable"; "`:read-write` excludes both readonly and disabled" (HTML spec; and `.anv-title` no longer ever receives `disabled`, so that half is a dead but accurate case); "The focus ring below is deliberately NOT gated" (`.anv-title:focus` at `:979-981`, ungated); "the panel keeps the dirty buffer but can no longer save it" (`handleSave` early-returns on `isGone` at `:302`; Save `disabled` at `:668`).
- **All agents**: grepped for `gecko|firefox|chromium|chrome|safari|webkit` across all four changed files — **zero hits**. The `readonly` justification correctly rests on the durable HTML-spec fact, exactly as instructed. Affirmed positively by knowledge, consistency, design, adversarial, typescript and spec-compliance.
- **design-reviewer**: `readonly` and form semantics — checked directly rather than reasoning from the general rule. **Zero `<form>` elements exist in `web/src` or `index.html`**; zero `FormData`, zero `requestSubmit`, zero `form=` attributes. Nothing enumerates the panel's controls (`[disabled]` appears only in three Tailwind `data-[disabled]` variants inside shadcn menu internals). The "readonly participates in submission" concern is real in the abstract and inert here.
- **design-reviewer**: metadata edits unrecoverable in a gone dirty buffer — dismissed as coherent by design. The discriminator is long-or-source-hidden vs short-and-visible: the body is the only field whose *raw* form is hidden, so it needs a button; metadata values are short visible words, selectable in Chromium and trivially retyped; the title is covered twice over (readonly selection + the `title={form.title}` native tooltip, which matters because it is ellipsized).
- **adversarial-reviewer**: the "Copy body" button vanishing under the cursor mid-click — `form.body` can only change while gone via `applyExternal`, which runs **only when the buffer is clean** (`useActiveView.svelte.ts:579-584`); a clean buffer has no unsaved edits, so the escape hatch disappearing costs nothing. The dirty case cannot mutate `body`.
- **adversarial-reviewer**: `handleCopyBody`'s `const f = form; if (f)` guard is dead (the template is inside `{#if form}` and `form` cannot change within one synchronous handler). Not flagged as a defect — design, typescript and consistency all independently confirmed the alias-then-guard shape is the file's consistent idiom for narrowing `$derived` state (`handleSave:289`, `handleProseClick:266`, `handleLoadTheirs:336`, `handleOverwrite:347`).
- **adversarial-reviewer**: attacked the "`handleSave` is unreachable while gone" claim from the keyboard side and **could not break it** (see the R4 note above). Also: no focus trap wraps `ActiveNibView` in either presentation (`App.svelte:560,574`); autofocus-on-create is guarded at `isCreating`, which is disjoint from `isGone`, so it can never target a readonly title.
- **typescript-reviewer**: floating `copyToClipboard(...)` calls — contract-compliant (the JSDoc guarantees the promise always resolves), matches the pre-existing sibling `handleCopyId` and `RowContextMenu.svelte:97`, and `web/` has **no ESLint config and no lint script**, so `no-floating-promises` is not enforced here. Anchor 0.
- **typescript-reviewer**: `readonly={disabled}` boolean-attribute rendering — Svelte 5 removes the attribute entirely when `false` rather than emitting `readonly="false"`; consistent with the new test and the passing suite. Anchor 0.
- **consistency-reviewer**: `data-testid="anv-gone-copy-body"` matches the file's `anv-<context>-<action>` convention; the "Copy the description's markdown source" tooltip correctly reuses the visible UI term "Description" (`:787`) rather than the internal `body` field name; the new doc comment's prose style matches the codebase's dominant no-`@param` JSDoc convention; no dead `.anv-title:disabled` selector remains after the swap.

**Out of scope per instructions (not evaluated):** `--warning-foreground` missing from both theming layers (pre-existing, shared with `.anv-conflict`); `TreeTable.svelte` (nibs-s0tn); `internal/nibcore/*` (nibs-9cac); `nibForm.svelte.ts` (nibs-dsc8); `MarkdownEditor.svelte` (nibs-1nqt); `activeView.ts`/`useActiveView.svelte.ts` gating (nibs-gysg).

---

## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `web/src/lib/components/ActiveNibView.svelte` | comment-truth / knowledge-preservation | 9 | 2026-07-14 |

Matched lightweight on file path + category across 89 prior reviews in `.decaf/code-reviews/`. This is the codebase's documented dominant defect class — eight false comments caught in the two days preceding this review, two of them authored by the batch conductor. **This review adds two more Highs (#2, #3) and one Minor**, both Highs in comments written to justify a change whose entire purpose was to retire a false claim about platform behavior. The pattern is not incidental: the false claims cluster specifically around confident assertions about UA/library behavior that was never executed. Both #2 and #3 would have been caught by the same question — *"has anyone run this?"*

---

## Session Metrics (--report)

**Wave timing**: review roster dispatched 2026-07-15 ~21:50 UTC in **two batches** (2 agents, then 7 — see anomalies); validation wave of 7 dispatched after consolidation, single message. All 16 agents returned their reports as tool results.

| Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings submitted |
|-------|------|-----------|-------:|-----------:|---------:|-------------------:|
| quick-reviewer | reviewer | mid-tier (sonnet) | 103,171 | 14 | 185,055 ms | 0 |
| broad-reviewer | reviewer | mid-tier (sonnet) | 142,695 | 25 | 507,082 ms | 3 |
| knowledge-reviewer | reviewer | session (opus) | 88,383 | 20 | 291,288 ms | 3 |
| consistency-reviewer | reviewer | mid-tier (sonnet) | 92,013 | 32 | 199,887 ms | 1 |
| design-reviewer | reviewer | session (opus) | 85,093 | 11 | 201,054 ms | 1 |
| test-reviewer | reviewer | mid-tier (sonnet) | 101,477 | 36 | 583,899 ms | 3 |
| spec-compliance-reviewer | reviewer | session (opus) | 93,385 | 23 | 302,197 ms | 1 |
| adversarial-reviewer | reviewer | session (opus) | 115,494 | 20 | 311,704 ms | 3 |
| typescript-reviewer | reviewer | mid-tier (sonnet) | 112,148 | 15 | 148,719 ms | 3 |
| finding-validator #1 (contrast) | validator | mid-tier (sonnet) | 66,922 | 18 | 120,743 ms | confirmed |
| finding-validator #2 (select-none) | validator | mid-tier (sonnet) | 60,889 | 12 | 77,588 ms | confirmed |
| finding-validator #3 (test comment) | validator | mid-tier (sonnet) | 62,935 | 5 | 106,651 ms | confirmed |
| finding-validator #4 (loadingUnseeded) | validator | mid-tier (sonnet) | 69,205 | 10 | 133,824 ms | confirmed |
| finding-validator #5 (archived) | validator | mid-tier (sonnet) | 85,273 | 15 | 161,955 ms | confirmed |
| finding-validator #6 (label API) | validator | mid-tier (sonnet) | 56,731 | 6 | 71,126 ms | confirmed |
| finding-validator #7 (dead zone) | validator | mid-tier (sonnet) | 64,381 | 9 | 113,275 ms | confirmed |
| **Reviewers subtotal** | | | **933,859** | **196** | | **18 raw** |
| **Validators subtotal** | | | **466,336** | **75** | | **7 confirmed** |
| **Total** | | | **1,400,195** | **271** | | |

All figures are the harness-reported values from each agent's tool result, verbatim. Findings-submitted counts are raw pre-consolidation counts (18 raw → 12 after dedup: 7 primary + 5 minor).

**Pre-flight gates** (run once, shared): `task build` PASS (no warnings); `task lint` (golangci-lint) PASS (0 issues); `npx svelte-check` PASS (0 errors / 0 warnings, 4737 files); `npx vitest run` PASS (60 files / 1285 tests). All four independently confirmed the state the conductor reported.

**Anomalies**:
1. **Review roster dispatched in two batches (2, then 7) rather than one message** — a deviation from Step 3's single-message rule. All 9 agents ran and all 9 returned reports as tool results, so no data was lost; the cost was reduced parallelism on the first batch. Orchestrator error, not a harness fault.
2. **No probe-protocol anomaly.** Working tree verified byte-identical after both waves — `git status --short` shows exactly the 4 expected modified files. `git worktree list` shows no leaked probe worktrees (the `nibs-mcp` entry is pre-existing and unrelated). test-reviewer explicitly reported tearing down `probe-test` with plain `rm` on the `node_modules` symlink followed by `worktree remove --force`. No reviewer reported the `go build ./...` / `pattern all:web/dist` artifact as a finding.
3. **Named-dispatch experiment: no `name` was passed to any of the 16 agents; all 16 returned their reports as tool results.** The skill's own Step 3 mandates exactly this ("NEVER pass `name` on a review dispatch"), so there was **no conflict** with the conductor's instruction — both agree. Running total for unnamed dispatch in this session remains 100%.
