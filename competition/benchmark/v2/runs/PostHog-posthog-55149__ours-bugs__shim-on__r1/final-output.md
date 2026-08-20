✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-20_09-52-18.md`

**Preset `bugs`** (single seat, `roster=1`, `reach=narrow`). No spec found. Nothing was posted anywhere; no tracked file was modified (`git status --porcelain` shows only the untracked `.decaf/` output directory).

**Verdict: NEEDS_CHANGES** — 1 Critical, 3 High, 4 Medium, 5 Low.

The load-bearing findings:

1. **Critical, `rust/feature-flags/src/handler/mod.rs:196`, `:223`** — `detailed_analysis` is gated behind `is_internal_request`, but `override_flags_definitions` and `only_use_override_person_properties` are not. `/flags` authenticates only on the public project token, so any caller can substitute an arbitrary flag definition and read the result for a `distinct_id` they do not own, turning the endpoint into an attacker-chosen predicate oracle over another user's person properties.
2. **High, `posthog/api/feature_flag.py:3521`** — `model_to_dict` cannot emit `id` (`AutoField` is non-editable), and the Rust `FeatureFlag` requires it with no serde default. Deserialization fails, `flags.rs:177` warns and keeps the cached flag, so historical evaluation silently returns the *present-day* definition. The change's central feature does not work, and it fails confidently rather than loudly.
3. **High, `posthog/api/feature_flag.py:3388`** — the action returns `person_properties` under `required_scopes=["feature_flag:read"]`, a scope escalation past `person:read`.
4. **High, `rust/feature-flags/src/api/types.rs:675`** — `rollout_excluded` is gated on `rollout_percentage == 0.0`, so ordinary partial-rollout exclusion is reported with the false explanation "not evaluated due to an earlier condition matching".

**Two caveats you should weigh.** The promised build toolchain was absent — `cargo` and `rustc` are not installed, and `uv sync --frozen` refuses (uv 0.11.16 against the pinned `~=0.10.2`). I verified this myself. No finding is execution-confirmed; I spot-checked the load-bearing facts behind #2 and #6 against source. Separately, the single-seat path gives no corroboration signal, and seven of thirteen findings sit below full confidence.
