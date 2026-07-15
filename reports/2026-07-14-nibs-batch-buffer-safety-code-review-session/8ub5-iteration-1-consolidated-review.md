# Code Review

**Mode**: mid (explicit) | **Reviewers**: quick, broad, knowledge, consistency, design, test, adversarial, performance, typescript | **Date**: 2026-07-14
**Source**: local uncommitted changes (branch `batch/buffer-safety-watch-cleanup`)
**Scope**: 2 files changed, +102/-23 lines
**Spec**: none found
**Validation**: 5 confirmed, 1 refuted, 0 uncertain (6 dispatched, 0 waived, 0 over budget)

## Agent Selection Rationale

Mode was **explicit** (`mid`), so Step 2a.5 selection was skipped.

- `quick-reviewer` — always (review floor)
- `broad-reviewer` — always (review floor)
- `knowledge-reviewer` — substantive change; the diff encodes a subtle library invariant almost entirely in comments
- `consistency-reviewer` — substantive change with sibling components and 60 sibling test files to compare against
- `design-reviewer` — the component's prop contract semantics changed (a new exception to the ECHO-LOOP CONTRACT's rule 1)
- `adversarial-reviewer` — state-sync echo loop on a data-mutation-with-persistence path; test additions exceed 50 executable lines
- `performance-reviewer` — the changed `$effect` is on the keystroke hot path; the diff adds a full-string regex pass over an unbounded body
- `typescript-reviewer` — hard gate: TS/JS files in changeset
- `test-reviewer` — hard gate: test files in changeset
- `security-reviewer`: skipped — no security-adjacent surface; the one new expression is a bounded, backtrack-free `/\r\n?/g`
- `spec-compliance-reviewer`: skipped — no spec found (hard gate); no `plans/`, no `docs/specs`, no PR, no session spec
- `data-migration-reviewer`: skipped — no migration artifacts (hard gate)
- `dotnet` / `cpp` / `go` / `rust` reviewers: skipped — no such files in changeset (hard gate). The Go file cited in the brief is out of scope and not in the diff.
- `prior-feedback-reviewer`: skipped — not a PR (hard gate)

**Model tiering (mid):** judgment agents (`knowledge`, `design`, `adversarial`) inherited the session model; volume agents (`quick`, `broad`, `consistency`, `test`, `performance`, `typescript`) and all 6 validators ran mid-tier.

**Pre-flight gates** (run once for the wave): web tests PASS (60 files, 1215 tests) · svelte-check PASS (4737 files, 0 errors, 0 warnings) · web build PASS (no warnings).

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 2 |
| 🟡 Medium | 1 |
| 🟢 Low | 0 |
| 🔵 Minor | 3 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts the reported-but-non-blocking findings. Pre-existing issues are listed separately and excluded from both.

**Verdict**: ❌ NEEDS_CHANGES

All three primary findings are **documentation-accuracy defects, not behavioral defects**. The code fix itself was verified correct by four independent agents. The verdict is driven by two High-severity comment inaccuracies in a docblock whose entire purpose is to stop a future maintainer from reintroducing this bug — in a repo that just completed a 4-commit comment audit. The fixes are small comment edits plus one test fixture.

**What was verified and held up** (recorded because it is the majority of this diff's value):
- The core fix is **correct**. `/\r\n?/g` was verified byte-equivalent to CodeMirror's `DefaultSplit = /\r\n?|\n/` (`node_modules/@codemirror/state/dist/index.js:608`) by four agents independently, including hand-traced edge cases (`"\n\r"`, `"\n\r\n"`, `"\r\r\n"`, `"a\r\nb\r"`). It is an exact inverse, not an approximation.
- The **new regression tests genuinely fail against the unfixed code**. test-reviewer ran a non-destructive revert probe: unfixed → `5 failed | 10 passed`; restored → `15 passed`; `git diff --stat` byte-identical afterward. The tests are a real guard, not vacuous.
- Switching `@codemirror/state` from the hand-rolled fake to `vi.importActual` is a **material testing improvement** — the old mock's verbatim `toString()` echo would have hidden exactly this bug class.
- The prompt's suspected failure modes **did not survive contact**: diff offsets stay in doc coordinate space (`{from:3,to:4,insert:"x"}` confirmed by probe); there is no mount-time disagreement window; performance cost is negligible (real nib bodies average 2.6 KB, max 13 KB observed across 377 files).

---

## Findings

### #1 🟠 High: Comment asserts a backend round-trip property the backend does not have

| | |
|---|---|
| **File** | `web/src/lib/components/MarkdownEditor.svelte:238-239` (mirrored at `web/src/lib/components/MarkdownEditor.test.ts:250-251`) |
| **Category** | knowledge-preservation / assumption-unvalidated |
| **Confidence** | 75 |
| **Found by** | knowledge-reviewer (SHOULD → High) |
| **Validation** | CONFIRMED |

**Issue:** The new comment claims nib bodies "round-trip through the backend with their line endings untouched". The validator independently re-derived that this is false at the body's trailing edge. `internal/nib/nib.go:446` does `strings.TrimSuffix(string(body), "\n")` on bytes returned verbatim by `github.com/adrg/frontmatter` (`parser.go:50-54` reads the post-delimiter remainder through `bytes.Buffer.ReadFrom` with no normalization). So a file body ending `...\r\n` yields `b.Body` ending `...\r` — a **dangling lone CR**, not `...\r\n`. That field is exposed via GraphQL with no re-normalization (`internal/graph/generated.go:2579`: `return obj.Body, nil`), and the path is reached by both the initial disk load (`internal/nibcore/core.go` `loadNib` → `nib.Parse`) and the fsnotify watcher's reload.

`Render()` (`nib.go:695-744`) is asymmetric-but-stable: since `b.Body` ends in `\r` rather than `\n`, it re-appends `\n`, so a no-op resave round-trips the file back to `...\r\n`. The behavior is therefore **benign today** — but the in-memory/GraphQL-visible value during that window is the mangled form, and the comment is the only place in the web tree describing what CRLF shapes actually arrive.

The error already propagated into this diff: the fixture labeled `"realistic CRLF body"` (`MarkdownEditor.test.ts:258`) ends `"\r\n"` — the shape the disk-load path never produces. The genuinely realistic shape (trailing lone CR) is untested.

**Validator nuance worth keeping:** "the backend never emits a trailing `\r\n`" is slightly overbroad as a universal claim. A body returned directly from a Create/UpdateNib mutation response (`schema.resolvers.go:41/223` sets `b.Body = *input.Body` and returns it without going through `nib.Parse`) *could* retain a literal trailing `\r\n` if a non-web client (e.g. CLI `--body-file`) submitted one. This does not refute the finding — the comment's own stated scenario is the Windows-CRLF-file disk-load path, where the mangling is real and demonstrated.

**Fix:** Correct the claim at `MarkdownEditor.svelte:238-239` to state that the backend does not normalize line endings **and** trims one trailing `\n`, so a CRLF body's last line ending arrives as a lone `\r`. Mirror at `MarkdownEditor.test.ts:250-251`. Change the fixture at line 258 to the shape the disk-load path actually emits:

```ts
["realistic CRLF body", "# T\r\n\r\n- [ ] one\r\n- [ ] two\r"],
```

---

### #2 🟠 High: "It buys nothing" records a rationale that is materially false and hides the real constraint

| | |
|---|---|
| **File** | `web/src/lib/components/MarkdownEditor.svelte:29-30` |
| **Category** | knowledge-preservation / decision-log-missing |
| **Confidence** | 75 |
| **Found by** | knowledge-reviewer (SHOULD → High) |
| **Validation** | CONFIRMED |

**Issue:** The new text reads:

> Consumers still should not pre-normalize — it buys nothing and rule 1 is easier to honor as an absolute.

This is rigorously true only for the narrow act of normalizing the value fed *back* as `initialValue`. But the sentence carries **no scope qualifier**, and the preceding sentence has just established that the consumer *retains* CRLF — so it reads as blanket guidance covering the snapshot boundary too, where it buys a great deal.

The validator independently reproduced the underlying premise: `EditForm` seeds both `body` and `baseline.body` from the same unnormalized `fieldsFromSnapshot` (`nibForm.svelte.ts:90-100, 405-407`), but `ActiveNibView.svelte:788` (`onchange={(v) => (form.body = v)}`) writes CodeMirror's always-LF doc straight into the public `body` field, **bypassing `setBody`/`rebaseline` entirely**. After any edit that returns content to its original text, `body` (LF) permanently differs from `baseline.body` (CRLF) despite being semantically identical, so `dirty` (`nibForm.svelte.ts:192-203`) and `#matchesFields` (`429-439`) cannot reconverge.

The validator confirmed this docblock is **the only place in the codebase discussing CRLF policy at all**, and that no code near `fieldsFromSnapshot` documents the etag/round-trip trade-off. A maintainer grepping for `CRLF`/`normalize` while debugging the stuck-dirty bug (see P1) lands here, reads "it buys nothing", and is steered off the actual fix point by a false premise — while the real, live constraint that should stop them was never written down.

**Fix:** Narrow the claim to the feed-back path and record the real constraint. Replace lines 29-30 with:

```
 * Consumers must not normalize the value they feed BACK — rule 1 is easier to
 * honor as an absolute and the guard already handles it. Normalizing where a body
 * ENTERS the form (`fieldsFromSnapshot`) is a separate, open question: it would
 * keep `body` and `baseline.body` in the same encoding (today the first keystroke
 * flips `body` to LF while the baseline stays CRLF, so `dirty` and
 * `EditForm.#matchesFields` never settle), but it commits to a CRLF→LF-on-open
 * policy whose etag / round-trip blast radius is unverified. Deliberately not done.
```

---

### #3 🟡 Medium: The `EditorState.lineSeparator` facet dependency is unmanaged

| | |
|---|---|
| **File** | `web/src/lib/components/MarkdownEditor.svelte:26` (comment) and `:263` (code) |
| **Category** | knowledge-preservation / evolution-readiness |
| **Confidence** | 75 (promoted on agreement from 50) |
| **Found by** | knowledge-reviewer (COULD → Medium, 50), design-reviewer (Medium, 50) |
| **Validation** | CONFIRMED — and it settled a direct contradiction between the two finders |

**Issue:** The docblock says "CodeMirror **unconditionally** stores the doc as LF". This is config-dependent, not unconditional. `EditorState.create` splits on `configuration.staticFacet(EditorState.lineSeparator) || DefaultSplit` (`node_modules/@codemirror/state/dist/index.js:2741`), and `Text.toString()` rejoins with a hardcoded `"\n"` (`:179`, `:271`).

The two finders made **contradictory runtime claims** about this. The validator settled it with a scratch script against the installed package:

- No facet: `EditorState.create({doc:'a\r\nb'}).doc.toString() === 'a\nb'` ✅ (matches the comment's claim and the guard's regex)
- With `EditorState.lineSeparator.of('\n')`: the same call returns **`'a\r\nb'` — the CR is retained**, falsifying "unconditionally"

So knowledge-reviewer was right and design-reviewer's passing remark ("true even with a CRLF `lineSeparator` facet configured") was wrong. The invariant holds today only because `editorBasics` (`MarkdownEditor.svelte:163-187`) never sets that facet. Under it, the guard's `next` would be `'a\nb'` against a real `cur` of `'a\r\nb'` → spurious dispatch and false `dirty`: **exactly the bug this diff fixes**.

The word "unconditionally" is precisely what tells a maintainer the invariant is unbreakable — so the comment fails to catch the one edit it exists to prevent. And `lineSeparator`'s documented purpose ("allowing you to round-trip documents through the editor without normalizing line separators") is *directly* on-topic for the residual this change deliberately leaves open, which is why the validator judged the 75 anchor reasonable rather than speculative.

The tests cannot catch a facet regression either: `MarkdownEditor.test.ts:271-276` uses `crlfBody.replace(/\r\n?/g, "\n")` as its own oracle — the same assumption as the production code.

**Fix (two options, not mutually exclusive):**

1. *Comment-only (minimum)* — at line 26, replace "because CodeMirror unconditionally stores the doc as LF, so a CRLF value is indistinguishable from its own echo" with: "because CodeMirror splits CR / CRLF / LF (`DefaultSplit`) and `doc.toString()` always rejoins with LF, so the doc is LF and a CRLF value is never `===` its own echo. This depends on leaving `EditorState.lineSeparator` unset — do not set that facet, or the doc retains CR and the guard breaks."

2. *Structural (design-reviewer's, validated)* — delegate the split policy to CodeMirror instead of restating it. The validator verified `v.state.toText(raw).toString()` uses the identical facet lookup and the same hardcoded `"\n"` join, so it tracks `doc.toString()` by construction under **any** facet:
```js
const raw = initialValue;        // read first so the $effect still tracks it
const v = view;
if (!v) return;
const next = v.state.toText(raw).toString();
```

**Sub-claim not upheld:** knowledge-reviewer additionally argued "a CRLF value is indistinguishable from its own echo" is *inverted*. The validator judged this defensible as intended phrasing (describing the normalization's purpose, not a literal identity claim) and immaterial to the verdict. Not part of the fix.

---

## Pre-existing Issues

Informational only — excluded from the verdict and Summary counts. **Both P1 and P2 were reattributed here by validators against the reviewers' own claims**, on evidence that this diff *narrows* rather than creates the exposure. This is the most important structural result of the review: the adversarial-reviewer's two highest-severity findings blamed this diff for a chain that runs entirely through code it does not touch.

### P1 🟠 High: Dirty/convergence predicates compare an LF body against a CRLF baseline

| | |
|---|---|
| **File** | `web/src/lib/nibForm.svelte.ts:200` (second manifestation at `:436`) |
| **Category** | design / async — cascade |
| **Confidence** | 100 (promoted on agreement) |
| **Found by** | adversarial-reviewer (High, claimed `pre_existing: false`), design-reviewer (Medium, `pre_existing: true`) |
| **Validation** | CONFIRMED — **`pre_existing` corrected to `true`**; line corrected 199 → 200 (and 435 → 436; the cited lines pointed at the `estimate` comparisons) |

**Issue:** `BaseForm.dirty` compares `this.body !== b.body` where `baseline.body` is the CRLF-origin snapshot (`useActiveView.svelte.ts` `snapshotFromDetail`: `body: n.body ?? ""`), while `form.body` becomes the editor's LF doc as soon as `onchange` fires once. Open a CRLF nib, type one character, delete it → `body` is `"a\nb"`, `baseline.body` is `"a\r\nb"` → **`dirty` is permanently true** for semantically-unchanged content.

The validator traced the full cascade and confirmed it: permanent `dirty` routes a concurrent agent-side `nibs update` to `noteExternalChange` instead of the clean `applyExternal` (`useActiveView.svelte.ts:452`); the self-heal effect at `:476-485` requires `dirty` to go false, which it structurally cannot once diverged; so `#matchesFields` never converges either, the documented converged-save path (`nibForm.svelte.ts:421`) is dead, and the conflict banner cannot self-clear. A user who clicks **Overwrite** — the natural choice when you believe you changed nothing — writes the buffer's stale fields against the remote etag, silently reverting the agent's change.

**Why pre-existing:** the diff touches only the out-of-band sync effect, not the user-typing `onchange` path, and does not touch `nibForm.svelte.ts` at all. The validator established that the pre-diff code (`const next = initialValue;`) made a CRLF nib spuriously self-fire `onchange` with LF text **on mere mount** — `cur` is always LF-normalized by `EditorState.create`, `next` was raw CRLF, so they could never match. That was a *broader, keystroke-free* trigger for the identical mismatch. This diff eliminates the mount-time auto-dirty case.

**Fix (unchanged in substance, and deliberately comparison-only):** route both body comparisons through a `sameBody(a, b)` helper doing `a.replace(/\r\n?/g, "\n") === b.replace(/\r\n?/g, "\n")`. This changes only the comparison — never what is stored or transmitted — so it commits to no CRLF→LF-on-open policy and carries no etag blast radius. Note `dirty` can only ever be falsely *true* here, never falsely false, so the `useActiveView` F1 stale-overwrite guard (`:481`) stays intact either way.

**Recommended action:** this is out of scope for the current diff but is the highest-value follow-up surfaced by this review. Per CLAUDE.md ("findings too large to fix in-place should be deferred as nibs, not silently skipped"), file a nib.

### P2 🟡 Medium: The sync dispatch's own write-back flips the body to LF, defeating `toggleTaskLine`'s CRLF preservation

| | |
|---|---|
| **File** | `web/src/lib/components/MarkdownEditor.svelte:278` (policy statement at `:24`) |
| **Category** | design / composition |
| **Confidence** | 100 (promoted on agreement) |
| **Found by** | adversarial-reviewer (Medium, claimed `pre_existing: false`), design-reviewer (Medium, `pre_existing: true`) |
| **Validation** | CONFIRMED — **`pre_existing` corrected to `true`** |

**Issue:** The validator confirmed the mechanism against source. `get docChanged() { return !this.changes.empty; }` (`@codemirror/view/dist/index.js:1697`) is **unconditional on annotations** — `addToHistory` is consumed only by the history extension in `@codemirror/commands` to skip the undo stack, and is never checked by `updateListener`. So the sync effect's dispatch (`MarkdownEditor.svelte:278-283`) *does* fire `update.docChanged` → `onchange(update.state.doc.toString())` (`:202`) → an LF-only string → `ActiveNibView.svelte:788` writes it straight into `form.body`.

Chain: checkbox flip on a CRLF body → `toggleTaskLine` correctly preserves CRLF (`markdown.ts:189-212`; its docblock at `:194-199` was quoted accurately: *"rejoining with the CAPTURED terminators preserves the body's original endings (CRLF stays CRLF, a lone CR stays a lone CR) rather than rewriting them all to LF"*) → sync effect dispatches → `form.body` silently loses every CRLF.

The edit-vs-preview divergence is **real and reachable**: the identical `handleProseClick` checkbox markup is wired to two DOM sites — `anv-prose` in preview-only mode (`ActiveNibView.svelte:766-775`, MarkdownEditor unmounted) and `anv-preview-pane` in side-by-side mode (`:796`, editor mounted at `:786`). Same click, two different persisted bodies, decided by an unrelated view toggle. Two sibling writers of the same field hold opposite line-ending conventions, and the editor's silently wins whenever it is mounted.

**Why pre-existing:** the `updateListener` → `onchange` → LF-overwrite chain originates in the already-committed `aa51bbf`. Before this diff, the unnormalized comparison meant `cur === next` was essentially never true for a CRLF body, so the effect dispatched — and overwrote `form.body` to LF — on *every* effect re-run including initial mount with zero user interaction. This diff narrows the exposure to the checkbox-flip trigger.

**Genuine coverage blind spot:** the validator confirmed `MarkdownEditor.test.ts:74` mocks `dispatch = vi.fn()`, which never applies a transaction or re-invokes `updateListener`. No test exercises this chain. The new `vi.importActual` suite is an honest oracle for the *guard*, but not for what happens *after* a dispatch lands.

**Fix (the two finders proposed different shapes; both are viable):**
- adversarial: suppress the `onchange` write-back for the component's own sync dispatch — a `syncing` flag around `v.dispatch`, or check `update.transactions.some(tr => tr.annotation(Transaction.addToHistory) === false)`.
- design: pick ONE line-ending policy for `form.body`, state it in one place, and cross-reference it from both writer sites so the next maintainer cannot read one and conclude the opposite.

### P3 🟢 Low: `MockEditorView.dispatch` freezes `state.doc`, a latent trap for future multi-dispatch tests

| | |
|---|---|
| **File** | `web/src/lib/components/MarkdownEditor.test.ts:52-57` |
| **Category** | test-quality / mock-fidelity |
| **Confidence** | 75 |
| **Found by** | test-reviewer (Low, `pre_existing: true`) |

**Issue:** Because `dispatch = vi.fn()` never mutates `view.state`, `view.state.doc.toString()` stays at its create-time value for the mock instance's lifetime. Honest for every current test (each performs at most one doc-relevant `rerender` per view instance, so the frozen create-time doc is exactly the correct "before" state). It becomes dishonest for a future test chaining two sequential non-echo `rerender`s: real CodeMirror would apply the first transaction and update `state.doc`; the mock would still diff against the pristine mount-time doc, producing a `changes` object real CodeMirror would never need — and passing regardless.

Pre-existing: the old hand-rolled `@codemirror/state` mock had the same static-`doc` characteristic. This diff only changed the frozen doc's *value* (real LF-normalized instead of verbatim echo).

**Fix (optional):** extend the comment at `:52-57` to name the constraint explicitly — that `view.state.doc` cannot compound across dispatches, so tests should keep to a single doc-changing `rerender` per instance (or the mock must be extended to apply changes).

---

## Minor Findings

### Consistency

- `web/src/lib/components/MarkdownEditor.test.ts:3` — **Unused `EditorState` import** (quick-reviewer, broad-reviewer, test-reviewer; anchor 100 ×3). `import { EditorState, Transaction } from "@codemirror/state";` — only `Transaction` is used (line 9); `EditorState` appears solely in comment prose. Fix: `import { Transaction } from "@codemirror/state";`. Note *why* the gates missed it: `tsconfig.json` sets no `noUnusedLocals` and the repo has no ESLint config, so svelte-check and the build pass silently.
- `web/src/lib/components/MarkdownEditor.test.ts:250` — **New regression-test comments omit the `Regression:` marker** (consistency-reviewer, anchor 100). Sibling regression-guard comments consistently lead with the literal word: `TreeTable.test.ts:256, 1180, 1430, 1462`; `useHistoryNav.test.ts:71, 88`; `useScrollRestore.test.ts:159, 230, 258`; `SettingsSheet.test.ts:66`. Applies to the comments at `:250-253` and `:287-288`.
- `web/src/lib/components/MarkdownEditor.svelte:263` — **Line-ending regex duplicates `markdown.ts:137`** (consistency-reviewer, anchor 75). `markdown.ts:137` already does `body.replace(/\r\n?/g, "\n")` with its own precision-critical comment. The codebase's established mechanism for a regex needed in more than one file is an exported named constant (`TAG_REGEX` at `markdown.ts:339`, imported by `TagEditor.svelte:4,77`). The reviewer rated this only Low/75 for a good reason worth preserving: the two sites are pinned to two *different* upstream contracts that currently happen to coincide (CodeMirror's `DefaultSplit` vs. marked's lexer normalization), so a shared constant would introduce a coupling that is not strictly accurate. Weigh against finding #3's option 2, which removes the duplication from the other direction by delegating to `state.toText()`.

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| knowledge-reviewer | 3 | 2 |
| design-reviewer | 3 | 0 |
| consistency-reviewer | 2 | 2 |
| test-reviewer | 2 | 1 |
| adversarial-reviewer | 2 | 0 |
| quick-reviewer | 1 | 0 |
| broad-reviewer | 1 | 0 |
| performance-reviewer | 0 | 0 |
| typescript-reviewer | 0 | 0 |
| **Total** | **9** | |

Notes:
- **Issues Found**: total findings attributed to this agent (including shared findings). Refuted findings excluded.
- **Unique Issues**: findings reported ONLY by this agent.
- `adversarial-reviewer` submitted 3 findings; one was refuted, and both survivors were reattributed to pre-existing. Its value here was mechanism-tracing (it correctly identified the `onchange` write-back chain that P2 rests on) rather than attribution.
- `performance-reviewer` and `typescript-reviewer` returning zero is a **result, not a miss**: both verified their lanes against installed package source and Svelte's compiled output rather than reasoning by assumption. See Considered But Not Flagged.

---

## Specialist Notes

### Considered But Not Flagged (all agents)

**Refuted by validator:**
- `web/src/lib/components/MarkdownEditor.svelte:263` — *"One keystroke in a CRLF nib rewrites every line ending, producing whole-body git churn in the `.nibs/` repo"* (adversarial-reviewer, Medium, 75). **Refuted.** Two independent grounds: (1) the write-back chain runs entirely through pre-existing untouched code (`doc: initialValue` at `:193` and the `updateListener` at `:202` are verbatim in HEAD; `ActiveNibView.svelte:788` is untouched) — line 263 belongs to a separate effect that never feeds `onchange`; (2) **the trigger has no live instance**: `grep -lU $'\r' .nibs/*.md` across all 377 nib files returns **zero** CRLF files. The proposed fix (`.gitattributes` in the `.nibs` repo) is outside both the diff and the outer repo. If the operator wants the `.nibs` repo hardened against a future Windows clone with `core.autocrlf=true`, that is a reasonable standalone nib — but it is not a finding against this changeset.

**Suppressed by the confidence gate:**
- `web/src/lib/components/MarkdownEditor.test.ts:52-57` — *"Comment borders on narrating removed-code history"* (test-reviewer, Low, anchor 50). Suppressed below the 75 gate, and the dismissal is corroborated: knowledge-reviewer and broad-reviewer **each independently examined this exact comment against the CLAUDE.md rule and cleared it**, on the grounds that "A hand-rolled `toString: () => config.doc` would echo the doc back verbatim" is framed as a live forward-looking prohibition (subjunctive), not as history. test-reviewer itself rated it "defensible/debatable". Not flagged.
- `web/src/lib/components/MarkdownEditor.svelte:263` — *"Extra `.replace()` scan on the per-keystroke `$effect`"* (performance-reviewer, anchor 25). Traced and quantified rather than hand-waved: `.nibs/` holds 377 files averaging **2.6 KB** (largest 13,330 bytes); one extra O(n) regex scan costs microseconds, dwarfed by the pre-existing unchanged `doc.toString()` rope flatten and prefix/suffix scan on the same path. Additionally bounded: after the first keystroke `initialValue` is already LF, so every subsequent call hits the zero-match path. Explicitly declined to manufacture a finding on bounded input.

**Examined and cleared (notable verifications):**
- **`initialValue.replace(...)` null-safety** (typescript-reviewer) — verified rather than assumed. Compiled the exact `let { initialValue = "" } = $props()` pattern with `svelte/compiler` 5.55.0 and read `node_modules/svelte/src/internal/client/reactivity/props.js`: in runes mode the binding is a getter `prop(props, 'initialValue', 3, "")` whose fallback is **re-applied on every read**, not memoized at mount. Even an explicit `initialValue={undefined}` could never reach `.replace`. No `!`/`as` needed and none used.
- **`$effect` dependency-tracking change** (typescript-reviewer) — not a behavior change. Both before and after perform exactly one read of `initialValue` in the same relative position; `.replace` is a plain call on the already-read primitive and touches no additional reactive source.
- **`vi.mock(..., async () => vi.importActual(...))` soundness** (typescript-reviewer, design-reviewer, consistency-reviewer) — sound, not a hoisting/circularity hazard. `vi.mock` factories are hoisted above imports, so the top-level import and the component's dynamic `import()` resolve through the same intercepted specifier to one real module instance — which is why `historyExcluded` deep-matches what the component dispatches. Stylistically the passthrough is a no-op (omitting the mock or `vi.unmock` would express intent more directly), but consistency-reviewer found **no sibling precedent contradicting it**: all five sibling `importActual` uses (`App.test.ts:9`, `dispatcher.test.ts:20`, `store.test.ts:9`, `ActiveNibView.svelte.test.ts:34`, `TreeTable.test.ts:34`) override part of the module, so a zero-override passthrough is a genuinely new case, and the comment above it does real work (documents "deliberate, not forgotten").
- **Unicode line separators** (` `, ` `, `\f`, ``) — verified against `@codemirror/state/dist/index.js:608` rather than assumed: `DefaultSplit = /\r\n?|\n/` covers only CRLF/CR/LF. `/\r\n?/g` is an exact match.
- **Infinite echo loop from sync dispatch → onchange → effect re-run** (adversarial-reviewer) — terminates: after write-back `form.body` is already LF and the normalize is idempotent, so the second run hits `cur === next`.
- **Trailing-CR amplification loop via `nib.go:446`** (adversarial-reviewer) — attempted and failed to construct: disk `"a\r\n"` → `TrimSuffix` → `"a\r"` → doc `"a\n"` → guard holds → save → `Render` appends `"\n"` → `"a\r\n"`. Fixpoint. The trailing-CR bug is inert on this path.
- **`applyExternal` / clean-buffer rebaseline reintroducing CRLF** (design-reviewer) — traced every external-apply path in `useActiveView.svelte.ts` (`:455`, `:482`, `:524`); all go through `applyExternal` → `bumpBodyVersion()` → remount via `{#key form.bodyVersion}`. `EditorState.create` normalizes without firing `updateListener`, so no echo and `form.body`/`baseline.body` stay consistently CRLF. This diff's normalization is what makes the post-remount sync effect correctly no-op.
- **etag threading across the LF transition** (design-reviewer) — `save()` sends LF, rebaselines to LF, adopts the returned etag; the subscription self-echo is dropped on `remote.etag === this.#etag`. No stale-etag or lost-update path opens from the encoding change.
- **False-CLEAN `dirty` enabling the `useActiveView` F1 stale-overwrite** (`:481`) (adversarial-reviewer) — the dangerous direction is unreachable; a CRLF baseline against an LF-only editor can only make `dirty` falsely *true*.
- **Mount-time `EditorState.create({doc: initialValue})` using the raw value while the effect uses the normalized one** — harmless: CodeMirror splits the raw CRLF before the effect ever reads `doc.toString()`. Probe confirmed `guard holds at mount: true`.
- **CLAUDE.md comment/spelling compliance** — checked independently by quick, broad, knowledge, design, and consistency. No British spellings, no change-history narration, no nib/issue IDs. The `LINE-ENDING NORMALIZATION:` heading matches the file's own `ECHO-LOOP GUARD:` / `MINIMAL DIFF:` style; the new `it.each` matches sibling label/`%s` conventions (`activeView.test.ts:150-196`, `useHistoryNav.test.ts:245`, `nibForm.svelte.test.ts:390`).

---

## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `web/src/lib/components/MarkdownEditor.svelte` | knowledge-preservation | 2 | 2026-07-14 |
| `web/src/lib/nibForm.svelte.ts` | design | 2 | 2026-07-14 |
| `web/src/lib/components/MarkdownEditor.test.ts` | test-quality | 2 | 2026-07-14 |

All three recur from `CODE_REVIEW_2026-07-14_17-18-12.md`, the review of the immediately preceding commit (`aa51bbf`) that introduced this sync effect. The pattern is consistent and worth naming: this component's **comments** keep drawing findings while its **code** keeps passing. The sync effect encodes a genuinely subtle CodeMirror invariant, and each round of work on it has been correct in behavior but has over- or mis-stated the invariant in prose. Findings #2 and #3 are the same failure mode as the prior review's `knowledge-preservation / comprehension-risk` finding.
