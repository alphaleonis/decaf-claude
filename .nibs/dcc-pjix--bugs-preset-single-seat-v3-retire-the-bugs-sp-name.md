---
# dcc-pjix
version: 1
title: bugs preset = single-seat v3; retire the bugs-sp name; wave behind roster flag
status: in-progress
type: feature
priority: high
created_at: 2026-08-18T07:04:38Z
updated_at: 2026-08-18T07:06:35Z
parent: dcc-hyxw
order: arw
---

Operator decision 2026-08-18, on the evidence in `v2/analysis/BUGS-SP-RESULTS.md` (five subjects,
three application types): the `bugs` preset's mechanism becomes the single-seat `solo-reviewer` path
(brief v3). The four-seat wave is no longer what `bugs` means; it stays reachable as an explicit
`bugs roster=N` (N ≥ 2) override. The `bugs-sp` name is retired — kept only as an alias that
resolves to `bugs` so existing invocations and the benchmark arms keep working.

## What changes

- `code-review` SKILL.md: presets table (`bugs` = roster 1, seat on session model, evidence
  self-calibrated, reach narrow); "The bugs-sp path" section becomes "The `bugs` path"; Step 2a.5
  recommendation unchanged in spirit (bugs for small/low-risk changes) but now points at the seat;
  Step 2b/2b.5 wording for the wave-under-flag; the `bugs roster≥2` wave runs `evidence=norm`
  (dcc-sk3k's fix — corroboration is scarce at ≤4 seats and `strong` binned real defects on 3 of 5
  subjects); skip markers, report header, examples.
- `solo-reviewer.md` description names the `bugs` preset.
- CLAUDE.md, decaf-quality/README.md.
- Benchmark: `ours-bugs` arm now measures the new `bugs`; new `ours-bugs-wave` arm = `bugs roster=4`;
  `ours-bugs-sp*` arms marked historical (frozen brief revisions). Pre-2026-08-18 `ours-bugs` cells
  are the wave and are labelled as such in tools.json.
- dcc-sk3k closes as superseded for `bugs`; its remaining scope (review/audit) noted there.

## Acceptance

- [x] SKILL + brief + docs edited; no `bugs-sp`-as-preset text left except the alias line
- [ ] Dev copy synced; benchmark arms updated (`ours-bugs` → new bugs, `ours-bugs-wave` added,
      sp arms marked historical); tools.json baseline notes
- [ ] One probe cell (r0, never scored) of `ours-bugs` on a fresh session confirms `bugs` resolves to
      the single seat and `bugs roster=4` announces the wave with `evidence=norm`
- [x] dcc-sk3k closed as superseded; results/proposal docs carry the decision
