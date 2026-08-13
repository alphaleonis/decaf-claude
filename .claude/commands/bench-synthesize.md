---
description: Roll every scored v2 subject into a cross-subject comparison — deterministic aggregate, then a published page
---

Build the cross-subject comparison over every **v2** subject scored so far. This replaced the v1
synthesis command; v1's dataset is void and its aggregator reads `v1-archive/` — never point this at
it.

## 1. Aggregate — deterministic, never by hand

```
python3 competition/benchmark/v2/scoring/aggregate_pilot.py \
  competition/benchmark/v2/pooled/<subject> [more subjects …] \
  competition/benchmark/v2/null/<null-subject> \
  -o competition/benchmark/v2/analysis/pilot-data.json
```

It **exits 3 rather than emit a number** when a rule fires. Do not work around a refusal:

- **n ≥ 10 reported clusters** before a precision *ratio* is emitted. Below the floor it writes
  `precision: null` with an explicit `withheld_reason` and the raw counts. This is not conservatism —
  during the pilot a tool's precision moved 1.00 → 0.60 when a second repeat took its denominator
  from 3 to 5.
- **Precision is the median across grading passes**, with the observed range. A single-pass per-tool
  figure is not publishable: judge variance exceeds tool variance at every denominator size.
- **`vintage.check_pooling`** refuses to mix in-window and out-of-window subjects in one figure.
- **The null arm is reported beside the pooled subjects, never averaged in.**
- **`scope.single_app_type`** is emitted into the data. If it is true, the page must say so above the
  numbers — the corpus is designed around size × application type, and a reader must not infer
  breadth from the cell count.

Read the printed summary. Every withheld tool it names must appear on the page as withheld, not
omitted.

## 2. Read the per-subject material

Numbers come from step 1. The *narrative* — what a tool actually caught, where the judge disagreed
with itself, which threads nobody raised — is only in `v2/analysis/PILOT-RESULTS.md` and each
subject's `analysis.json`. Skim them; the specifics are what make a comparison land.

## 3. Write the page

Load `artifact-design` first, and `dataviz` before writing chart code. Sections, each one claim:

1. **Masthead** — thesis headline, standfirst, scope chips (cells / tools / grading passes / findings / clusters / judge / spend).
2. **Scope notice, above the numbers** — application types covered, subject count, whether ranges overlap. Not a footnote.
3. **Headline table** — one row per tool, with a `measured` / `withheld` state. A withheld tool keeps its row and its rank position; the reason goes inline.
4. **Precision with its observed range** — the range across subjects and passes, so overlap is visible rather than asserted.
5. **Signal vs noise** — normalized stacked bars over the **full four-way split**
   (substantive / valid-minor / trivia / false-positive), with absolute findings-per-cell beside
   them. **Do not collapse this to real-vs-wrong.** The whole point of the vocabulary is that these
   tools rarely produce false positives and routinely produce correct-but-immaterial output — a
   two-bucket chart hides the only failure mode that actually separates them, and `trivia_ratio` is
   emitted per tool precisely so this section can exist.
6. **The axes against each other** — precision vs thread recall, because they disagree and a merged score would hide it.
7. **Severity calibration** — P(substantive | the tool called it critical or high), from each cell's
   *tool-reported* severity against the judge's verdict. This is the axis `score_pooled.py`'s
   empty-severity guard exists to protect, so it must actually appear. **Caveat it honestly:** at
   least one tool emits no severity labels of its own on some runs — its extract carries the
   extractor's inference, not the tool's claim — and a calibration figure over inferred severities
   measures the extractor. Exclude those cells and say which.
8. **Cost per real finding.**
9. **What the data supports** — a small number of claims, each traceable to a figure above.
10. **What this may not be used for** — application types not covered, rankings not settled, withheld figures, thread identity, pooling refusals.
11. **Method** — name the aggregator and the rules it enforces by refusing.

Charts: prefer single-hue with identity carried by direct labels — with seven labelled marks there is
no categorical set to cycle and no legend needed. If you do use a categorical palette, run
`validate_palette.js` in both themes and fix FAILs before shipping; do not eyeball ΔE.

## 4. Publish

Publish via the Artifact tool, favicon 🔬, and copy the file to
`competition/benchmark/v2/analysis/pilot-comparison.html` so it survives independently of the
artifact. **Update the existing artifact rather than minting a new one** — pass its URL:

```
https://claude.ai/code/artifact/d3f2021d-ed24-4f82-9315-e74e1effa7ad
```

## Rules

- Never hand-compute a figure. If it is not in `pilot-data.json`, it is not on the page.
- A withheld precision is shown as withheld, with its n. Omitting the row reads as a missing cell.
- Report the judge model and that it is pre-cutoff on most subjects.
- Never present a v1 number, in any form, for any reason.
