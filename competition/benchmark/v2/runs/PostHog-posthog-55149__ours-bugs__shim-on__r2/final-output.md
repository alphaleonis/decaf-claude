✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-20_10-14-11.md`

**Mode**: `bugs` (single seat, roster=1, reach=narrow) · **Scope**: 18 files, +1253/−38 · **Spec**: none found · **Verdict**: ❌ NEEDS_CHANGES

| Severity | Count |
|---|---|
| 🔴 Critical | 1 |
| 🟠 High | 4 |
| 🟡 Medium | 6 |
| 🟢 Low | 5 |

Headline findings:

1. **🔴 `rust/feature-flags/src/handler/mod.rs:196`** — `override_flags_definitions` reaches `fetch_and_filter` with no authorization gate on the public `/flags` endpoint (public `phc_` token is the only credential), while the strictly weaker `detailed_analysis` capability *is* gated behind `is_internal_request` 22 lines below. `flags.rs:151-186` replaces the whole server-side `FeatureFlag`, enabling caller-supplied regexes compiled server-side, induced Postgres writes to `posthog_featureflaghashkeyoverride` via a forged `ensure_experience_continuity`, and `id`/`team_id` desync against Django-computed `evaluation_metadata`.
2. **🟠 `flag_matching.rs:827`** — the new `|| self.only_use_override_person_properties` short-circuits *all* DB preparation, not just person properties, so cohort and group conditions silently evaluate as `no_condition_match`. The intended effect is already achieved separately at `flag_matching.rs:1696-1704`.
3. **🟠 `posthog/api/feature_flag.py:1961`** — response serializer `value` lacks `allow_null=True`; Rust emits `value: null` for `is_set`/`is_not_set` filters, so `is_valid(raise_exception=True)` throws and the blanket handler returns HTTP 500. Reproduced against the pinned DRF 3.16.1.
4. **🟠 `api/types.rs:652`** — `rollout_excluded` only fires on exactly 0% rollout, so a 30%-rollout exclusion is reported as "not evaluated due to an earlier condition matching" when no earlier condition exists — contradicting `reason: out_of_rollout_bound` in the same response.
5. **🟠 `feature_flag.py:3388`** — `test_evaluation` requires only `feature_flag:read` but returns a person's full property blob, bypassing PostHog's separate `person` scope.

Also worth noting: `INTERNAL_REQUEST_TOKEN` (#6) exists in exactly two files and no settings/env/docs, so detailed analysis ships returning `"conditions": []` with no warning — which is also why #3 stays hidden until the token is deployed. And `return_debug_info` (#8) was removed from `build_person_properties_at_time` while `posthog/api/person.py:1448` still passes it.

Two caveats on evidence: `cargo` is unavailable in this environment, so all eight Rust findings are static traces, not builds — I re-verified the cited lines for #1, #2 and #10 directly against source. The Python findings #3 and the two `model_to_dict` dismissals were confirmed by execution against the pinned dependency versions. No files were modified.
