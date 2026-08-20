Reviewer subagent report, verbatim:

---

## Strengths

- **`reconstruct_flag_at_timestamp` as a thin wrapper** (`version_history.py:269-287`) is the right decomposition — it reuses `reconstruct_flag_at_version` rather than duplicating the backward-walk logic, which is exactly what the "DRY" follow-up commit claimed to do.
- **`_validate_aware_timestamp`** (`version_history.py:18-21`) fails loudly on naive datetimes instead of producing a silent wrong comparison, and it is tested (`test_find_version_at_timestamp_naive_timestamp_raises`).
- **Rust `detailed_analysis` is gated behind an internal-token check** (`handler/mod.rs:218`) rather than being publicly reachable — the right instinct for a debug-surface feature.
- **`FlagDetails::create` delegating to `create_with_analysis(.., false, None)`** (`api/types.rs:452`) keeps a single construction site, and the `Eq`→`PartialEq` derive relaxation on `FlagDetails`/`FlagsResponse`/`ServiceResponse` was correctly propagated for the new `f64`-bearing type.
- **`point_in_time_properties.py` cleanup** — removing the `return_debug_info` tuple-or-dict union return is a genuine improvement to a bad signature (though it was done without fixing the caller; see below).

---

## Issues

### Critical (Must Fix)

**1. `build_person_properties_at_time` lost a parameter its existing caller still passes**
`posthog/models/person/point_in_time_properties.py:105` (signature) vs `posthog/api/person.py:1448`

The diff deletes the `return_debug_info` parameter, but `posthog/api/person.py:1443-1451` still calls `build_person_properties_at_time(..., return_debug_info=True)` and then `cast(tuple[...], result)`. That call raises `TypeError: unexpected keyword argument 'return_debug_info'`. It is behind `if debug and settings.DEBUG`, so it will not fire in production — but it is a hard break of an existing code path and mypy runs in CI (`.github/workflows/ci-python.yml:142`), so this will also fail the type check.

Fix: update `posthog/api/person.py` to stop requesting debug info (and drop the now-wrong `cast` and the `debug_rows`/`debug_query`/`debug_params` plumbing), or keep the parameter.

**2. Deletion state is only tracked on entries that carry a version change — so bulk-deleted flags are reported as alive**
`posthog/models/feature_flag/version_history.py:243-250`

```python
if version_after is not None:
    most_recent_version = version_after
    if activity == "deleted":
        flag_was_deleted = True
    elif activity == "restored":
        flag_was_deleted = False
```

The `deleted`/`restored` transition is nested inside `if version_after is not None`. The docstring at `version_history.py:188-190` promises "The flag was soft-deleted at or before the timestamp" makes the flag non-existent, and the code comment at :242 explicitly names bulk deletes as the entries being skipped.

The bulk-delete path in this same repo logs exactly such an entry: `posthog/api/feature_flag.py:2836-2847` writes `activity="deleted"` with `detail=Detail(changes=[], name=old_key)` — no `version` change — and the accompanying `.update(deleted=True, last_modified_by=..., updated_at=...)` does not bump `version` either. So for any flag deleted through bulk delete, `flag_was_deleted` never becomes `True`, and `find_version_at_timestamp` returns a version as if the flag existed.

The inverse direction is worse for the feature's headline use case: because that bulk-delete entry records no `deleted` change either, `reconstruct_flag_at_version` cannot undo it, so `_extract_tracked_fields` carries today's `deleted=True` into a reconstruction of a *past* timestamp when the flag was live. The Rust side then filters the flag out and the endpoint answers `reason: "flag_not_found"` for a flag that was very much active at that time.

Fix: decouple the two concerns — track `deleted`/`restored` for every entry, and extract the version only when present.

**3. `only_use_override_person_properties` skips *all* DB preparation, not just person properties**
`rust/feature-flags/src/flags/flag_matching.rs:827`

```rust
if flags_requiring_db_preparation.is_empty() || self.only_use_override_person_properties {
    self.flag_evaluation_state.skip_person_properties();
    return false;
}
```

`prepare_flag_evaluation_state` (`flag_matching.rs:1997+`) does much more than fetch person properties: it loads cohort definitions, static cohort membership, group-type mappings, group properties, and the person id. `requires_db_preparation` (`flag_operations.rs:38-41`) returns `true` specifically for group-type and cohort filters. Short-circuiting the whole function therefore evaluates cohort-based and group-based flags against empty cohort/group state.

Python's historical path always sets this flag (`posthog/api/feature_flag.py:3545`, `only_use_override_person_properties=timestamp is not None`), so historical evaluation of any cohort- or group-targeted flag returns a silently wrong answer. The narrow change intended here belongs in `get_person_properties` (`flag_matching.rs:1696`), which the diff already patches correctly; the `flag_matching.rs:827` short-circuit should be reverted.

**4. Override flag definitions are applied with no authentication**
`rust/feature-flags/src/handler/mod.rs:196` → `rust/feature-flags/src/handler/flags.rs:152-186`

`detailed_analysis` is correctly gated on `is_internal_request` (`mod.rs:218`), but `override_flags_definitions` and `only_use_override_person_properties` are passed straight through from the request with no gate. `/flags` authenticates only with the project API token, which is public by design (it ships in web snippets). Any caller can therefore:

- replace a flag's entire definition (`*flag = override_flag;`, `flags.rs:177`) for their own evaluation, including `active`, `deleted`, `ensure_experience_continuity`, `filters`, `evaluation_contexts` — note the filtered-out set at `flags.rs:191+` is computed *after* the override, so an override bypasses runtime/context filtering;
- set `ensure_experience_continuity: true` to drive hash-key-override writes;
- flip `only_use_override_person_properties` to force `skip_writes` (`flags.rs:336-338`).

Cross-team escape appears blocked (`flags.iter_mut().find(|f| &f.key == flag_key)` only matches the caller's own team's flags, and cohorts are fetched per team), so this is not a data-disclosure hole — but a request-controlled definition override on a public endpoint should carry the same `is_internal_request` gate as `detailed_analysis`, or be rejected outright.

**5. A failed or unmatched override silently degrades to evaluating the *current* definition, still labeled historical**
`rust/feature-flags/src/handler/flags.rs:170-186`

Both the parse-failure arm (`Err(e) => tracing::warn!(...)`) and the flag-not-found arm (`else { tracing::warn!(...) }`) log and continue. The response carries no signal that the override was dropped. Python's `test_evaluation` then presents the result as the flag's historical state.

This is reachable in normal operation. `posthog/api/feature_flag.py:3521-3533` builds the override with `model_to_dict`, which includes the `analytics_dashboards` M2M (it is excluded from `RECONSTRUCTABLE_FIELDS` at `activity_log.py:367-373` but *not* from the `exclude=` list here). `ManyToManyField.value_from_object` returns model instances when the pk is set — and `evaluation_flag` is constructed with `id=feature_flag.id` (`feature_flag.py:3478-3488`). For any flag with linked analytics dashboards, the dict contains `Dashboard` objects, `requests`' `json=` raises `TypeError`, and the outer `except Exception` at `feature_flag.py:3612` turns it into a 500. It also costs an extra query per call for flags that have none.

Fix: add `analytics_dashboards` to the `exclude=` list (and prefer an explicit field allowlist over `model_to_dict`), and make a dropped override an error the caller sees rather than a warn-and-continue.

---

### Important (Should Fix)

**6. The feature is inert in every existing environment, with no signal**
`posthog/api/feature_flag.py:3547`, `rust/feature-flags/src/config.rs:611`

`internal_request_token=os.getenv("INTERNAL_REQUEST_TOKEN")` is the only reference to this variable anywhere in the repo besides the Rust `envconfig` declaration — it is not in Django settings, any compose file, or any chart. Unset, no `Authorization` header is sent, `is_internal_request` returns `false`, `detailed_analysis` is forced to `Some(false)` (`mod.rs:218-222`), and the endpoint returns `conditions: []` with a 200. The caller cannot distinguish "no conditions matched" from "the feature is not configured".

Also: reading config via `os.getenv` bypasses `posthog/settings`, so the variable is undeclared and undocumented; `settings` is already imported in this file.

**7. Only a fraction of the reconstructed historical state is actually used**
`posthog/api/feature_flag.py:3478-3489`

`reconstruct_flag_at_timestamp` returns every field in `RECONSTRUCTABLE_FIELDS`, but only `name`, `active`, `deleted`, `version`, and `filters` are copied onto `evaluation_flag`. Everything else takes the model default on the freshly constructed instance — including `bucketing_identifier` (defaults to `"distinct_id"`), `ensure_experience_continuity` (`False`), and `evaluation_runtime` (`"all"`). `bucketing_identifier` directly determines rollout bucketing, so a flag whose bucketing changed since the queried timestamp will produce the wrong historical result while being reported as historical.

**8. Missing version metadata silently returns version 1 instead of raising**
`posthog/models/feature_flag/version_history.py:260-266`

If activity-log entries exist at or before the timestamp but none carries a `version` change (retention trimming, or the bulk paths above), the function falls through to `return 1`. Everywhere else this module raises `VersionHistoryIncomplete` for exactly this situation (`version_history.py:93`, `:161`, `:201`). Returning `1` hands back a confidently wrong reconstruction.

**9. `.iterator()` immediately defeated by `list()`; the reversal is a no-op**
`posthog/models/feature_flag/version_history.py:212-236`

The comment at :212 says "streaming with `.iterator()` to avoid loading all entries into memory", then :235 does `entries_list = list(entries)` — materializing up to `MAX_HISTORY_ENTRIES` (10,000) rows. Worse, the reverse-iteration is pointless for its stated purpose: the loop unconditionally overwrites `most_recent_version` on every versioned entry, so with `reversed()` it lands on the newest one — identical to taking the first entry of the newest-first ordering and breaking. As written the whole materialize-and-reverse achieves nothing that `next()` on the original ordering would not, and it is the reversal that creates the coupling bug in finding #2.

**10. Zero tests for ~600 lines of new logic**

- `posthog/api/feature_flag.py:3379-3614` (`test_evaluation`, ~235 lines including the override serialization, the Rust response shape parsing, and five error paths) has no tests at all — no test file references it.
- `rust/feature-flags/src/api/types.rs:541-731` (`build_condition_analysis`, ~190 lines of explanation/rollout logic) has no tests. Every Rust test change in the diff is a mechanical struct-field addition.
- `is_internal_request` (`handler/authentication.rs:27-49`) and the override application in `fetch_and_filter` (`flags.rs:152-186`) are untested, including the security-relevant gate.

`version_history.py` is the only new code with real tests, and those omit the deletion cases that matter (a `deleted` entry with no version change; delete-then-update).

**11. `rollout_excluded` only ever considers 0% rollout, so partial-rollout exclusions get a wrong explanation**
`rust/feature-flags/src/api/types.rs:652, 675-687`

`is_zero_rollout = rollout_percentage == 0.0` is the only rollout test. A condition at 50% whose properties matched but whose user hashed outside the bucket gets `rollout_excluded: false` and, at :310-315, the explanation *"Condition N matched properties but was not evaluated due to an earlier condition matching"* — which is simply not what happened. For a debugging surface whose entire value is a correct explanation, this is a substantive defect. The real bucketing decision is available from `flag_match.reason == OutOfRolloutBound` plus `condition_index`; the `is_zero_rollout` conjunct at :679/:682/:686 should be dropped.

**12. `ConditionAnalysis.matched` means something different on each side of the wire**
`rust/feature-flags/src/api/types.rs:713` vs `posthog/api/feature_flag.py:1970`

Rust sets `matched: all_properties_matched`. The Python serializer's `help_text` says *"Whether this condition was the one that matched"*. The Rust code even computes that value (`condition_matched`, `types.rs:558-568`) and then uses it only for the explanation string. Pick one meaning; if both are wanted, emit both fields.

**13. Cohort and flag-dependency filters are analyzed as if they were person properties**
`rust/feature-flags/src/api/types.rs:601-604`

`match_property(property, props, false)` is called for every property in the group regardless of `prop_type`, but the real evaluator routes `Cohort` and `Flag` filters through cohort membership and dependency resolution. For a cohort filter the analyzer looks up a person property literally named `id`, finds nothing, and reports `matched: false` with *"Property 'id' is not in [cohort id]"* — for a condition that may well have matched. `PropertyType::Cohort`/`Flag` should be reported as not-analyzable rather than analyzed incorrectly.

**14. Full flag filters logged at INFO on a high-throughput service**
`rust/feature-flags/src/handler/flags.rs:154, 156, 159-163, 167-171`

Four `tracing::info!` calls per override request, two of which dump `{:?}` of the complete `FlagFilters` — i.e. customer targeting property keys and values — into service logs. These read as development diagnostics; they belong at `debug!`/`trace!`, and the filter dumps arguably should not be logged at all.

---

### Minor (Nice to Have)

**15. `rustfmt` will fail CI** — `rust/feature-flags/src/handler/billing.rs:96-97` now has two consecutive blank lines (`blank_lines_upper_bound` defaults to 1), and `handler/mod.rs:218` is ~110 characters (`max_width` 100). I could not run `cargo fmt` (no toolchain in this environment), so [Inference] on the exact failure, but both are textbook violations. `flag_matching.rs:1604` also has an unrelated blank-line deletion — stray noise in the diff.

**16. Dead `try`/`except`** — `posthog/models/person/point_in_time_properties.py:80-81` is `except Exception: raise`, which does nothing. Either drop the `try` or restore contextual wrapping. Note this also silently changed the exception type callers see (previously `Exception("Failed to query person distinct_ids: ...")`).

**17. Unreachable fallback with worse semantics than the property it replaces** — `point_in_time_properties.py:65-77`. `Person.distinct_ids` is a `@property` (`posthog/models/person/person.py:210`), so `hasattr(person, "distinct_ids")` is always `True` and the `PersonDistinctId` branch is dead. If it ever were reachable it would be worse than the property it duplicates: it omits `.order_by("id")`, and `feature_flag.py:3435` uses `distinct_ids[0]` for bucketing, so ordering is load-bearing. The comment "The personhog-routed functions already include distinct_ids" is also misleading — the ORM path has it too.

**18. Speculative parsing of a response shape the service never produces** — `posthog/api/feature_flag.py:3577-3583` tries four locations for `conditions`, of which only `flag_result["conditions"]` exists in `FlagDetails` (`api/types.rs:406`). `analysis` is not a field anywhere in the Rust response. Guessing at four shapes suggests the contract was not checked; also `.get("analysis", {}).get(...)` would raise on a JSON `null`.

**19. Non-constant-time secret comparison** — `rust/feature-flags/src/handler/authentication.rs:45`, `auth_token == *internal_token`. A remote timing attack on a shared secret over HTTP is impractical, but there is no reason not to use a constant-time compare; the repo currently has no such helper, so this would mean adding `subtle` or `constant_time_eq`.

**20. Misleading comment** — `posthog/api/feature_flag.py:3470` says *"using the efficient single-pass method"*. `reconstruct_flag_at_timestamp` issues two independent activity-log queries (`find_version_at_timestamp` with `created_at__lte`, then `reconstruct_flag_at_version` without it) and walks the log twice.

**21. Test class inheritance duplicates 18 tests** — `posthog/models/feature_flag/test/test_version_history.py:279`, `class TestTimestampBasedReconstruction(TestReconstructFlagAtVersion)`. Subclassing a `TestCase` re-runs every inherited test method. Extract `_create_flag`/`_simulate_update` into a mixin or shared non-`TestCase` base.

**22. Assorted style/consistency** — `logging.exception(f"...")` at `feature_flag.py:3536` uses the root logger and an f-string while the same function uses the module `logger` elsewhere; `headers = {}` at `flags_service.py:91` lacks the annotation its neighbor `params: dict[str, str]` (`:83`) has; the type guard added at `feature_flag.py:1103-1105` is redundant (the existing `except (ValueError, TypeError)` already covers non-numeric input) and lands in a block the surrounding comment marks as unreachable — unrelated scope creep; `person_existed_at_timestamp` (`point_in_time_properties.py:270`) calls `timestamp.astimezone(UTC)` with no awareness check, unlike `version_history._validate_aware_timestamp` — a naive datetime would be silently interpreted as server-local time; and a production viewset action named `test_evaluation` reads as a test (`evaluate` or `preview_evaluation` would be clearer).

**23. Generated OpenAPI/TypeScript artifacts not regenerated** — three new serializers and a new action, but no changes under `frontend/src/generated/`. `AGENTS.md` asks for `hogli build:openapi`; CI auto-commits these (`ci-backend.yml:616-633`), so this is not blocking. There is also no frontend consumer of the new endpoint in this diff.

---

## Recommendations

1. **Fix the two silent-wrong-answer paths first** (#2, #3). Both make the feature return plausible but incorrect historical results, which is worse for a debugging tool than returning an error.
2. **Make dropped overrides loud** (#5, #6). The whole chain — env var unset, override parse failure, override key not found — currently degrades to a 200 that looks like a successful historical evaluation. Each of these should be an explicit error to the caller. This is the same failure mode three times over in one change.
3. **Gate the override surface exactly as `detailed_analysis` is gated** (#4), and consider whether `override_flags_definitions` belongs on the public `/flags` endpoint at all versus a separate internal route.
4. **Replace `model_to_dict` with an explicit field mapping** (#5, #7). The current approach both over-includes (`analytics_dashboards`, `last_called_at`, `rollback_conditions`) and under-applies the reconstruction (`bucketing_identifier`, `ensure_experience_continuity`). A single explicit dict built from `reconstructed_flag_data` fixes both and makes the Rust `FeatureFlag` contract legible at the call site.
5. **Add tests before landing** (#10). At minimum: one end-to-end `test_evaluation` test with a timestamp (mocking the flags service response), one `build_condition_analysis` unit test per rollout outcome, one `is_internal_request` test per branch, and a `find_version_at_timestamp` test for a `deleted` entry with no version change.
6. **Split the change.** The Rust analysis feature and the Python timestamp-reconstruction feature are independently reviewable and independently testable; the `point_in_time_properties` signature cleanup and the `between`-operator type guard are unrelated to both. Reviewing 1,253 lines across two languages and three concerns in one pass is how #1 (a broken caller in a file the diff never touches) slipped through.

---

## Assessment

**Ready to merge?** No.

**Reasoning:** Five defects are load-bearing on the feature's core promise: an existing caller is broken (#1), soft-delete detection misses the repo's own bulk-delete path (#2), the historical path disables cohort/group evaluation entirely (#3), request-controlled flag definitions are accepted without authentication on a publicly-tokened endpoint (#4), and a dropped override — including the JSON-serialization failure this code will hit on any flag with linked analytics dashboards — degrades to a result still labeled historical (#5). Compounding this, the feature is inert unless an undeclared env var is set, and there are no tests for the ~600 lines of new evaluation and analysis logic.
