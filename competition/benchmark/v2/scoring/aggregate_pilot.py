#!/usr/bin/env python3
"""Cross-subject aggregation for v2, with the pilot's publication rules enforced (nib dcc-vkeh).

Usage: aggregate_pilot.py <subject-dir> [<subject-dir> ...] -o pilot-data.json

This is the v2 counterpart of the v1 `aggregate_synthesis.py`. It is NOT that script: v1's dataset is
void and its aggregator reads v1-archive paths.

Every rule below came out of the pilot and each one exists because a figure without it was wrong or
unstable (`analysis/PILOT-RESULTS.md`):

  n >= 10       A precision ratio over fewer than 10 reported clusters is not a measurement. The
                pilot's every unstable figure came from a tool below that line: `ours-bugs` moved
                1.00 -> 0.60 when a second repeat took it from n=3 to n=5. Below the floor this
                emits counts and `precision: null`, never a ratio.
  two passes    Judge variance exceeds tool variance at every denominator size, so a single-pass
                figure is a point estimate of something that moves. Where a subject has a second
                graded pass, per-tool figures are emitted as median with the observed range.
  no mixing     METHODOLOGY-v2 section 5 forbids pooling in-window and out-of-window subjects into
                one headline. Enforced by vintage.check_pooling, which refuses rather than warns.
  null apart    The null arm is a different instrument. It is reported beside the pooled subjects,
                never averaged into them.

Exits 3 on a violation rather than emitting a number.
"""
import json, sys, argparse, os, statistics
from collections import defaultdict
import vintage

MIN_CLUSTERS_FOR_RATIO = 10


class Refused(Exception):
    """A rule fired. Emit nothing."""


def load_subject(d):
    m = json.load(open(os.path.join(d, "metrics.json")))
    alt = os.path.join(d, "grading", "metrics-pass2.json")
    m2 = json.load(open(alt)) if os.path.exists(alt) else None
    fx = json.load(open(os.path.join(d, "fixture.json")))
    return {
        "dir": d,
        "subject": m.get("subject"),
        "instrument": m.get("instrument"),
        "app_type": fx.get("app_type"),
        "size": fx.get("size"),
        "status": (m.get("vintage") or {}).get("status", "unknown"),
        "n_cells": m.get("n_cells"),
        "n_clusters": m.get("n_clusters"),
        "repeats": max((c.get("repeat", 1) for c in json.load(
            open(os.path.join(d, "analysis.json")))["cells"]), default=1),
        "tools": m["tools"],
        "tools_p2": (m2 or {}).get("tools"),
        "threads": m.get("threads"),
    }


def per_tool(subj, tool):
    """One tool on one subject: the ratio only if the denominator earns it, plus the pass range."""
    a = subj["tools"][tool]
    n = a["clusters_reported"]
    out = {
        "reported": n, "found": a["clusters_found"], "real": a["real"],
        "unique_real": a["unique_real"], "false_positive": a["false_positive"],
        "trivia": a["trivia"], "valid_minor": a["valid_minor"],
        "cost_usd": a["cost_usd"], "cost_per_real": a["cost_per_real_finding"],
        "thread_recall": a["thread_recall"], "thread_recall_found": a["thread_recall_found"],
        "below_floor": n < MIN_CLUSTERS_FOR_RATIO,
    }
    vals = [a["precision"]] if a["precision"] is not None else []
    if subj["tools_p2"] and tool in subj["tools_p2"]:
        p2 = subj["tools_p2"][tool]["precision"]
        if p2 is not None:
            vals.append(p2)
    if out["below_floor"] or not vals:
        # Deliberately null, not omitted: a consumer must see that the tool WAS measured and that the
        # ratio was withheld, otherwise a missing key reads as a missing cell.
        out["precision"] = None
        out["precision_range"] = None
        out["withheld_reason"] = (f"n={n} < {MIN_CLUSTERS_FOR_RATIO} reported clusters"
                                  if out["below_floor"] else "no graded pass")
    else:
        out["precision"] = round(statistics.median(vals), 3)
        out["precision_range"] = [round(min(vals), 3), round(max(vals), 3)] if len(vals) > 1 else None
        out["passes"] = len(vals)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subjects", nargs="+")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    subs = [load_subject(d) for d in a.subjects]

    pooled = [s for s in subs if s["instrument"] != "null-arm"]
    nulls = [s for s in subs if s["instrument"] == "null-arm"]

    err = vintage.check_pooling([{"subject": s["subject"], "status": s["status"]} for s in pooled])
    if err:
        raise Refused(err)

    # A "cross-subject" figure that covers one application type is not cross-subject in the sense the
    # corpus was designed around (size x application type). Say so in the data rather than let a
    # reader infer breadth from the subject count.
    app_types = sorted({s["app_type"] for s in pooled})
    sizes = sorted({s["size"] for s in pooled})

    tools = sorted({t for s in subs for t in s["tools"]})
    agg = {}
    for t in tools:
        rows = {s["subject"]: per_tool(s, t) for s in pooled if t in s["tools"]}
        ratios = [r["precision"] for r in rows.values() if r["precision"] is not None]
        recalls = [r["thread_recall"] for r in rows.values() if r["thread_recall"] is not None]
        agg[t] = {
            "per_subject": rows,
            "subjects_above_floor": len(ratios),
            "precision_mean": round(statistics.mean(ratios), 3) if len(ratios) == len(rows) else None,
            "precision_note": (None if len(ratios) == len(rows) else
                               f"withheld: {len(rows) - len(ratios)} of {len(rows)} subjects below the "
                               f"n>={MIN_CLUSTERS_FOR_RATIO} floor"),
            "thread_recall_mean": round(statistics.mean(recalls), 3) if recalls else None,
            "real_total": sum(r["real"] for r in rows.values()),
            "unique_real_total": sum(r["unique_real"] for r in rows.values()),
            "fp_total": sum(r["false_positive"] for r in rows.values()),
            # The four-way split, rolled up. Reported separately from precision because these tools
            # almost never emit a false positive (3 in 793 findings across the pilot) and routinely
            # emit correct-but-immaterial output — collapsing to real-vs-wrong hides the only failure
            # mode that separates them. `reported_total` is the denominator for all four.
            "reported_total": sum(r["reported"] for r in rows.values()),
            "valid_minor_total": sum(r["valid_minor"] for r in rows.values()),
            "trivia_total": sum(r["trivia"] for r in rows.values()),
            "mix": None,  # filled below, once the denominator is known
            "cost_total": round(sum(r["cost_usd"] for r in rows.values()), 2),
            "null": {s["subject"]: per_tool(s, t) for s in nulls if t in s["tools"]},
        }
        n = agg[t]["reported_total"]
        if n:
            agg[t]["mix"] = {
                "substantive": round(agg[t]["real_total"] / n, 3),
                "valid_minor": round(agg[t]["valid_minor_total"] / n, 3),
                "trivia": round(agg[t]["trivia_total"] / n, 3),
                "false_positive": round(agg[t]["fp_total"] / n, 3),
            }
            # The four shares partition the reported set, so they must sum to 1. A drift here means
            # a verdict escaped the vocabulary and the mix is describing a different population than
            # the precision figure beside it.
            tot = sum(agg[t]["mix"].values())
            if abs(tot - 1.0) > 0.005:
                raise Refused(f"{t}: verdict mix sums to {tot:.3f}, not 1.000 — a verdict is "
                              f"unaccounted for and the mix does not describe the reported set")

    out = {
        "generated_from": [s["dir"] for s in subs],
        "rules": {
            "min_clusters_for_ratio": MIN_CLUSTERS_FOR_RATIO,
            "precision_is_median_of_passes": True,
            "null_arm_reported_separately": True,
        },
        "scope": {
            "pooled_subjects": len(pooled), "null_subjects": len(nulls),
            "app_types_covered": app_types, "sizes_covered": sizes,
            "single_app_type": len(app_types) == 1,
            "total_cells": sum(s["n_cells"] for s in subs),
            "total_clusters": sum(s["n_clusters"] for s in subs),
        },
        "subjects": [{k: s[k] for k in
                      ("subject", "app_type", "size", "status", "n_cells", "n_clusters", "repeats")}
                     for s in subs],
        "tools": agg,
    }
    s = json.dumps(out, indent=2)
    if a.out:
        open(a.out, "w").write(s + "\n"); print(f"wrote {a.out}")
    else:
        print(s)
    print(f"  pooled {len(pooled)} subject(s), null {len(nulls)}; app types {app_types}; "
          f"{'SINGLE APPLICATION TYPE — not a cross-type figure' if len(app_types) == 1 else ''}")
    for t, d in agg.items():
        if d["precision_note"]:
            print(f"  {t}: {d['precision_note']}")


if __name__ == "__main__":
    try:
        main()
    except Refused as e:
        print(f"REFUSED — rule fired, no figures emitted:\n  {e}", file=sys.stderr)
        sys.exit(3)
