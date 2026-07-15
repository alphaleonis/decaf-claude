---
# dcc-unre
version: 1
title: 'Review-skill tuning candidates — 4-session re-scoring (gate met; apply #1/#3/#4 on main)'
status: todo
type: task
priority: normal
created_at: 2026-07-04T12:45:01Z
updated_at: 2026-07-04T18:28:28Z
order: "y"
---

Analysis of reports/2026-07-04-nibs-5a8k-code-review-session (the 'after' picture for the sn96-driven tuning: dcc-n87o, dcc-n7bm, dcc-6yi4, dcc-8tbb) confirmed the tuning held — zero manual nudges, single-segment orchestrators, capped re-reviews (mid 9 → mid6 → mid3) with recorded drop rationale, ~49% lower reported review-orchestrator tokens (918k → 465k), [Estimate] all-in review ~2.5-4.5M → ~1.3-2.4M — while catching two ship-blockers (app-wide cn() silent no-op; false-positive regression test). Natural ablation: no dropped agent would have changed a verdict. quick-reviewer found the iteration-1 headline bug after being dry all of sn96 — evidence AGAINST shrinking the floor and for waiting on more samples before further tuning.

**Gate: hold until a couple more session reports accumulate on this branch (sample of 2 is still thin; the 5a8k diff was declarative/easy-to-review, which confounds the cost numbers).**

Candidate tunings to re-evaluate once more evidence exists:

1. **Fix-added tests must prove they can fail** (sharpens dcc-6yi4): when a fix round adds a regression test outside the fixTdd path, require demonstrating each guard fails against the unfixed/mutated code (iteration 3's orchestrator mutation experiment, moved to fix time). Would have caught 5a8k's iteration-2 High one round earlier. Fix rounds created fresh defects in 2 of 3 rounds here and 1 of 2 in sn96 — the top remaining defect source.
2. **Family-sweep rule**: a fix changing a vendored primitive family's shared class contract triggers a same-round sweep of sibling primitives. The ui/dropdown-menu/* family produced findings in all three 5a8k rounds (whack-a-mole); one sweep would likely have collapsed it.
3. **Encode post-APPROVED trivial-residual handling** in auto-code-review: a sole Low residual after an APPROVED verdict may be applied directly in main context + gate re-run, no fix subagent, no extra iteration (5a8k did this by improvisation; correct proportionality).
4. **Record pre-flight gates in every report header**: iterations 2-3 recorded 'Pre-flight gates (run once for the wave)'; iteration 1 (the 9-agent wave, where sharing saves most) has no line — compliance is unauditable. Add the field to code-review's report template.

Keep as-is (explicitly re-confirmed by this session): the floor (quick's redemption), the re-review trigger even for small deltas (both catches were fix-round regressions), the validation wave (6/6 confirmed, one severity recalibration), assurance-only reviewers ('found 0 != did nothing' — typescript cleared the app-wide cn() risk twice).

## Todo

- [x] Accumulate 2+ more code-review session reports on the tuning branch (p07b, qj7m)
- [x] Re-evaluate the four candidates against the fuller sample (see Re-scoring section: #1/#3/#4 act, #2 parked)
- [ ] On `main`: apply #1 (fix-added-tests-must-fail), #3 (in-loop metered post-APPROVED pass), #4 (pre-flight full gate + record)
- [ ] Keep accumulating reports; re-check #2 (family-sweep) and #dcc-jxya against a larger, more diverse sample

## Re-scoring — 4-session sample (2026-07-04)

Gate met: p07b + qj7m are the two additional reports this nib waited for. Full synthesis in
`reports/2026-07-04-cross-session-analysis.md`. Verdicts over the four sessions (sn96, 5a8k, p07b, qj7m):

1. **Fix-added tests must prove they can fail — ACT.** 4 of 5 re-reviewed fix rounds introduced a
   fresh reviewable defect (sn96 1/2, 5a8k 2/2, p07b 1/1); 2 were specifically bad fix-added tests
   (5a8k false-positive `cn()` test; p07b `try/finally` test leak). Top remaining defect source.
2. **Family-sweep rule — KEEP PARKED.** Still only 5a8k (`ui/dropdown-menu/*` whack-a-mole). p07b and
   qj7m show nothing comparable. Sample of one.
3. **Post-APPROVED fix pass — ACT + BROADEN.** Post-APPROVED fixing occurred in 4 of 4 sessions,
   inline and UNMETERED in 3 of 4 (5a8k iter-3, p07b iter-2, qj7m). Not always a trivial Low residual
   — qj7m applied 3 Mediums intrinsic to the deliverable. Encode an in-loop, metered
   "APPROVED-with-residual → optional bounded fix pass + re-verify gate" scoped to deliverable-intrinsic
   findings. Also closes a token-accounting blind spot.
4. **Record pre-flight gates — ACT + EXPAND.** qj7m showed pre-flight ran tests but not build/lint
   (filed nibs-k3zb) — recording alone is insufficient; pre-flight should run the full build/lint/test
   gate AND record which it ran.

New signal, spun out: adversarial-reviewer failed its first dispatch in both p07b iterations (one
injection-looking payload, ~66.8k tokens wasted) → #dcc-jxya.

Re-confirmed keep-as-is: the floor (quick drove verdicts in 2/4; sn96 dry is unrepresentative), the
re-review trigger even for small deltas (every re-review caught a fix-round regression), the validation
wave (refuted a wrong finding in 2/4), assurance-only reviewers. Application of #1/#3/#4 lands on `main`.

Caveat carried forward: sample is four (one pre-tuning); all post-tuning sessions are Svelte/TS web-UI;
p07b/qj7m diffs are small. Keep accumulating.
