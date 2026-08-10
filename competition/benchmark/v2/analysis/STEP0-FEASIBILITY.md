# Step 0 feasibility: does "revert names a mechanism" exist outside infrastructure?

Run 2026-08-10 for `dcc-595v`. Method: 273 merged revert PRs across 9 application/SPA/full-stack
repos and 3 infrastructure repos (25 each), screened with `v2/screen_step0.sh`, then hand-classified
against the METHODOLOGY-v2 Step 0 rule — *does the fix body name a mechanism, or only a symptom?*

**Answer: yes, comfortably. The hypothesis that application repos cannot satisfy Step 0 is wrong.**

## Rates

| Group | PRs sampled | link+causal signal | hand-confirmed Step 0 pass |
|---|---|---|---|
| Infrastructure | 75 | 15 (20%) | ~7 (**9%**) |
| Application | 198 | 21 (11%) | ~9 (**4.5%**) |

Infrastructure is roughly twice as productive per revert PR. That is a **screening cost difference,
not a feasibility barrier** — and application repos merge far more PRs, so absolute availability is
comparable.

## Domain is the wrong predictor; repo discipline is the right one

Per-repo `link+causal` counts out of 25:

```
rust-lang/rust        7      mattermost/mattermost  6      PostHog/posthog   6
kubernetes/kubernetes 5      prometheus/prometheus  3      immich            3
jellyfin              2      grafana                2      element-web       2
twentyhq/twenty       0      outline/outline        0
```

`mattermost` and `PostHog` **match or beat kubernetes and prometheus**. The near-zero repos
(`outline`, `twentyhq`) are younger and smaller, not more application-shaped. `cal.com` returned zero
merged revert PRs to the search at all.

So the original reasoning — "revert discipline is plausibly why every survivor is infra" — confused
*project maturity* with *project domain*. Mature application projects have the same discipline. What
they do **not** have is the k8s/rust habit of a formal re-land PR, which is where subject 8's key came
from; that source will be rarer here.

## What application reverts fail on

The failures differ in kind, and this is the real cost. Application repos revert for **non-defect
reasons** far more often: CI configuration changes, capacity incidents, release management, upstream
dependency breakage, and plain developer error ("I did something wrong in #19630… I commit to the
remote incorrectly"). Those inflate the denominator without ever being scorable.

Infrastructure has its own version of this — backports, "missed the train", bare triagebot reverts,
and hedged bodies ("Performance regression fix (maybe — it's not entirely certain yet)", which is a
Step 0 failure by our own rule). Both groups are noisier than the surviving corpus suggests.

## Concrete candidates found

Not vetted past Step 0 — screens 2–4 (defect present in the diff, `must_flag` writable, vintage) still
apply. Listed because they demonstrate the pattern is real, and several are vintage-safe:

| Candidate | Stack / shape | Mechanism named | Merged |
|---|---|---|---|
| PostHog#65223 | Django + React + ClickHouse, full-stack | `SELECT *` expansion changed to follow each table's stamped `position` order | 2026-06-22 ✅ safe |
| mattermost#35996 | Go + React | two CI regressions, one a deterministic named test failure | 2026-04-09 ✅ safe |
| grafana#127870 | Go + React, UI-heavy | links both the introducing and the fixing PR | 2026-07-03 ✅ safe |
| immich#28260 | TS + Dart, SPA + backend | `ˆ` in tag names disallowed upstream, breaking metadata writing | 2026-05-06 ✅ safe |
| mattermost#30337 | Go + React | "accidentally changed it so that these APIs returned nil" — **a contract-crossing defect**, the shape the corpus entirely lacks | 2025-02-26 |
| jellyfin#12414 | .NET + web UI | limit applied at the wrong level; behavior described in the linked issue | 2024-08-23 |

Application repos are more active, so recent reverts are plentiful — **four of six candidates postdate
the Jan-2026 cutoff**, against only two of seven in the current surviving corpus. Vintage safety is
*easier* here, not harder.

## What this settles, and what it does not

**Settles:** the corpus axis is genuinely open. Nothing forces a retreat to infrastructure-only
subjects, and application, UI and contract-crossing subjects can be sourced against the existing
screen. `dcc-ixyy` can target them.

**Does not settle:** the instrument. The n=12 density problem was never a feasibility argument — it
is arithmetic about how few entries a key yields per subject, and it applies identically to
application subjects. Sourcing better subjects raises relevance; it does not fix ranking power.
Pooled adjudication still has to be decided on its own merits.

One caveat on these rates: a single 25-PR sample per repo, classified by one reader against a
judgment-based rule. The gap between 9% and 4.5% is well within what a different sample could move.
Treat the direction as informative and the magnitudes as rough.
