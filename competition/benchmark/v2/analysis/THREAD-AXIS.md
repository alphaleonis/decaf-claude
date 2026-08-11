# The thread axis — what the 120 admitted threads actually are

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

## Recommended disposition

1. **Filter thread authors against a real bot list, not a regex on the name.** The nine logins here
   are the seed; maintain it explicitly and re-derive per corpus rather than pattern-matching.
2. **Do not delete the bot threads — split them into a second axis.** "Agreement with incumbent
   automated review" is a legitimate and interesting measurement; it simply is not the miss detector,
   and must never be pooled with the human axis.
3. **Report the human thread axis per subject, never pooled**, until the thin cells are addressed.
4. **Correct §2's independence claim** to what the data supports.

Filed as `dcc-qwt3`.

## Limits of this census

- **The classifier is an Opus 5** — the same model family as the judge. Classification is a judgment
  call at the preference/defect boundary (e.g. is "AtTimeZone, Collate" a missing-case defect or a
  discussion fragment?), and a different classifier would move some rows. The bot/human split, the
  per-subject counts and the co-location count are mechanical and not subject to that.
- **Authorship is a proxy for provenance.** It reliably identifies tool output posted under a bot
  account; it cannot identify tool output posted under a human account.
- Every row is in `thread-classification.tsv` so any disputed call can be found and re-argued.
