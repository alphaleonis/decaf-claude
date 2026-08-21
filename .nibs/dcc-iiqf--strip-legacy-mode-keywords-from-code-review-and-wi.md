---
# dcc-iiqf
version: 1
title: Strip legacy mode keywords from code-review and wire the axis surface through every caller
status: completed
type: task
priority: high
created_at: 2026-08-21T07:39:00Z
updated_at: 2026-08-21T07:46:11Z
order: zzzzk
---

Two changes, one surface.

## 1. Drop the legacy mode keywords

`code-review` still resolves `low`/`quick`, `mid`/`std`, `high`, `max` and the `modeN` roster-cap
suffix (`mid4`, `high6`, `max8`). They predate the preset + four-axis model and are now a second
vocabulary for the same space — three names for `review models=high`, and a suffix form that only
exists because the old keywords had nowhere to put a roster.

Nothing in the corpus is measured under the legacy names: the benchmark arms invoke `bugs`,
`review`, `audit` and explicit axes. Removing them costs no evidence and removes the ambiguity where
`mid4` and `review roster=4` are the same thing written twice.

## 2. Wire the axes through every caller

`--review` currently takes a bare preset in `auto-dev`, `auto-tdd`, `batch-dev` and `auto-deliver`,
so **none of the four axes can be reached from any of them**. Tuning is only possible by invoking
`/code-review` by hand, which is exactly the situation that makes real-world feel hard to get.

Design: `--review` takes the preset **plus any axis overrides**, forwarded verbatim to
`/code-review`. One flag, code-review's own grammar, no second vocabulary, and no caller needs
editing again when an axis is added or changed.

    --review audit
    --review "review roster=6 reach=narrow"
    --review "bugs reach=norm"

## Done 2026-08-21

One behavior change worth naming, because removing the legacy names was not purely cosmetic:
**`low` carried real pipeline skips** — it clustered inline, skipped the Step 4.95 screen, and
skipped the Step 5.6 validation wave, all justified by "speed is the point". With `low` gone those
skips had no mode to attach to. Keeping them keyed on `roster=2` would have meant `review roster=2`
silently producing unvalidated findings, which is exactly the hidden second vocabulary this nib
removes. So they are re-keyed on mechanics instead:

- clustering skips when there is one report (`bugs`) and runs inline when there are two
- the screen and the validation wave skip only on the single-seat `bugs` path

`bugs` is now the fast path and earns its skip structurally — one seat, self-calibrated anchors,
nothing to cross-check — so `low`'s niche is absorbed rather than lost. A two-seat *wave* now keeps
its screen and validation, which costs more than `low` did and is the correct trade: its agents do
not calibrate their own anchors.

Also re-keyed off the dead mode: the `broad-reviewer` model rule now reads "at the two-agent floor,
broad always inherits the session model", which is what it always meant.

## Acceptance

- [x] No legacy mode keyword resolves anywhere in `decaf-quality` or `decaf-build`
- [x] `code-review`'s argument-hint and Argument Parsing describe only the preset + four axes
- [x] `auto-code-review` accepts and forwards the full spec, and its internal re-review presets are
      written in the new grammar
- [x] `auto-dev`, `auto-tdd`, `batch-dev`, `auto-deliver` accept axis overrides on `--review` and
      forward them
- [x] No skill still defaults to `std`/`mid` in prose
- [x] READMEs match

Historical `reports/` are left untouched: they record runs that happened under the old vocabulary,
and rewriting them would falsify the record.

## Summary

**Completed 2026-08-21** — Legacy mode keywords removed from `code-review` — the `Legacy mode keywords` section, the `modeN`
roster-cap suffix, and every `low`/`mid`/`high`/`max` reference through the execution steps, rewritten
onto the preset names. `mid` as a MODEL TIER is untouched; only the mode sense was overloaded.

One real behavior change fell out: `low` carried pipeline skips (inline clustering, no screen, no
validation wave) that had no mode to attach to once it was gone. Re-keyed on mechanics — clustering
on report count, screen and validation on the single-seat `bugs` path — rather than on `roster=2`,
which would have made `review roster=2` silently skip validation.

`--review` in `auto-dev`, `auto-tdd`, `batch-dev` and `auto-deliver` now takes a preset plus any axis
overrides and forwards the whole string verbatim; none of them interpret the axes, so a new one works
the day `/code-review` ships it. `auto-code-review` gained the same pass-through as `reviewSpec` and
its internal re-review presets are written in the new grammar. All four `--review` defaults were
saying `std`; they now say `review`.

READMEs updated at all three levels. `reports/` deliberately untouched — those record runs that
happened under the old vocabulary.
