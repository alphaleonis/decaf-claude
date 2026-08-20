# The thread axis — what the 120 admitted threads actually are

> **UPDATED 2026-08-20.** Findings 1-4 below stand as written. Two further defects were found in how
> the axis is *counted*, not in what the threads are, and they change the arithmetic in
> "What survives": admission never checked that a thread's subject exists at the checkpoint
> ([[dcc-hw48]]), and duplicate threads split credit between the two origin axes ([[dcc-qfr5]]).
> See **The counting was wrong too** at the end. Finding 4 turns out to have been the second defect
> in plain sight, recorded as an independence problem and never followed through to the scoring.

Census run 2026-08-11. Full classification in `thread-classification.tsv` (one row per thread,
auditable and greppable). Prompted by subject 12's anchor key, where **all 12** review threads failed
the `must_flag` test — which raised the question of whether the pooled corpus's thread axis measures
what METHODOLOGY-v2 §2 says it measures.

**It does not, for 28% of it.** The headline finding is not that threads are nitpicks. It is that a
quarter of the answer key was written by competing automated review tools.

## The premise being tested

§2 justifies the thread axis as the miss detector — the thing pooled adjudication is structurally
blind to — on one specific claim:

> A thread is an independent statement that something was worth raising, written by an expert,
> and *not derived from tool output*.

§5 leans harder still: the threads are "the only scoring signal in the design not produced by an
Opus 5", which is why they are called load-bearing.

## Finding 1 — 28% of admitted threads are tool output

| Author | Threads | What it is |
|---|---|---|
| `copilot-pull-request-reviewer` | 13 | GitHub Copilot code review |
| `greptile-apps` | 4 | Greptile — an AI code-review product |
| `github-code-quality` | 4 | automated lint/quality checks |
| `github-advanced-security` | 3 | CodeQL alerts |
| `graphite-app` | 3 | Graphite's AI review |
| `chatgpt-codex-connector` | 2 | OpenAI Codex review |
| `coderabbitai` | 2 | CodeRabbit — an AI code-review product |
| `vercel` | 2 | Vercel's AI review |
| `hex-security-app` | 1 | automated security scanning |
| **total** | **34 of 120 (28.3%)** | |

`coderabbitai` is a direct member of the product category under test — this repository carries a
`competition/coderabbit-claude-plugin/`. Copilot, Codex, Greptile and Graphite are peers. **Scoring a
tool's recall against these threads measures agreement with incumbent automated review, not recall
against expert human review.** It is the circularity §2 built the thread axis to escape, arriving
through the door nobody checked.

The contamination is real in content, not just in authorship: these are substantive findings —
*"override_flags_definitions is not gated by the internal token check"*, *"vars[0] undefined causing
a runtime crash"*, *"Coalesce is not null-propagating"*. That is what makes them dangerous. A weak bot
comment would be filtered by any quality bar; a strong one is indistinguishable from the human signal
except by author.

### Why the existing filter missed them

`find_candidates.sh:55` filters bots — but only for the **PR author**, never for thread authors, and
`build_pooled_fixture.py` records `author` without ever testing it. Worse, the regex
(`(?i)bot$|\[bot\]|renovate|dependabot`) matches **none of the nine names above**. So even applying it
at thread level would have changed nothing. Verified by running it against each login.

## Finding 2 — contamination is wildly uneven, so cells are not comparable

| Subject | Admitted | Bot | Bot share |
|---|---|---|---|
| `element-hq/element-web#32964` | 5 | 4 | **80%** |
| `grafana/grafana#117615` | 7 | 5 | **71%** |
| `sveltejs/kit#15685` | 3 | 2 | **67%** |
| `PostHog/posthog#55149` | 35 | 15 | 43% |
| `mattermost#36824` | 6 | 2 | 33% |
| `PostHog/posthog#52408` | 19 | 4 | 21% |
| `grafana/grafana#124181` | 6 | 1 | 17% |
| `dotnet/efcore#34127` | 11 | 1 | 9% |
| `immich#24627`, `immich#28886`, `jellyfin#12834`, `prometheus#18081` | 28 | 0 | **0%** |

Four subjects have none; three are majority-bot. A thread-recall number therefore means something
different in each cell, and cross-subject pooling of that axis is not defensible as it stands.

## Finding 3 — what the threads say, once separated

Classified against the same `must_flag` standard the anchor keys use: does the thread state a
specific thing that is wrong, missing, or broken (`defect`), propose a nicer alternative without
claiming the current form is wrong (`preference`), ask rather than assert (`question`), or neither
(`other` — praise, process, self-review)?

| Population | n | defect | preference | question | other |
|---|---|---|---|---|---|
| Bot-authored | 34 | **29 (85%)** | 5 (14%) | 0 | 0 |
| Human-authored | 86 | 44 (51%) | 26 (30%) | 10 (11%) | 6 (6%) |
| Human, excluding the single dominant author | 55 | **15 (27%)** | 24 (44%) | 10 (18%) | 6 (11%) |

Two things follow. The bots are *better* at stating defects than the humans by this measure, which is
exactly why their presence inflates the axis. And the human defect rate is dominated by one reviewer:
`haacked` supplies 31 of 86 human threads (36%) and 29 of 44 human defects (66%), all on two PostHog
PRs, written in strict conventional-comments style (`blocking:` / `suggestion:` / `nit:`). Remove that
one author and the human defect rate falls from 51% to **27%**.

⚠️ **Whether that author's threads are themselves AI-assisted is not determinable from the data, and
that is itself a finding.** The "not derived from tool output" premise is unverifiable for any human
account in an era where reviewers use AI assistance routinely. The axis can be defended as "what
expert reviewers chose to say", never as "what unaided humans found."

## Finding 4 — 9 human threads restate a bot thread

Nine of 86 human threads sit within ±3 lines of a bot thread on the same file, several at the exact
same line: `types.rs:713` (haacked / Copilot), `flags.rs:172` vs `:171` (haacked / Greptile),
`point_in_time_properties.py:80` vs `:81` (haacked / Copilot). Independent discovery and restatement
are indistinguishable here, so the human and bot populations are not fully independent either.

## What survives

Apply both filters — drop bot threads, and drop the five in-window subjects the vintage rule already
makes unpoolable (§5):

| | threads |
|---|---|
| admitted, all 12 subjects | 120 |
| human-authored | 86 |
| on the 7 citable subjects | 44 |
| **human-authored AND citable** | **30** |

**Four of the seven citable subjects have ≤2 human threads** (element-web 1, sveltejs 1,
grafana#117615 2, immich#28886 2). So the reportable thread axis is ~30 items, unevenly spread, with
four cells too thin to carry a per-cell recall number.

> **The 30 is a pre-correction count.** It counts admitted human threads without asking whether any
> could be matched at the checkpoint. On the six subjects since annotated, matchability removes 13 of
> 48 human threads (27%), and grafana#117615 loses both of its two. The corrected figure for the full
> 12-subject corpus is not yet known — six subjects remain unannotated — so **30 is an upper bound,
> not a count.** See "The counting was wrong too" below.

## Recommended disposition

1. **Filter thread authors against a real bot list, not a regex on the name.** The nine logins here
   are the seed; maintain it explicitly and re-derive per corpus rather than pattern-matching.
2. **Do not delete the bot threads — split them into a second axis.** "Agreement with incumbent
   automated review" is a legitimate and interesting measurement; it simply is not the miss detector,
   and must never be pooled with the human axis.
3. **Report the human thread axis per subject, never pooled**, until the thin cells are addressed.
4. **Correct §2's independence claim** to what the data supports.

Filed as `dcc-qwt3` — since implemented: every thread in the corpus carries `origin: human|bot`,
classified by GitHub GraphQL actor type into the committed `v2/pooled/bot-authors.json`
(`derive_bot_authors.py` re-derives it per corpus; `annotate_thread_origin.py` applies it).
`score_pooled.py` computes `thread_recall` over human threads only, scores bot-thread hits as a
separate `incumbent_agreement` axis, stamps `human_axis_thin` on the four ≤2-human-thread cells
(reportable per subject with n shown, never pooled), and refuses to score an admitted thread whose
origin is unstamped. The derivation also found a **tenth** bot the census's admitted-only scope did
not cover: `cursor`, one *rejected* thread on grafana#117615 — nothing admitted changes, but it is
one more login no name regex would have caught.

## Limits of this census

- **The classifier is an Opus 5** — the same model family as the judge. Classification is a judgment
  call at the preference/defect boundary (e.g. is "AtTimeZone, Collate" a missing-case defect or a
  discussion fragment?), and a different classifier would move some rows. The bot/human split, the
  per-subject counts and the co-location count are mechanical and not subject to that.
- **Authorship is a proxy for provenance.** It reliably identifies tool output posted under a bot
  account; it cannot identify tool output posted under a human account.
- Every row is in `thread-classification.tsv` so any disputed call can be found and re-argued.

## The counting was wrong too (added 2026-08-20)

The census above asked what the threads *are*. It did not ask whether a tool could have matched them,
or whether two threads were the same item. Both turned out to be wrong, and both deflated every arm
equally — which is why neither showed up as an anomaly in any comparison.

### Defect A — admission never tested whether the thread's subject exists ([[dcc-hw48]])

`admission` is a line-position test: "line inside a changed hunk at the checkpoint". A thread written
three pushes later, about code introduced two pushes later, is admitted whenever its line lands in a
changed hunk. Those threads cannot be raised by a reviewer looking at the checkpoint, so they enter
the denominator and count against every arm.

Every admitted thread in the corpus now carries `matchable_at_checkpoint`, decided by a judgment pass
that reads the checkpoint code and is blind to the pool:

| subject | human admitted | matchable | excluded | share lost |
|---|---|---|---|---|
| `PostHog/posthog#55149` | 20 | **13** | 7 | 35% |
| `dotnet/efcore#34127` | 10 | **8** | 2 | 20% |
| `prometheus#18081` | 10 | **9** | 1 | 10% |
| `mattermost#36824` | 4 | **3** | 1 | 25% |
| `immich#28886` | 2 | **2** | 0 | 0% |
| `grafana#117615` | 2 | **0** | 2 | 100% |

**The loss scales with post-checkpoint review activity.** PostHog#55149 was reviewed across 12
commits over three weeks and loses 35%; prometheus was reviewed largely at its checkpoint commit and
loses 10%. So this penalized precisely the subjects selected for having rich review histories — the
population the corpus deliberately seeks. The checkpoint rule makes it worse by construction: it is
"the commit the earliest review comment was written against", which maximizes the number of later
pushes.

The obvious mechanical fix does not work, and was measured not to. Looking up the code tokens a thread
quotes in the thread's own file at the checkpoint would have **wrongly excluded 4 threads whose
defects the pool credited** on PostHog#55149 while catching only 2 of the 10 real cases: threads quote
error strings from earlier drafts, name symbols living in other files, and often describe behavior
without quoting anything. `annotate_thread_matchability.py` therefore emits a worksheet with that
lexical evidence as a *hint* and refuses to invent verdicts.

Compound threads need care. One efcore thread's quoted suggestion restructures a block absent at the
checkpoint, while its closing sentence — "move `nullPropagatedOperands` below" — describes an ordering
that **seven arms** reported and that is present at `SqlNullabilityProcessor.cs:580-583`. The rule is
**matchable if ANY claim targets present code**; the first pass got it wrong and the cross-check below
caught it.

### Defect B — duplicate threads split credit across the two axes ([[dcc-qfr5]])

**This is Finding 4, followed through.** The census found "9 human threads restate a bot thread" and
recorded it as a threat to population independence. It is also a scoring defect, and the larger one:
a cluster carries one `matches_thread`, so when a bot and a human raise the same defect at the same
line, one thread is credited and the other reads as missed. Because `thread_recall` counts human
threads and `incumbent_agreement` counts bot threads, the tie-break moves credit **between two axes
that are reported separately and must never be merged**.

The grader broke ties by earliest index. On a review-disciplined repo the scanners comment within days
and the humans arrive later, so "earliest" is a systematically bot-biased rule.

Measured on PostHog#55149 — three human threads read as missed while their defects had been found:

| human thread | credited instead | shared defect | arms that found it |
|---|---|---|---|
| T38 `point_in_time_properties.py:80` | T23 (bot) | `except Exception: raise` is a no-op | 4 |
| T44 `api/types.rs:713` | T24 (bot) | `matched` set from `all_properties_matched` | 4 |
| T45 `handler/flags.rs:172` | T27 (bot) | `*flag = override_flag` replaces identity fields | 2 |

All three pairs are on the census's own co-location list. Threads now carry `thread_group`; recall is
computed over groups, and a group credits the human axis if any member is human and the incumbent axis
if any is bot — independently, since the axes are separate anyway. Grouping also collapses same-axis
duplicates: grafana#117615 has a bot/bot pair (the same non-idempotent `quoteIdentifierIfNecessary`
raised at two call sites), which inflated a denominator without shifting it.

### What the correction did to the numbers

Not one-directionally, which is the evidence it is unbiased. On PostHog#55149 every arm roughly
doubled (`ours-review` 0.450 → 0.846, `ours-bugs` 0.200 → 0.385) — about a third of that from
grouping and two thirds from matchability. prometheus rose slightly; **mattermost fell** on every arm
(0.750 → 0.667, losing a hit and a denominator slot); efcore split until the compound-thread verdict
was fixed. grafana#117615 went from `0.000` on four arms to `null`, which stops it dragging pooled
averages as though four arms had failed.

### A permanent cross-check

A cluster credited to a thread judged unmatchable is a contradiction — a tool cannot match a comment
about code that does not exist. `score_pooled.py` now reports `credited_to_unmatchable_thread` and
warns on stderr. It found four on the first run: one real annotation error (the efcore compound
thread, which had silently cost seven arms a hit) and three loose *grading* matches that remain open —
a `== true` style cluster credited to a thread asking for `is null` on a line with no `== null`; a
decoder-placement cluster credited to a logger-context request; an inert-test-values cluster credited
to a missing-integration-test request. It reports rather than refuses, because which of the two
judgments is wrong differs case by case.

### Consequence for §2 and for any published figure

Every thread-recall figure computed before 2026-08-20 rests on an inflated denominator and, where the
subject has duplicate threads, on credit assigned to the wrong axis. `thread_axis_publishable` now
travels in each subject's metrics and is false unless every admitted thread carries a matchability
verdict — absent annotation is **not** read as "all matchable", because that is the assumption this
correction removes.
