#!/usr/bin/env python3
"""Aggregate every graded subject into the cross-subject synthesis dataset.

Deterministic: all cross-subject arithmetic lives here, not in the LLM — the same rule
compute_metrics.py follows per subject. Reads every analysis.json + metrics.json under
analysis/subject-*/ and emits one JSON blob with the numbers the synthesis page needs.

Usage:  aggregate_synthesis.py [analysis_dir] [-o synthesis-data.json]

Why shares, not counts: cluster granularity varies per subject (18-95 clusters observed),
so raw per-run counts are NOT comparable across subjects. Quality comparisons use each
cell's mix as a share of what that cell reported. Substantive share == precision by
construction; the four tiers sum to 100%. Verify both when sanity-checking output.
"""
import json, glob, os, argparse, statistics as st
from collections import defaultdict

SUBSTANTIVE = {"TP-primary", "TP-human", "valid-other"}
MINOR = {"valid-minor"}
TRIVIA = {"trivia", "nitpick"}          # legacy 'nitpick' folds into trivia
FP = {"false-positive"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("analysis_dir", nargs="?", default=os.path.join(os.path.dirname(__file__), ".."))
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()

    cells = {}      # (subject,size,lang,tool,repeat) -> tier counts
    subjects = {}

    for path in sorted(glob.glob(os.path.join(a.analysis_dir, "subject-*", "analysis.json"))):
        d = json.load(open(path))
        sid = d["subject_id"]
        subjects[sid] = {"lang": d["lang"], "size": d["size"], "repo": d.get("repo"),
                         "pr": d.get("pr"), "n_clusters": len(d["clusters"])}
        for c in d["clusters"]:
            v = c.get("verdict", "false-positive")
            # one credit per (tool,repeat) that reported this cluster, however many findings it sent
            for tool, rep in {(r["tool"], r["repeat"]) for r in c.get("reported_by", [])}:
                k = (sid, d["size"], d["lang"], tool, rep)
                e = cells.setdefault(k, {"subst": 0, "minor": 0, "triv": 0, "fp": 0, "tot": 0, "tp_primary": 0})
                e["tot"] += 1
                if v in SUBSTANTIVE:
                    e["subst"] += 1
                    if v == "TP-primary":
                        e["tp_primary"] += 1
                elif v in MINOR:  e["minor"] += 1
                elif v in TRIVIA: e["triv"] += 1
                elif v in FP:     e["fp"] += 1

    # per-cell cost/timing from each subject's metrics.json
    cost = {}
    for path in sorted(glob.glob(os.path.join(a.analysis_dir, "subject-*", "metrics.json"))):
        m = json.load(open(path))
        for tool, t in m["tools"].items():
            for r in t["repeats"]:
                cost[(m["subject_id"], tool, r["repeat"])] = {
                    "cost_usd": r["cost_usd"], "wall_s": r["wall_s"],
                    "ws_output": r.get("ws_output"), "subagents": r.get("subagents")}

    rows = []
    for (sid, size, lang, tool, rep), e in cells.items():
        c = cost.get((sid, tool, rep), {})
        rows.append({"subject": sid, "size": size, "lang": lang, "tool": tool, "repeat": rep,
                     **e, "caught": e["tp_primary"] > 0, **c})

    tools = sorted({r["tool"] for r in rows})
    mean = lambda xs: round(st.mean(xs), 4) if xs else None
    share = lambda rs, k: mean([r[k] / r["tot"] for r in rs if r["tot"]])

    def tool_block(rs):
        n = len(rs)
        subst_tot = sum(r["subst"] for r in rs)
        return {
            "cells": n,
            "bug_caught": sum(1 for r in rs if r["caught"]),
            "bug_catch_rate": round(sum(1 for r in rs if r["caught"]) / n, 4) if n else None,
            "substantive_share": share(rs, "subst"), "minor_share": share(rs, "minor"),
            "trivia_share": share(rs, "triv"), "fp_share": share(rs, "fp"),
            "clusters_per_cell": mean([r["tot"] for r in rs]),
            "substantive_per_cell": mean([r["subst"] for r in rs]),
            "fp_per_cell": mean([r["fp"] for r in rs]),
            "cost_per_cell": mean([r["cost_usd"] for r in rs if r.get("cost_usd") is not None]),
            "cost_total": round(sum(r.get("cost_usd") or 0 for r in rs), 2),
            "cost_per_substantive": round(sum(r.get("cost_usd") or 0 for r in rs) / subst_tot, 2) if subst_tot else None,
            "out_tokens_per_cell": mean([r["ws_output"] for r in rs if r.get("ws_output")]),
            "wall_min_per_cell": mean([r["wall_s"] / 60 for r in rs if r.get("wall_s")]),
            "subagents_per_cell": mean([r["subagents"] for r in rs if r.get("subagents")]),
        }

    # severity calibration + unique-true come straight from the per-subject metrics
    cal, uniq = defaultdict(list), defaultdict(int)
    for path in sorted(glob.glob(os.path.join(a.analysis_dir, "subject-*", "metrics.json"))):
        m = json.load(open(path))
        for tool, t in m["tools"].items():
            if t.get("severity_calibration") is not None:
                cal[tool].append(t["severity_calibration"])
            uniq[tool] += t.get("unique_true_n", 0)

    out = {
        "n_subjects": len(subjects), "n_cells": len(rows),
        "total_cost_usd": round(sum(r.get("cost_usd") or 0 for r in rows), 2),
        "subjects": subjects,
        "tools": {t: {**tool_block([r for r in rows if r["tool"] == t]),
                      "severity_calibration": mean(cal[t]), "unique_true": uniq[t]} for t in tools},
        "by_size": {sz: {"subjects": len({r["subject"] for r in rows if r["size"] == sz}),
                         **tool_block([r for r in rows if r["size"] == sz])}
                    for sz in ("small", "medium", "large") if any(r["size"] == sz for r in rows)},
        "bug_catch_matrix": {t: {str(sid): sum(1 for r in rows if r["tool"] == t and r["subject"] == sid and r["caught"])
                                 for sid in sorted(subjects)} for t in tools},
        "caught_by_subject": {str(sid): sum(1 for r in rows if r["subject"] == sid and r["caught"])
                              for sid in sorted(subjects)},
        "cells": rows,
    }

    txt = json.dumps(out, indent=1)
    if a.out:
        open(a.out, "w").write(txt)
        print(f"wrote {a.out}")
    else:
        print(txt)

    # sanity checks the synthesis MUST pass before it is written up
    print("\n--- sanity ---")
    for t in tools:
        b = out["tools"][t]
        s = sum(b[k] for k in ("substantive_share", "minor_share", "trivia_share", "fp_share"))
        flag = "OK " if abs(s - 1.0) < 0.005 else "BAD"
        print(f"  {flag} {t:28s} tiers sum {s:.3f}  substantive_share {b['substantive_share']:.3f} "
              f"(must equal precision_mean in per-subject metrics)")
    print(f"\n  {out['n_subjects']} subjects · {out['n_cells']} cells · ${out['total_cost_usd']:,.0f}")
    sat = sum(1 for v in out["caught_by_subject"].values() if v >= 9)
    print(f"  subjects where >=9/10 cells caught the bug: {sat}/{out['n_subjects']} "
          f"(if most, recall is saturated — say so in the report)")


if __name__ == "__main__":
    main()
