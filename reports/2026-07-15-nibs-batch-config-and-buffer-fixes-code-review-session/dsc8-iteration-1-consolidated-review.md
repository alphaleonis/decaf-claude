# Code Review

**Mode**: mid (explicit) | **Reviewers**: quick, broad, knowledge, consistency, design, test, typescript, spec-compliance, adversarial, performance (10) | **Date**: 2026-07-15
**Source**: local changes — branch `batch/config-and-buffer-fixes` (uncommitted)
**Scope**: 2 files changed, +178/-3 lines
**Spec**: `.nibs/nibs-dsc8--dirtyconvergence-predicates-compare-an-lf-body-aga.md` (inferred — session context; spec-compliance findings capped at Medium)
**Validation**: 3 confirmed, 6 refuted, 0 uncertain, 1 corroborated ×2 (not selected)

## Agent Selection Rationale

Mode was **explicit** (`mid`), so Step 2a.5 selection was skipped. Roster = floor + every agent whose dispatch gate matched. No roster cap given.

- **quick-reviewer** — always (review floor) · mid-tier
- **broad-reviewer** — always (review floor) · mid-tier
- **knowledge-reviewer** — substantive change; the new `sameBody` docblock encodes a deliberate, contested decision · session model
- **consistency-reviewer** — substantive change with a direct sibling (`sameTags`) the new helper claims to follow · mid-tier
- **design-reviewer** — `dirty` is a public predicate consumed across a module boundary and its semantics change · session model
- **test-reviewer** — test files present (hard gate) · mid-tier
- **typescript-reviewer** — TypeScript files present (hard gate) · mid-tier
- **spec-compliance-reviewer** — a spec is available (hard gate): `nibs-dsc8` · session model
- **adversarial-reviewer** — 178 changed executable lines (≥50); the change gates a real write path · session model
- **performance-reviewer** — `sameBody` allocates two full body copies per `dirty` evaluation on a reactive path · mid-tier
- **security-reviewer**: skipped — no auth/crypto/network/file-I/O/serialization/secrets/privilege surface; `/\r\n?/g` has no backtracking risk
- **data-migration-reviewer**: skipped — no migration artifacts in the diff (hard gate)
- **prior-feedback-reviewer**: skipped — local changes, not a PR (hard gate)
- **dotnet / cpp / go / rust-reviewer**: skipped — no such files in the changeset (hard gate)

**Model tiering (mid policy)**: judgment agents (knowledge, design, spec-compliance, adversarial) inherited the session model; volume agents (quick, broad, consistency, test, typescript, performance) and all 9 validators ran mid-tier (`sonnet`).

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 1 |
| 🟠 High | 0 |
| 🟡 Medium | 1 |
| 🟢 Low | 2 |
| 🔵 Minor | 0 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. Pre-existing issues and Minor findings are excluded from both.

**Verdict**: ❌ NEEDS_CHANGES

All four surviving findings are **documentation- and test-quality defects with one-line-to-one-block fixes**. None is a runtime defect: the fix's core logic — `sameBody`, its two call sites, and the whole `dirty` cascade — was probed hard by five agents and survived intact. See *Assurance delivered* below for what was actively cleared.

---

## Findings

### #1 🔴 Critical: The change falsifies the `MarkdownEditor` docblock it points the reader at

| | |
|---|---|
| **File** | `web/src/lib/components/MarkdownEditor.svelte:34-36` (falsified by `web/src/lib/nibForm.svelte.ts:153`) |
| **Category** | knowledge-preservation / doc-vs-code contradiction (RULE 0) |
| **Confidence** | 100 |
| **Found by** | knowledge-reviewer (MUST → Critical) |
| **Validation** | ✅ confirmed |

**Issue:** The new `sameBody` docblock delegates its central rationale with "(see the MarkdownEditor docblock)". That docblock currently reads:

> Normalizing where a body ENTERS the form (`fieldsFromSnapshot`) is a separate, open question: it would keep `body` and `baseline.body` in the same encoding **(today the first keystroke flips `body` to LF while the baseline stays CRLF, so `dirty` and `EditForm.#matchesFields` never settle)**, but it commits to a CRLF→LF-on-open policy whose etag / round-trip blast radius is unverified. Deliberately not done.

The parenthetical's premise stays true — the encodings *do* still diverge, and `sameBody` does not change that. But its stated consequent is now **false**: `dirty` and `#matchesFields` are exactly what `sameBody` makes settle, and the diff's own tests pin it (`"a CRLF baseline vs the editor's LF doc is NOT dirty"`, `"#matchesFields converges for a CRLF-origin body"`). The docblock describes the just-fixed bug as live.

The validator confirmed `MarkdownEditor.svelte` is untouched by this changeset, so the text is pre-existing — but its *falsity* is created by this diff, and the new `sameBody` docblock makes it load-bearing by name.

**Why Critical rather than a nit:** this is the third recurring `MarkdownEditor.svelte` knowledge-preservation finding (see Recurring Findings), the repo has two commits from the last two days auditing exactly this defect class (`5d7258d`, `fad6f7b`), and the failure mode is concrete: a maintainer follows the pointer, reads that `dirty`/`#matchesFields` never settle, and either (a) "fixes" the fixed bug by normalizing in `fieldsFromSnapshot` — adopting the very CRLF→LF-on-open policy both docblocks say is deliberately not done — or (b) distrusts `sameBody` as ineffective and reverts it, restoring the permanently-dirty CRLF buffer.

**Fix:** Replace the parenthetical at `:34-36`, leaving the surrounding (still-true) policy sentence intact:

```
     * ENTERS the form (`fieldsFromSnapshot`) is a separate, open question: it would
     * keep `body` and `baseline.body` in the same encoding (the first keystroke flips
     * `body` to LF while the baseline stays CRLF; `nibForm.svelte.ts`'s `sameBody`
     * absorbs that at the comparison sites, so `dirty` and `EditForm.#matchesFields`
     * settle regardless), but it commits to a CRLF→LF-on-open policy whose etag /
     * round-trip blast radius is unverified. Deliberately not done.
```

---

### #2 🟡 Medium: Guard assertions sit *after* fix-dependent assertions, so they never execute under the pre-fix predicate

| | |
|---|---|
| **File** | `web/src/lib/nibForm.svelte.test.ts:292` (also `:305`, `:331`) |
| **Category** | test-quality / false-positive-risk |
| **Confidence** | 100 |
| **Found by** | test-reviewer |
| **Validation** | ✅ confirmed (independently re-traced; all line numbers verified exact) |

**Issue:** This finding directly answers the central claim put to this review — that the over-breadth guard tests *"passed pre-fix, so they anchor rather than ride the fix."* **For one of the three named claims, that is false as written.**

Vitest's `expect` throws and aborts the rest of the `it()` body on first failure. Three of the nine new tests place a **fix-dependent** assertion *before* the assertion meant to prove the guard holds independently of the fix — so under the byte-exact pre-fix predicate the earlier one throws and the guard assertion **never runs**:

| Test | Throws pre-fix at | Guard assertion that never runs |
|---|---|---|
| `"a trailing terminator is content…"` (`:292`) | `:297` — `"a\r\n"` vs `"a\n"` → not dirty | `:302` — **`"a\r\n"` vs `"a"` → dirty** ← *one of the three claimed anchors* |
| `"an empty body compares clean…"` (`:305`) | `:315` — `"\r\n"` vs `"\n"` → not dirty | `:319` — `""` vs `"\n"` → dirty |
| `"#matchesFields converges…"` (`:331`) | `:347` — `externalChange` → null | `:350-353` — "a real body difference re-surfaces it" |

The other two named claims hold up: `"a\r\nb"` vs `"a\n\nb"` → dirty (`:284`) genuinely does run first and pass pre-fix — that test (`:277-290`) is correctly ordered and is the model for the fix — and the standalone `"genuinely different content IS dirty"` (`:256`) passes pre-fix as claimed.

**Consequence:** (a) the three tests cannot be cited as evidence their later assertions anchor over-breadth — they were never exercised in that state; (b) if `sameBody` later regresses breaking only the earlier property, the failure output will never reveal whether the over-breadth property also broke.

**Fix:** Split each compound test into single-purpose `it()` blocks so every named assertion is independently exercised:

```typescript
it("a genuine CRLF terminator equals a lone LF terminator", () => {
  const { deps } = makeMutations();
  const form = editNibForm(deps, seed({ body: "a\r\n" }));
  form.body = "a\n";
  expect(form.dirty).toBe(false);
});

it("dropping the terminator entirely is a real edit, not masked by normalization", () => {
  const { deps } = makeMutations();
  const form = editNibForm(deps, seed({ body: "a\r\n" }));
  form.body = "a";
  expect(form.dirty).toBe(true);
});
```

Apply the same split to `:305` (three independent cases) and `:331` (converge vs. re-diverge).

---

### #3 🟢 Low: `\n\r` (reversed) and `\r\r` boundary inputs are unpinned

| | |
|---|---|
| **File** | `web/src/lib/nibForm.svelte.test.ts:242-376` |
| **Category** | test-coverage |
| **Confidence** | 75 |
| **Found by** | test-reviewer (Low), broad-reviewer (Low) — corroborated ×2, not selected for validation |

**Issue:** Both reviewers independently verified — by direct execution against the regex, outside the test suite — that the current behavior on these inputs is **correct**:

```
"a\r\rb" vs "a\n\nb"  -> equal      (each \r is its own break)
"a\n\rb" vs "a\n\nb"  -> equal      (\n and \r each count separately)
"a\r\rb" vs "a\nb"    -> not equal  (break count still distinguished)
```

But no test pins them. The closest is the mixed-endings case (`"a\r\nb\rc\nd"`), which contains no bare CR-run and no reversed pair. This is a coverage gap, not a bug — flagged because a future "simplification" of the regex to `/\r?\n|\r/g` or `/\r|\n/g` would silently mishandle exactly these corners with no red test.

**Fix:**
```typescript
it("reversed and doubled CR sequences each count as their own break", () => {
  const { deps } = makeMutations();

  const f1 = editNibForm(deps, seed({ body: "a\r\rb" }));
  f1.body = "a\n\nb";
  expect(f1.dirty).toBe(false);

  const f2 = editNibForm(deps, seed({ body: "a\n\rb" }));
  f2.body = "a\n\nb";
  expect(f2.dirty).toBe(false);
});
```

---

### #4 🟢 Low: The work item's "Proposed fix" rationale overclaims — "never what is stored or transmitted" is false

| | |
|---|---|
| **File** | `.nibs/nibs-dsc8--dirtyconvergence-predicates-compare-an-lf-body-aga.md:30` |
| **Category** | spec-deviation / doc-vs-code contradiction |
| **Confidence** | 75 |
| **Found by** | spec-compliance-reviewer (capped at Medium by inferred-spec provenance; filed Low) |
| **Validation** | ✅ confirmed (line corrected from section-level to `:30`) |

**Issue:** `nibs-dsc8`'s "Proposed fix" section asserts:

> This changes only the comparison — **never what is stored or transmitted** — so it commits to no CRLF->LF-on-open policy and carries no etag blast radius.

Decomposed, two of three clauses hold and one is false:

1. *"changes only the comparison — never what is stored or transmitted"* — **FALSE.** `#matchesFields` is not a pure observer; it is a control-flow gate. The validator traced `EditForm.save()` (`nibForm.svelte.ts:481-580`): when `#matchesFields(external)` is true (`:497`), `save()` falls through to a **real write** with `ifMatch = external.etag` (`:516`) and `input.body = this.body` — the LF buffer. Pre-fix, a CRLF-origin buffer could never converge, so this path returned `{conflict}` and never wrote. The diff's own test pins the new behavior (`calls[0].input.body === "a\nb\nc"` over an `"a\r\nb\r\nc"` remote).
2. *"commits to no CRLF->LF-on-open policy"* — **TRUE.** Nothing normalizes at entry.
3. *"carries no etag blast radius"* — **TRUE.** Etag threading untouched.

**This is a spec defect, not an implementation deviation.** The prescribed mechanism is exactly what was built; the *justification* is what is wrong — it sells the approach as consequence-free, and it isn't. The implementer's own `sameBody` docblock is the more accurate document and states the consequence plainly. This matters because that "no blast radius" claim is what would let a future reader approve the approach without noticing it authorizes a write.

**Fix:** Amend `nibs-dsc8`'s "Proposed fix" section — drop the "never what is stored or transmitted" clause and record the accepted consequence the docblock already states. Keep clauses 2 and 3. **No code change.** (`.nibs/` is a separate git repo — commit there separately.)

---

## Assurance delivered (found 0 ≠ did nothing)

Five agents returned zero findings. What they actively cleared is the substance of this review:

- **Is `sameBody` over-broad?** — **No.** Probed independently by quick, broad, consistency, typescript, adversarial and design across every boundary named in the brief (lone `\r`, mixed endings, CRLF-pair-vs-two-breaks, empty body, no trailing terminator, `\n\r` reversed, `\r\r`, terminator-only bodies). No input was found where semantically-different content collapses to equal. The `"a\r\nb"` vs `"a\n\nb"` case — the one a naive `/\r/g` would get wrong — is correct and pinned.
- **Can `dirty` be falsely FALSE?** (the brief's headline challenge) — **No**, closed on two verified points by adversarial-reviewer: CodeMirror's doc is always LF and paste normalizes, so a user cannot *author* a line-ending-only difference; and `toggleTaskLine` — the only real `setBody` caller — provably preserves original terminators (`markdown.ts:194-200`, terminator-capturing split/rejoin). A line-ending-only divergence therefore always means the user's net edit is zero. The stale-overwrite guard holds.
- **Every `dirty` consumer** — traced independently by broad, design and adversarial. All six cited sites verified as improvements. **`:374 noteMissing` specifically is not data loss**: `CLOSE` requires `dirty === false`, which (per the above) means no user work exists; a *never-touched* CRLF nib already took `CLOSE`, so the change makes typed-then-undone consistent with never-touched. The `:542-551` self-heal effect **terminates** (`applyExternal` nulls `#externalChange`; the effect re-runs to a no-op) — no ping-pong.
- **Comment truth of the `sameBody` docblock** — every factual claim verified against primary sources by quick, broad, knowledge and consistency: the "CRLF pair counts as ONE break" claim (true — `?` binds only the trailing `\n`), "the backend does not normalize" (true — `nib.go:446` is an LF-only `TrimSuffix`, zero `\r` handling in Go source), the `ActiveNibView.svelte:788` bypass (true), the MarkdownEditor cross-reference (exists), and the write-path claim (true, and pinned by a test). **The new docblock does not overclaim.** The defect is in the *referenced* docblock (#1), not this one.
- **The regex is the right one** — design-reviewer verified `/\r\n?/g` is byte-identical to CodeMirror 6's own `DefaultSplit = /\r\n?|\n/` (`node_modules/@codemirror/state/dist/index.js:608`) and to marked's normalization (`markdown.ts:137`). Three-way alignment means the predicate cannot disagree with the encoding the editor actually emits.
- **CLAUDE.md conventions** — American English, no change-history narration, no nib IDs in code comments: clean per quick, consistency, knowledge, design and adversarial (and see the refuted #4 below for the one contested call).

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| knowledge-reviewer | 1 | 1 |
| test-reviewer | 2 | 1 |
| spec-compliance-reviewer | 1 | 1 |
| broad-reviewer | 1 | 0 |
| quick-reviewer | 0 | 0 |
| consistency-reviewer | 0 | 0 |
| design-reviewer | 0 | 0 |
| typescript-reviewer | 0 | 0 |
| adversarial-reviewer | 0 | 0 |
| performance-reviewer | 0 | 0 |
| **Total** | **4** | |

Notes:
- **Issues Found**: findings surviving validation attributed to this agent (shared findings count for each finder). Refuted findings excluded.
- **Unique Issues**: findings reported ONLY by this agent.
- Refuted-finding submitters: performance-reviewer (1), typescript-reviewer (1), spec-compliance-reviewer (2 of its 3), knowledge-reviewer (1 of its 2), broad-reviewer (1 of its 2).

---

## Specialist Notes

### Requirement Coverage Matrix (spec-compliance-reviewer)

⚠️ **The matrix below is superseded.** It was produced against a transient no-op `sameBody` created by a sibling reviewer's probe (see Anomalies). Re-derived against the actual tree:

| Req | Description | Type | Status | Evidence |
|-----|-------------|------|--------|----------|
| R1 | `dirty` returns false for a CRLF-origin body semantically unchanged | functional | **Met** | `sameBody` at `:158-160`; test `"a CRLF baseline vs the editor's LF doc is NOT dirty"` passes |
| R2 | `EditForm.#matchesFields` converges for a CRLF-origin body | functional | **Met** | `:459`; test `"#matchesFields converges for a CRLF-origin body"` passes |
| R3 | Test: open CRLF nib, type a char, delete it → not dirty | test | **Met** | `nibForm.svelte.test.ts:239-251` |
| R4 | Test: conflict banner self-clears for a CRLF nib once content matches remote | test | **Met** | `:331-354` (see finding #2 — assertions beyond `:347` are order-masked) |
| R5 | `task test` green | constraint | **Met** | Pre-flight: 60 files / 1231 web tests pass; svelte-check 0/0. Go untouched. |

The reviewer's Finding 3 (the spec's rationale overclaims) is **independent of the probe artifact** and survives as finding #4 above — confirmed by its own validator.

### Considered But Not Flagged (all agents)

**Refuted by validators (6):**
- **`sameBody` is a no-op stub / the pre-flight gate is false** (spec-compliance-reviewer, Critical-in-effect ×2; typescript-reviewer, Critical) — *refuted by two independent validators*: the file contains the normalizing implementation, `git diff HEAD --stat` matches the original +178/-3, and 54/54 tests pass. An artifact of a sibling reviewer's probe (see Anomalies). Both validators noted the reviewers' *reasoning was sound given what they observed* — this is a process hazard, not reviewer error.
- **`sameBody` lacks a reference-equality fast path; `dirty` re-runs it 7× per keystroke** (performance-reviewer, Medium/75) — **refuted**. The `dirty` getter is a `||` chain that checks title/status/type/priority/estimate **before** `!sameBody(...)`; `||` short-circuits, so a title keystroke returns before `sameBody` is ever reached. The flagship "16 ms frame budget on every title keystroke" scenario is impossible. (`#matchesFields` has the same protection via its `&&` chain.) The validator reproduced the raw benchmark within an order of magnitude — the arithmetic was sound, the *triggering condition* was not. Residual real trigger: a tag edit while all five earlier fields match baseline — a discrete click, not a hot path. The suggested `a === b ||` fast path remains harmless and correct if ever wanted.
- **"now takes the write path" narrates change history** (broad-reviewer, Medium/75; dissented by knowledge-reviewer) — **refuted**, dissent upheld. Decisive evidence: `fad6f7b`'s own diff strips explicit retrospection ("Prior to the fix…", "the old grouped shape", "originally named") while deliberately leaving `now`/`currently`/`once` soft-temporal markers — including `sameTags`' own "mattered once this fed #matchesFields" (`:129-130`) and "currently unreachable from the UI anyway" (`:507`), both untouched by audits that edited other comments *in this same file*. The project has drawn the line where the dissent says it does.
- **`sameBody`'s do-not-share-with-`markdown.ts` contract is unrecorded** (knowledge-reviewer, MUST/75) — **refuted**. The "only coincidentally agree" premise is empirically false: CodeMirror's own `DefaultSplit = /\r\n?|\n/` means marked, CodeMirror and `sameBody` converge on the same universal newline convention *structurally*, not by luck. Both docblocks already state their own pin. The failure chain (a DRY pass merges them without reading either explanatory docblock, **and** a decades-stable convention later diverges) is speculative and fails knowledge-reviewer's own pre-flag gates.
- **`NibFormFields.dirty`'s contract is undocumented while its guarantee changed** (promoted by the orchestrator from design-reviewer's dismissed list under Step 5.5) — **refuted**. The knowledge is preserved: the diff's own 19-line `sameBody` docblock — which both `dirty` and `#matchesFields` delegate to — states the CRLF/LF divergence, that `dirty === false` no longer implies byte-equality, and the write consequence. The validator re-grepped all 15 non-test `.dirty` call sites and confirmed each treats it as a pure boolean gate with no byte-exact reliance. Both design- and knowledge-reviewer independently declining to file it was sound judgment; the promotion was over-cautious.

**Dismissed with reasoning found sound (not promoted):**
- **`CreateForm.afterTypeChange:352` still uses byte-exact `this.body !== this.#lastTemplate`** — dismissed by four agents independently with converging evidence: create bodies originate only from `bodyTemplates.ts` (verified 0 CR bytes) and `.gitattributes` (`* text=auto eol=lf`) guarantees LF templates on every platform, so CRLF cannot reach that compare. Worth noting only if templates ever gain CRLF content via a future import/paste path.
- **Go round-trip asymmetry** (adversarial-reviewer) — `nib.go:446`'s `TrimSuffix(body, "\n")` vs `Render`'s `HasSuffix(b.Body, "\n")` means a body ending `"...b\r\n"` parses back as `"...b\r"`, and a trailing `\n` is eaten per round-trip. **Pre-existing and orthogonal**; `sameBody` handles the first correctly and does not mask the second. Slightly qualifies the brief's "the backend does not normalize" premise without contradicting it (that claim is about line endings, not terminator trimming). Not caused or worsened by this diff.
- **Whole-file `.nibs/` git diffs** — the accepted LF-over-CRLF write flips every line of a CRLF nib file on a one-character edit. Cosmetic downstream consequence of the explicitly-accepted decision.
- **Unicode line separators (U+2028/U+2029, NEL U+0085)** — not matched by `/\r\n?/g`, but CodeMirror never emits them; no realistic path. Lone surrogates: `\r`/`\n` are single BMP code units, `.replace()` cannot split a pair.
- **`applyExternal` remounts the editor under a live cursor in the newly-clean case** (design-reviewer, anchor 25) — not a new class; already happens for any clean buffer.
- **`sameBody(string, string)` vs `sameTags(readonly string[], ...)` signature drift** — not drift: `readonly` is a container-mutation marker; strings are immutable primitives with no analogous qualifier.
- **Null bodies reaching `sameBody`** — all three `NibSnapshot.body` construction sites guard with `?? ""` (`App.svelte:127`, `nibChange.ts:69`, `useActiveView.svelte.ts:563`).

No findings were suppressed by the confidence gate.

---

## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `web/src/lib/components/MarkdownEditor.svelte` | knowledge-preservation | 3 | 2026-07-14 |

Finding #1 is the **third** knowledge-preservation defect logged against this file's docblocks in two days. The file's comment block is dense, load-bearing (it defines the ECHO-LOOP CONTRACT other modules cite by name) and demonstrably drifts as the code around it changes. Worth considering a follow-up nib: either tighten the contract text so it states invariants rather than current-bug status, or add it to a checklist for changes touching the editor/form boundary.

Related prior context (not a recurrence): a 2026-07-14 review already flagged the `markdown.ts:137` line-ending regex duplication at `MarkdownEditor.svelte:263` (consistency-reviewer, Low/75), reaching the *same* conclusion this review's validator did — the two sites are pinned to different upstream contracts, so a shared constant would introduce an inaccurate coupling. That prior reasoning independently corroborates refuting finding #5 here.

---

## Session Metrics (--report)

**Wave timing**: pre-flight gates 15:28:58 → 15:35 (approx.) · review wave dispatched **not recorded** → last reviewer returned **not recorded** (longest reviewer duration 483,069 ms) · consolidated **not recorded** · validation wave dispatched **not recorded** → last validator returned **not recorded** (longest validator duration 266,281 ms) · verification test run 15:43:57 · file written 15:51:26.
*[Unverified] Per-agent durations below are harness-reported and exact; the wave boundary timestamps were not captured at dispatch time and are recorded as missing rather than reconstructed.*

| Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings submitted |
|-------|------|-----------|--------|-----------|----------|--------------------|
| quick-reviewer | reviewer | sonnet (mid) | 93,420 | 9 | 195,374 ms | 0 |
| broad-reviewer | reviewer | sonnet (mid) | 125,513 | 15 | 327,210 ms | 2 |
| knowledge-reviewer | reviewer | opus (session) | 94,894 | 18 | 332,988 ms | 2 |
| consistency-reviewer | reviewer | sonnet (mid) | 93,001 | 20 | 165,556 ms | 0 |
| design-reviewer | reviewer | opus (session) | 114,482 | 16 | 413,372 ms | 0 |
| test-reviewer | reviewer | sonnet (mid) | 101,378 | 20 | 309,768 ms | 2 |
| typescript-reviewer | reviewer | sonnet (mid) | 90,157 | 15 | 294,521 ms | 1 |
| spec-compliance-reviewer | reviewer | opus (session) | 61,689 | 7 | 130,717 ms | 3 |
| adversarial-reviewer | reviewer | opus (session) | 99,870 | 29 | 483,069 ms | 0 |
| performance-reviewer | reviewer | sonnet (mid) | 93,477 | 17 | 282,899 ms | 1 |
| validator — #1 docblock falsified | validator | sonnet (mid) | 63,714 | 7 | 96,263 ms | confirmed |
| validator — #2 test anchors | validator | sonnet (mid) | 62,416 | 5 | 78,944 ms | confirmed |
| validator — perf fast path | validator | sonnet (mid) | 67,804 | 10 | 164,909 ms | refuted |
| validator — "now" comment | validator | sonnet (mid) | 76,550 | 11 | 86,186 ms | refuted |
| validator — do-not-share contract | validator | sonnet (mid) | 65,851 | 8 | 266,281 ms | refuted |
| validator — dirty contract undoc | validator | sonnet (mid) | 65,554 | 9 | 82,143 ms | refuted |
| validator — #4 spec overclaim | validator | sonnet (mid) | 61,882 | 7 | 79,545 ms | confirmed |
| validator — TS race artifact | validator | sonnet (mid) | 53,334 | 5 | 52,804 ms | refuted |
| validator — spec stub race artifact | validator | sonnet (mid) | 50,641 | 5 | 36,934 ms | refuted |

Reviewer subtotal: **967,881** tokens / 166 tool calls. Validator subtotal: **567,746** tokens / 67 tool calls. Wave total: **1,535,627** tokens / 233 tool calls.
*[Unverified] whether a subagent's reported token figure includes its own children — carry this caveat wherever these figures are summed.*

**Pre-flight gates**: web tests (`npx vitest run --reporter=agent`) → PASS, 60 files / 1231 tests, 31.27 s. Typecheck (`npx svelte-check --threshold warning`) → PASS, 4737 files, 0 errors / 0 warnings. Go build/lint/test → not run (no Go files in changeset). Gates ran **once** before dispatch; reviewers were instructed not to re-run them.

**Anomalies**:

1. ⚠️ **Concurrent-probe race corrupted three reviewers' observations — the headline process finding of this run.** `test-reviewer` performed a sanctioned revert-probe and disclosed it verbatim: it *"edited `sameBody` in place to the byte-exact pre-fix predicate (`return a === b;`), ran the new describe block, then restored the function to its exact original text"*, verifying the restore with `diff` and `git diff --stat`. The probe was **correct by the letter of the skill's rules** (Step 3's working-tree safety clause explicitly permits "a precise inline edit and undo it by re-editing back to the exact original") and produced this review's most valuable finding (#2). But all 10 reviewers ran **in parallel against the same working tree**, so three siblings that read during the mutation window (`typescript-reviewer`, `spec-compliance-reviewer`, `adversarial-reviewer`) observed a no-op stub with 7 failing tests. Consequences: `spec-compliance-reviewer` filed the stub as a real spec failure and declared the pre-flight gate report false (2 findings, both refuted); `typescript-reviewer` filed a Critical (refuted); `adversarial-reviewer` compounded it by applying its own inverse probe, then correctly diagnosed the state as transient and reviewed the right code. All three reviewers' *reasoning was sound given what they observed* — both validators explicitly classified this as a process hazard, not reviewer error. **Tuning candidate: the skill's inline-edit-and-restore probe permission is unsafe under parallel dispatch and should require an isolated copy or worktree** (`isolation: "worktree"`), or serialize mutating probes after the read-only wave.
2. ⚠️ **Orchestrator promotion was over-cautious.** The Step 5.5 promotion of design-reviewer's dismissed `NibFormFields.dirty` item was refuted — both agents' original judgment to decline was correct. Step 5.5 is designed to compensate for agents reasoning themselves out of real findings; here it manufactured one. Cost: one validator (65,554 tokens).
3. ℹ️ **Unrelated commit landed mid-wave.** `6cae9d1 fix(demo): serve the fixture with --config, not --nibs-path` was committed during the review (HEAD was `0516fe1` at session start). Verified via `git show --stat` to touch only `Taskfile.yml`, `testdata/fixtures/gen-sample-project.sh`, `web/playwright.screenshots.config.ts` — **not** the reviewed files. No impact on the diff under review.
4. ✅ **No dispatch retries, no unusable returns, no injected-content flags.** All 10 reviewers and all 9 validators returned parseable reports as tool results on first dispatch.
5. ✅ **Working tree verified intact post-wave**: `sameBody` holds the normalizing implementation, `git diff HEAD --stat` shows the original +178/-3, `npx vitest run src/lib/nibForm.svelte.test.ts` → 54/54 pass.

**Validation yield**: 9 validators, **3 confirmed / 6 refuted** (67% refutation rate). Two refutations were race artifacts; four overturned genuine reviewer over-reach — including the performance finding's impossible trigger (missed by the finder *and* by the orchestrator, caught only on independent re-trace of the `||` short-circuit) and the "now"-comment call, overturned on git-archaeology evidence neither the finder nor the dissenter had produced. On this changeset the validation wave was the difference between a report with 1 real Critical and one with 3 spurious Criticals.
