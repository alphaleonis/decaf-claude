# Code Review

**Mode**: mid (explicit) | **Reviewers**: quick, broad, knowledge, consistency, typescript, test, adversarial | **Date**: 2026-07-15
**Source**: local changes — branch `batch/config-and-buffer-fixes` (uncommitted)
**Scope**: 2 files changed, +104/-21 lines
**Spec**: none found
**Validation**: 2 confirmed, 0 refuted, 0 uncertain, 1 waived (corroborated ×2)

## Agent Selection Rationale

Mode chosen: **explicit** (`mid` passed by the caller) — Step 2a.5 recommendation logic skipped. No roster cap.

Gate decisions:
- **quick-reviewer** (always) — review floor
- **broad-reviewer** (always) — review floor
- **knowledge-reviewer** — substantive change; three comment blocks rewritten, and comment truth is this changeset's central risk
- **consistency-reviewer** — substantive change with abundant sibling code (the other delegated handlers, the drag guards, the sibling tests)
- **typescript-reviewer** — TS/Svelte files in changeset (hard gate)
- **test-reviewer** — test files in changeset (hard gate)
- **adversarial-reviewer** — 104 changed executable lines (≥50 gate); the boundary matrix and "can a bucket id still reach `toggleSelect` by any path" are squarely its lane
- **design-reviewer**: skipped — change confined to one component's internal dispatch order; `TreeTableRow` and the delegation contract untouched
- **security-reviewer**: skipped — no auth/crypto/user-input/network/file-I/O/serialization/secrets surface
- **performance-reviewer**: skipped — no DB, I/O loops, async, or caching; the fix adds one `Set` membership test per click
- **spec-compliance-reviewer**: skipped — no spec available (hard gate)
- **data-migration / dotnet / cpp / go / rust**: skipped — domain absent from changeset (hard gates)
- **prior-feedback-reviewer**: skipped — local changes, not a PR (hard gate)

Model tiering (mid policy): judgment agents **knowledge** and **adversarial** on the session model; volume agents **quick, broad, consistency, typescript, test** and both validators mid-tier (`sonnet`).

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 1 |
| 🟡 Medium | 1 |
| 🟢 Low | 0 |
| 🔵 Minor | 5 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts reported-but-non-blocking findings. Pre-existing issues are listed separately and excluded from both.

**Verdict**: ❌ NEEDS_CHANGES

The fix itself is **correct and well-tested** — all three implementer mutation claims were empirically confirmed in an isolated worktree, and the four new tests bite. The blocker is a single new comment that asserts an invariant the code does not hold, proven false by probe. It is a comment-only edit to clear.

---

## Findings

### #1 🟠 High: The bucket-guard comment asserts an invariant the guard does not establish — `rangeSelect` still sweeps bucket ids into `selectedIds`

| | |
|---|---|
| **File** | `web/src/lib/components/TreeTable.svelte:445-448` (mirrored in `TreeTable.test.ts:1305`) |
| **Category** | comment-truth |
| **Confidence** | 100 — **probe-confirmed** |
| **Found by** | knowledge-reviewer (MUST), adversarial-reviewer (Medium) |
| **Validation** | corroborated ×2 at anchor 100 — validation waived; independently probe-confirmed by the orchestrator |

**Issue:** The new comment reads:

```
// A synthetic grouping bucket is not a nib, so it can never join the
// bulk-action set: feeding its id to rangeSelect/toggleSelect would put an
// unresolvable id in selectedIds.
```

The guard at `:449` only tests the **clicked** `nibId`. It cannot close the range-sweep path:

- `visibleRowIds = rows.map(r => r.nib.id)` (`TreeTable.svelte:148`) — no `isBucketId` filter, and `tree.ts:217` pushes bucket rows **interleaved** with real nib rows.
- `rangeSelect` (`selection.svelte.ts:60-62`) does `const rangeIds = visibleIds.slice(lo, hi + 1); this.selectedIds = new Set(rangeIds);` — every id in the swept span, never re-tested.

So a shift-click whose range *spans* a bucket puts the synthetic id in `selectedIds` while the clicked id is a real nib that sails through the guard.

**Probe evidence (run in an isolated worktree against the reviewed tree, byte-identical to the change under review):** using the fixture already in the test file (`makeBucketTestNibs`), anchor on `nibs-e1`, shift-click `nibs-loose`:

```
PROBE selectedIds: ["nibs-e1","__no_milestone__","nibs-loose"]
AssertionError: expected true to be false
```

The synthetic id **is** in the bulk-action set, on the very tree whose comment says it can never be.

`retainOnly` (`selection.svelte.ts:96`) is not a backstop: the `$effect` at `:168-185` reads only `$result.fetching` / `allNibs` / `resolvedFilter` and wraps the selection access in `untrack`, so it does **not** re-run when `selectedIds` changes. The synthetic id persists until an unrelated refetch.

**Why this is the blocker:** the false clause sits *immediately above the guard*, so it reads as a statement of what the guard achieves. A maintainer adding a bulk mutation over `selectedIds` will trust "can never join the bulk-action set" and omit the `isBucketId` filter. An invariant claimed but not enforced is worse than no comment — it suppresses the defensive check a reader would otherwise write. Note the runtime consequence is tracked separately as **P1** (pre-existing); what is **new in this diff** is the comment denying it.

**Fix:** Narrow the claim to what the guard actually does and record the residual as a live constraint:

```
// A synthetic grouping bucket is not a nib: feeding its id to
// rangeSelect/toggleSelect would put an unresolvable id in selectedIds.
// Every click on a bucket row — plain or modified, title or row body —
// toggles its group, like its caret.
// Scope: this guards the CLICKED id only. rangeSelect slices the whole
// visibleRowIds span, and bucket rows sit in that list, so a shift-range
// spanning a bucket still sweeps its id into selectedIds. Consumers of
// selectedIds must filter isBucketId themselves.
```

Also drop the same false clause from the test comment at `TreeTable.test.ts:1305` ("A bucket is not a nib, so it can never join the bulk-action set.") — that test only proves the direct-click case.

**Severity note (dissent):** knowledge-reviewer rated this MUST (→ Critical under the normalization table); adversarial-reviewer rated the same clause Medium. Recorded as **High**: the comment causes no runtime failure on its own — its runtime consequence is P1, which is pre-existing — but it is proven false, is new in this diff, and belongs to this codebase's dominant defect class. The verdict is NEEDS_CHANGES either way.

---

### #2 🟡 Medium: The "Default:" comment claims a gesture means the same thing "anywhere on the row" — false for the caret and the [+] button

| | |
|---|---|
| **File** | `web/src/lib/components/TreeTable.svelte:454-455` |
| **Category** | comment-truth |
| **Confidence** | 100 (quotable-fact re-anchor; filed at 75) |
| **Found by** | knowledge-reviewer (SHOULD) — single finder |
| **Validation** | **confirmed** — severity corrected High → Medium by validator |

**Issue:** The comment reads:

```
// Default: row click and title click share one modifier path, so the same
// gesture means the same thing anywhere on the row.
```

The first half is true and is exactly what this fix achieves. The scope claim in the second half is not. The validator enumerated every `data-action` in `TreeTableRow.svelte` — exactly three exist: `add-child` (`:124`), `toggle` (`:164`), `title` (`:188`). Both `toggle` (`TreeTable.svelte:433-436`) and `add-child` (`:438-443`) early-return **above** this comment without ever reading `e.shiftKey` / `e.ctrlKey`. A ctrl-click on the caret toggles the node; a ctrl-click on `[+]` opens the type picker. No other cell (state/effort/tags/blocking) carries a `data-action`, so the exceptions are exactly the two named. The claim holds for the title cell and the row body — the two paths this fix unified — not for the whole row.

**Fix:** Bound the claim to the paths it covers. The validator independently verified this replacement text is itself accurate and complete (it correctly excludes `title`, which does *not* return above, and names no `data-action` that does not exist):

```
// Default: row-body and title clicks share one modifier path, so the same
// gesture means the same thing in both. Cells with their own data-action
// (toggle, add-child) returned above and never read modifiers.
```

**Severity note:** filed High; validator corrected to Medium — the contradicting early-returns are visible ~15 lines above the comment, so the risk is local to this function rather than propagating outward. That matches the finder's own rationale for self-downgrading from MUST to SHOULD.

---

## Pre-existing Issues

Informational only — excluded from the verdict and Summary counts. Both are mechanisms this change did not introduce; the fix's only relationship to them is that #1's comment denies P1, and that P2 gains one more entry point.

### P1 🟠 High: `rangeSelect` sweeps interior bucket ids into `selectedIds`, and bulk mutations then receive an unresolvable id

| | |
|---|---|
| **File** | `web/src/lib/selection.svelte.ts:60-62` (surfaced via `TreeTable.svelte:464`) |
| **Category** | error-handling / ADV_CASCADE |
| **Confidence** | 100 — **probe-confirmed** (see #1) |
| **Found by** | adversarial-reviewer (High, `pre_existing: true`) |

**Issue:** Epics lens, anchor on a nib under an epic header → shift-click a loose nib inside the bucket → `rangeSelect` slices `visibleRowIds` **across** the interior bucket row → `__no_epic__` lands in `selectedIds` → right-click Delete → `deleteBatch` includes it → `DeleteNib("__no_epic__")` errors → `dispatcher.ts:141` (`ok: failures === 0`) turns one bucket failure into a whole-batch failure → the real nibs **are** deleted, but `RowContextMenu.svelte`'s `if (result.ok)` cleanup is skipped, so `selection.clearAll()` and `nav.replaceClosed()` never run — leaving a stale `?nib=<deleted>` URL and deleted ids selected.

Consumers that receive the synthetic id: `RowContextMenu.svelte:56`, `useKeyboardShortcuts.svelte.ts:56`, `useTreeDrag.svelte.ts:117`.

**Fix (deferred — this is the hole #1 must stop denying):** filter synthetic ids inside `SelectionState` rather than at the dispatcher — have `rangeSelect` drop bucket ids from `rangeIds` (`.filter(id => !isBucketId(id))` before `new Set(...)`), or pass `visibleRowIds.filter(id => !isBucketId(id))` at the call site so a bucket can be neither an endpoint nor an interior member. Guarding the clicked id alone cannot cover the interior case. **Worth a follow-up nib** — per CLAUDE.md, findings too large to fix in-place should be deferred as nibs rather than silently skipped.

### P2 🟡 Medium: `syncTo` abandons a dirty editor buffer with no prompt on any multi-select gesture

| | |
|---|---|
| **File** | `web/src/lib/components/TreeTable.svelte:464-470` |
| **Category** | error-handling / ADV_COMPOSITION |
| **Confidence** | 75 |
| **Found by** | adversarial-reviewer (High) — **contested**: broad-reviewer examined and declined to flag |
| **Validation** | **confirmed**, but `pre_existing` corrected **false → true** by validator |

**Issue:** The mechanism is real and was verified by direct read: `open(nibId)` (`useActiveView.svelte.ts:685-686`) routes through `guarded` (`:334-341`) → `deps.confirm(...)` on a dirty buffer; `syncTo(nibId)` (`:728-730`) calls `apply(...)` directly — no guard, no prompt. So a docked editor dirty on nib A, then ctrl-click nib B's **title**, discards the unsaved edits silently, where the pre-fix title path prompted.

**Why it is reattributed pre-existing rather than a regression introduced here:** the validator established that (a) `useActiveView.svelte.ts:212-215` documents `syncTo` as *"the only transition that may ABANDON a dirty buffer without a confirm"*, (b) `useActiveView.svelte.test.ts:357` **pins the bypass with a passing test** ("syncTo bypasses the guard entirely (no confirm, no nav push)") — strong evidence it is designed, not accidental — and (c) the pre-fix default branch already sent ctrl/shift-clicks on most of the row's surface through this exact bypass. This fix routes one more entry point into a pre-existing, tested, intentional design.

The counterfactual also does not favor the old behavior: pre-fix, ctrl-click on a title prompted only because it was doing the *wrong* thing (routing to `view.open` and hard-resetting `selectedIds` — the bug being fixed).

**Residual worth a decision (not a blocker):** adversarial's sharper point survives reattribution — the title is the *primary* affordance, so the blast radius of the lossy semantics grows from incidental cells (nib-type, status) to the thing users actually click. Whether multi-select should prompt on a dirty buffer is a design question about `syncTo`, not about this fix. If the operator wants it revisited, it belongs in its own nib.

---

## Minor Findings

### Consistency

- `web/src/lib/components/TreeTable.svelte:449` — the new bucket guard's `return;` carries no trailing `// Don't fire row click for X` comment, unlike both of its siblings in the same function (`:435`, `:442`) (consistency-reviewer)
- `web/src/lib/components/TreeTable.svelte:414-415` — "mirroring the drag **handlers**, which skip buckets via the same isBucketId test": of the two sites, `:508` (`handleDelegatedPointerDown`) is a handler but `:620` (`draggable={!isBucketId(...)}`) is a markup prop (knowledge-reviewer, Low). **Disputed and likely fine:** broad-reviewer found a genuine second handler-level guard — `isValidDropTarget` (`dropZone.ts:41`) called from `onDragPointerMove` (`useTreeDrag.svelte.ts:192`) — which makes the plural accurate; consistency-reviewer and adversarial-reviewer also read the clause as true ("mild stretch" at worst). Recorded for the record; no action needed. The rewrite from the stale `~lines 428/540` to a symbolic reference is an unambiguous improvement — that was the one clause the brief flagged, and it checks out.
- `web/src/lib/components/TreeTable.test.ts:1296`, `:1321` — the two new bucket-click tests omit the `expect(bucketTitle).toBeInTheDocument()` element-presence assertion their immediate siblings make (`:1244`, `:1278`) (consistency-reviewer, filed Medium). **Downgraded:** typescript-reviewer refuted the vacuous-pass risk — a selector miss makes `user.click(null)` throw loudly, so this is pure convention drift, not a correctness gap.
- `web/src/lib/components/TreeTable.test.ts:1311` — the new Shift+click bucket-body test pre-selects an anchor nib but never asserts the selection survives, unlike its own Ctrl+click sibling (`:1306`) and the established row-level shift test (`:983-1004`) (consistency-reviewer)

### Residual Risks

- `web/src/lib/components/TreeTable.svelte:449` — the new guard duplicates `openOrToggleBucket`'s `isBucketId` + `toggleNode` logic (quick-reviewer, Low). **Counter-evidence:** broad-reviewer and consistency-reviewer independently concluded the two checks serve distinct live purposes — `openOrToggleBucket`'s internal test is now unreachable *from the click path*, but remains load-bearing for `handleDelegatedDblClick` (`:482`) and `navigateToNib` (`:386`, keyboard nav), neither of which has a bucket guard of its own. Not dead code; reads as defense-in-depth across distinct call sites.

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| quick-reviewer | 1 | 1 |
| broad-reviewer | 0 | 0 |
| knowledge-reviewer | 3 | 2 |
| consistency-reviewer | 3 | 3 |
| typescript-reviewer | 0 | 0 |
| test-reviewer | 0 | 0 |
| adversarial-reviewer | 3 | 2 |
| **Total** | **9** | |

Notes:
- **Issues Found**: total findings attributed to this agent (including shared findings)
- **Unique Issues**: findings reported ONLY by this agent
- Total counts each consolidated finding once: 2 primary + 2 pre-existing + 5 minor.
- broad, typescript, and test each returned zero findings but did substantial **refutation** work that shaped this report: broad supplied the counter-evidence on the "drag handlers" plural and on the guard-duplication finding; typescript refuted the vacuous-pass risk in the new tests; test-reviewer independently predicted all three mutation outcomes correctly before they were run. Zero findings is not zero contribution.

---

## Specialist Notes

### Probe Results (orchestrator, isolated worktree)

Six probes were nominated across the wave. All were run **after** the review wave joined, in a detached worktree created from `git stash create` — never in the shared tree. The probe worktree was verified to contain the fix before any result was trusted (`isBucketId(nibId)` guard present at `:449`; zero occurrences of `action === "title"`), and verified byte-identical to the reviewed state (`git diff --stat` empty vs. the stash commit) before the headline probe. Baseline in-probe: 70/70 TreeTable tests passing.

| # | Probe | Predicted | Actual | Outcome |
|---|-------|-----------|--------|---------|
| A | Restore the `action === "title"` early return | 2 fail | 2 failed — `Ctrl+click on the title text…`, `Shift+click on the title text…` | ✅ exactly as claimed |
| B | Remove the bucket guard (`:449-452`) | 2 fail | 2 failed — both bucket tests | ✅ exactly as claimed |
| C | Narrow guard to `isBucketId(nibId) && action === "title"` | 1 fail (body) | 1 failed — **bucket body only** | ✅ exactly as claimed |
| D | Shift-range spanning a bucket (knowledge + adversarial) | FAILS red | FAILED — `selectedIds: ["nibs-e1","__no_milestone__","nibs-loose"]` | ✅ finding #1 confirmed |
| E | ~18 `App.test.ts` plain-click-on-title sites | no regression | 1292/1292 green | ✅ no regression |
| F | Dirty-buffer ctrl-click on title (adversarial) | needs a view stub | not run — `setupWithNibs` has no view-stub seam (`opts` takes only `selection`/`drag`) | resolved by code read instead; see P2 |

**Test integrity verdict: all four new tests bite.** Mutations A, B, and C reproduced the implementer's claims exactly — including the subtle one: mutation C fails **only** the bucket-**body** test, proving that test discriminates guard *placement* and is not redundant with the bucket-title test. No decorative guards in this changeset. The implementer's decision to delete the old `:1166` test rather than ship a decorative rewrite is corroborated by test-reviewer's independent read (post-fix it was byte-identical to `:1027`).

### Considered But Not Flagged (all agents)

**Bucket guard placement — the brief's primary probe target. Cleared by four independent agents.** quick, broad, consistency, and adversarial each traced every branch and converged: the guard's placement before the modifier block is correct and complete *for the clicked id*. `action === "toggle"` short-circuits above it (same `toggleNode` effect, no divergence); `action === "add-child"` is **unreachable** on a bucket — `makeBucketNode` sets `type: ""` (`tree.ts:162`), `canHaveChildren("")` is false (`typeHierarchy.ts:40-43`), so `TreeTableRow:118` never renders the `[+]`. Every other click on a bucket `<tr>` reaches the guard. No path lets a bucket be the *clicked* argument to `toggleSelect`/`rangeSelect`. The interior-range path (finding #1 / P1) is the one axis the guard cannot cover, and it is a different mechanism.

**`retainOnly` (`selection.svelte.ts:96`) — the brief asked whether it matters and whether not relying on it is correct.** Both broad and adversarial answered: not relying on it is correct, but the reasoning differs from the obvious one. broad: a bucket id can never enter `selectedIds` via a direct click, so there is nothing to prune. adversarial (sharper, and correct given P1): the prune `$effect` depends only on `$result.fetching` / `allNibs` / `resolvedFilter`, with `retainOnly` inside `untrack` — a click mutates none of those, so it does **not** re-run after a shift-range. It is a backstop for filter changes, not a synchronous invariant. The window between a shift-click and the next bulk action is fully open.

**Boundary inputs — all cleared:**
- *Bucket with no children*: structurally impossible — `tree.ts:217` only pushes a bucket node when `bucketItems.length > 0`.
- *Shift-click with no anchor*: safe — `rangeSelect`'s `const anchor = this.anchorId ?? nibId` collapses to a single-element range → `selectedNibId = rangeIds[0]`; `startIndex/endIndex < 0` is guarded.
- *Drag in progress*: `if (drag.isDragging) return;` at `:425` is untouched and still short-circuits first.
- *Stale bucket id*: not reachable — bucket ids are compile-time constants per lens (`tree.ts:44-46`), re-derived identically each render.
- *Abandoned-drag → click*: adversarial tried and dropped it — `:508` already excludes buckets from drag initiation, and the sequence behaves identically before and after this diff.
- *Ctrl-click on a title inside a group that then collapses*: dropped — `toggleSelect` does not mutate `treeView.collapsedIds`, so the row cannot move out from under the pointer.

**`isBucketId` string-identity safety**: typescript-reviewer verified `isBucketId` (`tree.ts:59-68`) is exact `Set` membership against three fixed literals (`__no_milestone__`, `__no_epic__`, `__no_feature_or_bug__`) — not a prefix/pattern test — so it cannot collide with a real nib id under any `nibs.prefix` configuration.

**Retained comment clauses below "Default:" (`:456-462`)**: knowledge verified all four against the newly-routed title path — no Back/Forward entry (both modifier branches call `selection.*` + `syncTo`, never `view.open`); collapse-to-exactly-one opens the panel (`toggleSelect:43-44`, `rangeSelect:65-66`); collapse-to-zero closes it (`toggleSelect:47`); "only a plain click is treated as navigation" (the `else` branch at `:472` is the sole `view.open` route). Retaining them unchanged is correct.

**Deleted test / `"Title click selects, not row click"` comment**: no knowledge lost. The comment encoded that title and row-body were *distinct* dispatch paths — precisely the premise this fix removes; preserving it would be false. The surviving plain-click assertion is covered by `:1027` plus both new title-modifier tests.

**Pre-existing, out of diff, not filed**: `TreeTableRow.svelte:196` carries `"see nibs-e81b for the planned mirrored emphasis treatment"` — a nib ID in a code comment, against CLAUDE.md. Noted by knowledge-reviewer for completeness; in a file this changeset does not touch.

**Suppressed by the confidence gate**: none. No finding was submitted below anchor 75.

**Out of scope, correctly left alone by all seven agents**: nibs-504h (Space on a focused title), nibs-w4zz (`:131-137` reexecute branch), and the pre-existing bucket modifier-click hole (not re-filed as a regression by anyone).

---

## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `web/src/lib/components/TreeTable.svelte` | comment-truth | 1 (this review) | 2026-07-15 |

No prior review flagged `TreeTable.svelte` for comment-truth specifically, so there is no file+category recurrence to report.

**Category-level pattern worth surfacing anyway:** comment-truth / comment-accuracy findings appear in **11 of the review files** under `.decaf/code-reviews/`, most recently on `ActiveNibView.svelte` (2026-07-15). This review adds a 12th, on a different file. The category — not any single file — is the recurring defect, which is consistent with the brief's account of nine false comments in two days. Both primary findings in this review are comment-truth. That is the signal: the changeset's *logic* was clean under adversarial probing and mutation testing; its *comments* were where the defects were.

## Session Metrics (--report)

**Wave timing**: dispatched 23:38 → last reviewer returned ~23:45 → probes run 23:46–23:55 → validation dispatched 23:55 → validation done ~23:57 → file written 23:58

| Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings submitted |
|-------|------|------|--------|-----------|----------|--------------------|
| quick-reviewer | reviewer | sonnet (mid) | 85,087 | 18 | 180,095 ms | 1 |
| broad-reviewer | reviewer | sonnet (mid) | 108,122 | 33 | 272,021 ms | 0 |
| knowledge-reviewer | reviewer | opus (session) | 97,888 | 19 | 240,991 ms | 3 |
| consistency-reviewer | reviewer | sonnet (mid) | 90,874 | 17 | 241,937 ms | 3 |
| typescript-reviewer | reviewer | sonnet (mid) | 75,651 | 13 | 96,677 ms | 0 |
| test-reviewer | reviewer | sonnet (mid) | 105,251 | 24 | 277,215 ms | 0 |
| adversarial-reviewer | reviewer | opus (session) | 95,270 | 23 | 253,963 ms | 3 |
| finding-validator (#2 "anywhere on the row") | validator | sonnet (mid) | 60,879 | 5 | 85,178 ms | verdict: confirmed |
| finding-validator (#6/P2 dirty-guard bypass) | validator | sonnet (mid) | 72,230 | 13 | 141,498 ms | verdict: confirmed |

Totals (sums of harness-reported figures): **791,252 tokens**, **165 tool calls** across 9 agents.
[Unverified] whether a subagent's reported token figure includes its own children — this caveat carries to both totals.
Review wave wall-clock ≈ longest reviewer (277,215 ms); validation wave ≈ longest validator (141,498 ms). Probe pass is orchestrator-side and not represented in any agent row.

**Pre-flight gates**:
- `npx vitest run --reporter=agent` (web) — **PASS**, 60 files / 1292 tests
- `npx svelte-check --threshold error` — **PASS**, 0 errors / 0 warnings / 0 files with problems
- `task test` / `task lint` / `task build` — reported green by the implementer; not independently re-run by this wave (the web suite is the relevant gate for a web-only changeset)

**Anomalies**: none. All 7 reviewers and both validators were dispatched without `name` and with `run_in_background: false`; all 9 returned their reports as tool results. No spawn acknowledgments, no teammate-mode returns, no re-dispatch needed. No injected-content flags. No reviewer reported an admissibility problem from a sibling's build/test activity. The shared working tree was verified byte-identical (+104/-21, no stash entries) after the probe pass; the probe worktree was removed and pruned.
