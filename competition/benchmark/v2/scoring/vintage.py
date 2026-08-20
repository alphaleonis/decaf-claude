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
rather than replaced. Superseded 2026-08-20 (`dcc-ryo4`) — all five were replaced, and every active
subject is now out-of-window on this key.

TWO KEYS, ONE OF THEM LOAD-BEARING (`dcc-60qk`). `merged_at` is the permissive key and the one that
gates. It is defensible for a specific thing: the *merged* PR — squashed commit, final state,
resolved conversation, the outcome — only exists after merge. But the artifact this instrument
actually shows a reviewer is the CHECKPOINT diff and the review threads written against it, and an
open PR carries both, publicly, from the day it is created. Measured on the corpus: five active
subjects were created and reviewed inside the window although they merged outside it, and
efcore#34127's PR was open for nearly two years.

So `pr_created_at` is the conservative key. Operator decision, 2026-08-20: **key on `merged_at`,
report both.** Every classification carries `status_by_pr_created_at` alongside `status`, and
`check_pooling()` gates on the merged key while `exposure_warnings()` names the subjects the
conservative key would have excluded. The assumption travels with the figure instead of hiding
underneath it; switching keys later is a one-line change plus a replacement round.
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

IN_WINDOW = "in-window"          # dated at or before the cutoff — memorization possible
OUT_OF_WINDOW = "out-of-window"  # dated after the cutoff — provably unmemorized
UNKNOWN = "unknown"              # no published cutoff for this model

# The key `classify()` and `check_pooling()` gate on. `pr_created_at` is computed and reported
# beside it, never instead of it — see the module docstring.
GATING_KEY = "merged_at"
EXPOSURE_KEY = "pr_created_at"


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


def describe(merged_at, model, pr_created_at=None):
    """Status plus the reasoning, so a result carries its own justification.

    `pr_created_at` is optional only because callers predating dcc-60qk do not pass it. Pass it
    whenever the fixture has it: without it the block cannot say whether the conservative key
    agrees, and a reader has no way to tell "agrees" from "was never checked".
    """
    status = classify(merged_at, model)
    cutoff = MODEL_CUTOFFS.get(model)
    if status == UNKNOWN:
        return {"status": status, "key": GATING_KEY, "model": model,
                "merged_at": str(merged_at)[:10],
                "why": f"no published training cutoff for {model!r}"}
    bound = _first_day_after(cutoff)
    out = {
        "status": status, "key": GATING_KEY, "model": model, "merged_at": str(merged_at)[:10],
        "model_cutoff": cutoff, "provably_clean_from": bound.isoformat(),
        "why": (f"{model} publishes a month-granular cutoff of {cutoff}; a subject is provably "
                f"out-of-window only if it merged on or after {bound.isoformat()}"),
    }
    # The conservative key, always reported, never gating (dcc-60qk).
    if pr_created_at:
        exposure = classify(pr_created_at, model)
        out["pr_created_at"] = str(pr_created_at)[:10]
        out["status_by_pr_created_at"] = exposure
        if exposure == IN_WINDOW and status == OUT_OF_WINDOW:
            out["exposure_note"] = (
                f"the PR was opened {str(pr_created_at)[:10]}, inside the window, and its diff and "
                f"review threads were public from then. This figure is licensed by the merge date; "
                f"under the conservative key it would not be.")
    else:
        out["pr_created_at"] = None
        out["status_by_pr_created_at"] = UNKNOWN
        out["exposure_note"] = ("pr_created_at not supplied, so the conservative key was not "
                                "evaluated — this is 'unchecked', not 'agrees'")
    return out


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


def exposure_warnings(subjects):
    """Subjects the CONSERVATIVE key would have excluded, for a figure the merge key licensed.

    Not an error and deliberately not wired into check_pooling: the operator chose `merged_at` as
    the gate on 2026-08-20 (`dcc-60qk`). This is the disclosure that goes with that choice, so a
    pooled figure states how much of itself rests on the permissive reading instead of leaving a
    reader to discover it. Returns [] when nothing is exposed.

    `subjects` is an iterable of {subject, status_by_pr_created_at}.
    """
    return sorted(s.get("subject", "?") for s in subjects
                  if s.get("status_by_pr_created_at") == IN_WINDOW)


def _main(argv):
    """CLI so a shell can gate on vintage without embedding Python in a heredoc.

        vintage.py <model> <merged_at> [pr_created_at]

    Prints `status|status_by_pr_created_at|exposure_note` on one line. One line and one separator
    because the caller is `run_cell_v2.sh` doing parameter expansion, and anything richer would put
    a JSON parser on the refusal path of the script whose job is to refuse cheaply.
    """
    if not 2 <= len(argv) <= 3:
        print("unknown|unknown|usage: vintage.py <model> <merged_at> [pr_created_at]")
        return 2
    model, merged = argv[0], argv[1]
    created = argv[2] if len(argv) == 3 and argv[2] else None
    if not merged:
        print("unknown|unknown|no merged_at supplied")
        return 2
    d = describe(merged, model, created)
    print(f"{d['status']}|{d.get('status_by_pr_created_at', UNKNOWN)}|{d.get('exposure_note', '')}")
    return 0


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(_main(_sys.argv[1:]))
