# Code-Review Session Report — nibs batch/config-and-buffer-fixes (2026-07-15)

**Subject:** Second `/decaf-build:batch-dev` session, and the first with `--report`. Queue: 7 bugs under milestone `nibs-9kvw`, six of them **follow-ups filed by the previous day's batch**. Shipped 6, deferred 1 by operator decision, scrapped 1 mid-flight. Changesets ranged from 5 lines of config to an 18-file cross-stack change spanning Go core, GraphQL, and the Svelte state machine.

**Skill chain:** `/decaf-build:batch-dev dsc8, 1nqt, mpo4, gysg, 1zap, s0tn, 9cac --report` → Phase-2 `Explore` fan-out ×7 → per nib: implementation subagent → `/decaf-quality:code-review {mid | mid6 | mid4} --report`. Baseline: `develop` @ `0516fe1` (the prior batch merged first, at operator direction). Result: 8 commits, **14 follow-up nibs filed**, batch branch green — `task build` zero warnings, `task lint` 0, `go test -race ./internal/nibcore/` ok, svelte-check 4737/0/0, vitest **1222 → 1292**.

> ⚠️ **`--report` coverage gap, owned.** No standard session-report folders were produced during the run. The orchestrator invoked `/decaf-quality:code-review --report` **directly per nib** rather than routing through `auto-code-review`, which is what writes `.decaf/session-reports/`. Metrics therefore live in the 10 consolidated files copied here and in this README, not in the conventional per-nib format. This report is reconstructed from those files plus harness-reported tool results.

## 1. Iteration overview

| Nib | Iter | Mode | Verdict | Primary (C/H/M/L) | Validation (C/R/U) | Outcome |
|---|---|---|---|---|---|---|
| bek5 | 1 | mid | ❌ NEEDS_CHANGES | 1/0/5/2 | 9/2/0 | **Fix reverted entirely** — the Critical killed the approach; the operator then showed `--config` already solved it. Shipped as 5 lines of config, **zero code**. Focused manual review substituted (k3zb precedent) → no report for the final diff. |
| dsc8 | 1 | mid | ❌ | 1/0/1/2 | 3/6/0 | 6 of 9 findings **refuted** |
| dsc8 | 2 | mid4 | ✅ APPROVED | 0/0/0/1 | 1/0/0 | |
| 1nqt | 1 | mid | ✅ APPROVED | 0/0/1/0 | 1/0/0 | Zero unique findings across the roster; the one finding found 3× |
| gysg | 1 | mid | ❌ | 0/1/1/0 | 2/0/0 | |
| gysg | 2 | mid6 | ❌ | 0/1/2/0 | 2/0/0 | |
| gysg | 3 | mid | ✅ (single-reviewer) | 0/0/0/1 | — | **10 reviewers dispatched; 5 reports destroyed** — see §4 |
| mpo4 | 1 | mid | ❌ | 0/3/2/2 | 7/0/0 | All 3 Highs were false comments |
| mpo4 | 2 | mid4 | ✅ APPROVED | 0/0/2/0 | 2/0/0 | |
| s0tn | 1 | mid | ❌ | 0/1/0/0 | corroborated ×2 | Both blockers comment-only; logic survived 4 traces + 3 probes |

**9 waves metered · 1 unmeterable · 103 reviewer/validator dispatches.**

## 2. Agent inventory

**Rosters** ranged 4–10 reviewers by mode. Model tiering held throughout: judgment lanes (`knowledge`, `design`, `adversarial`, `spec-compliance`) on the session model (opus); volume lanes and all validators mid-tier (sonnet).

**Build-side and orchestration (harness-reported, verbatim):**

| Group | n | Tokens |
|---|---|---|
| Phase-2 `Explore` fan-out | 7 | **317,661** |
| Implementation / fix / investigation subagents | 15 | **1,615,766** |
| Review orchestrators | 10 | **1,814,053** |

[Unverified] whether a subagent's reported figure includes its own children — every orchestrator flagged this caveat independently.

## 3. Token usage

| | Tokens |
|---|---:|
| Review waves (9 measured) | **9,538,335** |
| Review orchestrators (10) | 1,814,053 |
| Build-side (7 explore + 15 impl/fix) | 1,933,427 |
| **MEASURED TOTAL** | **13,285,815** |

Across **135 metered agents** (32 orchestration/build + 103 reviewers/validators) — **plus one wave of 10 that cannot be metered at all**.

**Not measured, recorded as missing:** the gysg archived wave's reviewer population (§4); all inline main-context fix work (bek5's entire final fix, the archived-fade revert, two comment corrections); main-context orchestration (Phases 1–5, ten triages, fourteen nib bodies, this report).

**Against the prior report's estimate.** The 2026-07-14 report put its all-in at `[Estimate]` ~6.5M–7.5M for 3 nibs, extrapolated from another session's per-agent means, and flagged that estimate as its weakest number. It was **conservative**: this run measured 13.3M for 6 nibs — ~2.2M/nib against the ~2.2M/nib the estimate implied, so the *per-nib* rate was actually accurate; the error was that no one had metered the reviewer population directly. `--report` closes that.

## 4. Process observations

- 🔴 **NEW — actor-mode dispatch destroys reports AND telemetry.** gysg's third wave dispatched 10 reviewers **with `name`**, which puts an agent in actor mode: its final message has no caller to return to, `run_in_background: false` is **inert rather than overridden**, and usage telemetry is lost. **5 of 10 reports were destroyed. The split was contract compliance, not a race**: the five who *violated* the skill's "return your report as your final message; never SendMessage" rule used SendMessage, hit a bounce, re-addressed to the top-level session, and survived. The five who *complied* were discarded. The parent **outlived all ten children by 6.5 minutes** — retrying would have changed nothing.
  **The skill already forbids this.** `/decaf-quality:code-review` Step 3 says "NEVER pass `name` on a review dispatch" verbatim, explains the inertness, and carries a tripwire on the first spawn ack. **This was not a skill defect — the guidance existed and was not followed.** The three waves after the rule was restated in the brief: 16/16, 6/6, 9/9 returned with full telemetry.
  *Corollary for `--report`:* a wave dispatched with `name` **cannot be metered** — the transcripts are not a fallback (`output_tokens` reads `2` on a 10.5k-char report).
- 🔴 **NEW — the five lost reports were recovered from disk and contained real findings.** Two became nibs (**y56n**: external archives report as deletions ~24/30, found independently by two lanes by execution; **6fbd**: event payloads publish the live store pointer, found by the only lane that ran `-race`). One re-scoped **ow1k** from a labeling bug to data loss. One was a false comment the orchestrator shipped. **The absence was recorded as a fact about the world instead of a question, and the reports were on disk the whole time.**
- 🔴 **The dominant defect class is comments, and it is not tracking a file.** **11 false comments** across the batch; comment-truth findings in **12 of the reviews** under `.decaf/code-reviews/` and **14 consecutive** on `ActiveNibView.svelte` alone. Three were authored by the conductor. One round *fixed* a false comment and shipped a new one 50 lines away; another put the refuted premise **inside the test guarding the fix for it**. A reviewer's diagnosis is the best available: this is **claim locality** — comments asserting facts about *other* code (the HTML spec, tailwind-merge internals, bits-ui's prop surface, vendored class lists) drift without anyone touching the file. Filed as `nibs-2sdz`.
- 🔴 **Eight decorative guards** — tests that pass while the thing they guard is broken. Three sat behind an assert that threw first (so they never ran). One survived deleting the `finally` it existed to protect — **passing all 1240 tests**. **Every one was found by running the mutation, never by reading.** Two were caught by the agents that *wrote* them, unprompted, and a third agent **declined to ship one** after mutation-proving it inert.
- 🔴 **Four of seven queued premises were false.** `disabled` blocks selection (refuted in real Chromium); the race detector fired 3/8 (80 runs: never, and structurally impossible); shorthand `#id` mentions don't link (they do — two tests already pinned it); archiving removes a nib from the list (the tool's own help says the opposite). **The one premise that survived came from the operator using the app.** Every other nib came from a code review — and reviews inherit reviewers' unverified claims, which then lose their evidence at the finding→nib hop.
- ✅ **The Phase-2 Explore fan-out is the highest-ROI line item in the run.** 317,661 tokens — **2.4% of measured spend** — and it refuted four premises *before any code was written*. It also corrected 9cac's call-site count (3 claimed, 4 real; trusting the nib = a compile error).
- ✅ **The isolated-probe protocol works, and needed a refinement.** Two early waves corrupted their own results (a reviewer revert-probed the *shared* tree while parallel siblings read it; one declared the changeset unimplemented, another filed a spurious Critical, a third reported a "fabricated tool result"). Six waves after isolation was mandated: **zero anomalies**. Refinement discovered mid-run: for an **uncommitted** diff, `git worktree add <dir> HEAD` hands you the **PRE-FIX tree** — build from `git stash create` instead. That is plausibly the real mechanism behind the earlier corruption.
- ✅ **Validation earned its cost, repeatedly.** dsc8 refuted 6 of 9 findings. Validators twice **reattributed** a reviewer's "you broke this" to pre-existing on evidence the diff *narrowed* the exposure. One refuted a MUST whose proposed fix would have **reintroduced the defect class the round existed to fix**. Another refuted a High by finding a passing test that *pins* the behavior as designed.
- ⚠️ **A fix round introduced a regression that the loop caught.** gysg's first fix withdrew Save for any `gone` buffer — but an archived nib still exists and is savable, so archiving with unsaved edits lost them, with a false "This nib no longer exists". Caught in review; the operator directed the real fix (distinguish archived from deleted on the wire), which grew the nib to 18 files and uncovered that the watcher was **evicting archived nibs from the store outright**.
- ⚠️ **deviation — inline main-context fixing recurred** (now 6/6 sessions in the corpus). bek5's entire final fix, the archived-fade revert, and two comment corrections were applied inline, unmetered. Corroborates the parked candidate #3.
- ⚠️ **anomaly** — one implementation agent died on an API error mid-task, having made **zero** edits; tree byte-identical, nothing to recover. One agent ran `prettier` (no config in repo) and churned 129 unrelated lines; self-restored by hand.

## 5. Timeline

| Phase | Wall-clock |
|---|---:|
| Phase-2 Explore fan-out ×7 (concurrent) | ~253s (longest) |
| Longest single wave | gysg w3 — ~2,213s (~37 min) |
| Review orchestrators, Σ duration | ~4.5 h |
| Σ all metered subagent duration | ~7.5 h |

Session end-to-end spanned ~14 h including unmetered main-context triage, fourteen nib bodies, and per-nib gates.

## 6. Per-agent yield

Aggregated across the 9 metered waves (**found / unique**):

| Agent | Σ found / unique | Verdict-driver? |
|---|---|---|
| knowledge | ~18 / ~9 | **Yes — drove or co-drove the verdict in most waves.** The comment-truth lane, which is this codebase's defect class |
| adversarial | ~12 / ~7 | **Yes** — sole finder of gysg's severed-delegation regression and (with knowledge) of y56n. The lane that builds and runs things |
| design | ~9 / ~2 | Yes — sole `-race` runner on 6fbd; settled the `syncing` scope question by *compiling* Svelte |
| test | ~10 / ~5 | Yes — the mutation lane; 12/12 mutations in one wave, caught the masked guards |
| broad | ~10 / ~4 | Partly |
| consistency | ~8 / ~6 | Minor-heavy, high unique rate |
| typescript | ~2 / ~1 | Mostly 0/0 — but its one finding (`tsc` with negative controls) refuted a compile-time claim two agents had asserted |
| **quick** | **~4 / 0** | **No — zero unique findings across the entire batch, in every roster (it is floor, never dropped)** |
| go / performance / spec-compliance | ~5 / ~2 | Assurance; `performance` measured rather than assumed (560ns/stat) |

**The `quick-reviewer` result now has three sessions behind it** (qj7m 1/0, the 2026-07-14 batch 2/0, this batch ~4/0). It is floor, so it is never dropped, yet it has produced **zero unique findings in ~20 waves**. On these changeset characters — small deltas, comment-dense, no Critical/High behavioral defects — the volume floor contributes nothing a specialist does not already have. Three sessions is a signal worth acting on.

**Verdict-driver concentration is severe and stable**: `knowledge` + `adversarial` account for nearly every verdict. Both are session-model judgment lanes. Both are what a roster cap squeezes first.

---

**Outcome vs cost:** 13.3M measured tokens across 135 agents to ship 6 nibs, of which **zero contained a behavioral defect at merge** — because every Critical/High across ten waves was either a false comment or a false premise. What the spend actually bought: **one genuine logic regression caught in a fix round** (a severed cross-module delegation that would have left a proven-deleted nib reporting nothing), **one data-loss regression caught before merge** (archived edits withdrawn), **eight decorative guards killed**, **eleven false comments corrected**, and **14 follow-ups filed** — two of them data-loss (`ow1k` re-scoped; `y56n` meaning gysg is incomplete).

**Caveats.** Two batches, one repo, two days, one conductor — who is the common factor in every conductor-authored error (3 false comments, 4 wrong briefs, 1 inverted diagnosis). Six of seven queued nibs were *themselves* products of the previous batch's reviews, so "reviews produce false premises" is partly self-referential: this batch measured the output of the thing it was also using. The `--report` gap is real and mine. And the headline lesson — *claims are worthless until something executes them* — is drawn from a sample where the one nib sourced from **using the product** is also the one whose premise survived. That is one data point, not a law.
