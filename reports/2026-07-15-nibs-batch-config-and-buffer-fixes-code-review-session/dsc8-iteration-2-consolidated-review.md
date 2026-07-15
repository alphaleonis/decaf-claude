# Code Review

**Mode**: mid (explicit) · roster cap 4 — 3 gate-matched agents dropped | **Reviewers**: quick-reviewer, broad-reviewer, knowledge-reviewer, test-reviewer | **Date**: 2026-07-15
**Source**: local changes (branch `batch/config-and-buffer-fixes`) — regression check on the fix round for `.decaf/code-reviews/CODE_REVIEW_2026-07-15_15-51-26.md`
**Scope**: 2 files reviewed, +212/-4 lines (`MarkdownEditor.svelte` +5/-4 comment-only; `nibForm.svelte.test.ts` +203). `nibForm.svelte.ts` read as unchanged context.
**Spec**: none found
**Validation**: 1 confirmed (severity corrected Medium → Low), 0 refuted, 0 uncertain, 0 waived, 0 unvalidated

## Agent Selection Rationale

Mode was **explicit** (`mid4`) — not second-guessed. The changeset is docs + tests with **zero executable production lines**.

| Agent | Decision |
|---|---|
| quick-reviewer | included (always) — mid-tier |
| broad-reviewer | included (always) — mid-tier |
| knowledge-reviewer | included — the entire Critical fix IS a docblock; comment truth is the stated primary risk, and this file has a documented recurring knowledge-preservation defect class — **session model** |
| test-reviewer | included — hard gate (test files present) AND tests are 203 of 212 changed lines; guard-masking is the stated #2 risk — mid-tier |
| typescript-reviewer | **dropped — roster cap (mid4)**: hard-gate coverage traded. The TS domain IS present, but zero production TS executable lines changed (the only TS is test code, covered by test-reviewer) and `svelte-check` reports 0 errors / 0 warnings. See the ablation note below. |
| consistency-reviewer | dropped — roster cap (mid4): ranked below the 2 kept (lane overlaps `broad`) |
| adversarial-reviewer | dropped — roster cap (mid4): ranked below the 2 kept |
| design-reviewer | skipped — no API/contract/data-model/concurrency surface touched |
| security-reviewer | skipped — no security-adjacent surface |
| spec-compliance-reviewer | skipped — no spec available (hard gate) |
| data-migration / dotnet / cpp / go / rust / prior-feedback | skipped — hard gates (domain absent / not a PR) |

**Model tiering (mid)**: judgment agent (`knowledge-reviewer`) on the session model; volume agents (`quick`, `broad`, `test`) and the validator mid-tier (`sonnet`).

**Roster-cap ablation note**: no dropped agent's lane produced evidence it was missed. `typescript-reviewer`'s lane (floating promises, type escape hatches, coercion, event-loop, mutation) has no surface in a comment rewrite plus synchronous test assertions; the one `async` test was checked by test-reviewer and found to await correctly. `consistency-reviewer`'s lane was partially covered — three reviewers independently checked the two docblocks' cross-reference consistency.

---

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 0 |
| 🟡 Medium | 0 |
| 🟢 Low | 1 |
| 🔵 Minor | 1 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts reported-but-non-blocking findings. Pre-existing issues are listed separately and excluded from both.

**Verdict**: ✅ **APPROVED**

### The headline: the recurring defect class did NOT recur

The fix round's own risk — that a false replacement comment re-introduces the exact class being fixed — **did not materialize**. `MarkdownEditor.svelte` produced **zero findings**. Three reviewers (`quick`, `broad`, `knowledge`) independently verified every clause of the rewritten passage against the code and all three concluded it is true, correctly scoped, and not over-corrected. Given this file produced four knowledge-preservation findings in the two prior days, that is the material result of this review.

All three fixes land:

| Prior finding | Status |
|---|---|
| **#1 Critical** — docblock falsified | ✅ **Fixed, verified clause-by-clause by 3 reviewers.** No over-correction. |
| **#2 Medium** — guards masked | ✅ **Fixed** for the dirty-flag tests, empirically confirmed by two independent revert probes (8 failed / 52 passed, reproduced exactly). One residual instance found → finding #1 below (Low). |
| **#3 Low** — `\n\r` / `\r\r` unpinned | ✅ **Fixed, and the expectations are actually correct** — three reviewers independently re-derived the regex semantics rather than trusting the assertions. |

---

## Findings

### #1 🟢 Low: A guard assert is masked by a fix-dependent assert in the `#matchesFields converges…` test — but the guard is inert for the regression that masks it

| | |
|---|---|
| **File** | `web/src/lib/nibForm.svelte.test.ts:387` (block spans 367-390) |
| **Category** | test-quality / guard-masking |
| **Confidence** | 100 |
| **Found by** | test-reviewer (Medium) — single finder |
| **Validation** | **confirmed**, severity corrected **Medium → Low** by the validator's isolation probe |

**Issue:** The prior review's #2 was fixed for the dirty-flag tests, but the ordering pattern survives in one block that the split pass did not recognize as containing an at-risk guard:

```ts
form.title = "Theirs";
form.body = "a\nb\nc";
expect(form.externalChange).toBeNull();       // 383 — FIX-DEPENDENT, fails first under a reverted sameBody

// Derived, not one-shot: a real body difference re-surfaces it.
form.body = "a\nb\nd";
expect(form.externalChange).toEqual(remote);  // 387 — never executes when 383 fails
form.body = "a\nb\nc";
expect(form.externalChange).toBeNull();       // 389
```

Vitest aborts an `it()` at the first failing `expect`, so under a `sameBody` regression the block dies at 383 and line 387 never runs. Both the finder and the validator reproduced this exactly in isolated copies (`8 failed / 52 passed`, matching the implementer's own figure).

**Why this is Low, not Medium** — the validator went beyond the finding and ran the decisive probe the finder did not: it isolated line 387's assertion from 383 under the *same* reverted `sameBody`, and **it passed**. A real content difference (`"d"` vs `"c"`) is caught by naive `===` just as well as by the correct normalizing implementation. So for the very bug class that causes the masking, 387 was never going to add discriminating power even if reached. The complementary class it *is* uniquely suited to catch — a one-shot/latch regression of the derived `externalChange` getter — would not trip 383 at all (383 is the first resolution, where latching and deriving agree), so masking never occurs for that class either. **There is no realistic regression that this ordering renders undetectable.** The over-breadth property is separately and unconditionally covered by the standalone test at `:392-406`, confirmed passing under the revert.

This is test entanglement and misleading framing, not a coverage hole.

**Fix:** Either option is sound (the finder's and validator's assessments agree):
- **(a)** Accept the block as inherently sequential and drop the guard framing from the trailing comment, relying on `:392-406` for the over-breadth guarantee — lowest risk.
- **(b)** Keep the "derived, not one-shot" intent but decouple it from the `sameBody` path so the re-surface round trip stays provable independently:

```ts
// Derived, not one-shot: a re-diverge on a non-body field re-surfaces it too,
// independent of the body/sameBody comparison path.
form.title = "Someone else";
expect(form.externalChange).toEqual(remote);
form.title = "Theirs";
expect(form.externalChange).toBeNull();
```

---

## Pre-existing Issues

### P1 🟠 High: `setBody`'s docblock still describes `dirty` as byte-exact after the predicate changed

| | |
|---|---|
| **File** | `web/src/lib/nibForm.svelte.ts:230-231` |
| **Category** | knowledge-preservation / doc-vs-code contradiction (RULE 0) |
| **Confidence** | 100 (quotable fact — verified directly against the file) |
| **Found by** | knowledge-reviewer (SHOULD) — single finder |
| **Pre-existing** | yes — relative to *this fix round*. The comment text is untouched by this round; the **prior wave's** `dirty` change is what falsified it. |

**Issue:** The comment reads:

```
// A body change alone marks the buffer dirty via the derived `dirty` getter
// (body !== baseline). DEFAULT is in-place / non-remounting: ...
```

The `dirty` getter 15 lines above (`:223`) no longer does that — the prior wave replaced `this.body !== b.body` with `!sameBody(this.body, b.body)`. That same wave updated the sibling `#matchesFields` docblock to say "The body is compared line-ending-insensitively (sameBody)" but **missed this parenthetical**. It now asserts the pre-`sameBody` mechanism as fact.

**Why this matters beyond its severity:** this is *the same defect class as the round's Critical* — a comment claiming something the code does not do — and it is **contrary evidence worth surfacing** against the "core logic was probed by five agents and survived" framing. The logic survived; a comment describing it did not. Five prior agents missed it because it sits in `setBody`, not at the `dirty`/`sameBody` sites they were pointed at. A maintainer reading `setBody` is told body dirtiness is byte-exact — precisely the belief `sameBody` exists to refute.

**Rated High but non-blocking here** — it is out of this round's scope (`nibForm.svelte.ts` is not a reviewed file) and pre-existing relative to the delta, so per the consolidation rules it is excluded from the verdict. It is a one-line fix that belongs with the next touch of this file.

**Fix:** At `web/src/lib/nibForm.svelte.ts:231`, replace `(body !== baseline)` with `(body vs baseline, compared line-ending-insensitively via sameBody)`.

---

## Minor Findings

### Consistency

- `web/src/lib/nibForm.svelte.test.ts:308` — `it("an empty body compares clean")` is tautological: `""` vs `""` is byte-equal before *and* after normalization, so it passes identically under the real `sameBody`, the reverted `a === b`, or almost any implementation. Confirmed by probe: not among the 8 failures under the revert, i.e. it cannot fail from a `sameBody` regression. A legitimate no-crash-on-empty smoke check, but it exercises no line-ending logic. (test-reviewer, anchor 50 — retained per Step 5.5: `broad-reviewer` dismissed it as "harmless", `test-reviewer` flagged it.) Optional: fold into the adjacent `"a terminator-only CRLF body equals a lone LF"` / `"an empty body gaining a newline IS dirty"` tests, which already cover the meaningful empty-body boundary.

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| quick-reviewer | 0 | 0 |
| broad-reviewer | 0 | 0 |
| knowledge-reviewer | 1 | 1 |
| test-reviewer | 2 | 2 |
| **Total** | **3** | |

`quick-reviewer` and `broad-reviewer` found 0 — but **found 0 ≠ did nothing**. Both independently verified all four clauses of the rewritten docblock against the code, hand-derived the regex against every new test case (quick: 15/15; broad: 13 fixture pairs in a standalone Node probe), confirmed the `:277` compound's guard ordering, and confirmed diff scope and file integrity. Their agreement with `knowledge-reviewer` on the passage's truth is the corroboration behind this review's headline.

---

## Specialist Notes

### Comment-truth audit — the four clauses (quick + broad + knowledge, independently concurring)

| Clause | Verdict |
|---|---|
| "the first keystroke flips `body` to LF while the baseline stays CRLF" | **TRUE.** `onchange` emits `update.state.doc.toString()` (`MarkdownEditor.svelte:210`); CodeMirror line-splits the CRLF `initialValue` at `EditorState.create` and rejoins with `\n`, so the doc is LF from init. `ActiveNibView.svelte:787` binds `initialValue={form.body}` and assigns `onchange`'s value back. Baseline is set once via `rebaseline(init)` in the `EditForm` constructor; nothing rebaselines on typing. |
| "`sameBody` absorbs that at the comparison sites, so `dirty` and `EditForm.#matchesFields` settle regardless" | **TRUE for BOTH, on every path.** Grep confirms `sameBody` has exactly two call sites: `dirty` (`:223`) and `#matchesFields` (`:460`). Every suggested counterexample was checked and none holds: `setBody` assigns only, never compares; `discard`/`bumpBodyVersion`/`applyExternal` do no body equality; `CreateForm.afterTypeChange:352` (`this.body !== this.#lastTemplate`) compares against a **template**, is create-mode only, and CRLF cannot reach it (templates are LF, create bodies only change via the LF editor). `CreateForm` inherits `dirty` with no override. The claim is also **scoped** — it names exactly two predicates rather than claiming universality. |
| "commits to a CRLF→LF-on-open policy whose etag / round-trip blast radius is unverified. Deliberately not done." | **Premise intact.** `fieldsFromSnapshot` still assigns `body: s.body` unnormalized. `sameBody` is comparison-side-only and changes nothing about entry. The parenthetical honestly *deflates* the upside (normalizing no longer buys settling), which is the correct post-`sameBody` state, and "Deliberately not done" still follows. |
| **Over-correction check** | **No over-correction.** The passage scopes its claim to "`dirty` and `#matchesFields` settle" and never discusses the write path. `sameBody`'s own docblock (`:150-156`) owns and states the accepted consequence (an LF body persisting over a CRLF remote), and the new SAVES test (`:408-427`) pins exactly that (`calls[0].input.body` is the LF string). A maintainer evaluating the passage's actual question — "should `fieldsFromSnapshot` normalize?" — reaches the correct conclusion from the passage alone; knowing the LF-persist consequence would not change that answer, since entry-normalization would persist LF too. |
| **Is "settle" precise?** | **Yes** — the same sentence states the outcome explicitly: `body` → LF, baseline stays CRLF. It does not paper over which encoding wins. |
| **Cross-reference pair** | **Accurate in both directions, complementary not circular.** `sameBody`'s "(see the MarkdownEditor docblock)" points at text genuinely holding the CRLF→LF-on-open blast-radius reasoning; MarkdownEditor's "`nibForm.svelte.ts`'s `sameBody`" points at a function that genuinely exists and genuinely absorbs at those sites. Each side holds the half the other lacks. |

Also verified: the new test docblock's assertion that **"the backend does not normalize"** is TRUE — `internal/nib/nib.go:446` is `strings.TrimSuffix(string(body), "\n")`, and grep finds no CR/CRLF `ReplaceAll` in the file.

### The `:277` compound — the implementer's judgment is sound (4/4 concurrence)

`it("a CRLF pair collapses to ONE newline, not two")` was deliberately left compound. **All four reviewers independently verified the reasoning and all four found it correct**, two of them empirically: the guard (`f1`, `expect(f1.dirty).toBe(true)` — genuinely different content) runs **first** and passes under the reverted predicate; only the fix-dependent `f2` fails. Since JS aborts an `it()` at the first failing `expect`, the guard is never masked. The implementer's call was right.

Similarly cleared: the first test (`:243`) — its leading `expect(form.dirty).toBe(false)` is **not** fix-dependent (body is byte-identical to baseline at that point), so it masks nothing; only the final assert (`:253`) fails under revert. And `"a body with no line terminator at all"` (`:358`) opens with a `dirty === false` assert, but that case contains no CR — byte-exact under either predicate, so it cannot mask.

### The `\n\r` / `\r\r` expectations are correct, not merely asserted

Three reviewers independently re-derived `/\r\n?/g` semantics (the `?` binds to the trailing `\n` only) rather than trusting the assertions — the specific false-positive risk being a test that asserts the wrong thing but passes because the implementation shares the same misunderstanding. All derivations agree with all assertions:

| Input | Normalizes to | Breaks |
|---|---|---|
| `"a\r\nb"` | `"a\nb"` | 1 |
| `"a\r\rb"` | `"a\n\nb"` | 2 |
| `"a\n\rb"` | `"a\n\nb"` | 2 (an `\n` plus an independent lone-`\r` break) |
| `"a\r\n\r\nb"` | `"a\n\nb"` | 2 |
| `"\r\n"` | `"\n"` | 1 |

The test file's own gloss — "`/\r\n?/g` binds `?` to the TRAILING \n only" — is precisely correct. `knowledge-reviewer` re-derived all 9 cases in a scratch probe (9/9 match); `broad-reviewer` reproduced 13 fixture pairs standalone in Node; `quick-reviewer` hand-verified all 15.

### Considered But Not Flagged (all agents)

**quick-reviewer** — several new `it()`s still carry 2-3 sequential `expect`s; assessed as one coherent state-machine narrative per test, not maskable independent purposes (note: `test-reviewer` flagged one specific instance of this, which is finding #1 — the specialist's flag was retained over the generalist's dismissal per Step 5.5). No change-history narration, no nib IDs, no British spellings introduced. `git diff --stat` confirms no hidden executable changes in the `MarkdownEditor.svelte` hunk.

**broad-reviewer** — `"an empty body compares clean"` (`:308`) and `"a body with no line terminator at all"` (`:358`) assert conditions that hold under strict equality too; dismissed as harmless. **`:308` was promoted to Minor per Step 5.5** (test-reviewer flagged it). `:358` not promoted — no agent flagged it, and unlike `:308` it does carry a real fix-independent guard (`"single line!"` → dirty).

**knowledge-reviewer** — checked every suggested counterexample to the "settle regardless" claim (`setBody`, `discard`, `bumpBodyVersion`, `applyExternal`, `CreateForm.afterTypeChange`) and found none refutes it. The "a naive `/\r/g`" note in the test comments is a hypothetical-wrong-implementation rationale (forward-relevant), **not** change-history narration. The dropped "today" is a neutral edit, and `now`/`currently` are established as acceptable in this codebase regardless.

**test-reviewer** — no silent failures (no `async void`, no un-awaited assertions, no empty catches), no test-isolation violations, no flaky time/random patterns, no scope creep. The async save test (`:408`) properly awaits and all five post-await assertions are meaningful.

**Suppressed by the confidence gate**: 0 findings. (Finding #2 at anchor 50 was retained via the Step 5.5 cross-reference rule and routed to Minor per the false-positive-test rule.)

---

## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `web/src/lib/nibForm.svelte.test.ts` | test-quality | 2 | 2026-07-15 |

Prior `#2` (`:292`, `:305`, `:331` — "guard assertions sit after fix-dependent assertions") → current `#1` (`:387`). The fix addressed the three flagged instances; a fourth surfaced in a block the split pass did not recognize as containing a guard. The validator's isolation probe establishes this instance is materially inert, so the recurrence is one of pattern, not of risk.

**Class-level note (not a file-path match, recorded in prose):** `MarkdownEditor.svelte` carried a knowledge-preservation / doc-vs-code finding in **four** prior reviews — `2026-07-14_17-18-12` #3, `2026-07-14_20-12-33` #1 and #2, and `2026-07-15_15-51-26` #1 (Critical). **This round it produced none.** The class did, however, appear once more in the adjacent `nibForm.svelte.ts` (P1) — a file whose comments were not in any review's scope. Both data points support treating "comments in this cluster overclaim" as a standing hazard rather than a solved one, and suggest the next review of this cluster should scope `nibForm.svelte.ts`'s comments explicitly.

---

## Session Metrics (--report)

**Wave timing**: dispatched 16:04:00 → last reviewer returned ~16:10:18 → consolidated ~16:10:30 → validation done ~16:15:15 → file written 16:20:06

| Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings submitted |
|-------|------|-----------|--------|-----------|----------|--------------------|
| quick-reviewer | reviewer | sonnet (mid) | 84,468 | 9 | 168,168 ms | 0 |
| broad-reviewer | reviewer | sonnet (mid) | 94,713 | 14 | 278,822 ms | 0 |
| knowledge-reviewer | reviewer | session model (opus) | 92,443 | 12 | 251,088 ms | 1 |
| test-reviewer | reviewer | sonnet (mid) | 114,954 | 11 | 378,420 ms | 2 |
| finding-validator (#1) | validator | sonnet (mid) | 81,015 | 17 | 275,300 ms | 1 verdict (confirmed, severity corrected) |

**Total reported subagent tokens**: 467,593. *[Unverified] whether a subagent's reported token figure includes its own children — carry this caveat wherever these figures are summed.*

Wave timing figures other than the dispatch timestamp (16:03:59, measured) and the file-write timestamp (16:20:06, measured) are **[Inference]** derived by adding harness-reported durations to the dispatch time; intermediate return times were not directly measured.

**Pre-flight gates**: ran once for the wave and shared to every reviewer.
- `cd web && npx vitest run --reporter=agent` → **PASS**, 60 files / 1237 tests passed (25.19s)
- `cd web && npx svelte-check` → **PASS**, 0 errors / 0 warnings

**Anomalies**: **none.** Specifically — and notably, given the two prior waves in this session were both corrupted by a reviewer applying an inline revert probe to the live working tree while siblings read it in parallel — the mandatory probe protocol held completely:
- All 5 agents independently verified the SHA256 integrity baseline on arrival; all reported a match.
- Both agents that ran revert probes (`test-reviewer`, `finding-validator`) did so in isolated copies under the scratchpad (`testprobe/`, `validator/`) with symlinked `node_modules`, never touching the repo.
- Post-wave re-check: all three file hashes byte-identical to the pre-wave baseline; `git diff --stat` unchanged at 3 files / +235 / -7.
- Zero reviewers reported the changeset as absent, reverted, or flapping. No dispatch retries, no unusable returns, no injected-content flags.
