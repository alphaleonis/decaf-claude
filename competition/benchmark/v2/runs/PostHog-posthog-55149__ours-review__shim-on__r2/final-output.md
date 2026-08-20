Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-20_14-07-53.md`

**Verdict: NEEDS_CHANGES** — 1 Critical, 13 High, 18 Medium, 4 Low, 7 Minor. Working tree untouched; `.decaf/` is the only new (untracked) path.

**Most consequential findings**

- **Critical** — `override_flags_definitions` is added to the public `/flags` body and applied with no authorization gate (`handler/flags.rs:152`, forwarded at `mod.rs:196`), while the sibling `detailed_analysis` added in the same change *is* gated. `/flags` authenticates on the public project API token, so any holder can substitute an arbitrary flag definition. `only_use_override_person_properties` is ungated the same way.
- `only_use_override_person_properties` short-circuits all of `prepare_flag_evaluation_state`, not just person properties, so cohort and group data never load and every cohort-targeted flag reports as not matching (`flag_matching.rs:827`).
- `rollout_excluded` is gated on `rollout == 0.0`, but `check_rollout` returns `OutOfRolloutBound` for any rollout below 100 percent — so ordinary partial rollouts get a factually wrong explanation naming a nonexistent earlier condition.
- The override payload includes the `analytics_dashboards` M2M as Dashboard *instances*, so `json.dumps` raises and the endpoint returns 500 for any flag with an attached analytics dashboard. This was promoted from a reviewer's own dismissed-items list, where the reasoning was wrong.
- `INTERNAL_REQUEST_TOKEN` appears in exactly two source files and nowhere in settings or deployment config; unset, the flagship capability returns 200 with `conditions: []`.

**Two caveats worth your attention**

A three-reviewer consensus was **refuted**: they claimed `model_to_dict` omits the `id` field. Django keeps AutoField `editable=True`, so it does not. I had repeated that claim mid-review before verifying it; the correction is recorded in the report.

Nothing was verified by execution — no `cargo`, no `ruff`, and `uv sync --frozen` fails on a version mismatch. All nine nominated probes went unrun. Findings are static, with library source read where load-bearing.
