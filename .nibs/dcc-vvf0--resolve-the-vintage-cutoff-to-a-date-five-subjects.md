---
# dcc-vvf0
version: 1
title: 'Resolve the vintage cutoff to a date: five subjects merged inside May 2026'
status: completed
type: task
priority: high
created_at: 2026-08-11T08:09:43Z
updated_at: 2026-08-11T09:23:06Z
parent: dcc-ho2w
order: t
---

METHODOLOGY-v2 section 6 makes it a **hard** admission rule that a new subject must be "merged after
2026-05" — out of window for both `BENCH_MODEL` and the judge, which are both Opus 5. The rule is
written at month granularity; `find_candidates.sh` resolves it to the earliest possible day
(`AFTER=2026-05-01`).

Five of the twelve pooled subjects merged *inside* May 2026:

| Subject | merged |
|---|---|
| PostHog/posthog#52408 | 2026-05-06 |
| PostHog/posthog#55149 | 2026-05-06 |
| grafana/grafana#124181 | 2026-05-08 |
| immich-app/immich#24627 | 2026-05-11 |
| jellyfin/jellyfin#12834 | 2026-05-21 |

Against a cutoff written as "2026-05" their status is unprovable in either direction. That is not
necessarily a corpus defect, but it is an unresolved ambiguity in a rule labelled hard, and section 6
also says a headline number "must never pool in-window and out-of-window cells without showing the
split" — which is not decidable for these five as things stand.

Found by `dcc-3cm6`; see `v2/analysis/HARNESS-REVIEW.md` M5.

## Options

- Resolve the cutoff to a **date**, re-screen, and replace whichever of the five fall inside it.
  Costs up to five subjects and a rebuild; `dcc-ixyy` recorded ~19k eligible PRs, so replacements are
  cheap to find.
- **Accept month granularity**, state it explicitly in section 6, and flag the five per cell so no
  headline pools them silently.

## Acceptance

- [x] Cutoff semantics stated as a date in METHODOLOGY-v2 section 6, not a month
- [x] `find_candidates.sh` default matches whatever is decided (2026-06-01)
- [x] Kept and flagged: `scoring/vintage.py` classifies per (subject, model) pair at analysis time and `check_pooling()` fails a mixed headline
- [x] The decision and its reasoning recorded where a later reader will find it

## Summary

**Completed 2026-08-11** — **Completed 2026-08-11.** The semantics turned out to be forced, not chosen; only the corpus response
was a judgment call.

**Anthropic publishes no day-level training cutoff.** There is no cutoff field in the Claude API model
catalog or in the Models API capability tree, and the model card states a month. So "2026-05" cannot
be resolved by lookup — only interpreted, and only the conservative reading is defensible: Opus 5 may
have seen anything up to 2026-05-31, so provably out-of-window means **merged 2026-06-01 or later**.
Reading it as 2026-05-01 would claim a cleanliness the published data does not support.

Under that bound, 5 of the 12 pooled subjects are in-window — and they are not scattered:

| Cell | Subject | merged |
|---|---|---|
| backend S | jellyfin#12834 | 2026-05-21 |
| backend M | grafana#124181 | 2026-05-08 |
| backend L | PostHog#52408 | 2026-05-06 |
| contract L | PostHog#55149 | 2026-05-06 |
| app-ui M | immich#24627 | 2026-05-11 |

**The entire `backend` row is in-window, so this corpus yields no backend number at all.** The
citable seven are contract S/M, app-ui S/L, library S/M/L.

**Operator decision: keep and flag, not replace.** Replacement was checked and was feasible — grafana
98 candidates after 2026-06-01, mattermost 67, immich 20, element-web 19, jellyfin 6 — but would have
cost five audited thread sets. Keeping them preserves the corpus at the price of a permanently
unreportable row.

The flag is enforced in code rather than left as a note, because a convention nobody checks is how
this kind of rule dies:

- `v2/scoring/vintage.py` — cutoff table plus `classify()`/`describe()`/`check_pooling()`. Status is
  computed per **(subject, model) pair at analysis time**, never baked into a fixture: section 6 is
  explicit that a stored boolean is wrong the day a model ships.
- `score_pooled.py` — refuses to emit metrics without `merged_at`, refuses an unknown judge model,
  and stamps `vintage` into `metrics.json`.
- `/bench-analyze-v2` copies `merged_at` from the fixture and leads its report with the status.
- `/bench-synthesize` gains a non-negotiable: never pool the two classes; call `check_pooling()`
  behind any cross-subject figure.
- `find_candidates.sh` defaults to 2026-06-01 so the flagged set cannot grow.

Two findings surfaced while resolving it:

- **All three null subjects are also in-window** (early May 2026). Accepted, not fixed — section 6's
  soak-beats-vintage rule already exempts the null arm, and a memorized null subject *deflates* the
  measured noise floor, which is the conservative direction.
- **`find_candidates.sh` has an undisclosed 100-result sampling cap** and uses comment volume as a
  proxy for thread count. Its zero for PostHog means "none in the top-100-by-comments window", not
  "none in the repo" — the same silent-cap class as [[dcc-nvrt]]. Now stated in its header and in §4A.

25 scoring tests pass, up from 21; the new ones pin the end-of-month resolution (including the
December year-roll), the pooling refusal, and the missing-`merged_at` guard.
