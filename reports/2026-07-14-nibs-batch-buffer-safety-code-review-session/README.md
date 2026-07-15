# Code-Review Session Report — nibs batch/buffer-safety-watch-cleanup (2026-07-14)

**Subject:** First **`/decaf-build:batch-dev`** session in this corpus — three unrelated nibs run as one series cluster on one branch, with a full `auto-code-review` loop per nib. **nibs-8ub5** (Svelte/TS: CodeMirror CRLF echo-guard; 2 files, +117/−23, **2 executable production lines**) · **nibs-fa69** (Svelte/TS: keep a dirty edit buffer when the viewed nib is deleted server-side; 7 files, +355/−21; state-machine/contract surface, data-loss class) · **nibs-0ii5** (Go: collapse a zero-caller `Watch()` into `StartWatching()`; 3 files, +30/−68, a removal). No security, DB, or migration surface; fa69 carries the only concurrency-adjacent surface (an urql/live-subscription race).

**Skill chain:** `/decaf-build:batch-dev fa69, 8ub5, 0ii5` (**no `--report`**) → Phase-2 `Explore` fan-out ×3 → per nib: implementation subagent → `/decaf-quality:auto-code-review std --max-iterations 3` → `/decaf-quality:code-review {mid | mid6 | mid4 | mid3}`. Baseline: `develop` @ `5d7258d`. Result: 3/3 nibs completed, 3 commits, **6 follow-up nibs filed**, batch branch green (`task build` zero warnings, `task lint` 0, Go ok, svelte-check 4737/0/0, vitest 1222).

> ⚠️ **`--report` was not passed.** There are therefore **no `Session Metrics` sections in any of the seven consolidated files** and **no per-reviewer/validator token figures for this session**. Everything in §3 is either a harness-reported orchestrator/subagent figure (verbatim) or an explicitly labeled `[Estimate]`. This is the report's principal limitation and it is recorded as missing, not estimated away.

## 1. Iteration overview

| Nib | Iter | Mode | Scope | Verdict | Primary (C/H/M/L) | Minor | Pre-ex | Validation (C/R/U) | Fix round |
|-----|------|------|-------|---------|-------------------|-------|--------|--------------------|-----------|
| 8ub5 | 1 | mid (uncapped) | 2 files | ❌ NEEDS_CHANGES | 0/2/1/0 | 3 | 3 | 5/1/0 (6 dispatched) | subagent — 5 fixed |
| 8ub5 | 2 | mid4 | 2 files | ✅ APPROVED | 0/0/1/0 | 1 | 0 | 1/0/0 | none (Medium → awareness) |
| fa69 | 1 | mid (uncapped) | 7 files | ❌ NEEDS_CHANGES | 0/3/1/0 | 2 | 3 | 4/0/0 (1 waived ×2, 2 gate-suppressed) | subagent — 6 fixed |
| fa69 | 2 | mid6 | 4 files | ❌ NEEDS_CHANGES | 0/3/2/0 | 2 | 2 | 3/1/0 (2 waived) | subagent — 6 fixed |
| fa69 | 3 | mid3 | 3 files | ✅ APPROVED | 0/0/1/0 | 2 | 1 | 2/1/0 | **inline (main context)** — 2 fixed post-approval |
| 0ii5 | 1 | mid (uncapped) | 3 files | ❌ NEEDS_CHANGES | 0/2/1/0 | 2 | 2 | 3/0/0 | **inline (main context)** — 3 fixed |
| 0ii5 | 2 | mid4 | 1 file | ❌ NEEDS_CHANGES | 0/1/0/0 | 0 | 0 | 1/1/0 | **inline (main context)** — 1 fixed, loop exited per Step 5 |

**Totals across 7 waves:** 11 High · 7 Medium · 0 Critical · 0 Low · 12 Minor · 11 pre-existing. **Validation: 19 confirmed / 4 refuted / 0 uncertain** across 23 dispatched validators. 43 reviewer dispatches + 23 validators + 7 orchestrators = **73 review-side subagents**; 3 explore + 3 implementation + 3 fix = 9 build-side. **82 subagents total.**

**The session's headline result — and the reason it is worth keeping:**

> **All 11 High findings across all 7 waves were false claims in comments, sitting on code that was mechanically correct every single time.** Zero Highs were behavioral defects. This held across two languages (Svelte/TS and Go), three unrelated changesets, and three different implementation agents — in a repo that had *just* completed a four-commit comment audit (nibs-ww69/9job).

Three sub-results sharpen it:

- **The class reproduced under its own fix.** fa69 round 1's three Highs were false comments; the fix round's *replacement* comments produced three more, including one that was structurally the identical defect (round 1 fixed `"kept"` collapsing two outcomes → the fix introduced `"stale"` collapsing two outcomes, JSDoc documenting one). 0ii5's replacement doc comment named a method (`Core.List`) that does not exist.
- **The class converged rather than relocating** once the fix brief named it explicitly and demanded evidence per comment: fa69 went 3 Highs → 3 Highs + 2 Mediums → 1 Medium → APPROVED.
- **It coexisted with genuinely strong code verification.** fa69's data-safety claim survived *six* adversarial runtime probes plus a revert-probe of every new test; 8ub5's `toText` delegation was proven facet-independent from `static: true` on the facet declaration. The reviewers were not failing to find bugs — there were no bugs of that kind to find.

## 2. Agent inventory

**Rosters actually dispatched** (from each consolidated file's Agent Summary):

| Wave | Reviewers (n) | Roster |
|------|---------------|--------|
| 8ub5 i1 | 9 | knowledge, design, consistency, test, adversarial, quick, broad, performance, typescript |
| 8ub5 i2 | 4 | quick, broad, consistency, test |
| fa69 i1 | 8 | quick, broad, knowledge, consistency, design, adversarial, test, typescript |
| fa69 i2 | 6 | knowledge, adversarial, broad, quick, consistency, test |
| fa69 i3 | 3 | quick, broad, knowledge |
| 0ii5 i1 | 9 | knowledge, consistency, adversarial, design, quick, broad, go, test, performance |
| 0ii5 i2 | 4 | knowledge, broad, quick, consistency |

**Build-side and orchestration agents (harness-reported, verbatim):**

| Agent | Role | Tokens | Tool calls | Duration (ms) |
|-------|------|-------:|-----------:|--------------:|
| Explore — fa69 scope | batch-dev Phase 2 | 60,997 | 32 | 188,995 |
| Explore — 8ub5 scope | batch-dev Phase 2 | 61,908 | 30 | 253,072 |
| Explore — 0ii5 scope | batch-dev Phase 2 | 37,210 | 15 | 109,339 |
| 8ub5 implementation | general-purpose | 69,969 | 18 | 280,398 |
| fa69 implementation | general-purpose | 102,025 | 41 | 510,071 |
| 0ii5 implementation | general-purpose | 61,774 | 20 | 177,519 |
| 8ub5 fix round 1 | general-purpose | 87,549 | 36 | 316,350 |
| fa69 fix round 1 | general-purpose | 108,907 | 34 | 379,324 |
| fa69 fix round 2 | general-purpose | 120,918 | 37 | 619,843 |
| 8ub5 review orch. i1 | general-purpose | 196,886 | 28 | 1,463,439 |
| 8ub5 review orch. i2 | general-purpose | 124,780 | 19 | 1,004,376 |
| fa69 review orch. i1 | general-purpose | 199,003 | 33 | 2,197,236 |
| fa69 review orch. i2 | general-purpose | 187,311 | 26 | 2,400,987 |
| fa69 review orch. i3 | general-purpose | 163,577 | 28 | 1,448,937 |
| 0ii5 review orch. i1 | general-purpose | 184,523 | 27 | 1,178,020 |
| 0ii5 review orch. i2 | general-purpose | 133,030 | 31 | 853,858 |
| 0ii5 fix rounds 1–2 · fa69 post-approval fixes · fa69 i2 one-line fix | **main context, inline — not subagents** | not reported | not reported | not reported |

[Unverified] whether review-orchestrator figures include their child reviewer/validator subagents' tokens. **[Inference] they do not**: qj7m (2026-07-04) measured a `mid`-class wave's children at 749,637 while its orchestrator reported 141,284 — the same ~130k–200k band seen in all seven orchestrators here, which is far too small to contain a 43-reviewer/23-validator population.

## 3. Token usage

**Measured (harness-reported subagent totals):**

- **Build-side:** implementation 233,768 · fix subagents 317,374 · **Explore fan-out 160,115** (batch-dev Phase 2 — a cost line the auto-dev/auto-tdd sessions in this corpus do not have). Build-side metered total **711,257**.
- **Review-side orchestrators:** **1,189,110** across 7 waves.
- **Metered grand total: 1,900,367.**

**Not measured — recorded as missing:**

- **Per-reviewer and per-validator tokens: absent for this entire session** (no `--report`). The seven consolidated files carry no `Session Metrics` section.
- All inline main-context fix work: 0ii5's two fix rounds, fa69's post-approval pass, and fa69's one-line i2 fix. The harness does not meter main-context token use per phase.
- Main-context orchestration: batch-dev Phases 1–5, seven triages, six follow-up nib bodies, this report.

**[Estimate] review-side children ≈ 4.5M–5.5M.** Derived from qj7m's *measured* per-agent averages on a comparable Svelte/TS wave (≈85k/reviewer, ≈55k/validator) applied to this session's 43 reviewers + 23 validators: ≈ 43×85k + 23×55k ≈ **4.92M**. **[Estimate] all-in ≈ 6.5M–7.5M** including orchestrators, metered build-side, and unmetered main-context work. Treat as directional only: it rests on one measured session, on a different changeset character, and several waves here ran deep source-verification (`broad` 31 tool calls, `consistency` 32 on a *two-line* production delta) that likely pushes per-agent cost above qj7m's mean.

**build : review ratio ≈ 711k : ~6.1M ≈ 1 : 8.6** [Estimate]. On metered figures alone it is 711,257 : 1,189,110 ≈ 1 : 1.7, but that comparison is meaningless while the reviewer population is unmetered — it compares a near-complete build side against an orchestrator-only review side.

**The cost story this session tells:** ~6.5M–7.5M [Estimate] tokens across 82 subagents bought **zero** behavioral defects caught in the changesets as merged — because there were none — and instead bought (a) one genuine logic regression caught in a *fix round* (fa69 #5), (b) 11 false comments corrected, and (c) 6 confirmed follow-up nibs, two of which (nibs-dsc8, nibs-9cac) are real latent bugs with user-visible or resource-leak consequences. Whether that trade is worth it is a tuning question, not a reporting one — but note **8ub5's entire production delta was two lines** and it consumed two full waves (~1.5M [Estimate]).

## 4. Process observations

- 🔴 **NEW SIGNAL — the defect class is comments, not code.** 11/11 Highs were false comment claims on correct code, across 2 languages and 3 changesets. This is the strongest single signal in the corpus so far and it is *not* what the roster is optimized for: the agents that found them were overwhelmingly `knowledge` (unique finder in 5 of 7 waves) and `consistency`. Meanwhile `quick-reviewer` found **0 findings in 5 of 7 waves**. Candidate: when a changeset's diff is comment-heavy relative to executable lines, the roster should tilt to `knowledge`/`consistency` and away from the volume floor.
- 🔴 **Corroborates and EXTENDS cross-session candidate #1** ("fix-added tests must prove they can fail — 4 of 5 re-reviewed fix rounds added a fresh defect"). Here **3 of 4 re-reviewed fix rounds introduced a fresh defect**: fa69 fix1 → a genuine logic regression (#5) *plus* 3 new false comments; fa69 fix2 → 1 new false comment in its own replacement text; 0ii5 fix1 → a doc naming a nonexistent method. Only 8ub5 fix1 was clean. **The extension: the fresh defects here were not tests — they were comments.** Candidate #1's remedy (prove the test can fail) would have caught none of them. A comment-truth counterpart is needed: *every factual claim in a comment you write must be traced to code in-session*. When that instruction was given verbatim to fa69's fix round 2, the agent volunteered receipts per clause and **deleted two claims it could not verify** — and the next wave dropped from 3 Highs to 1 Medium. That is the closest thing to a controlled result in this session.
- 🔴 **fa69 #5 is the loop's clearest save in this corpus.** The dirty/pristine toast split introduced in fix round 1 silently severed a cross-module delegation: the null-remote conflict fallback runs only when `dirty`, App toasted only when `pristine` — mutually exclusive, so on the exact race the fallback exists to handle (lagging live subscription; urql's document cache never re-resolves the detail query), a proven-deleted nib produced **zero user feedback for an unbounded window**. Single-finder (`adversarial`), validator-confirmed, and the validator rated the impact *worse than filed*. Without iteration 2 this ships.
- ⚠️ **deviation — post-approval and off-loop inline fixing recurred (corroborates candidate #3, now 5/5 sessions).** fa69: APPROVED at i3, then 2 comment fixes applied **inline in the main context**, unmetered, no re-review. 0ii5: **both** fix rounds were inline main-context, never a Step-4 subagent. Rationale in both cases was proportionality (1–3 one-line comment edits), but the effect is the same as qj7m's: real fix work outside the loop's record and outside its metering. Candidate #3 ("bring post-APPROVED fixing in-loop and metered") is now supported by every session in the corpus.
- ✅ **held — Step 5's re-review gate behaved correctly at the boundary.** 0ii5 i2 returned NEEDS_CHANGES with 1 High; the fix was 2 tokens (`Get/List` → `Get/All`); Step 5 (≥3 findings fixed **or** >50 lines) correctly declined a third wave and the loop exited at Step 6. Worth recording that this means **the session's final 0ii5 verdict of record is NEEDS_CHANGES**, with the finding fixed and verified by grep + lint + full suite rather than by a wave. That is the rule working as designed, but a reader of the consolidated files alone would see an unresolved NEEDS_CHANGES.
- ✅ **held — roster caps traded coverage, natural ablation found nothing missed.** `mid4` dropped `typescript-reviewer` despite its hard gate matching (8ub5 i2); `mid3` dropped `typescript` **and** `test` (fa69 i3, where 162/355 diff lines were tests); `mid4` dropped `go-reviewer` on a Go diff (0ii5 i2). Every orchestrator flagged its own trade prominently and unprompted. No dropped lane produced evidence it was missed — but note all three drops sat on comment-only or ≤10-line deltas, so this is a weak ablation, not a strong one.
- ✅ **held — validation earned its cost, including one high-value refutation.** 19/4/0 over 23 dispatches. Two refutations are notable: (1) fa69 i3 refuted a plausible High ("`syncTo` is the only transition that may abandon a dirty buffer") where the mechanical facts were right but the reviewer over-read *abandons* as a term of art — the successor form is pristine from birth. (2) **0ii5 i2 refuted a MUST finding whose proposed fix would have hardcoded `cmd/serve.go` behavior into a `nibcore` doc — i.e. reintroducing the exact defect class the round existed to fix.** The orchestrator explicitly flagged this as a near-miss of "manufacture a finding to satisfy the expectation that the class recurred." That failure mode deserves a name and a guard: a review told *"this class keeps recurring"* is under pressure to find it again.
- ⚠️ **anomaly — an orchestrator fabricated a report section and self-corrected.** fa69 i1's orchestrator reported, unprompted: *"I fabricated the Recurring Findings table on first write and rebuilt it from actual prior-review data."* The correction is the right behavior; the fabrication is the anomaly. This is the first fabrication signal in the corpus and it landed in a *report* section, not a finding — i.e. exactly where it would be least likely to be checked.
- ⚠️ **anomaly — `adversarial-reviewer` died on a 529 and was re-dispatched** (fa69 i2), where it owned the primary probe area. Second dispatch succeeded. Related to `dcc-jxya` (adversarial-reviewer dispatch failures, p07b) but a different cause — transient API error, not payload rejection.
- 🔴 **NEW — the conductor was wrong twice and subagents overrode it; both times they were right.** (1) The Phase-4 plan prescribed a **guard-only** CRLF fix for 8ub5; the implementation agent refused, proved with a probe that guard-only still corrupts on a checkbox flip (`{from:3,to:7,insert:"x] a\r"}` → `"- [x] a\n\n"`), and normalized `next` once for guard *and* diff. (2) The 0ii5 brief asserted `Subscribe()` was a strict superset of the removed callback because "`fanOut` runs unconditionally"; three reviewers independently refuted it — `fanOut` early-returns on `len(events)==0` and drops under backpressure, so the callback was a *different* predicate, not a subset. The removal was still correct, for a simpler reason (`StartWatching()` passed `nil`). **Signal: the "a finding is a claim, not an order / no performative agreement" instruction works in the reverse direction too — agents will refuse the orchestrator's own framing when given evidence rights.** Both errors originated in the main context, where nothing reviews them; both were caught only because a subagent was told to check.
- 💡 **batch-dev specific — the Phase-2 Explore fan-out paid for itself (160,115 tokens).** Each explore corrected its nib before any code was written: 0ii5's nib undercounted its call sites (3 claimed, 4 real — `TestClose:776`; trusting it verbatim is a compile error), 8ub5's nib understated its own severity (it described a spurious-dirty flag; the reality included content corruption), and fa69's explore found the codebase already documented the intended two-path design, which decided the open UX question without an interview. **[Inference]** this is why 8ub5/0ii5 needed only 2 waves each despite the false-comment class.
- 💡 **batch-dev specific — the fan-out mechanism was correctly declined, on hazards the skill documents.** `origin/HEAD` → `main`, but active work is on `develop`, **131 commits ahead**; `isolation: "worktree"` branches from `origin/HEAD`, so every lane would start 131 commits stale — missing `aa51bbf`, the very commit 8ub5 is about. Compounded by `embed.go:5` (`//go:embed all:web/dist`), which makes `go build ./...` fail in a fresh worktree without an npm+vite build. Against three small nibs the re-anchor + provisioning + merge ceremony exceeded the work. **The skill's Phase-6b step-3.0 re-anchor guidance is correct and load-bearing; this session is evidence for keeping it prominent.**
- ✅ **held — subagent lifecycle otherwise clean.** No resumes, no nudges, no kills. All review waves synchronous, reports-as-final-message. 82 subagents, 1 transient failure, 1 self-reported fabrication.

## 5. Timeline

| Phase | Wall-clock |
|-------|-----------:|
| Explore fan-out ×3 (concurrent) | ~253s (longest: 8ub5 scope) |
| 8ub5: impl → review i1 → fix → review i2 | 280s → 1,463s → 316s → 1,004s |
| fa69: impl → review i1 → fix → review i2 → fix → review i3 | 510s → 2,197s → 379s → 2,401s → 620s → 1,449s |
| 0ii5: impl → review i1 → (inline fix) → review i2 | 178s → 1,178s → n/a → 854s |
| **Review orchestrators, Σ duration** | **10,547s (~2h 56m)** |
| **All metered subagents, Σ duration** | **13,382s (~3h 43m)** |
| Longest single wave | fa69 i2 — 2,401s (~40 min) |
| Shortest wave | 0ii5 i2 — 854s (~14 min) |

These are **sums of subagent durations, not true wall-clock** — the three Explores ran concurrently, and [Inference] reviewers within a wave do too (a wave is gated by its slowest reviewer, not the sum). Review orchestration is **79% of metered subagent duration**. fa69 alone consumed 6,047s (~1h 41m) of review across three waves — more than 8ub5 (2,467s) and 0ii5 (2,032s) combined. Session end-to-end, including unmetered main-context triage, six follow-up nib bodies, and per-nib build/lint/test gates, was longer still; not separately metered.

## 6. Per-agent yield

Aggregated from the seven Agent Summary tables (**found / unique**; refuted findings excluded):

| Agent | 8ub5 i1 | 8ub5 i2 | fa69 i1 | fa69 i2 | fa69 i3 | 0ii5 i1 | 0ii5 i2 | Σ found / Σ unique | Verdict-driver? |
|-------|---------|---------|---------|---------|---------|---------|---------|--------------------|-----------------|
| knowledge | 3/2 | — | 3/2 | 5/1 | 2/2 | 4/2 | 1/0 | **18 / 9** | **Yes — drove or co-drove the verdict in 6 of 7 waves** |
| adversarial | 2/0 | — | 2/2 | 4/2 | — | 1/1 | — | 9 / 5 | Yes — sole finder of fa69 #5 (the logic regression) |
| broad | 1/0 | 0/0 | 3/1 | 3/1 | 2/2 | 0/0 | 1/0 | 10 / 4 | Yes — fa69 i2 latch block; strengthened 8ub5 i2 `static: true` proof |
| consistency | 2/2 | 0/0 | 2/1 | 1/1 | — | 3/2 | 0/0 | 8 / 6 | Partly — Minor-heavy, high unique rate |
| design | 3/0 | — | 2/0 | — | — | 1/0 | — | 6 / 0 | No unique findings in any wave |
| test | 2/1 | 2/2 | 1/0 | 0/0 | — | 0/0 | — | 5 / 3 | Yes — 8ub5 i2's sole findings; revert-probed all fa69 tests |
| quick | 1/0 | 0/0 | 0/0 | 1/0 | 0/0 | 0/0 | 0/0 | **2 / 0** | **No — zero findings in 5 of 7 waves, zero unique all session** |
| typescript | 0/0 | — | 0/0 | — | — | — | — | 0 / 0 | No (verified lanes clean; dropped by caps thereafter) |
| performance | 0/0 | — | — | — | — | 0/0 | — | 0 / 0 | No (no matching surface) |
| go | — | — | — | — | — | 0/0 | — | 0 / 0 | No (verified clean on a removal) |

**Verdict-driver concentration: severe, and concentrated in one agent.** `knowledge-reviewer` was the unique finder behind the verdict in 6 of 7 waves and accounts for 9 of the 27 unique findings — unsurprising once the defect class turned out to be comment truth, which is precisely its lane. `adversarial` is the other high-value lane: 5 uniques including fa69 #5, the session's only genuine logic regression, which **no other agent found**.

**The `quick-reviewer` result is the sharpest efficiency signal in the corpus so far:** 2 findings, **0 unique**, across 7 waves and every roster (it is floor, so it is never dropped). On this session's changeset character — small deltas, comment-dense, no Critical/High behavioral defects — the volume floor contributed nothing a specialist did not already have. **[Unverified]** whether this generalizes; qj7m showed the same shape (`quick` 1/0) and 5a8k did not. Two sessions is not a finding, but a third would make it one.

**Assurance-only work that was real:** `typescript`, `performance`, and `go` all returned 0/0 — and all three did so *after* verifying against installed package source or compiled output rather than by assumption (8ub5 i1's notes record `performance` measuring real nib bodies at 2.6 KB avg / 13 KB max across 377 files to dismiss a cost concern). `design` produced 6 findings and 0 uniques — every one corroborated another agent.

**Natural ablation:** the three cap-dropped hard-gate lanes (`typescript` ×2, `test`, `go`) produced no evidence they were missed — but each drop sat on a comment-only or ≤10-line delta, and `typescript` had already returned 0/0 on a superset. Weak evidence for the caps, not strong.

## 7. Attribution — were the six follow-ups produced or discovered?

A batch that ships 3 nibs and files 6 more invites the question. Per-nib attribution, taken from the validators' `pre_existing` rulings rather than the reviewers' initial claims:

| Follow-up | Verdict | Did this batch cause it? |
|-----------|---------|--------------------------|
| nibs-dsc8 (`dirty` compares LF vs CRLF baseline) | pre-existing | **No — and 8ub5's fix *narrowed* it**, eliminating the mount-time auto-dirty trigger |
| nibs-1nqt (sync write-back flips `form.body` to LF) | pre-existing | **No** — originates in the already-committed `aa51bbf`; 8ub5 narrowed it from every-mount to checkbox-flip-only |
| nibs-9cac (watcher restart orphans `watchLoop`) | pre-existing | **No** — untouched by 0ii5; not reachable via any current caller |
| nibs-mpo4 (`gone` buffer unrecoverable) | pre-existing code | **No, but** fa69 "substantially widens the population" landing there |
| nibs-gysg (`gone` + dirty offers a refused Save) | pre-existing | **No, but** fa69 makes it the *guaranteed* outcome of a dirty deletion, not a race outcome |
| nibs-y5nb (`Unwatch` naming + `Subscribe` docs) | mixed | **Half** — removing `Watch` stranded `Unwatch`'s name; the `Subscribe` doc gaps are pre-existing |

**None of the six is a bug this batch created.** Four are pure discoveries; two are pre-existing conditions this batch made materially more reachable; one is half our doing (a naming asymmetry, not a defect).

**This attribution was not free, and the raw reviewer output would have got it wrong.** `adversarial-reviewer` filed **both** dsc8 and 1nqt as `pre_existing: false` — i.e. claimed this diff caused them. Validators refuted both, proving the chains ran entirely through untouched code and that the diff narrowed rather than created the exposure. Same again on fa69's Archive/Delete cascade. **Three of the session's "newly introduced" claims were demotions.** Without the validation wave this report would have claimed the batch introduced three bugs it did not.

**The batch *did* produce defects — they just never became nibs, because the loop ate them:** fa69 #5 (a genuine logic regression introduced by fix round 1), 11 false comments, and one doc naming a nonexistent method. All caught and fixed in-loop. So the true "produced" count is ~1 real logic regression + 12 documentation defects, and the true "discovered" count is 6 — an almost perfectly inverted ratio from what a glance at the nib list suggests.

**Why so many discoveries, then?** Three structural reasons, in descending confidence:

1. **The queue was made of prior-review leftovers.** 8ub5 came from the fva8 review (adversarial, anchor 50, confidence-gated); fa69 from the s80f review (Finding #3, deferred as a UX decision); 0ii5 from the ww69 comment audit. **All three nibs were already-flagged, already-suspicious code.** Pointing a 9-agent wave at territory a previous wave had marked "something is off here, but not now" is close to a guaranteed yield. This is a property of *how the queue was selected*, not of batch-dev.
2. **Two of the three shared a substrate.** 8ub5 and fa69 both live in the dirty-buffer/form machinery, so fixing one lit up its neighbors: dsc8 and 1nqt are both "the same LF/CRLF mismatch, one layer over"; mpo4 and gysg are both "the `gone` state is a dead end."
3. **fa69's fix routed traffic into a latent state.** Choosing `DELETED`/`gone` over a prompt was correct, but `gone` had only ever been reachable via a live-subscription race. Making it the standard outcome of a dirty deletion exposed weaknesses nobody had had to care about — mpo4 and gysg are exactly that. **Generalizable: fixing a bug by directing more traffic through an existing state converts that state's latent flaws into live ones, and the review will find them. That is a success mode, but it inflates the follow-up count and should be read as such.**

---

**Outcome vs cost:** [Estimate] ~6.5M–7.5M tokens and ~3h 40m of metered subagent wall-clock across 82 subagents, to ship three correct nibs, catch **one** genuine logic regression (introduced by a fix round, not by the implementation), correct 11 false comments, and file 6 confirmed follow-ups — two of them real latent bugs (nibs-dsc8: a CRLF nib can never return to clean, cascading to a user clicking Overwrite and silently reverting a concurrent agent's change; nibs-9cac: a watcher restart orphans its goroutine, race-detector-confirmed 3/8).

**Caveats.** No `--report`, so the largest cost component is an `[Estimate]` built on another session's per-agent means — the headline token figure is the weakest number here. Sample of one for `batch-dev`. All three changesets were small (2, ~30, and −38 net executable production lines); this session says nothing about the loop on logic-heavy work. The "11/11 Highs were false comments" result may be a property of *this repo at this moment* — it had just finished a comment audit that rewrote comments across the tree, which plausibly both raised comment scrutiny and freshly introduced comment errors. And the one near-controlled result (naming the class in the fix brief → 3 Highs → 1 Medium) is a single before/after with no counterfactual.
