#!/usr/bin/env python3
"""Vintage classification for a (subject, model) pair (nib dcc-vvf0).

METHODOLOGY-v2 section 5: a subject is *in-window* for a model if it merged before that model's
training cutoff, so the model may have memorized the PR and its review. Vintage is a property of the
PAIR, never of the subject alone — a boolean baked into a fixture is wrong the day a model ships.
Hence this module: fixtures store `merged_at`, and the status is computed here at analysis time.

WHY THE CUTOFFS ARE MONTHS. Anthropic publishes no day-level training cutoff — there is no cutoff
field in the model catalog or in the Models API capability tree, and the model card states a month.
So a cutoff cannot be resolved to a date by looking it up, only interpreted. This module takes the
conservative reading: a cutoff of "2026-05" means the model may have seen anything up to and
including 2026-05-31, so a subject is provably out-of-window only if it merged on 2026-06-01 or
later. Reading it the other way (2026-05-01) would claim a cleanliness the published data does not
support.

Operator decision, 2026-08-11: the five subjects that merged inside May 2026 are KEPT and flagged
rather than replaced. They are `in-window` here, and a headline that pools them with out-of-window
cells without showing the split is invalid — see check_pooling() and METHODOLOGY-v2 section 5.
"""
from datetime import date

# Model → published training cutoff, at the granularity Anthropic actually publishes (YYYY-MM).
# Update when a model ships; do NOT convert these to dates here — the resolution rule below is what
# turns a month into a bound, and it must stay in one place.
MODEL_CUTOFFS = {
    "claude-opus-5":       "2026-05",   # BENCH_MODEL and the judge — the binding constraint
    "claude-sonnet-5":     "2026-01",   # anthropic-code-review's review agents
    "claude-haiku-4-5":    "2025-07",   # anthropic-code-review's helpers
}

IN_WINDOW = "in-window"          # merged at or before the cutoff — memorization possible
OUT_OF_WINDOW = "out-of-window"  # merged after the cutoff — provably unmemorized
UNKNOWN = "unknown"              # no published cutoff for this model


def _first_day_after(cutoff_month):
    """The earliest merge date that is provably after a month-granular cutoff."""
    y, m = (int(x) for x in cutoff_month.split("-"))
    return date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)


def classify(merged_at, model):
    """Vintage status of one (subject, model) pair. `merged_at` is an ISO date or datetime string."""
    cutoff = MODEL_CUTOFFS.get(model)
    if not cutoff:
        return UNKNOWN
    merged = date.fromisoformat(str(merged_at)[:10])
    return OUT_OF_WINDOW if merged >= _first_day_after(cutoff) else IN_WINDOW


def describe(merged_at, model):
    """Status plus the reasoning, so a result carries its own justification."""
    status = classify(merged_at, model)
    cutoff = MODEL_CUTOFFS.get(model)
    if status == UNKNOWN:
        return {"status": status, "model": model, "merged_at": str(merged_at)[:10],
                "why": f"no published training cutoff for {model!r}"}
    bound = _first_day_after(cutoff)
    return {
        "status": status, "model": model, "merged_at": str(merged_at)[:10],
        "model_cutoff": cutoff, "provably_clean_from": bound.isoformat(),
        "why": (f"{model} publishes a month-granular cutoff of {cutoff}; a subject is provably "
                f"out-of-window only if it merged on or after {bound.isoformat()}"),
    }


def check_pooling(subjects):
    """Refuse to pool in-window and out-of-window cells into one headline without a split.

    `subjects` is an iterable of {subject, status}. METHODOLOGY-v2 section 5 forbids a headline that
    mixes the two without showing the split; this returns the error string to raise, or None.
    """
    seen = {}
    for s in subjects:
        seen.setdefault(s["status"], []).append(s.get("subject", "?"))
    if IN_WINDOW in seen and OUT_OF_WINDOW in seen:
        return (f"cannot pool {len(seen[IN_WINDOW])} in-window and {len(seen[OUT_OF_WINDOW])} "
                f"out-of-window subjects into one figure without showing the split "
                f"(in-window: {sorted(seen[IN_WINDOW])}) — METHODOLOGY-v2 section 5")
    return None
