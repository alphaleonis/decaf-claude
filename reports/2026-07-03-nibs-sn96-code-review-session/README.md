# Code-Review Session Report — nibs-sn96 (2026-07-03)

Session analysis of the `/decaf-quality:auto-code-review` loop (invoked via `/decaf-build:auto-tdd sn96`)
in the `nibs` repository, written for skill-tuning purposes.

**Subject under review:** fix for nib `nibs-sn96` — "Keyword search does not match nib IDs"
(`Core.Search` ID-match union in `internal/nibcore`).

**Skill chain:** `/decaf-build:auto-tdd` → TDD subagent → `/decaf-quality:auto-code-review std --max-iterations 3`
→ 3 × (`/decaf-quality:code-review mid` in a general-purpose orchestrator subagent → triage in main context → fix subagent).

**Files in this folder:**

| File | Contents |
|------|----------|
| `README.md` | This report |
| `iteration-1-consolidated-review.md` | Copy of `.decaf/code-reviews/CODE_REVIEW_2026-07-03_20-11-49.md` |
| `iteration-2-consolidated-review.md` | Copy of `.decaf/code-reviews/CODE_REVIEW_2026-07-03_20-43-07.md` |
| `iteration-1-individual-reports.md` | Raw per-reviewer reports that reached the main context (4 of 10 + 1 validator) |
| `iteration-3-individual-reports.md` | Raw per-reviewer reports that reached the main context (9 of 10) |

There is **no iteration-3 consolidated file**: the orchestrator was killed mid-write after the main
context had already consolidated and triaged from the raw reviewer reports (see Process Issues below).
Iteration-2 individual reports are **not available**: that orchestrator ran its reviewers synchronously,
so their reports stayed inside its context and only the consolidated file survives.

---

## 1. Iteration overview

| Iter | Mode | Scope | Verdict | Primary findings | Minor | Validation wave | Fixes applied after |
|------|------|-------|---------|-----------------|-------|-----------------|---------------------|
| 1 | `mid` | Full uncommitted diff (TDD output: 3 files) | ✅ APPROVED | 2 Medium, 5 Low | 4 (+1 pre-existing) | 4 validated (all confirmed, 1 severity corrected Med→Low), 3 waived as corroborated, 0 refuted | 7 (user-approved post-APPROVED batch, 2 TDD) |
| 2 | `mid` | Modified files from fix round 1 (9 files) | ❌ NEEDS_CHANGES | 1 High, 2 Medium | 5 | 4 validators: 3 confirmed, 1 refuted | 8 (autonomous, 1 TDD) |
| 3 | `mid` | Modified files from fix round 2 (10 files) | (no consolidated verdict — consolidator killed; main-context triage) | 1 Medium (4× independently confirmed w/ executed repros), 1 Low-Med perf, ~10 comment/naming/test items | — | none ran | 12 (autonomous, 1 TDD) + 1 deferred as nib `nibs-es0b` |

Totals: **27 findings fixed** (4 via TDD), 1 deferred, 3 skipped, 1 refuted-by-validator, several
pre-existing awareness items. Final state: merged to `main` (`3b3d5ab`), all gates green.

Notable quality signal: iteration 3's headline finding (charset gate broke exact-ID lookup of
foreign-prefix nibs) was found **independently by 4 of 10 reviewers** — broad and adversarial with
*executed* repros; design and knowledge by independent hand-trace ([Unverified] whether those two
executed anything; their reproduced reports show traces only). Strong corroboration for a regression
introduced by the previous fix round. The loop design (re-review after substantial fixes) earned its
cost here *given the fix process* — see §6 for why the regression was foreseeable at fix time.

## 2. Agent inventory

### Iteration 1 — orchestrator `aafd0b196a90e5fa8` (general-purpose)

Roster (10, gated dispatch; security / data-migration / non-Go stack / prior-feedback reviewers skipped per gates):

| Agent | Type | Individual report in main context? |
|-------|------|-----------------------------------|
| quick-reviewer | decaf-quality:quick-reviewer | Yes (full) |
| broad-reviewer | decaf-quality:broad-reviewer | Yes (full) |
| test-reviewer | decaf-quality:test-reviewer | Yes (full) |
| go-reviewer | decaf-quality:go-reviewer | Yes (full) |
| performance-reviewer | decaf-quality:performance-reviewer | No (idle notification only) |
| consistency-reviewer | decaf-quality:consistency-reviewer | No |
| knowledge-reviewer | decaf-quality:knowledge-reviewer | No |
| design-reviewer | decaf-quality:design-reviewer | No |
| spec-compliance-reviewer | decaf-quality:spec-compliance-reviewer | No |
| adversarial-reviewer | decaf-quality:adversarial-reviewer | No |

Validation wave: 4 validators observed (`validator-f2`, `validator-f3`, `validator-f4`, `validator-f6`);
only validator-f6's report (trailing-whitespace finding, 2 parts) reached main context.

### Iteration 2 — orchestrator `a4a7aa41455bde558` (general-purpose)

Reported "10 reviewers launched in parallel (floor + 8 gate-matched specialists), all completed
synchronously" + 4 validators (3 confirmed, 1 refuted). No individual reports visible in main context
(synchronous children — reports returned as tool results inside the orchestrator). Roster composition
per its consolidated file matches iteration 1's.

### Iteration 3 — orchestrator `a21900ec6058c5e47` (general-purpose, killed before writing report)

Roster (10): `rev-quick`, `rev-broad`, `rev-consistency`, `rev-knowledge`, `rev-design`, `rev-test`,
`rev-spec`, `rev-adversarial`, `rev-perf`, `rev-go`. Individual reports for **9 of 10** reached the
main context (all except `rev-spec`). No validation wave ran. Main context performed consolidation +
triage directly from the raw reports.

### Non-reviewer agents in the loop

| Agent | Role | Harness-reported usage |
|-------|------|------------------------|
| `a128bc9a067847937` | TDD execution (`/decaf-build:tdd`) | 98,730 tok / 47 tools / 652 s |
| `a910a0409b032d428` | Fix round 1 (7 findings) | 86,877 tok / 47 tools / 487 s |
| `a288bc187f31a80e8` | Fix round 2 (8 findings) | 96,266 tok / 42 tools / 426 s |
| `a3236ec59a8fdbbf4` | Fix round 3 (12 findings) | 85,075 tok / 44 tools / 477 s |

## 3. Token usage

All figures below are the harness-reported `subagent_tokens` values from Agent tool results /
task notifications in the session. **[Unverified]** whether these figures include the tokens of
*children* spawned by each orchestrator (the reviewer/validator agents) — the numbers are plausible
for the orchestrator conversations alone, which suggests children are NOT included, but I cannot
verify this from the session data.

### Harness-reported (verified as reported, per segment)

| Component | Segments (tokens) | Sum |
|-----------|-------------------|-----|
| Iter-1 review orchestrator `aafd0b196a90e5fa8` | 105,543 + 104,640 + 151,980 + 197,810 (initial + 3 resumes) | 559,973 |
| Iter-2 review orchestrator `a4a7aa41455bde558` | 161,520 (single synchronous run) | 161,520 |
| Iter-3 review orchestrator `a21900ec6058c5e47` | 99,057 + 97,532 (+ one killed segment, unreported) | ≥ 196,589 |
| Fix round 1 | 86,877 | 86,877 |
| Fix round 2 | 96,266 | 96,266 |
| Fix round 3 | 85,075 | 85,075 |
| TDD subagent (pre-review) | 98,730 | 98,730 |
| **Sum of reported** | | **≥ 1,285,030** |

Caveat on the iteration-1 segments: whether resume segments are cumulative or disjoint is
**[Unverified]**; the dip from 105,543 → 104,640 between consecutive segments suggests they are
per-segment (disjoint), so they are summed here.

### Not reported anywhere (must be estimated)

- **30 reviewer agents** (10 × 3 iterations) and **8 validators** (4 × 2 iterations): no usage
  figures surfaced. [Estimate] Based on the observed cost of comparable general-purpose subagents in
  this session doing similar work (file reads + `go build`/`go test`/lint runs + a 2–8 KB report:
  85k–105k tokens each), and reviewers being somewhat narrower in scope: roughly **40k–90k tokens per
  reviewer**, **20k–50k per validator** → ballpark **1.4M–3.1M additional tokens** across the three
  waves. This is speculation from analogy, not measurement.
- Main-context overhead for triage, nudging, and consuming ~25 broadcast teammate messages
  (idle notifications + duplicated report resends): not measurable from here, but the resend storm in
  iteration 3 alone re-delivered ~9 full reports (~35 KB of text) into the main context.

**[Estimate] Grand total for the three review iterations including children: ~2.5M–4.5M tokens.**
The verified floor (orchestrators + fixers, excluding reviewers/validators) is ~1.19M excluding the
TDD phase.

## 4. Process issues observed (tuning material)

These are the concrete failure modes seen while driving the loop. Iterations 1 and 3 each required
multiple manual `SendMessage` nudges from the main context; iteration 2 — given an explicit
"actively wait, do not stand by" instruction — completed cleanly in one shot.

1. **Orchestrator returns prematurely while its reviewers run in the background.**
   In iterations 1 and 3 the general-purpose orchestrator spawned reviewers (background) and then
   *ended its turn* ("Standing by for their results", "I'll consolidate as notifications arrive").
   A subagent's final message is its return value — ending the turn to "wait" returns a useless
   result to the caller. Iteration 1 needed **3 resumes**; iteration 3 needed 2 resumes and was
   ultimately killed. Cost: iteration 1's three resume segments total ~454k tokens and iteration 3's
   reported resume adds ~98k — not all of it waste (resumed segments also did the real consolidation
   work); benchmarked against iteration 2's clean single run (161,520 for the same roster and mode),
   iteration 1's overhead is ~400k. Wall-clock impact was modest: iteration 1 ran from spawn (~17:45)
   to its consolidated file at 18:11 UTC — ~26 min vs iteration 2's clean 21. The real costs were
   tokens and manual operator nudges.
   *(Corrected 2026-07-03: this section previously said "~455k extra" — counting consolidation work
   as pure waste, iteration 1 only — and "final report ~19:11", contradicting the §5 timeline; the
   file timestamp 20-11-49 is local UTC+2 = 18:11 UTC.)*
   *Tuning suggestion:* the code-review skill should instruct orchestrators to either spawn
   reviewers **synchronously in one parallel batch** (multiple Agent calls in a single message,
   `run_in_background: false`) — which is exactly what made iteration 2 work — or, if background
   spawning is used, to explicitly loop on task-status polling rather than ending the turn.
   *Post-analysis note:* the skill already mandated single-message parallel dispatch (`code-review`
   SKILL.md Step 3); the instruction went stale when the harness made Agent calls
   background-by-default, so "parallel in one message" stopped implying synchronous. Fixed in
   dcc-n87o by requiring `run_in_background: false` and reports-as-final-message.

2. **Broken reply topology: reviewers cannot message their spawner.**
   Reviewers spawned by an orchestrator subagent tried to `SendMessage` their reports back and got
   `No agent named 'general-purpose' is reachable`. Their reports were instead **broadcast to the
   main conversation**, which (a) flooded the main context and (b) never reached the consolidator,
   which sat waiting for replies that could not arrive. When nudged, the consolidator asked all 10
   reviewers to *resend* — every resend also bounced to main, duplicating ~9 full reports.
   *Tuning suggestion:* reports should be returned as the reviewer's **final message** (tool result
   to the spawner), never via SendMessage; and/or orchestrators should be spawned with a `name` so
   they are addressable.

3. **Timer/watcher-armed idling that never fires usefully.**
   The iteration-1 consolidator twice armed a "timer"/"watcher" and stopped, including once when all
   10 reviewer reports were already in. Each recovery required an external nudge (which re-reads the
   full transcript — expensive).

4. **Idle-notification noise.** Every reviewer teammate emitted `idle_notification` JSON messages to
   the main conversation (~25 such messages across the session), each one triggering a main-context
   turn. Zero information content beyond "done", which the spawner already learns via task
   notifications.

5. **No consolidated artifact for iteration 3.** Because the consolidator stalled, the main context
   triaged directly from raw reports and the orchestrator was killed mid-write (it was, at kill time,
   legitimately writing the report — a race between manual takeover and delayed recovery). If the
   skill guarantees a review file per iteration, the orchestrator-return-value contract (issue 1)
   is the root cause to fix.

6. **What worked well (keep):**
   - Gated dispatch: go-reviewer fired, dotnet/ts/rust/cpp/security/migration/prior-feedback
     correctly skipped each round.
   - The validation wave killed one plausible-but-wrong finding (iteration 2's "2-char noise pinned
     at top of web results" — refuted on ORDER-sort facts) and corrected two severities. Cheap
     insurance against autonomous fixing of bogus findings.
   - Multi-reviewer corroboration: the exact-ID regression was independently found and *executed*
     by 4 reviewers; convergent evidence made autonomous triage safe.
   - Reviewers consistently ran the code (builds, tests, live CLI invocations, standalone repro
     tests) rather than only reading it; several findings state "verified by execution".
   - The "Considered But Not Flagged" sections proved valuable for the consolidator and for
     cross-checking reviewer overlap — several later-round non-issues were pre-answered there.

## 5. Timeline (wall clock, from message timestamps / harness durations)

| Event | Time (UTC) |
|-------|-----------|
| Iteration-1 review spawned | ~17:45 |
| Iteration-1 reviewer reports arriving | 17:55–18:03 |
| Iteration-1 validators | 18:07–18:08 |
| Iteration-1 consolidated file written | ~18:11 (file named 20-11-49 local, UTC+2) |
| Fix round 1 | ~18:15–18:25 |
| Iteration-2 review (single synchronous run) | ~18:22–18:43 (21 min) |
| Fix round 2 | ~18:47–18:55 |
| Iteration-3 review spawned | ~18:56 |
| Iteration-3 reviewer reports arriving | 19:01–19:09 |
| Iteration-3 orchestrator killed; main-context triage + fix round 3 | ~19:10–19:25 |

End-to-end for the review-fix portion: roughly 100 minutes, of which a substantial share was
consolidator stall/nudge overhead in iterations 1 and 3.

## 6. Cost scrutiny — was the roster warranted? (post-hoc analysis, added 2026-07-03)

Added after the fact from per-agent yield data (Agent Summary tables for iterations 1–2;
raw-report attribution for iteration 3, which has no consolidated table).

| Agent | Iter 1 (found/unique) | Iter 2 | Iter 3 | Drove a verdict or fix round? |
|-------|----------------------|--------|--------|-------------------------------|
| broad | 5 / 2 | 0 / 0 | headline regression (executed repro) + perf hoist | yes, repeatedly |
| knowledge | 2 / 0 | 3 / 1 (incl. the High that flipped the verdict) | headline + 2 unique | yes, repeatedly |
| design | 4 / 0 | 3 / 2 | headline + DESIGN-2 (→ `nibs-es0b`) | yes, repeatedly |
| adversarial | 3 / 1 | 1 / 0 (co-found the High) | headline (executed repro) | yes, repeatedly |
| consistency | 3 / 2 | 2 / 1 | 5 (comment contradictions) | minors only, but unique |
| quick | 1 / 0 | 0 | 0 | no — zero unique output all session |
| test | 1 / 0 | 1 / 0 | 1 unique cosmetic nit | no |
| go | 2 / 0 | 0 | 1 low comment suggestion | no |
| performance | 1 / 0 | 0 | 1 (duplicated by broad) | no |
| spec-compliance | 1 / 0 | 1 / 1 (Low minor) | report lost, never arrived | no (coverage matrix = assurance value) |

Observations:

- **Verdict-driver concentration.** Every verdict-driving finding all session (iteration 1's two
  Mediums, iteration 2's High, iteration 3's regression) came from the same four agents: broad,
  knowledge, design, adversarial. A 5-agent roster (those + consistency) in all three rounds would
  have lost, on this evidence: one Low minor (iteration 2's ordering-docs item, whose facts the
  A2-refuting validator established independently anyway) and two cosmetic nits (iteration 3).
- **Natural ablation.** rev-spec's iteration-3 report was lost entirely; the triage outcome was
  unaffected and nothing had to compensate.
- **Redundant work inside rounds.** ~30 independent build/vet/lint/test runs (one per reviewer per
  wave); the NoOp→Bleve necessity independently re-derived 5×; the ordering-docs claim traced
  end-to-end by 4 agents in iteration 3; corroboration ran past the ×2 validation-waiver threshold
  (headline finding ×4).
- **Iteration 3 was insurance against a fix-time-foreseeable regression.** Iteration 2's Finding #1
  offered a doc-only alternative; the autonomous fixer chose the behavioral charset gate, and its
  own new tests pinned cases on both sides of the exact-ID gap (DESIGN-1: "the gap sits precisely
  between the two pinned cases"). Wave cost [Estimate] ~0.6M–1.1M tokens vs. a fix-time boundary
  probe at tens of k.
- **Build:review ratio.** Building the fix cost ~367k reported tokens (TDD + 3 fix agents);
  reviewing it cost ~2.3M–4M (orchestrators verified + reviewers/validators [Estimate], per §3) —
  roughly 6:1 to 11:1.

Caveats: single session, single changeset — quick/go being dry is only knowable ex-post, and the
hard-gate agents are legitimate ex-ante insurance for a *first* pass. The waste concentrates in
re-dispatching the full uncapped roster against small fix deltas in iterations 2–3.

Resulting skill changes (this repo): `dcc-n87o` (synchronous waves via `run_in_background: false`,
reports as final message), `dcc-n7bm` (conservative re-review rosters — first re-review `mid4`/`mid6`
by fix-delta size and complexity, third-and-later minimal `mid3`), `dcc-6yi4` (fix-round boundary
self-check + least-invasive-fix preference), `dcc-8tbb` (shared pre-flight gates per wave).
