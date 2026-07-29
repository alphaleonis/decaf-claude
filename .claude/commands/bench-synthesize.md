---
description: Roll every graded subject into the cross-subject synthesis web page (numbers + conclusions)
---

Build the **cross-subject synthesis** over every subject analyzed so far. Inputs are the committed
`competition/benchmark/analysis/subject-NN/` outputs (`analysis.json`, `metrics.json`, `report.md`).
Output is a single self-contained web page published as an Artifact.

The operator has approved this format (2026-07-28, 9 subjects / 90 runs) — **follow it**. The live
example is `competition/benchmark/analysis/synthesis-report.html`; read it before writing a new one.

## Steps

**1. Aggregate — deterministic, do NOT hand-compute.**
```
python3 competition/benchmark/analysis/scripts/aggregate_synthesis.py \
  -o competition/benchmark/analysis/synthesis-data.json
```
Emits per-tool aggregates, size slices, the bug-catch matrix, and per-cell rows. It prints sanity
checks — **every tool's four tiers must sum to 1.000, and `substantive_share` must equal that tool's
`precision_mean`**. If a check fails, fix it before writing anything.

**2. Read the per-subject `report.md` files.** The numbers come from step 1; the *narrative* (notable
catches, trap subjects, hallucinated or retrieval-driven findings, judge overrides) comes from these.
Skim all of them — the memorable specifics that make the synthesis land are only in there.

**3. Write the page**, following the approved section order. Each section = one claim, a chart, then
one or two short paragraphs:

1. **Masthead** — thesis headline, standfirst, scope chips (subjects / runs / blind-graded / judge model / total spend).
2. **Headline table** — one row per tool; color-code best/worst cells.
3. **Recall** — bug-catch matrix (tool × subject, repeats caught out of 2) *and* an explicit statement
   of how saturated recall is and how few subjects the ranking rests on.
4. **Signal vs noise** — normalized stacked bars (substantive / valid-minor / trivia) plus absolute
   findings-per-run beside them.
5. **False positives** — separate small chart. Report honestly if FP is *not* the differentiator.
6. **Trust** — severity calibration bars, P(substantive | tool said critical/high).
7. **Cost** — scatter of cost/run vs substantive share with direct point labels, then a resource table
   (cost, output tokens, wall, sub-agents, total, $/substantive).
8. **Size** — pooled table. This is the axis the data supports.
9. **Conclusions** — one verdict card per tool: role label ("Best overall", "Best value", …), a short
   honest paragraph, three key figures.
10. **Method & caveats** — bulleted, including what was deliberately *not* concluded.

**4. Publish** via the Artifact tool (load the `artifact-design` skill first; load `dataviz` before
writing chart code). Favicon 🔬. Also copy the file to
`competition/benchmark/analysis/synthesis-report.html` so it survives the scratchpad.

**Update the existing artifact — do not mint a new one.** Pass its URL:

```
https://claude.ai/code/artifact/99994352-ac12-4729-a6dc-29f6309ecdc4
```

Without `url`, a session that did not itself publish the page gets a *new* URL, and the old one
stays live with superseded numbers. That has already happened once: `198955f4-3eb…` is a stranded
2026-07-28 copy carrying the contaminated anthropic figures (#dcc-9kkz) — treat it as dead.

## Non-negotiables

- **Shares, not raw counts**, for every quality comparison. Cluster granularity varies per subject
  (18–95 observed); raw per-run counts are not comparable across subjects.
- **Refuse the language axis** and say why — one subject per language×size cell, so a single odd PR
  would masquerade as a language effect. Size pools 3–4 subjects and *is* reportable.
- **State where conclusions are weak.** Recall has been saturated on most subjects, so the bug-catch
  ranking rests on a couple of hard ones — say so plainly rather than presenting it as settled. The
  operator values the caveat more than the ranking.
- **Lead with the pivot**: finding the escaped bug is near-universal, so the real comparison is what
  *else* each tool reports and how well it filters trivia and false positives. Structure the page
  around that, don't bury it.
- **No long lists of individual bugs.** Numbers and overall performance; cite a specific finding only
  when it illustrates a claim (e.g. a tool that ranked the real bug "low").
- Charts: validated dataviz palette; **max three tiers in a stack** (blue/aqua/yellow passes CVD in
  both modes — adding red for FP fails dark-mode adjacency, so chart FP separately); 2px segment gaps;
  direct % labels; theme-aware tokens under `:root`, `@media`, and `[data-theme]`.
- Treatment is a utilitarian instrument readout, not editorial: system sans + mono pairing, mono for
  every figure, `tabular-nums`, cool near-neutral ground, one blue accent.

## Notes
- Read-only over `runs/` and `subject-NN/` — this command computes and writes up, it never regrades.
- Re-run it whenever new subjects land; the page is meant to be republished to the same Artifact URL.
