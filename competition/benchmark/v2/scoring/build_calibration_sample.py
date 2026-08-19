#!/usr/bin/env python3
"""Choose a subject's STANDING calibration sample, once (nib dcc-n4nf).

Usage: build_calibration_sample.py <subject-dir> [--n 15] [--force]

Judge drift between grading days is real and was unmeasured. On 2026-08-17 the same model with the
same prompt agreed with the pilot's pass-1 verdicts at 10-11/14 on prometheus and **3/12** on
efcore — inside a day when its own two passes agreed 12/14 and 9/12. Self-agreement cannot see this:
`judge_stability.py` compares today against today and never looks at the baseline.

The sample is FIXED and committed, not drawn fresh each day. A fresh draw confounds sampling with
drift — two days' numbers are then not comparable, which is exactly what happened on 2026-08-18/19.
The same clusters every day makes a difference in the number a difference in the judge.

Fixing the sample is safe because each grading pass runs in a fresh session with no memory of any
previous one, and the sample is always relabelled and mixed into whatever else is being graded, so
the judge cannot tell a calibration cluster from a live one.

Writes `<subject>/grading/calibration-sample.json`, carrying the pilot's pass-1 AND pass-2 verdicts
for each chosen cluster. Both baselines matter: on efcore the pilot's two passes disagreed with each
other 9/12, so agreement against one of them alone is not the whole picture.
"""
import json, os, sys, random, argparse

ORDER = ["matches-thread", "matches-key", "valid-other", "valid-minor", "trivia", "false-positive"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subject_dir")
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--force", action="store_true", help="overwrite an existing standing sample")
    a = ap.parse_args()

    d = os.path.abspath(a.subject_dir.rstrip("/"))
    subject = os.path.basename(d)
    out = os.path.join(d, "grading", "calibration-sample.json")
    if os.path.exists(out) and not a.force:
        sys.exit(f"{out} already exists. The sample is chosen ONCE — re-drawing it would make "
                 f"today's calibration incomparable with every earlier one. Pass --force only if "
                 f"you intend to reset the baseline and say so in the nib.")

    an = json.load(open(os.path.join(d, "analysis.json")))
    p2p = os.path.join(d, "grading", "verdicts-pass2.json")
    p2 = {v["cluster_id"]: v.get("verdict") for v in json.load(open(p2p))} if os.path.exists(p2p) else {}

    graded = [c for c in an["clusters"] if c.get("verdict")]
    if not graded:
        sys.exit(f"{subject}: no graded clusters — nothing to calibrate against")

    buckets = {}
    for c in graded:
        buckets.setdefault(c["verdict"], []).append(c)
    present = [v for v in ORDER if buckets.get(v)]
    per = max(1, a.n // max(1, len(present)))

    # Deterministic and subject-scoped, so the choice is reproducible from the repo alone.
    random.seed(f"dcc-n4nf:standing-calibration:{subject}")
    chosen = []
    for v in present:
        pool = sorted(buckets[v], key=lambda c: c["cluster_id"])
        chosen += random.sample(pool, min(per, len(pool)))
    rest = sorted([c for c in graded if c not in chosen], key=lambda c: c["cluster_id"])
    random.shuffle(rest)
    chosen += rest[:max(0, a.n - len(chosen))]
    chosen.sort(key=lambda c: c["cluster_id"])

    doc = {
        "subject": subject,
        "chosen_on": "2026-08-19",
        "n": len(chosen),
        "seed": f"dcc-n4nf:standing-calibration:{subject}",
        "note": ("STANDING sample — chosen once. Grade it blind (relabelled, mixed with live "
                 "clusters) on every grading day that touches this subject, and record the result "
                 "with judge_stability.py --calibration. Do not re-draw: a fresh draw confounds "
                 "sampling with drift."),
        "clusters": [{"cluster_id": c["cluster_id"],
                      "summary": c["summary"],
                      "location": c.get("location"),
                      "pilot_pass1": c.get("verdict"),
                      "pilot_pass2": p2.get(c["cluster_id"]),
                      "finding_class": c.get("finding_class")} for c in chosen],
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(doc, open(out, "w"), indent=1)
    dist = {}
    for c in chosen:
        dist[c["verdict"]] = dist.get(c["verdict"], 0) + 1
    agree = sum(1 for c in doc["clusters"]
                if c["pilot_pass2"] and c["pilot_pass1"] == c["pilot_pass2"])
    have2 = sum(1 for c in doc["clusters"] if c["pilot_pass2"])
    print(f"{subject:<32} n={len(chosen):<3} {dist}")
    print(f"{'':<32} the pilot's own two passes agree on {agree}/{have2} of this sample")


if __name__ == "__main__":
    main()
