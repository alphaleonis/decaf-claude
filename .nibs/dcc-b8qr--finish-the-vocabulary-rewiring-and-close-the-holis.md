---
# dcc-b8qr
version: 1
title: Finish the vocabulary rewiring and close the holistic code-review gaps (dcc-rrmo findings)
status: completed
type: task
created_at: 2026-08-21T08:02:45Z
updated_at: 2026-08-21T08:09:36Z
order: zzzzw
---

Findings from the prose review of 5cd5e7a / 94b9408 (nib dcc-rrmo). Two groups.

## Vocabulary rewiring leftovers

- [x] 1. Root README.md:169,190 — `--review high` / `--review max` examples are dead vocabulary; now silently reinterpreted as instructions
- [x] 2. Agent files still gate on `max`: cpp/dotnet/go/rust/typescript reviewers (description + hard-gate line), test-reviewer, prior-feedback-reviewer, spec-compliance-reviewer, data-migration-reviewer; plus conventions/persona-authoring.md:27
- [x] 3. conventions/code-review-consolidation.md step 8 — "skipped in low mode" + retired single-finder validation-selection rule; step 5 gate lacks the screen carve-out
- [x] 4. decaf-quality/README.md decision 12 — mode keywords; false "evidence and reach not yet settable"
- [x] 5. code-review/SKILL.md residuals: axes intro l.25 ("mode keyword"), l.334 `mode<N>`, duplicated stale example l.911, "mode" wording l.265/l.432, report-header field naming
- [x] 6. auto-code-review/SKILL.md:288 literal `mid (modified files)`; conventions/session-report.md:70,97 "Mode"
- [x] 7. bugs-sp contradiction: SKILL.md l.16 (one vocabulary) vs l.129 ("remains an alias") — resolve one way
- [x] 8. SKILL.md:409 stale models=low parenthetical (bugs pairs low with evidence=strong — wave is evidence=norm)
- [x] 9. auto-code-review:76 re-review cap line contradicts Step 5.4 (review roster=3–6 vs review roster=4/6/uncapped then bugs roster=3)
- [x] 10. Spellings introduced in 5cd5e7a: "unrecognised" (SKILL.md:16), "honour" (batch-dev:43)

## Holistic gaps

- [x] 11. Step 4.95 skip condition circular (needs scores it does not have yet); Step 5.6 score-based selection silently loses inputs when the screen skipped
- [x] 12. Step 5.5 promotions have no screen score — Step 5.6 selection/waiver cannot classify them; add explicit always-validate rule
- [x] 13. Anchor-50 non-Critical findings (bugs path emits them) have no action row in auto-code-review triage; check resolve-code-review for the same assumption
- [x] 14. solo-reviewer.md l.209 permits untagged CBNF process notes; skill counts untagged entries as malformed — reconcile
- [x] 15. Minor: Validation header value for the zero-primaries skip; re-reviews silently drop --spec (state the intent); "within 15 points of the bar" ambiguous for corroboration-admitted clusters

## Key Decisions
- `bugs-sp` is fully retired, not restored as a parsed alias — "one vocabulary" (5cd5e7a) is the newer, deliberate statement; the bugs-path prose now says the name is retired.
- The evidence=any screen skip is re-keyed on finder anchors (skip only when every cluster's finders anchor ≥50): anchor 25 and screen 25 name the same could-not-verify state, so anchors are the ex-ante signal the old circular condition lacked.
- Step 5.6 gains a no-screen-score rule: Step 5.5 promotions and skipped-screen clusters are always validated (nothing to waive against).
- Anchor-50 non-Critical findings (bugs path only): High@50 defers (human decides, mirroring Critical@50), Medium/Low@50 skips to awareness — in both auto-code-review and resolve-code-review.
- CBNF process notes get a fifth tag `[probe]`, excluded from the malformed-entry count, reconciling solo-reviewer with the orchestrator's closed-set check.
- Report header field renamed `**Mode**` → `**Preset**`; verified nothing outside archived v1 artifacts parses the old name.
- Old `--review high` README examples translate to `--review "review models=high"`; `--review max` → `--review audit`.

## Summary

**Completed 2026-08-21** — All 15 findings applied across 19 files: legacy mode/max vocabulary purged from the agent roster, persona-authoring, consolidation and session-report conventions, both READMEs, and the code-review/auto-code-review/resolve-code-review skills; the consolidation convention's validation step rewritten to match Step 5.6; the circular evidence=any screen skip re-keyed on finder anchors; a no-screen-score always-validate rule added for Step 5.5 promotions; anchor-50 non-Critical triage rows added to both fix loops; the [probe] tag reconciles solo-reviewer's process notes with the parked-entry count. Verified by repo-wide grep: no legacy tokens remain outside reports/ archives, the refactor skill's unrelated quick/deep mode, and one historical max reference in the decision log.
