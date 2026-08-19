---
# dcc-tmz2
version: 1
title: Does reach=narrow shorten exploration? Single-seat bugs at reach=norm, 3 repeats, found-per-cell
status: in-progress
type: task
priority: high
created_at: 2026-08-18T19:14:54Z
updated_at: 2026-08-18T19:24:35Z
parent: dcc-hyxw
order: arz
---

[[dcc-n5h2]]'s second question, now the load-bearing one: **does the `narrow` framing shorten the
seat's exploration?** Today's five-subject evidence eliminated the alternative explanation.

## Why this is now the question

Superpowers reported 16 defect-class clusters that `bugs` v3 (`ours-bugs-sp3`) did not. Only **3
were demoted** by `bugs`; the other **13 it never found**. Of the 6 real ones among those 13, five
sit **inside changed hunks** — squarely within what `reach=narrow` is defined to cover ("defects
introduced by the changed lines"):

| cluster | sev | in a changed hunk |
|---|---|---|
| efcore e02 | critical | yes |
| efcore e03 | high | no (same file, 61 lines out) |
| prom c03 | medium | yes |
| prom c07 | medium | yes |
| mattermost ma15 | medium | yes |
| mattermost ma26 | medium | yes |

So `narrow` does not excuse them on scope grounds. Either the seat looked and said nothing, or it
never looked. No parking rule, closed-set label or fail-closed trigger reaches a defect that was
never examined — which is why three brief revisions ([[dcc-1sbc]], [[dcc-pulk]], [[dcc-ce0m]]) left
per-cell yield flat at 3.0/3.0/3.0 on prometheus.

efcore **e02** (Critical: a search-condition THEN loses NULL, so NULL becomes false) is the sharpest
case: found in **both** brief-v1 repeats, absent from **all five** v2/v3 repeats, because the v1
seats generated SQL Server SQL and later ones did not. Now confirmed a fourth time with the reach
explanation ruled out.

## Design

Arm `ours-bugs-reachnorm` = `bugs reach=norm`, everything else identical to today's `bugs`.

- Subjects: **prometheus-18081** and **dotnet-efcore-34127** — the two with deep pools and the two
  carrying the named misses. 3 repeats each.
- **Re-run the `narrow` control here too** (`ours-bugs`, 3 repeats, same two subjects). Two reasons:
  the corpus rule "never compare a changed brief against old cells", and the `bugs-sp3` transcripts
  ran on the previous machine and did **not** travel — this comparison is about *what the seat
  looked at*, which only transcripts answer.
- 12 cells total. At the pooled `bugs` rate (~$5.46/cell) roughly **$65-80**; operator-gated.

## Primary readout — found, not reported

`reach` changes what is *reportable*, so a reported-side metric would confound disposition with
detection. Measure:

- **real defects FOUND per cell** (reported + demoted), against each subject's pool
- **per-named-cluster**: was e02 / e03 / c03 / c07 examined at all, in either arm
- from transcripts (`v2/scoring/cost_emit.py` classifies calls): files read, shell calls, build/test
  runs, `ToQueryString`-style probe invocations per cell — the [[dcc-n5h2]] question 1 comparison
- secondary: cost/cell, class distribution, reported volume (expected to rise under `norm`; not the
  point)

## The falsifiable prediction

If `narrow` shortens exploration, `norm` cells find **more real defects per cell**. If found-per-cell
is flat between the arms, exploration is not reach-driven and the cause is seat probing variance —
which redirects to [[dcc-n5h2]]'s third question (a cheap second-pass "what did you not look at"
turn) rather than to any axis change.

Either outcome is publishable and closes a question three brief revisions could not.

## Rules that bind

- 3 repeats minimum; 2 could not separate brief effect from seat variance ([[dcc-ce0m]]).
- New arm id; never fold a changed configuration under an existing one ([[dcc-u10u]] hit this).
- Class table + real-defect pool are the readouts, not precision — `bugs` never reaches n=10
  reported clusters on any subject, so it has no publishable precision by construction.
- Report judge calibration on the grading day ([[dcc-n4nf]]); defect recall must be cited with its
  pool size, which this fold-in will move again ([[dcc-dirp]]).

## Acceptance

- [ ] 12 cells CLEAN, committed, transcripts retained on this machine
- [ ] Found-per-cell compared between `narrow` and `norm`, 3 repeats, both subjects
- [ ] Per-cluster: was e02/e03/c03/c07 examined, in either arm
- [ ] Transcript comparison of exploration (files read, probes run) written up
- [ ] Verdict stated: is `narrow` the cause, or is it seat variance — and what follows
