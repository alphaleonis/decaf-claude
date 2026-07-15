# Code Review

**Mode**: mid (explicit) | **Reviewers**: quick, broad, knowledge, consistency, design, test, adversarial, typescript | **Date**: 2026-07-15
**Source**: local changes — branch `batch/config-and-buffer-fixes` (uncommitted, vs. `d2ea45c`)
**Scope**: 3 files changed, +166/-13 lines
**Spec**: none found (no `plans/`, `docs/specs/`, `docs/prd/`, or top-level PRD in the repo)
**Validation**: 1 confirmed, 0 refuted, 0 uncertain, 0 waived, 0 unvalidated

## Agent Selection Rationale

Mode was **explicit** (`mid`), so Step 2a.5 recommendation was skipped. Changeset classification: TypeScript/Svelte executable code + test code; ~7 changed executable lines in production, ~100 in tests (≈107 total); substantive (not mechanical); no security-adjacent surface; API/contract + concurrency surface touched.

Review team:
- **quick-reviewer** (always — review floor)
- **broad-reviewer** (always — review floor)
- **knowledge-reviewer** — rewritten `initialValue` policy docblock, rewritten `onchange` contract, new WRITE-BACK SUPPRESSION paragraph; comment truth is this file's dominant historical defect class
- **consistency-reviewer** — substantive change with abundant sibling code in `web/src/lib/components/`
- **design-reviewer** — the `onchange` prop's documented contract was narrowed; reentrancy/guard-window surface
- **test-reviewer** — **hard gate**: test files present in changeset
- **adversarial-reviewer** — ≥50 changed executable lines; guard-flag ordering/reentrancy is squarely its lane
- **typescript-reviewer** — **hard gate**: TypeScript/Svelte files present in changeset
- **security-reviewer**: skipped — no security-adjacent surface (no auth, crypto, user input parsing, network, file I/O, serialization, secrets, or privilege boundaries)
- **performance-reviewer**: skipped — no DB/ORM queries, I/O loops, or caching logic introduced; the pre-existing prefix/suffix diff loop is untouched
- **spec-compliance-reviewer**: skipped — no spec available (hard gate)
- **data-migration-reviewer**: skipped — no migration artifacts (hard gate)
- **dotnet / cpp / go / rust reviewers**: skipped — languages absent from changeset (hard gate)
- **prior-feedback-reviewer**: skipped — local changes, not a PR (hard gate)

**Model tiering (mid)**: judgment agents (knowledge, design, adversarial) inherited the session model; volume agents (quick, broad, consistency, test, typescript) and the validator ran mid-tier (`sonnet`). No roster cap was given.

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 0 |
| 🟡 Medium | 1 |
| 🟢 Low | 0 |
| 🔵 Minor | 0 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts the reported-but-non-blocking findings. Pre-existing issues are listed separately and excluded from both.

**Verdict**: ✅ APPROVED

The fix itself is correct and unusually well-verified. Every adversarial hypothesis the brief flagged for hard probing — contract-stranding via CodeMirror re-splitting the insert, a mis-scoped window, module-scoped flag leakage, async paths crossing the flag, extension-driven reentrancy, comment falsity — was **constructed and refuted with executed evidence**, not waved off. The single surviving Medium is not a defect in shipped behavior; it is an unpinned invariant with an asymmetric failure mode.

---

## Findings

### #1 🟡 Medium: Write-back suppression's window-close is unpinned; its failure mode is silent data loss

| | |
|---|---|
| **File** | `web/src/lib/components/MarkdownEditor.svelte:331` (production anchor); companion test gap at `web/src/lib/components/MarkdownEditor.test.ts:337` / `:371` |
| **Category** | evolution-readiness / test-coverage |
| **Confidence** | 100 |
| **Found by** | test-reviewer (Medium, 100), design-reviewer (Medium, 75), adversarial-reviewer (same evidence, documented out-of-lane, not filed) |
| **Validation** | **confirmed** — reproduced independently by the validator |

**Issue:**

The `syncing` boolean guards a *time window*:

```ts
syncing = true;
try {
  v.dispatch({ changes: {...}, ...(cmTransaction ? { annotations: cmTransaction.addToHistory.of(false) } : {}) });
} finally {
  syncing = false;
}
```

with the listener gated `if (update.docChanged && !syncing)`. The two failure modes are guarded **asymmetrically**:

- **Window fails to OPEN** (`&& !syncing` dropped) → CRLF loss. *Well covered* — reverting the guard fails both new tests. Verified in isolated worktrees by broad-reviewer, design-reviewer, and test-reviewer: `expected '- [x] a\n- [ ] b' to be '- [x] a\r\n- [ ] b'`.
- **Window fails to CLOSE** (the `finally` reset dropped or refactored away) → `syncing` stays `true` forever → the listener suppresses **every** subsequent doc change → the user's typing never reaches `onchange`, `form.body` never updates, `dirty` stays `false`, and Save persists the pre-edit body. **Silent, permanent data loss — and no test notices.**

Four independent agents ran the mutation in isolated worktrees and agree it survives the suite: test-reviewer (17/17 + 52/52 pass), design-reviewer (1240/1240, 60/60 files), adversarial-reviewer (66/66), validator (69/69).

The existing new test *"DOES call onchange for a landed dispatch it did not initiate"* (`:371`) **cannot** catch it, and its own comment overclaims: it renders a **fresh** component whose `initialValue` (`"a"`) already equals the doc, so the sync effect hits the `cur === next` early return and never dispatches — `syncing` is never set `true`. The validator confirmed this empirically by asserting zero `dispatch` calls before the manual one. The test therefore proves only the flag's *initial value*, not that the window ever closes.

The validator also drove the consequence directly rather than reasoning about it: against the mutant, a post-sync `view.dispatch({ changes: { from: 2, insert: "c" } })` on the same view instance produced `onchange` **calls: 0**; against the real fixed code the same driver passes with `"abc"`.

This is not mutation-coverage purism. The guard is a 3-line `try/finally` around a single dispatch — a plausible target for a future refactor (adding a second dispatch, converting to early-return branches) to silently drop the reset — and the failure is total, permanent, and symptomless until Save. It is a genuine gap on a **temporally-scoped invariant**: the code is right today, but nothing holds it right.

**Fix** — two alternatives, in ascending cost:

**(a) Minimal — add the missing test.** Render, trigger a sync via `rerender` (as `:337` already does), then call `view.dispatch({...})` on the **same** view instance and assert `onchange` fires for that post-sync dispatch. One test; closes the hole; keeps the design as-is.

**(b) Structural — make the guard fail-safe by keying on transaction identity rather than a time span:**

```ts
let syncTr: Transaction | null = null;
// ...
const tr = v.state.update({
  changes: { from: start, to: curEnd, insert: next.slice(start, nextEnd) },
  ...(cmTransaction ? { annotations: cmTransaction.addToHistory.of(false) } : {}),
});
syncTr = tr;
try {
  v.dispatch(tr);
} finally {
  syncTr = null;
}
// listener:
if (update.docChanged && !update.transactions.includes(syncTr)) onchange(...);
```

A stale or never-cleared reference is then **inert**: a later user transaction is a different object, so it never matches and always writes back. design-reviewer verified in an isolated worktree that this holds the CRLF invariant and is completely inert under the same "never reset" mutation (53/53 pass). The validator independently confirmed the mechanics against the installed `@codemirror/view` 6.40.0: `dispatch(tr: Transaction)` is a real overload (`dispatch(...args)` special-cases a single `Transaction` into `[tr]`), `ViewUpdate.transactions` is a real property, and `ViewUpdate`'s constructor assigns `this.transactions = transactions` without cloning — so object identity survives end-to-end.

This does **not** re-open the settled annotation-sniffing decision: it keys on the identity of the sync's own transaction object, not on a semantic annotation. Option (b) additionally closes the theoretical extension-reentrancy hole that broad-reviewer and adversarial-reviewer both found and dismissed as unreachable (see Considered But Not Flagged).

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| quick-reviewer | 0 | 0 |
| broad-reviewer | 0 | 0 |
| knowledge-reviewer | 0 | 0 |
| consistency-reviewer | 0 | 0 |
| design-reviewer | 1 | 0 |
| test-reviewer | 1 | 0 |
| adversarial-reviewer | 1 | 0 |
| typescript-reviewer | 0 | 0 |
| **Total** | **1** | |

Notes:
- **Issues Found**: Total findings attributed to this agent (including shared findings)
- **Unique Issues**: Findings reported ONLY by this agent and no other
- adversarial-reviewer submitted `[]` in its findings block but independently produced the same mutation evidence and named the same gap in prose, explicitly routing it to test-reviewer's lane. Credited as a finder here; its *submitted* count in Session Metrics is 0.
- **Zero unique findings across the roster** — the one finding was found three times over. See Session Metrics for the assurance-only work the other five agents performed (found 0 ≠ did nothing).

---

## Specialist Notes

### Adversarial depth tier (adversarial-reviewer)

**Deep.** The ~10-line production diff alone calibrates to Quick; escalated to Deep because the change is a data-mutation-with-persistence decision — it determines which bytes reach a nib file on disk. All four techniques run (assumption / composition / cascade / abuse), including two isolated-worktree probes and a mutation probe.

### Considered But Not Flagged (all agents)

**Refuted by probe — the brief's leading hypothesis (design, adversarial, knowledge; anchor 0).** *"Can CodeMirror alter the dispatched content (it re-splits inserts; `3e2e9be` fixed exactly that class), stranding the consumer with a value the doc does not have?"* — **No.** Three agents probed it independently against real `@codemirror/state` across a combined 37 adversarial cases (lone interior CR, `\r` at the very end, trailing CRLF, mixed CR/CRLF/LF, CR at a diff boundary, empty→CRLF, CRLF→empty, U+2028/U+2029, CR↔CRLF widening/narrowing, surrogate-pair swap, `"\r"` alone, repeated CRs, an `indentOnInput`-trigger char, a bracket-close insert). In **every** case the landed doc `=== next` and a second effect run did not re-dispatch. The reason is structural: `next = v.state.toText(raw).toString()` is already LF-only, so `ChangeSet.of`'s re-split is a no-op — both sides consult the same unset `EditorState.lineSeparator` facet and fall back to `DefaultSplit = /\r\n?|\n/`. **No contract hole; the suppression strands nobody.**

**The highest-risk comment clause is TRUE — and more universally than the author claimed (knowledge-reviewer).** The brief singled out *"after a sync, the consumer's value and the live doc are intentionally divergent ENCODINGS of the same content. That is stable… the sync guard compares in the doc's encoding, so the next effect run finds them equal and does not dispatch."* Verified: `state.toText(raw).toString()` is `Text.of(raw.split(/\r\n?|\n/))` rejoined with `"\n"` — a **pure, idempotent line-ending normalization that touches nothing else**. So (a) encoding is the *only* divergence `toText` can produce, and (b) `normalize(normalize(x)) === normalize(x)` guarantees the guard finds them equal on every subsequent run. CRLF-vs-LF is not "the case the author had in mind" — it is the *only* case that exists. Confirmed empirically across a 10-case matrix: `mountDispatch=false stable=true landedOk=true encodingOnly=true` in all 10.

**"No scheduling on the path" — TRUE (knowledge, broad, adversarial, test; verified against `@codemirror/view` 6.40.0 source, not trusted).** `docChanged` = `!this.changes.empty` (`view/dist/index.js:1697`). `dispatch` (7856) → `dispatchTransactions` (7831; defaults to `(trs) => this.update(trs)` since the component passes no override) → `update()` (7870) → synchronous `for (let listener of this.state.facet(updateListener))` (8153). The `Promise.resolve().then()` (≈7961) sits **after** the listener loop and wraps only `dispatchFocus` (requires the `focusChangeEffect` facet, not configured) and `domChange` (the Android delayed-key path) — both dispatch *separate* transactions after `syncing` is already false, which is correct, since a pending Android keystroke *is* a user edit and *should* write back. The second listener site in `measure()` (8173) builds `ViewUpdate.create(this, this.state, [])` with an **empty** transactions array, so `docChanged` is structurally always `false` there.

**Extension reentrancy inside the window — real mechanism, unreachable today (broad anchor 25, adversarial anchor 25).** Both independently found that `update()` resets `updateState = Idle` in a `finally` **before** the listener loop, so a nested `dispatch()` from inside a listener would *not* hit CodeMirror's "update in progress" throw — and would inherit the outer `syncing = true`, silently swallowing that transaction's write-back. But no extension actually wired into `editorBasics` (`history`, `drawSelection`, `dropCursor`, `indentOnInput`, `bracketMatching`, `closeBrackets`, `autocompletion`, `rectangularSelection`, `crosshairCursor`, `highlightActiveLine`, `highlightSelectionMatches`) synchronously dispatches in reaction to a non-user-event transaction. Theoretical given the current extension set; both agents held it below the anchor-50 floor. **Fix (b) in Finding #1 would close this too.**

**No extension can alter the sync transaction (adversarial, knowledge).** `indentOnInput` (`@codemirror/language:1188`) is the **only** `transactionFilter` across the entire loaded set (view/state/language/autocomplete/commands/search/lint/lang-markdown), and it bails unless `tr.isUserEvent("input.type"|"input.complete")`. The sync transaction carries only `addToHistory.of(false)` — no user event — so it returns `tr` untouched. `closeBrackets` uses a view-level `inputHandler` (user input only); `autocompletion`/`search`/`commands` register no filters. A *future* filter adding changes is the one way the landed doc could diverge (adversarial/design, anchor 25 — speculative, unreachable today).

**`syncing` is per-instance, NOT module-scoped — a correction to the task framing (design, typescript, adversarial, broad; anchor 0).** The brief described it as a "plain `let`, not `$state`" in a way that read as module-level; had that been true it would have been a Critical with two editors mounted. It is module-level only in *source position* (top of `<script>`), not in scope. design-reviewer **compiled the component with Svelte 5.55.0** and confirmed `let syncing` lands at line 81 *inside* `export default function MarkdownEditor($$anchor, $$props)` — per-instance, with zero compiler warnings (no `non_reactive_update`, since it is never referenced from the template). typescript-reviewer independently confirmed there is no `<script module>`/`context="module"` block anywhere in the file. Moot in practice regardless: `ActiveNibView.svelte:786` is the sole consumer and mounts exactly one editor under `{#key form.bodyVersion}`.

**Diff algebra is sound (adversarial, anchor 0).** `from <= to` always holds (the suffix loop guards on both `curEnd > start` and `nextEnd > start`; `start` is the common-prefix length so both bounds are `>= start`). The changeset is **never empty** when `cur !== next` — an empty one would algebraically imply `cur === next`, contradicting the guard — so the listener always fires and the suppression is always exercised, never silently skipped.

**Exception mid-dispatch — benign (adversarial, typescript; anchor 0/25).** `viewState.update` lands the doc before any throw, but the updateListener loop sits *after* `update()`'s try/finally, so `onchange` never fires — which is the desired outcome anyway. `finally` resets the flag either way; the consumer sees the identical end state as the success path. `dispatch` was equally unguarded before this change (pre-existing), and no path makes a throw newly reachable. What Svelte 5 does with an uncaught `$effect` error is real but unverified and unchanged by this diff (typescript-reviewer, anchor ~25).

**`cmTransaction` undefined → unreachable (adversarial, knowledge; anchor 0).** Would put the sync in the undo stack and let Ctrl-Z echo an un-flipped LF doc back. Not reachable: `cmTransaction = Transaction` (`:219`) is assigned before `view = new EditorView(...)` (`:221`), both synchronous, and the effect returns early on `!v`. This also makes the conditional `...(cmTransaction ? {...} : {})` unreachable-defensive, which is why knowledge-reviewer accepted the WRITE-BACK SUPPRESSION comment's future-hypothetical framing ("if the annotation were ever dropped") as an accurate record of the settled rationale.

**"The fix only delays the loss" — true but it is the documented policy (adversarial, anchor 0).** A user keystroke does emit the full LF doc and flip the consumer's CRLFs. But that is deterministic and user-initiated: typing requires the editor to be open, and in preview-only mode the user *cannot* type. The bug fixed here was **nondeterminism** — same click, two bodies, decided by an unrelated view toggle. That is genuinely gone.

**Undo cascade traced, no spurious dirty (adversarial, anchor 0).** Four orderings traced. CodeMirror maps history changes through the out-of-history sync, so flips survive an undo of prior typing; undoing back to original content leaves `form.body` LF while `baseline.body` is CRLF, which `sameBody` absorbs to `dirty === false`. (Reasoned about `sameBody` only for the trace; no finding filed against it, per scope.)

**Init race is safe (adversarial, typescript; anchor 0).** `initialValue` changing while the async import is in flight: `EditorState.create({doc: initialValue})` reads the *current* prop at IIFE time, then assigning `view` re-runs the sync effect, which finds `cur === next` and no-ops. The `aborted` path leaks no view.

**Sibling-convention census — `syncing` matches precedent (consistency-reviewer, anchor 0).** The plain-`let`-guard-flag-inside-an-`$effect` shape has **two agreeing siblings** doing the identical thing for the identical reason, both commented: `SettingsSheet.svelte:134` (`let wasOpen = false;`, one-shot open/close transition) and `TypePickerPopover.svelte:23` (`let selecting = false;`, synchronous callback-ordering race). Not a deviation.

**CRLF fixture duplication across the two test files (consistency-reviewer, anchor 0).** No shared-fixture module exists anywhere under `web/src/lib`; inline literal duplication is the established norm — `ActiveNibView.svelte.test.ts` itself duplicates `"- [ ] a\n- [ ] b"` at `:486` and `:523`. Not a `CONS_LITERAL` violation.

**Test naming/structure conventions all match (consistency-reviewer, anchor 0).** ALL-CAPS emphasis in test titles is established across `ConfirmDialog.test.ts:110`, `Toolbar.test.ts:663`, `TreeTableRow.test.ts:216,886,906`, `SettingsSheet.test.ts:46`, `TreeTable.test.ts` (5 sites), and pre-existing in `MarkdownEditor.test.ts` itself. The `"Regression:"` comment prefix is established in `TreeTable.test.ts:256,1180,1430,1462` and pre-existing at `MarkdownEditor.test.ts:269,307`. The relative `../markdown` import matches the majority style. `anv-*` testids all match what `ActiveNibView.svelte` actually emits (`:769`, `:739`, `:778`, `:796`). No `console.log`, `.only`, `.skip`, `TODO`/`FIXME`, or `debugger` in the diff.

**Test-mock `this` binding is correct (typescript-reviewer, anchor 0).** `web/tsconfig.node.json` has `useDefineForClassFields: true`. The `dispatch = vi.fn((spec) => { this.state.update(spec) ... })` arrow class field creates its closure at field-init time (capturing the instance as a stable reference) but its *body* runs only when invoked — after the constructor has set `this.state = config.state`. Because it is an arrow function, `this` is lexically fixed; neither the `vi.fn()` wrapper nor a detached `view.dispatch(...)` call can change it.

**Mock's shared `mockUpdateListenerCallback.current` singleton — latent, untriggered (typescript-reviewer anchor 25, test-reviewer concurs).** `EditorView.updateListener.of` is a `static` field on the mock, so constructing a second `MockEditorView` while an earlier one is live would redirect the callback to the newer instance. Reset in `beforeEach`; both new tests construct exactly one view and assert `mockViewInstances.length === 1` across every `rerender()`. Pre-existing test infrastructure, unmodified by this diff.

**Line-ending "stringify" phrasing at `:276-281` (broad-reviewer, anchor 25).** broad traced `Text.toString()` → `sliceString(0)`, whose `lineSep` parameter defaults to the literal `"\n"` and does **not** read the `lineSeparator` facet (only `toText`/`sliceDoc` do, for splitting). Read closely, the comment is accurate as written — its parenthetical "(both consult the `EditorState.lineSeparator` facet…)" attaches to the *split* policy, and it separately says "stringifies through the same `"\n"` join", which is exactly the literal default broad found. **Also pre-existing** (from `3e2e9be`), not part of this diff. Immaterial regardless: no `lineSeparator` facet is configured, so both paths fall back to the same defaults.

**"Read and written within one synchronous call stack" (knowledge-reviewer, dismissed on the inferability gate).** Literally imprecise — the listener reads `syncing` on *every* keystroke/undo/paste, i.e. from many other stacks. But it reads naturally as describing the flag's set→observe→clear *window*, the operative claim ("needs no reactivity") is true, and the imprecision is self-correcting from the two visible sites. Dismissal accepted: the comment's purpose — justifying plain `let` over `$state` — is served truthfully.

**"Consequence: after a sync…" (knowledge-reviewer, dismissed).** The divergence actually begins at *mount* (`EditorState.create` normalizes; the guard then finds them equal and never dispatches), not at a sync. But the immediately preceding pre-existing paragraph already states exactly that ("a CRLF value is never `===` its own echo"). Read together, no comprehension risk.

**Suppression↔normalization coupling — real but already fenced (knowledge-reviewer, dismissed on durable relevance).** The suppression's safety rests on `landed doc === toText(initialValue).toString()`. If the normalization were removed, the suppression would convert a self-announcing bug into a silent divergence (the effect never re-runs, since `initialValue` didn't change). The MINIMAL DIFF paragraph already warns that "Diffing against a non-normalized value would… insert a lone CR that CodeMirror re-splits" — the wrong edit is fenced.

**Second surviving mutant: making `syncing` module-scoped (adversarial, out-of-lane, not filed).** Also passes 66/66 — no test mounts two editors. Not promoted: the shipped code is correctly instance-scoped (verified three ways), and `ActiveNibView` mounts exactly one editor under `{#key}`, so a two-editor test would pin a configuration the application does not have.

**Project-rule compliance (knowledge, quick, consistency — all independently checked).** American English throughout; no work-item IDs in comments; no change-history narration in the new comments; `now`/`currently` usage consistent with `fad6f7b`. The test comments' counterfactual framing ("a bare `vi.fn()` stub would…") is forward-relevant maintenance guidance, not change-history narration, and matches the file's own pre-existing precedent ("a hand-rolled `toString:`… would echo the doc back verbatim and hide that").

**Out of scope per instructions (all agents):** `nibForm.svelte.ts` `sameBody`/`dirty`/`#matchesFields`; `ActiveNibView.svelte` component gone-state gating and `abandonsBuffer`/gone-Save; `TreeTable` title click; `internal/nibcore/watcher.go`; mention-index gaps and the `(?!-)` regex divergence; normalizing at `fieldsFromSnapshot`. None re-litigated. Finding #1's fix (b) keys on transaction *identity*, not the `addToHistory` annotation, so it does not re-open the settled annotation-sniffing decision.

---

## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `web/src/lib/components/MarkdownEditor.test.ts` | test-coverage | 2 | 2026-07-14 |
| `web/src/lib/components/MarkdownEditor.svelte` | evolution-readiness | 2 | 2026-07-14 |

The `test-coverage` recurrence is the sharper signal: `CODE_REVIEW_2026-07-14_20-44-33.md` flagged `MarkdownEditor.test.ts:255` "(spans the `it.each` block and the **'DOES dispatch' test**, 255-309)" — the same test family whose successor (`:371`, "DOES call onchange for a landed dispatch it did not initiate") is again the locus of today's gap. This file's tests have now twice been found to assert less than their names claim.

**Counter-signal worth recording**: `MarkdownEditor.svelte` produced **four** prior knowledge-preservation findings across `2026-07-14_17-18-12`, `2026-07-14_20-12-33` (×2), and `2026-07-15_15-51-26` (the last a RULE 0 doc-vs-code contradiction). This round — which rewrote the file's policy docblock and added a new named section — produced **zero**, with the dedicated knowledge-reviewer tracing every clause to `@codemirror/view` 6.40.0, `@codemirror/state`, `toggleTaskLine`, `sameBody`, and `ActiveNibView` wiring, plus a 10-case empirical stability matrix. The dominant defect class did not recur.

---

## Session Metrics (--report)

**Wave timing**: pre-flight gates 16:36:05–16:37:30 · probe-recipe verification 16:37:14 · review wave dispatched ≈16:38 → last reviewer returned ≈16:49 [Inference: reconstructed from harness-reported per-agent durations; exact dispatch/return wall-clock timestamps were not recorded at dispatch] → consolidated ≈16:50 → validation dispatched ≈16:52, done ≈16:56 → file written 16:58:32

| Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings submitted |
|-------|------|-----------|--------|-----------|----------|--------------------|
| quick-reviewer | reviewer | sonnet (mid) | 82,588 | 5 | 140,926 ms | 0 |
| broad-reviewer | reviewer | sonnet (mid) | 125,258 | 37 | 446,071 ms | 0 |
| knowledge-reviewer | reviewer | session (judgment) | 125,706 | 25 | 673,770 ms | 0 |
| consistency-reviewer | reviewer | sonnet (mid) | 98,277 | 27 | 184,464 ms | 0 |
| design-reviewer | reviewer | session (judgment) | 103,287 | 23 | 611,078 ms | 1 |
| test-reviewer | reviewer | sonnet (mid) | 128,426 | 40 | 549,512 ms | 1 |
| adversarial-reviewer | reviewer | session (judgment) | 104,817 | 24 | 564,994 ms | 0 |
| typescript-reviewer | reviewer | sonnet (mid) | 95,584 | 9 | 261,629 ms | 0 |
| finding-validator #1 | validator | sonnet (mid) | 84,389 | 21 | 255,416 ms | verdict: confirmed |

**Totals**: reviewers 863,943 tokens / 190 tool calls; validator 84,389 tokens / 21 tool calls; **wave total 948,332 tokens / 211 tool calls**. [Unverified] whether a subagent's reported token figure includes its own children — carry this caveat wherever these figures are summed.

**Pre-flight gates**: vitest **PASS** (60 files / 1240 tests, 25.26 s) · svelte-check **PASS** (4737 files, 0 errors, 0 warnings) · golangci-lint **PASS** (0 issues) · `task build` not run separately (web-only changeset; covered by vitest + svelte-check). All three match the state reported in the task brief.

**Anomalies**: **No probe-protocol anomalies.** All 8 reviewers and the validator honored the isolated-worktree protocol; none reported the changeset as absent, reverted, or flapping; none wrote to the shared tree. The shared working tree was verified byte-identical (3 files, +166/-13) at four checkpoints: before dispatch, after the orchestrator's own recipe-verification probe, after the review wave, and after cleanup. All probe worktrees removed (`git worktree list` clean; the orchestrator's `probe-recipe-check` pruned at the end). Three separate notes, none of them probe artifacts:

1. **broad-reviewer report-header slip** — states the repo is "currently checked out on `batch/buffer-safety-watch-cleanup`". The actual branch is `batch/config-and-buffer-fixes` (verified via `git branch --show-current` at three checkpoints). Its diff was still taken against `HEAD` as instructed, so its substance is unaffected. Recorded as a reporting inaccuracy.
2. **Task-brief factual correction (surfaced independently by design, typescript, adversarial, broad)** — the brief characterizes `syncing` as a module-level `let`; it is **per-component-instance**. design-reviewer settled it by compiling with Svelte 5.55.0 rather than reasoning from semantics, explicitly because a genuine module-scoped flag would have been a Critical.
3. **adversarial-reviewer submitted `[]`** while documenting the eventual Finding #1 in prose as an out-of-lane observation. Not a failure — a deliberate lane-routing call that the consolidation credited — but it means a strict findings-JSON reading would have lost a corroborating finder.

**Orchestrator probe note**: the recipe-verification probe (worktree at `HEAD` + new test files) independently reproduced the red output the task brief reported for `MarkdownEditor.test.ts` — `onchange` called once with `"- [x] a\n- [ ] b"` (LF) — before any reviewer was dispatched. This result was deliberately withheld from the reviewers' prompts so test-reviewer's red-check would be an independent confirmation rather than an anchored one; it duly matched.
