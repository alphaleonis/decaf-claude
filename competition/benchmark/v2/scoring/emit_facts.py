#!/usr/bin/env python3
"""Emit the benchmark's tidy FACT tables (nib dcc-t83x).

Usage: emit_facts.py <subject-dir> [more subject-dirs ...] [-o <facts-dir>]

Why this exists. On 2026-08-19 five conclusions about one 12-cell dataset reversed inside a single
session. Four of the five had the same cause: an intermediate artifact was interpreted in place of
the metric the experiment had pre-registered, because no artifact put arms side by side and every
question was answered by fresh ad-hoc code with its own column definitions.

The fix is not another table-emitting script — tables are where a definition gets baked in and then
diverges. It is to emit FACTS, in long form, and make every table a grouping over them:

    clusters.jsonl      one row per cluster           (the population)
    observations.jsonl  one row per cluster x arm x repeat  (who saw what)
    cells.jsonl         one row per cell              (what each run cost and whether it was clean)

Every table produced during that session — class breakdown, per-defect matrix, noise ratio, the
severity x class population grid, per-cell rates, model mix — is a GROUP BY over these three. A
published figure becomes re-derivable by someone who does not trust this script, which is the actual
requirement.

Nothing here computes a ratio. Ratios have guards (n>=10, pool size, coverage groups) and those
belong in the view, not in the facts. This file only reshapes what `score_pooled.py` and
`foldin.py` already produced, and asserts it round-trips.
"""
import json, os, re, sys, glob, argparse

V2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Kept in step with score_pooled.py deliberately: a verdict vocabulary that drifts between the
# scorer and the facts would let a published figure disagree with the data it claims to summarise.
sys.path.insert(0, os.path.join(V2, "scoring"))
from score_pooled import REAL, MINOR, NOISE, WRONG, ALL_VERDICTS  # noqa: E402


def isolation_verdict(cell_dir):
    """First recognised verdict line of isolation.txt. Absent file != clean — say which."""
    p = os.path.join(cell_dir, "isolation.txt")
    if not os.path.exists(p):
        return "MISSING"
    for line in open(p, errors="replace"):
        m = re.match(r"^(CLEAN|CONTAMINATED|NETWORK GIT|CANNOT VERIFY)", line)
        if m:
            return {"CANNOT VERIFY": "UNVERIFIED", "NETWORK GIT": "NETWORK-GIT"}.get(m.group(1), m.group(1))
    return "UNVERIFIED"


def cell_dir_for(subject_id, arm, repeat, shim):
    return os.path.join(V2, "runs", f"{subject_id}__{arm}__shim-{shim}__r{repeat}")


def emit(subject_dirs, out_dir):
    clusters, observations, cells = [], [], []
    for d in subject_dirs:
        d = os.path.abspath(d.rstrip("/"))
        subject = os.path.basename(d)
        an = json.load(open(os.path.join(d, "analysis.json")))
        shim = an.get("shim", "on")
        met_path = os.path.join(d, "metrics.json")
        met = json.load(open(met_path)) if os.path.exists(met_path) else {}
        vintage = (met.get("vintage") or {}).get("status")

        for c in an["clusters"]:
            v = c.get("verdict")
            if v is not None and v not in ALL_VERDICTS:
                sys.exit(f"FACTS REFUSED: {subject}/{c['cluster_id']} has verdict {v!r}, "
                         f"which is outside the closed set {sorted(ALL_VERDICTS)}")
            fc = c.get("finding_class")
            clusters.append({
                "subject": subject,
                "cluster_id": c["cluster_id"],
                "verdict": v,
                "judged_severity": c.get("judged_severity"),
                "finding_class": fc,
                "matches_thread": c.get("matches_thread"),
                "location": c.get("location"),
                "graded": v is not None,
                # `is_real` is the scorer's REAL set — matches-*/valid-other. valid-minor is
                # CORRECT BUT EXCLUDED; see METRICS.md. Carried as its own flag so a view can band
                # it separately instead of folding a correct finding into the miss column.
                "is_real": v in REAL if v else None,
                "is_valid_minor": v in MINOR if v else None,
                "is_noise": v in (NOISE | WRONG) if v else None,
                # The real-defect pool: the denominator most recall figures use. It is DYNAMIC —
                # adding an arm that finds something new enlarges it (nib dcc-dirp), so a view must
                # print its size beside any recall it derives.
                "in_defect_pool": bool(v in REAL and fc == "defect") if v else None,
            })
            for r in c.get("reported_by", []):
                observations.append({
                    "subject": subject,
                    "cluster_id": c["cluster_id"],
                    "arm": r["tool"],
                    "repeat": r["repeat"],
                    "disposition": r["disposition"],          # reported | demoted
                    "tool_severity": r.get("severity"),        # the TOOL's own severity, not the judge's
                })

        for cell in an["cells"]:
            cd = cell_dir_for(subject, cell["tool"], cell["repeat"], shim)
            meter = os.path.join(cd, "meter.json")
            models, is_error = {}, None
            if os.path.exists(meter):
                m = json.load(open(meter))
                is_error = m.get("is_error")
                models = {k: round(v.get("costUSD", 0), 4)
                          for k, v in (m.get("modelUsage") or {}).items()}
            cells.append({
                "subject": subject,
                "arm": cell["tool"],
                "repeat": cell["repeat"],
                "shim": shim,
                "cost_usd": cell.get("cost_usd"),
                "wall_s": cell.get("wall_s"),
                "access_total": cell.get("access_total"),
                "access_denied": cell.get("access_denied"),
                "models": models,
                "is_error": is_error,
                "isolation": isolation_verdict(cd),
                "cell_dir_present": os.path.isdir(cd),
                "vintage": vintage,
                "judge_model": an.get("judge_model"),
            })

    os.makedirs(out_dir, exist_ok=True)
    for name, rows in (("clusters", clusters), ("observations", observations), ("cells", cells)):
        with open(os.path.join(out_dir, f"{name}.jsonl"), "w") as f:
            for r in rows:
                f.write(json.dumps(r, sort_keys=True) + "\n")
    return clusters, observations, cells


def roundtrip(subject_dirs, clusters, observations, cells):
    """The facts must reproduce what the scorer already published, or they are not facts.

    Checks per subject and per arm that reported/found counts recomputed from observations match
    `metrics.json`. A mismatch means the facts and the metrics disagree about the same run, which is
    exactly the failure this file exists to prevent.
    """
    bad = []
    for d in subject_dirs:
        d = os.path.abspath(d.rstrip("/"))
        subject = os.path.basename(d)
        mp = os.path.join(d, "metrics.json")
        if not os.path.exists(mp):
            continue
        met = json.load(open(mp))
        graded = {c["cluster_id"] for c in clusters if c["subject"] == subject and c["graded"]}
        for arm, t in (met.get("tools") or {}).items():
            obs = [o for o in observations if o["subject"] == subject and o["arm"] == arm
                   and o["cluster_id"] in graded]
            found = {o["cluster_id"] for o in obs}
            rep = {o["cluster_id"] for o in obs if o["disposition"] == "reported"}
            if t.get("clusters_found") is not None and len(found) != t["clusters_found"]:
                bad.append(f"{subject}/{arm}: found {len(found)} from facts, {t['clusters_found']} in metrics.json")
            if t.get("clusters_reported") is not None and len(rep) != t["clusters_reported"]:
                bad.append(f"{subject}/{arm}: reported {len(rep)} from facts, {t['clusters_reported']} in metrics.json")
    return bad


def main():
    ap = argparse.ArgumentParser(description="Emit the tidy fact tables the analysis views read.")
    ap.add_argument("subject_dirs", nargs="+")
    ap.add_argument("-o", "--out", default=os.path.join(V2, "analysis", "facts"))
    ap.add_argument("--no-roundtrip", action="store_true",
                    help="skip the metrics round-trip check (for a subject not yet scored)")
    a = ap.parse_args()

    clusters, observations, cells = emit(a.subject_dirs, a.out)
    print(f"wrote {a.out}/")
    print(f"  clusters.jsonl      {len(clusters):>5} rows  "
          f"({sum(1 for c in clusters if c['graded'])} graded, "
          f"{sum(1 for c in clusters if c['in_defect_pool'])} in the real-defect pool)")
    print(f"  observations.jsonl  {len(observations):>5} rows  "
          f"({len({o['arm'] for o in observations})} arms)")
    print(f"  cells.jsonl         {len(cells):>5} rows  "
          f"({sum(1 for c in cells if c['isolation'] != 'CLEAN')} not CLEAN)")

    if not a.no_roundtrip:
        bad = roundtrip(a.subject_dirs, clusters, observations, cells)
        if bad:
            print("\nROUND-TRIP FAILED — the facts disagree with metrics.json:", file=sys.stderr)
            for b in bad:
                print(f"  {b}", file=sys.stderr)
            sys.exit(3)
        print("  round-trip vs metrics.json: OK")


if __name__ == "__main__":
    main()
