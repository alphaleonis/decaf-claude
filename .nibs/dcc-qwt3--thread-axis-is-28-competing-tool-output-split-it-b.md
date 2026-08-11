---
# dcc-qwt3
version: 1
title: Thread axis is 28% competing-tool output; split it before the pilot reports recall
status: todo
type: bug
priority: high
created_at: 2026-08-11T11:30:28Z
updated_at: 2026-08-11T11:30:28Z
parent: dcc-ho2w
order: "y"
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

- [ ] Thread authors filtered against an explicit bot list, not a name regex; list committed and
      re-derivable per corpus
- [ ] Bot threads retained as a SEPARATE axis ("agreement with incumbent automated review"), never
      pooled with the human axis
- [ ] `score_pooled.py` refuses to emit a pooled thread-recall figure that mixes the two populations,
      with a test that fires
- [ ] METHODOLOGY-v2 §2's independence claim corrected to what the data supports
- [ ] Decide what to do about the 4 citable cells with <=2 human threads
