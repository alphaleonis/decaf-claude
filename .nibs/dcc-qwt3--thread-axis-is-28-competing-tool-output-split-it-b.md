---
# dcc-qwt3
version: 1
title: Thread axis is 28% competing-tool output; split it before the pilot reports recall
status: completed
type: bug
priority: high
created_at: 2026-08-11T11:30:28Z
updated_at: 2026-08-11T12:01:12Z
parent: dcc-ho2w
order: 8g
---

The pooled corpus's thread axis is justified in METHODOLOGY-v2 §2 as the miss detector, on the claim
that a thread is *"an independent statement... not derived from tool output"*. §5 leans harder: the
threads are "the only scoring signal in the design not produced by an Opus 5".

**34 of the 120 admitted threads (28.3%) were written by automated review tools** —
`copilot-pull-request-reviewer` (13), `greptile-apps` (4), `github-code-quality` (4),
`github-advanced-security` (3), `graphite-app` (3), `chatgpt-codex-connector` (2), `coderabbitai` (2),
`vercel` (2), `hex-security-app` (1).

`coderabbitai` is in the product category under test (this repo carries
`competition/coderabbit-claude-plugin/`). Copilot, Codex, Greptile and Graphite are peers. Scoring
recall against these threads measures agreement with incumbent automated review, not recall against
expert human review.

Full census and per-thread classification: `v2/analysis/THREAD-AXIS.md` and
`v2/analysis/thread-classification.tsv`.

## Why the filter missed it

`find_candidates.sh:55` filters bots for the **PR author only**; `build_pooled_fixture.py` records
`author` and never tests it. And the regex `(?i)bot$|\[bot\]|renovate|dependabot` matches **none** of
the nine logins — verified by running it. So applying the existing filter at thread level would have
changed nothing.

## What it costs

- **Uneven contamination breaks cross-cell comparison**: bot share runs 0% (4 subjects) to 80%
  (element-web 4/5, grafana#117615 5/7, sveltejs 2/3).
- **Bots state defects at 85% vs humans at 51%** (27% excluding one dominant author), so their
  presence inflates the axis rather than merely diluting it.
- **After both filters — bots dropped, in-window subjects dropped — the axis is 30 threads**, and
  4 of the 7 citable subjects have <=2.

## Acceptance

- [x] Thread authors filtered against an explicit bot list, not a name regex; list committed and
      re-derivable per corpus
- [x] Bot threads retained as a SEPARATE axis ("agreement with incumbent automated review"), never
      pooled with the human axis
- [x] `score_pooled.py` refuses to emit a pooled thread-recall figure that mixes the two populations,
      with a test that fires
- [x] METHODOLOGY-v2 §2's independence claim corrected to what the data supports
- [x] Decide what to do about the 4 citable cells with <=2 human threads

## Summary

**Completed 2026-08-11** — Split the thread axis into two populations, enforced by construction. Every thread in the pooled
corpus now carries `origin: human|bot` (86 human / 34 bot admitted — exact census match), classified
by GitHub GraphQL actor `__typename` against the committed `v2/pooled/bot-authors.json` —
`derive_bot_authors.py` re-derives it per corpus (REST `users/` is unusable: it resolves same-named
orgs or 404s; GraphQL types the actual actor), `annotate_thread_origin.py` applies it and refuses
unknown authors. Two hand-audited facts surfaced: `hex-security-app` was renamed `parameter-app`
(recorded in the list's `manual` section, preserved across re-runs) and a TENTH bot the census's
admitted-only scope missed — `cursor`, one rejected thread on grafana#117615.

`score_pooled.py`: `thread_recall` is human-only; bot hits score a separate `incumbent_agreement`
(+`_found`) axis; corpus miss-detector and judge-calibration fields are human-only; an admitted
thread without origin is a DataDefect (exit 3). Six new self-tests, all watched fail first (the
mixed-population recall really did read 0.333 where human-only reads 0.5). `build_pooled_fixture.py`
stamps origin at build time; a deleted author gets origin null, which the scorer refuses rather than
defaulting into either axis.

## Key Decisions

- Bot threads are retained as a fourth axis ("agreement with incumbent automated review"), never
  deleted and never pooled with the human axis.
- Thin cells (4 citable subjects with ≤2 human threads): KEEP the cells — pooled/anchor axes are
  unaffected. Their recall is emitted but stamped `threads.human_axis_thin` (n ≤ 2); reportable per
  subject with n shown, never pooled or headlined. Threshold is THIN_HUMAN_AXIS_MAX = 2.
- The blind grader now must not see thread `author`/`origin` (bench-analyze-v2), so a judge cannot
  grade a thread differently for being bot-authored; bot threads are still matched — they score the
  incumbent axis.
- METHODOLOGY-v2 §2/§5 corrected to "holds by construction" rather than by assumption.
