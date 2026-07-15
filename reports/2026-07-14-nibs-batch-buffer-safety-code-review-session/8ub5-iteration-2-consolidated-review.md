# Code Review

**Mode**: mid (explicit) · roster cap 4 — 3 gate-matched agents dropped | **Reviewers**: quick, broad, consistency, test | **Date**: 2026-07-14
**Source**: local uncommitted changes (branch `batch/buffer-safety-watch-cleanup`)
**Scope**: 2 files changed, +117/-23 lines
**Spec**: none found
**Validation**: 1 confirmed, 0 refuted, 0 uncertain (1 dispatched, 0 waived, 0 over budget)

## Agent Selection Rationale

Mode was **explicit** (`mid4`), so Step 2a.5 selection was skipped. Step 2b matched 7 agents; the cap kept 4.

- `quick-reviewer` — always (review floor)
- `broad-reviewer` — always (review floor)
- `consistency-reviewer` — **kept**: comment-code mismatch is its declared lane, and this round's entire stated risk is comment accuracy plus CLAUDE.md comment conventions; it is the only persona required to quote a convention source for every finding
- `test-reviewer` — **kept**: hard gate matched (test files present), and the test file is 95 of 117 changed lines; the caller's "probe inputs between the pinned cases" ask is a test-adequacy question
- `typescript-reviewer`: **dropped — roster cap (mid4)**: hard-gate coverage deliberately traded. Only 2 executable production TS lines changed (`const raw = initialValue`, `const next = v.state.toText(raw).toString()`), so the TS-idiom surface is close to nil versus the comment/test risk. **Flagging per Step 2b.5**: this is a hard-gate agent dropped on a TS-bearing diff — a real coverage trade, not a gate decision. A higher `N` would restore it.
- `knowledge-reviewer`: **dropped — roster cap (mid4)**: ranked below the 2 kept. Its lane (missing/undocumented knowledge) overlaps `consistency` + `broad` here — the comments are abundant, and the risk is that they are *wrong*, not absent.
- `adversarial-reviewer`: **dropped — roster cap (mid4)**: ranked below the 2 kept; boundary-case probing delegated to `test-reviewer` plus the floor.
- `design-reviewer`: skipped — no public API/contract, data model, boundary, or concurrency surface changed (prop docblock text only)
- `security-reviewer`: skipped — no security-adjacent surface
- `performance-reviewer`: skipped — the diff **removes** the full-string regex pass the prior round added, replacing it with a library call on the same path; no new cost surface
- `spec-compliance-reviewer`: skipped — no spec found (hard gate)
- `data-migration-reviewer`: skipped — no migration artifacts (hard gate)
- `dotnet` / `cpp` / `go` / `rust` reviewers: skipped — no such files in changeset (hard gate). The Go file cited in the brief is context, not in the diff.
- `prior-feedback-reviewer`: skipped — not a PR (hard gate)

**Model tiering (mid):** all four agents in this roster are volume agents (`quick`, `broad`, `consistency`, `test`), so all ran mid-tier; the validator ran mid-tier. **Consequence worth naming**: the `mid` policy left this wave with no top-tier agent, because the cap's ranking dropped every judgment agent (`knowledge`, `adversarial`). The mode was explicit, so the policy was followed as specified — but `high4` would have run the same roster on the session model.

**Pre-flight gates** (run once for the wave): web tests **PASS** (60 files, 1215 tests) · svelte-check **PASS** (4737 files, 0 errors, 0 warnings).

**Working-tree integrity**: two agents ran non-destructive mutation probes on `MarkdownEditor.svelte:278`. Post-wave verification confirms the tree is byte-intact — `git diff HEAD --stat` still reports exactly `45` / `95` lines changed (117 insertions, 23 deletions), and `git stash list` is empty.

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 0 |
| 🟡 Medium | 1 |
| 🟢 Low | 0 |
| 🔵 Minor | 1 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts the reported-but-non-blocking findings (Consistency / Testing Gaps / Residual Risks). Pre-existing issues are listed separately and excluded from both.

**Verdict**: ✅ APPROVED

**The fix round did what it claimed, and the replacement comments survived adversarial fact-checking.** All three prior primaries are resolved. Critically, the specific regression risk the caller asked us to probe — *that a wrong replacement comment re-introduces the defect class being fixed* — **did not materialize**: three agents independently traced every factual claim in the new comments to source (`@codemirror/state` 6.6.0 dist, `internal/nib/nib.go`, `nibForm.svelte.ts`) and all claims checked out. No comment-code mismatch was found.

**What was independently verified this round** (recorded because it is the substance of the review):
- **The `toText` delegation is correct and provably tracks `doc.toString()`.** `EditorState.create` builds the doc via `Text.of(config.doc.split(configuration.staticFacet(EditorState.lineSeparator) || DefaultSplit))` (dist/index.js:2741); `EditorState.prototype.toText` uses `Text.of(string.split(this.facet(EditorState.lineSeparator) || DefaultSplit))` (dist/index.js:2672-2673). `broad-reviewer` went a step further than the brief required and confirmed `EditorState.lineSeparator` is declared `static: true` (dist/index.js:2027), so `staticFacet` and `facet` resolve through the *same* `config.staticValues` table — meaning `create()` and a later `toText()` are provably reading the same value, not merely equal today.
- **`Text.prototype.toString()` rejoins with `"\n"` unconditionally** (`sliceString(from, to, lineSep="\n")`, dist/index.js:106/179/271) — facet-independent, for both `doc.toString()` and `toText(...).toString()`. The new comment's claim is exact.
- **The dangling-lone-CR backend claim is accurate.** `frontmatter.Parse` (adrg/frontmatter v0.2.0) returns remaining bytes verbatim with no CRLF normalization; `internal/nib/nib.go:446` does `strings.TrimSuffix(string(body), "\n")`, trimming a bare `\n` but not `\r\n`. A CRLF-terminated body does arrive with a trailing lone `\r`.
- **The `dirty` / `#matchesFields` "never settle" claim is real**, not fabricated — `fieldsFromSnapshot` copies `body: s.body` unnormalized (`nibForm.svelte.ts:90-100`), and `dirty` (`:200`) / `#matchesFields` (`:436`) both do strict string equality.
- **The `Regression:` marker is a genuine codebase convention** — `TreeTable.test.ts:256,1180,1430,1462`, `useScrollRestore.test.ts:159,230`, `useHistoryNav.test.ts:71,88` all use the identical form.
- **Referencing a Go backend file from a web comment is established**, not drift — `nibForm.svelte.ts:112`, `typeHierarchy.ts:11`, `nibForm.svelte.test.ts:386` all do it.
- **CLAUDE.md comment rules hold**: no British spellings and no nib/issue IDs in any added line (grepped across the diff's `+` lines by three agents independently).
- **The `raw`/`v` reordering is not a regression.** `broad-reviewer` checked the specific risk the brief raised: the pre-patch code already read `initialValue` unconditionally before the same early return, so the diff only swaps two already-unconditional reads relative to each other. No tracking change.
- **`ChangeSet` insert re-splitting is not a hazard** — `ChangeSet.of` → `Text.of(insert.split(lineSep || DefaultSplit))` (dist/index.js:972); inserting an already-normalized substring is idempotent.
- **The tests are not vacuous against the primary regression class.** A revert probe to `const next = raw;` (the pre-round-1 bug) reproduces exactly `5 failed / 10 passed`, matching the prior round's figures; restored → 15/15.

The single Medium below is a genuinely new observation the caller's boundary-probing instruction earned: it is about what the tests *cannot* distinguish, not about anything being wrong.

---

## Findings

### #1 🟡 Medium: New CRLF tests cannot distinguish the `toText` delegation from the regex it replaced

| | |
|---|---|
| **File** | `web/src/lib/components/MarkdownEditor.test.ts:255` (spans the `it.each` block and the "DOES dispatch" test, 255-309) |
| **Category** | test-coverage |
| **Confidence** | 100 |
| **Found by** | test-reviewer (Medium) |
| **Validation** | ✅ confirmed — probe independently reproduced |

**Issue:** This round's structural fix replaced a local `raw.replace(/\r\n?/g, "\n")` with `v.state.toText(raw).toString()` (`MarkdownEditor.svelte:278`) precisely because the regex silently breaks once a custom `EditorState.lineSeparator` facet is configured. **The new tests do not pin that property.**

Two agents independently ran the same non-destructive mutation probe: swapping line 278 back to `const next = raw.replace(/\r\n?/g, "\n");` still yields **15/15 passing** — identical to the fixed state. Only removing normalization entirely (`const next = raw;`) produces the expected `5 failed / 10 passed`.

The cause is structural, not a patchable oversight. `MarkdownEditor.svelte`'s `editorBasics` extension list (lines 170-221) never includes `EditorState.lineSeparator.of(...)`, and the validator grepped all of `web/src` confirming the facet is never configured anywhere (the only hits are the explanatory comment in this very file). Under an unset facet, `toText` and the regex are mathematically identical for every reachable input — the validator checked empty string, trailing lone CR, trailing CRLF, consecutive CRs, and CRLF-CRLF blank lines, noting that `DefaultSplit`'s extra `|\n` alternative is a no-op since re-joining LF-split segments with `"\n"` changes nothing.

So the `it.each` table and the "DOES dispatch" test genuinely guard the outward CRLF-insensitivity behavior, but give **zero coverage** for the facet-independence property that `MarkdownEditor.svelte:250-255` cites as the whole reason for delegating to `toText`.

**This is not a restatement of an accepted scope decision.** The validator explicitly checked: the brief's accepted decision concerns the *test's own oracle* staying an independent regex; this finding is about the production-vs-test facet-sensitivity gap. Distinct point.

**Why it is Medium and not higher:** nothing today sets the facet, so there is no live bug — the fix is strictly better than the regex regardless of coverage. The exposure is a future refactor.

**Failure scenario:** A later PR "simplifies" `v.state.toText(raw).toString()` back to an inline `/\r\n?/g` regex during an unrelated cleanup — plausible, since the regex reads as equivalent and shorter, and the rationale lives only in a comment. All 15 tests and both pre-flight gates stay green. The regression stays invisible until the app gains a feature that configures a custom line separator (e.g. a "preserve original line endings" option), at which point the reintroduced regex silently corrupts CRLF documents — exactly the bug class this round closed off.

**Fix:** The component never exposes the facet, so the property cannot be pinned at the component level. Either add a narrow unit test against the real module (already imported via `vi.importActual` in this file):

```ts
it("toText tracks a configured line-separator facet where a bare regex would not", async () => {
  const { EditorState } = await vi.importActual<typeof import("@codemirror/state")>(
    "@codemirror/state",
  );
  const facetState = EditorState.create({ extensions: [EditorState.lineSeparator.of("\n")] });
  const crlf = "a\r\nb";
  expect(facetState.toText(crlf).toString()).toBe(crlf); // untouched: \n is the only separator
  expect(crlf.replace(/\r\n?/g, "\n")).not.toBe(crlf);   // the regex would normalize — divergence
});
```

…or document the limitation in a comment near the `it.each` block so a future reader does not mistake the suite for a guard against regex reintroduction. Either is acceptable; the first converts the docblock's "under ANY line-separator configuration" claim from an unpinned assertion into an executable one.

---

## Minor Findings

### Consistency

- `web/src/lib/components/MarkdownEditor.test.ts:52` — **Un-mock rationale comment sits close to the change-history line** (test-reviewer, Low/50; **dissent**: quick-reviewer examined the identical comment and dismissed at anchor 25; broad-reviewer dismissed the analogous hypothetical in the `MINIMAL DIFF` comment). The comment says *"A hand-rolled `toString: () => config.doc` would echo the doc back verbatim and hide that"* — a near-verbatim description of the mock this same diff deletes a few lines above. All three agents converge on the same reading: it uses no forbidden trigger word ("previously", "was", "changed from"), is phrased as forward-looking "why not to do X" design rationale, and is therefore **compliant with the letter of CLAUDE.md's rule** — but a future comment-audit pass could reasonably read it as narration. `consistency-reviewer` separately established that the contrastive "X rather than Y" idiom in the Svelte docblock *is* an established codebase convention (`tableData.ts:24`, `filter.ts:7,53`, `markdown.ts:198`, `treeView.svelte.ts:25`, `useTreeDrag.svelte.ts:187,275`) and not history narration. Reported for awareness only — no agent claims a violation. Optional rephrasing, if desired: state the invariant directly ("the sync effect's correctness depends on the real line-splitting behavior of `EditorState.create`/`toText`, and only the real module can honestly assert that CRLF/CR normalize to LF") rather than via the counterfactual that mirrors the deleted mock.

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| quick-reviewer | 0 | 0 |
| broad-reviewer | 0 | 0 |
| consistency-reviewer | 0 | 0 |
| test-reviewer | 2 | 2 |
| **Total** | **2** | |

Notes:
- **Issues Found**: Total findings attributed to this agent (including shared findings)
- **Unique Issues**: Findings reported ONLY by this agent and no other
- Three of four agents returned zero findings after independently fact-checking every claim in the new comments against library and backend source. That is the review's principal result, not an absence of effort — `broad` made 31 tool calls, `consistency` 32, `quick` 19, all substantially spent on source verification.

---

## Specialist Notes

### Convention census (consistency-reviewer)

Built from `web/src/lib/nibForm.svelte.ts`, `web/src/lib/markdown.ts`, `internal/nib/nib.go`, `node_modules/@codemirror/state/dist/index.js` (6.6.0), and ~6 sibling test files. Conventions checked, **all followed**:

| Convention | Source quoted | Verdict |
|---|---|---|
| `// Regression:` marker above guarded test | `TreeTable.test.ts:256,1180,1430,1462`; `useScrollRestore.test.ts:159,230`; `useHistoryNav.test.ts:71,88` | followed |
| Go backend file referenced from web comment | `nibForm.svelte.ts:112`; `typeHierarchy.ts:11`; `nibForm.svelte.test.ts:386` | followed |
| "X rather than Y" contrastive design rationale | `tableData.ts:24`; `filter.ts:7,53`; `markdown.ts:198`; `treeView.svelte.ts:25`; `useTreeDrag.svelte.ts:187,275` | followed (not history narration) |
| `it.each` table with `_label` first element | `activeView.test.ts:163,196` | followed |
| `const raw = ...` for a value read before use | `ActiveNibView.svelte:268`; `storage.ts:152` | followed |
| American spelling; no nib IDs in comments | CLAUDE.md; grepped all `+` lines | followed |

Noted but not reportable (anchor 25): the new `vi.mock("@codemirror/state", async () => vi.importActual(...))` returns directly without `await`/spread, where 4 siblings (`mutations/store.test.ts:9`, `ActiveNibView.svelte.test.ts:34`, `mutations/dispatcher.test.ts:20`, `TreeTable.test.ts:34`) do `const actual = await vi.importActual(...); return {...actual, override}`. Every sibling needs an override (hence the spread); this case needs none — the degenerate case of the same pattern, not a deviation.

### Considered But Not Flagged (all agents)

**quick-reviewer**
- Comment-narration boundary at `MarkdownEditor.test.ts:52-57` — hypothetical phrasing, no trigger words, reads as forward-looking rationale; permitted (anchor 25). *→ Promoted to Minor/Consistency by Step 5.5 cross-reference, since test-reviewer flagged it.*
- `raw`/`v` reordering at `:275-276` — comment implies the read must precede the early return; true, but already true pre-patch, so the reorder is cosmetic, not required (anchor 25).
- Mocked `EditorView.state` frozen at construction — real, but on the brief's do-not-flag list as pre-existing.
- Boundary inputs (empty, no trailing terminator, mixed CR/LF/CRLF) — traced through `DefaultSplit` and `Text.of(...).toString()`; all normalize identically under the unset facet. No gap rising to a finding.
- `ChangeSet` re-splitting the dispatched `insert` — confirmed idempotent; no double-normalization or echo-loop risk.

**broad-reviewer**
- `vi.mock(... vi.importActual)` — standard Vitest pass-through; verified no conflict with the mocked `@codemirror/view`.
- `historyExcluded` built once at module load vs. `addToHistory.of(false)` called fresh per dispatch — `toHaveBeenCalledWith` uses structural equality and `Transaction.addToHistory` is a module-level singleton `AnnotationType`, so the instances compare equal. Confirmed empirically and by reading `Annotation`/`AnnotationType`.
- The unused-`EditorState`-import removal named in the brief is **not present in this diff** — already committed in a prior state of the branch. Out of scope for a diff-based review. *(Noted: item 4 of the brief's fix list is only half-represented here; the `Regression:` markers are in the diff, the import removal is not.)*
- The `MINIMAL DIFF` comment's hypothetical — consequence-based rationale, not prior-behavior narration.

**consistency-reviewer**
- Enumeration order "CR / CRLF / LF" vs. `markdown.ts:198`'s "(CRLF, lone CR, LF, mixed)" — cosmetic ordering, not term drift.
- `// Precondition:` label — one-off marker with no competing sibling convention to cite.
- CRLF regex "duplication" between test oracle and production — no shared line-ending constant exists in `web/src/lib` (checked); `markdown.ts`'s regex is private to that file. Brief scopes the oracle as deliberately independent.

**test-reviewer**
- Precondition assertions verified non-vacuous for **all four** table rows plus extra boundary inputs (trailing CRLF-only, consecutive lone CRs, mixed CR/CRLF/LF, reversed LF-then-CR, empty string) — the regex oracle and `toText` agree in every case under the unset facet. No row is vacuous; if CodeMirror's behavior ever changes, the test fails at the precondition rather than passing silently.
- Hybrid mocking (real `@codemirror/state` + mocked `@codemirror/view`) holds — `view.state` is the real frozen `EditorState` from the component's own `create()`; `toText` does not depend on `dispatch` ever being applied, so the frozen-state limitation does not affect the new tests.

**Suppressed by the confidence gate**: 0 findings. No agent submitted a finding below anchor 75 that was not routed to Minor.

---

## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `web/src/lib/components/MarkdownEditor.test.ts` | test-quality / test-coverage | 3 | 2026-07-14 |

Prior occurrences: `CODE_REVIEW_2026-07-14_17-18-12.md` (`:191` — test-quality / false-positive-test) and `CODE_REVIEW_2026-07-14_20-12-33.md` (`:52-57` — test-quality / mock-fidelity).

**Worth noting**: this round's Minor finding lands on **exactly the same lines** (`:52-57`) as the prior round's mock-fidelity finding. That is expected — the prior finding caused the mock's removal, and the new comment explains the removal. The recurrence is locational, not a re-opening of the same defect. The broader pattern is real though: `MarkdownEditor.test.ts` has now drawn a test-quality finding in three consecutive reviews, each a different defect. The file is the diff's centre of gravity and is getting proportionate scrutiny.
