I'll start by invoking the skill.
Dispatching the reviewer subagent now.
Reviewer subagent report, verbatim:

---

### Strengths

- **`find_version_at_timestamp` / `reconstruct_flag_at_timestamp` split is right.** The wrapper delegates to the existing `reconstruct_flag_at_version` instead of duplicating the backward-walk, which satisfies requirement 1's "without duplicating reconstruction logic" cleanly (`version_history.py:269-287`).
- **`_validate_aware_timestamp` is a genuine fix** and the `test_find_version_at_timestamp_naive_timestamp_raises` test locks it in.
- **Rust builder pattern was extended idiomatically.** `with_detailed_analysis` / `with_only_use_override_person_properties` follow the existing `with_*` convention, and `create_with_analysis` was added by making the old `create` delegate to it — no call-site churn (`api/types.rs:442-460`).
- **Correct `Eq` derives removed** from `ServiceResponse` / `FlagsResponse` / `FlagDetails` once `f64` entered the type graph via `ConditionAnalysis`. Easy to get wrong.
- **`skip_writes` is forced on** for detailed/override evaluations (`handler/flags.rs:336-338`) so diagnostic requests do not persist experience-continuity hash keys.
- **`@validated_request` above `@action`** matches the five existing usages in the file, and the request serializer's mutual-exclusion `validate()` is correct.

### Issues

#### Critical (Must Fix)

**1. Bulk-deleted flags are reported as alive, and pre-deletion timestamps return the deleted state — `posthog/models/feature_flag/version_history.py:243-254`**

`flag_was_deleted` is only updated *inside* `if version_after is not None`. The bulk-delete path in `posthog/api/feature_flag.py:2836-2847` logs `activity="deleted"` with `detail=Detail(changes=[], name=old_key)` — no version change — and the accompanying `FeatureFlag.objects.filter(...).update(deleted=True, ...)` at line 2866 does **not** bump `version`. So the exact entry the comment on line 242 claims to handle ("Bulk delete entries without version changes should be skipped") is skipped for deletion-state tracking too.

Failure scenario: flag created, edited to v3, then bulk-deleted at T2.
- Query at T3 (after the delete): the newest versioned entry is v3, `flag_was_deleted` stays `False` → returns `3` instead of `None`. Requirement 3 is violated.
- Query at T1 (between v3 and T2, when the flag was live): returns `3`, which equals `flag.version`, so `reconstruct_flag_at_version` short-circuits at line 100 and returns the **current** field set — including `deleted=True` and `is_historical=False`. A timestamp at which the flag was live is reported as deleted.

Fix: track `deleted` state from the `activity` value independently of whether the entry carries a version, and make the bulk-delete path bump `version` / log a `deleted` change so `reconstruct_flag_at_version` can roll it back.

**2. Point-in-time evaluation silently returns `false` for any cohort-targeted flag — `rust/feature-flags/src/flags/flag_matching.rs:827`**

`if flags_requiring_db_preparation.is_empty() || self.only_use_override_person_properties` early-returns before `prepare_flag_evaluation_state`. That function does far more than fetch person properties: it sets `flag_evaluation_state.cohorts` (line 2022) and initializes group type mappings (line 2044). With the flag set, `flag_evaluation_state.cohorts` stays `None`, and `flag_matching.rs:1592-1594` does `None => return Ok((false, NoConditionMatch))`.

Since `test_evaluation` always sends `only_use_override_person_properties=timestamp is not None` (`posthog/api/feature_flag.py:3545`), **every** historical evaluation of a flag with a cohort filter returns "not enabled / no_condition_match" regardless of real membership — no error, no warning. Group-based flags are similarly affected via the skipped group-type-mapping init. The flag name and its doc comment promise only that DB *person properties* are ignored.

Fix: scope the skip to person properties (the `get_person_properties` change at line 1696 already does that correctly) and let cohort/group preparation proceed.

**3. `override_flags_definitions` is honored on the public `/flags` endpoint with no authentication gate — `rust/feature-flags/src/handler/flags.rs:152-186`, `rust/feature-flags/src/flags/flag_request.rs:80-81`**

`/flags` is the public client endpoint: `parse_and_authenticate` resolves the team from the project API token in the request body. The author clearly knew gating was required — `detailed_analysis` is gated behind `authentication::is_internal_request` at `handler/mod.rs:218` — but `override_flags_definitions` is applied unconditionally, and `*flag = override_flag` (line 168) replaces the entire flag struct.

Consequences for any anonymous caller holding a public token (i.e. anyone who loads the customer's website):
- Inject arbitrary `filters`, `ensure_experience_continuity`, `bucketing_identifier` for any flag key in the team.
- `skip_writes` is **not** set for the override-only case (line 336 keys off `detailed_analysis` and `only_use_override_person_properties` only), so an injected `ensure_experience_continuity: true` can drive writes to hash-key-override storage.
- Unbounded map size, each entry triggering a `FeatureFlag` deserialize plus cohort/property work — an amplification vector on a public, high-QPS endpoint.

Fix: gate `override_flags_definitions` behind `is_internal_request` exactly as `detailed_analysis` is, reject the request (rather than silently ignoring) when it is present without internal auth, and cap the map size.

**4. `is_set` / `is_not_set` property filters make `test_evaluation` return HTTP 500 — `posthog/api/feature_flag.py:1961`**

`FeatureFlagConditionPropertyAnalysisSerializer.value` is a `JSONField` with neither `allow_null=True` nor `required=False`. The Rust side emits `value: null` for valueless operators: `api/types.rs:694` sets `value: property.value.clone().unwrap_or(serde_json::Value::Null)`. DRF's `Field.validate_empty_values` fails with `'This field may not be null.'`, the `ValidationError` from `response_serializer.is_valid(raise_exception=True)` (line 3609) is swallowed by the blanket `except Exception` at line 3613, and the caller gets a generic 500 `"Failed to evaluate flag"` with no indication of the cause.

Fix: `allow_null=True` on `value`; also let `ValidationError` propagate rather than collapsing it into a 500.

#### Important (Should Fix)

**5. Historical `ensure_experience_continuity` / `bucketing_identifier` / `evaluation_runtime` are discarded — `posthog/api/feature_flag.py:3478-3489`**

`reconstruct_flag_at_timestamp` returns all of `RECONSTRUCTABLE_FIELDS`, but the reconstructed `FeatureFlag(...)` is built from only `name`, `active`, `deleted`, `version`, `filters`. Every other reconstructed field falls back to the model default — `ensure_experience_continuity=False`, `bucketing_identifier="distinct_id"`, `evaluation_runtime="all"` (`posthog/models/feature_flag/feature_flag.py:71,90,103`). `bucketing_identifier` and `ensure_experience_continuity` both change how a user is bucketed, so the "as it existed at that time" result can differ from the truth even when reconstruction succeeded. Requirement 1 asked for the flag *definition*, not four of its fields.

**6. `model_to_dict` pulls the `analytics_dashboards` m2m and breaks JSON serialization — `posthog/api/feature_flag.py:3521-3523`**

`exclude=["created_by", "last_modified_by", "team", "usage_dashboard"]` omits `analytics_dashboards` (`feature_flag.py:73`). `model_to_dict` iterates `opts.many_to_many`, and `ManyToManyField.value_from_object` returns `[]` only when `pk is None`; the constructed instance carries the real `id`, so it issues a DB query and returns a list of `Dashboard` **model instances**. For any flag with analytics dashboards attached, `requests.post(json=payload)` raises `TypeError: Object of type Dashboard is not JSON serializable`, the `except Exception` at line 3535 logs and sets `override_definitions = None`, and the endpoint then evaluates the flag against its **current** definition while still reporting historical person properties. Silent wrong answer, not an error. Add `analytics_dashboards` to `exclude` (or use an explicit `fields=` allowlist).

**7. `rollout_excluded` never fires for the case it exists to describe — `rust/feature-flags/src/api/types.rs:652,669-681`**

Both arms of the `this_condition_rollout_excluded` decision require `is_zero_rollout` (`rollout_percentage == 0.0`). For the normal case — reason `OutOfRolloutBound` on a 50% condition — `rollout_excluded` is `false` and the explanation chain falls to line 691: `"Condition {} matched properties but was not evaluated due to an earlier condition matching"`, which is factually wrong (there was no earlier match; the user lost the rollout dice roll). Gate on `flag_match.reason == OutOfRolloutBound && index == condition_index` and treat zero-rollout as a special case, not the only case.

**8. `ConditionAnalysis.matched` means something different from what the API documents — `rust/feature-flags/src/api/types.rs:713` vs. `posthog/api/feature_flag.py:1966`**

Rust sets `matched: all_properties_matched`. The DRF `help_text` says *"Whether this condition was the one that matched"*. The `condition_matched` variable computed at `types.rs:558-567` — which *is* that meaning — is used only in the explanation string. Consumers reading `matched` will see multiple conditions marked `true`. Pick one meaning and make both sides agree; if both are wanted, expose two fields.

**9. Condition analysis evaluates group and cohort filters against the person-property map — `rust/feature-flags/src/api/types.rs:600-604`**

`match_property(property, props, false)` ignores `property.prop_type` and looks `property.key` up in the person-properties map. A `PropertyType::Group` filter (whose key lives in group properties) or a `PropertyType::Cohort` filter (key `id`, operator `in`) will essentially always report `matched: false` with `actual_value: null`, even when the flag itself matched. The `type` field is computed at line 578 purely for display. Either route each type to the right property source or mark non-person types as "not analyzed" rather than emitting a confident wrong `false`.

**10. `.ok()` discards the property-fetch error, degrading to fabricated per-property results — `rust/feature-flags/src/flags/flag_matching.rs:1004-1006`**

When `get_person_properties` fails, `merged_person_props` becomes `None`, and `build_condition_analysis` takes the `else` branch at `api/types.rs:604`: `(condition_matched, None)`. Every property in the condition is then reported with the *condition's* match value and `actual_value: null` — indistinguishable from a real analysis. Propagate the error or set an explicit "analysis unavailable" marker.

**11. The whole feature silently no-ops when `INTERNAL_REQUEST_TOKEN` is unset — `posthog/api/feature_flag.py:3547`, `rust/feature-flags/src/handler/mod.rs:218`**

`os.getenv("INTERNAL_REQUEST_TOKEN")` returning `None` means no `Authorization` header, so `is_internal_request` is false and Rust forces `detailed_analysis` to `Some(false)`. The endpoint then returns `conditions: []` and a 200 — the caller cannot distinguish "no conditions matched" from "detailed analysis was refused". No `settings.py` entry, no `.env` documentation, and the Rust side has no default either (`config.rs:611`). Read it through `django.conf.settings` (already imported at line 13), and have Rust return an explicit error when `detailed_analysis=true` is requested without internal auth.

**12. `.iterator()` is negated by `list()`, and the scan is unnecessary — `posthog/models/feature_flag/version_history.py:215-235`**

The comment on lines 212-214 says the query streams "to avoid loading all entries into memory," and then line 235 does `entries_list = list(entries)`, materializing up to `MAX_HISTORY_ENTRIES` (10,000) rows of JSON `detail` blobs. The oldest-first loop is also redundant: since `most_recent_version` is unconditionally overwritten on every versioned entry, the result is exactly "the newest entry carrying a version" — obtainable with a single indexed row fetch. Either fix the comment and keep the scan, or iterate newest-first and `break` on the first versioned entry.

**13. `person_existed_at_timestamp` runs an unbounded ClickHouse scan with a 10 s cap — `posthog/models/person/point_in_time_properties.py:228-283`**

`WHERE team_id = … AND distinct_id IN … AND timestamp <= …` has no lower time bound and no date-partition pruning, so the query scans the team's entire event history for those distinct IDs. `max_execution_time: 10` is hardcoded (unlike `build_person_properties_at_time`, which accepts a `timeout`); on a timeout the raised exception becomes a 500 at `feature_flag.py:3452`. It also duplicates a scan `build_person_properties_at_time` is about to perform two lines later. Consider deriving existence from that call's result, or bound the range.

**14. No tests for any of the new behavior that matters.**

Zero tests were added for: the ~240-line `test_evaluation` view, `person_existed_at_timestamp`, `is_internal_request`, `fetch_and_filter`'s override branch, and `build_condition_analysis` (existing Rust tests only gained `conditions: None` struct fields). Most notably, `test_find_version_at_timestamp_skips_entries_without_version` uses `activity="updated"` with `changes=[]` — it never exercises the `activity="deleted"`-with-no-version case that finding 1 shows is broken, and which the production comment on line 242 explicitly names.

Also: `class TestTimestampBasedReconstruction(TestReconstructFlagAtVersion)` (`test_version_history.py:278`) subclasses a concrete `TestCase`, so all ~17 parent tests re-run under the subclass. Extract the helpers into a mixin or a module-level function (the file already does this for `_log_flag_update`).

#### Minor (Nice to Have)

- **`hasattr(person, "distinct_ids")` is always true; the fallback is dead code** — `point_in_time_properties.py:65-76`. `Person.distinct_ids` is a `@property` on the model (`posthog/models/person/person.py:210`) that already falls back to a `PersonDistinctId` query. The new branch duplicates that query *without* the property's `.order_by("id")`, so if it ever ran it would return a nondeterministically ordered list — and `evaluation_distinct_id = … distinct_ids[0]` (`feature_flag.py:3423`) depends on that order.
- **`except Exception: raise` is a no-op** — `point_in_time_properties.py:80-81`. Drop the `try` (moving the local import back out) rather than leaving a bare re-raise.
- **`cargo fmt --check` will fail.** `rust/feature-flags/src/handler/billing.rs:96-97` has two consecutive blank lines, and `rust/feature-flags/src/handler/mod.rs:218` is 117 characters (rustfmt `max_width` is 100). Also `use crate::api::auth::extract_bearer_token;` sits inside a function body at `authentication.rs:41` — move it to the module header with the other `use`s.
- **Non-constant-time secret comparison** — `rust/feature-flags/src/handler/authentication.rs:45`. `auth_token == *internal_token` short-circuits on first mismatching byte, on a publicly reachable endpoint. Use `subtle::ConstantTimeEq` or `constant_time_eq`.
- **`logging.exception` instead of the module logger** — `posthog/api/feature_flag.py:3536`. Every other new log line uses `logger`; this one goes to the root logger. It also uses an f-string where the surrounding code uses `%s` lazy formatting.
- **Guessing at the response shape** — `posthog/api/feature_flag.py:3577-3583`. The four-way `or` chain probes `flag_result["analysis"]`, `rust_response["conditions"]`, and `rust_response["analysis"]`, none of which the Rust side ever emits (only `FlagDetails.conditions` exists, `api/types.rs:404`). Two of those probes would also raise `AttributeError` if the key existed with a `null` value. Read the one real path.
- **Dead datetime conversion** — `posthog/api/feature_flag.py:3529-3530`. `updated_at` uses `auto_now=True`, so `editable=False` and `model_to_dict` never returns it; that branch cannot execute. (`created_at` uses `default=timezone.now`, so the line above it *is* live.)
- **Unrelated dead-code change with a "what" comment** — `posthog/api/feature_flag.py:1100-1106`. The block's own pre-existing comment says it is unreachable, and the new `isinstance` guard is behaviorally identical to the existing `except (ValueError, TypeError)` (which already caught the `TypeError` from `float([])`). The added comment "Type check: ensure both values can be converted to float" describes *what* rather than *why*, and is inaccurate — `isinstance(x, str)` does not imply float-convertibility. Consider dropping the change.
- **Docstrings on new Python tests** violate AGENTS.md's "Python tests: do not add doc comments" (`test_version_history.py:290, 350, 400, 419, 447`).
- **`headers = {}` needs a type annotation** — `posthog/api/services/flags_service.py:88`. The adjacent `params: dict[str, str] = {"v": "2"}` shows the file's convention, and mypy-strict (AGENTS.md "Code Style") requires it for an empty literal.
- **Parameterized test that special-cases itself** — `test_version_history.py:279-289`. The `("current_version", timedelta(hours=1), …)` row's `offset` is discarded by `if _name != "current_version"`, so the parameterization buys nothing for that case. Split it into its own test.
- **`flat=False` is the default** for `values_list` (`version_history.py:224`) — remove the noise.
- **Debug-level logging at `info`** — `rust/feature-flags/src/handler/flags.rs:154,157,169`. Four `tracing::info!` lines per override, one of which dumps the entire `filters` blob, on a request path reachable at public QPS. Demote to `debug!`.
- **Silently dropped overrides** — `rust/feature-flags/src/handler/flags.rs:180,187`. Both a parse failure and "flag not in the cached list" only `warn!`; the caller receives a 200 with a normally-evaluated (or missing) flag. Since a since-deleted flag is unlikely to be in the cache at all, historical evaluation of deleted flags will report `flag_not_found` rather than an error.

### Recommendations

1. **Treat the internal-auth boundary as one decision, not three.** `detailed_analysis` is gated, `override_flags_definitions` and `only_use_override_person_properties` are not. Resolve all three in one place immediately after `parse_and_authenticate`, and make an ungated request carrying any of them a hard error rather than a silent downgrade — that also fixes finding 11.
2. **Replace `only_use_override_person_properties`'s early return with a narrower flag.** The correct behavior already exists at `flag_matching.rs:1696`; the line-827 short-circuit is the bug. Add a Rust test asserting that a cohort-filtered flag still evaluates correctly with the flag set.
3. **Add an integration test for `test_evaluation`.** A single test that posts a timestamp against a flag whose `filters` changed, and asserts the historical `filters` reached the Rust service, would have caught findings 4, 5, and 6 at once.
4. **Narrow the `except Exception` blocks.** Three of the four Critical/Important failure modes above surface as an indistinguishable 500 or a silently degraded 200. Catch `requests.HTTPError`, `ValidationError`, and `TypeError` separately, and let unexpected exceptions produce a distinguishable error code.

### Assessment

**Ready to merge?** No.

**Reasoning:** Two of the four stated behavioral requirements are not met by the code: bulk deletes still mask deletion state in `find_version_at_timestamp` (the exact case its own comment claims to handle), and point-in-time evaluation silently returns `false` for every cohort-targeted flag because `only_use_override_person_properties` skips all DB preparation rather than just person properties. Separately, `override_flags_definitions` is accepted from unauthenticated callers on the public `/flags` endpoint while its sibling `detailed_analysis` is correctly gated — that gap needs closing before this ships regardless of the correctness fixes.

