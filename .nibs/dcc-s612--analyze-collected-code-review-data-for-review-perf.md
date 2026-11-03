---
# dcc-s612
version: 1
title: Measure review yield, outcome, token cost and runtime across the collected code-review corpus
status: in-progress
type: research
created_at: 2026-11-02T14:40:59Z
updated_at: 2026-11-03T20:27:18Z
order: zzzzzzzw
---

Extract a structured dataset from `code-review-reports/`, then write an analysis of review effectiveness, token cost and runtime that ends in recommendations for review defaults.

## Goal

Find ways to make reviews more effective along three axes:

- **Findings:** real issues found, and how many survive to a fix. This is the constraint; no recommendation may trade it away.
- **Token cost:** the primary thing to reduce, in raw tokens, not dollars, because the operator is on a subscription.
- **Runtime:** wall-clock duration; secondary.

Every recommendation is a candidate to cut tokens or runtime, or to raise findings, and must show what it would cost in findings. For example, a reviewer proposed for removal is shown with the findings only it produced. The recommendations are input for a later discussion, not decisions; changing a default is a separate follow-up nib.

## Approach

1. **Extract.** `code-review-reports/analysis/extract.py` (stdlib Python, run with `-I`) parses every report and session README into CSVs. It handles every table layout in the corpus: per-agent `Agent | Issues Found | Unique Issues` (1049 files), per-agent `Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings submitted` (245 files), the four session iteration-table layouts, and the prose token figures in 6 READMEs.
   - `reports.csv`: one row per report (1003 standalone reports plus the 48 lacy iteration files): project, date, preset, roster, scope (files, lines), verdict, finding counts by severity.
   - `agents.csv`: one row per agent per report: findings, unique findings, tokens, tool calls, duration where present.
   - `sessions.csv`: one row per session iteration, joined to its report through `session-iterations.tsv`: fixed, dismissed, skipped, deferred counts and validation results.
2. **Settle the orchestrator question.** Determine whether an orchestrator agent's token count includes its reviewers' tokens, from reports that list both: an orchestrator figure below the sum of its reviewers' figures cannot include them. Record the answer before summing tokens across agents.
3. **Write `code-review-reports/analysis/ANALYSIS.md`** with these sections: corpus and extraction coverage; token use by preset, roster size, reviewer, model tier, iteration and role (implementer vs. review); yield (findings and unique findings per reviewer); outcome (fixed vs. dismissed, validation refutations) as a stand-in for precision; iterations to settle and duration; tokens per finding and per fixed finding; per-project breakdown; limits; recommendations.

Constraints on the analysis:

- **Prior evidence.** Each recommendation states whether it confirms, contradicts or measures something different from the prior measurements on the unmerged `tuning` branch: nib `dcc-2a8i` (per-reviewer yield, e.g. adversarial-reviewer 1.85 vs. broad-reviewer 0.78) and `reports/2026-07-04-cross-session-analysis.md` (4 sessions). `dcc-2a8i` predates the voiding of benchmark v1; establish whether its runs were v1 before relying on it. Never cite a benchmark v1 figure.
- **Lacy.** Include lacy in pooled figures, but break every result down by project, and call out lacy wherever it moves a pooled number: it is a different codebase run with `--models high`.
- **Recall is out of reach.** The corpus records what reviews found and what happened to it, not what they missed. Say so wherever a recommendation leans on findings.

## Context

Collected on 2026-11-02 (topped up 2026-11-03) on the `analysis` branch from every project under `~/code/**`, plus a work project (`lacy/`) imported from `code-review-session-reports-2026-11-03.zip`:

- 1003 `CODE_REVIEW_*.md` reports in `code-review-reports/<project>/` (bibbla 512, lotsen 201, nibs 181, mazewebsite 50, erinra-mcp 22, ai-journal 15, lacy 14, vps 6, bgt 2), from both `.decaf/code-reviews/` and the older `.code-reviews/`.
- 148 session-report READMEs in `code-review-reports/<project>/session-reports/<session>/README.md` (bibbla 44, lotsen 60, lacy 29, nibs 15). Each one covers one auto-code-review loop and has per-agent token figures, tool calls, durations and per-agent yield.
- `code-review-reports/session-iterations.tsv` maps each session iteration to its `CODE_REVIEW_*.md`. The session iteration files were byte-identical copies of those reports, so they were not copied. The READMEs do not name their reports. Exception: the lacy archive did not include its sessions' reports, so its 48 iteration files are kept in the session folders and the TSV points to them.

Known limits of the data:

- Token figures exist only from about 2026-09 onward: 200 reports have a per-agent `Tokens` table (bibbla 76, lotsen 92, nibs 17, lacy 14, mazewebsite 1), plus the 148 session READMEs and the 48 lacy iteration files. The other reports have no cost data.
- The report and README layouts changed over time (e.g. 143 of the 148 READMEs give token figures in a table, the other 5 in sentences, some as bare `tokens / tool calls / duration` triples), so parsing has to handle several formats.
- One lotsen README notes it is unverified whether an orchestrator agent's token count includes its reviewers' tokens. Settle this before summing across agents.

## Acceptance

- [x] [run] `python3 -I code-review-reports/analysis/extract.py` — expect: exit 0; writes `reports.csv`, `agents.csv`, `sessions.csv` in `code-review-reports/analysis/`
- [x] [run] `python3 -I -c "import csv;print(sum(1 for _ in csv.DictReader(open('code-review-reports/analysis/reports.csv'))))"` — expect: `1051`
- [x] [run] `python3 -I -c "import csv;r=list(csv.DictReader(open('code-review-reports/analysis/sessions.csv')));print(len(r), sum(1 for x in r if not x['report']))"` — expect: `231 0`
- [x] [run] `python3 -I code-review-reports/analysis/extract.py --check` — expect: exit 0; every file with a `Tokens` table or prose token figures has a non-zero token total, and every file the parser skipped is listed with a reason
- [x] [run] `grep -c -E '^## ' code-review-reports/analysis/ANALYSIS.md` — expect: 9 or more
- [x] [run] `grep -c -E 'dcc-2a8i|2026-07-04-cross-session' code-review-reports/analysis/ANALYSIS.md` — expect: 2 or more, with each name matched at least once
- [ ] [manual] Each recommendation cites the figures it rests on, states its effect on findings, tokens and runtime, and states how it relates to the prior measurement it touches. Reason: whether an argument follows from its evidence is a judgment call.
- [ ] [manual] The orchestrator token question is answered with the reports used as evidence. Reason: the answer may be "cannot be determined", which only a reader can accept or reject.

## Follow-up
Follow-up work from the analysis and the operator walk-through on 2026-11-03 is under epic dcc-b578: dcc-k163, dcc-zsxg, dcc-zkwo, dcc-ysx8, dcc-6rza, dcc-lwo7.

## Corpus removed before merge
The corpus, the extraction and analysis scripts, ANALYSIS.md and the severity re-rating files were removed before the merge to main, because the collected reports may hold confidential material. They survive only in the local `analysis` branch history; the paths below no longer resolve on main.
