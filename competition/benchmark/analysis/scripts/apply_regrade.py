#!/usr/bin/env python3
"""Apply a valid-minor/trivia regrade to a subject's analysis.json.

Only clusters currently graded `nitpick` are touched; each gets the regrade verdict, keeps its
original confidence/rationale in regrade_* fields, and records regraded_from="nitpick" for audit.
Usage: apply_regrade.py <analysis.json> <regrade.json>
"""
import json, sys

analysis_path, regrade_path = sys.argv[1], sys.argv[2]
A = json.load(open(analysis_path))
R = {r["cluster_id"]: r for r in json.load(open(regrade_path))}

changed = {"valid-minor": 0, "trivia": 0}
missing = []
for c in A["clusters"]:
    if c["verdict"] != "nitpick":
        continue
    r = R.get(c["cluster_id"])
    if not r:
        missing.append(c["cluster_id"])
        continue
    c["regraded_from"] = "nitpick"
    c["verdict"] = r["verdict"]
    c["regrade_confidence"] = r.get("confidence")
    c["regrade_rationale"] = r.get("rationale", "")
    changed[r["verdict"]] += 1

if missing:
    sys.exit(f"ERROR: no regrade verdict for: {missing}")
json.dump(A, open(analysis_path, "w"), indent=2)
print(f"{analysis_path}: {changed['valid-minor']} valid-minor, {changed['trivia']} trivia")
