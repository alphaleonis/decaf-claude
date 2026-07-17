#!/usr/bin/env python3
"""Compute per-subject findings-quality metrics from a graded analysis.json + costs.json.

Deterministic: all arithmetic lives here, not in the LLM. See analysis/METHODOLOGY.md for
definitions. Usage: compute_metrics.py <analysis.json> <costs.json> [-o metrics.json]

analysis.json schema (produced by the LLM stages of /bench-analyze):
  { subject_id, lang, size, repo, pr, judge_model,
    answer_key:{ primary_bug:{...}, human_issues:[...], known_safe:[...] },
    clusters:[ { cluster_id, summary, file, line, category,
                 verdict:"TP-primary|TP-human|valid-other|false-positive|nitpick",
                 matches, judged_severity, confidence, rationale,
                 reported_by:[ {tool, repeat, subagent, severity} ] } ] }
"""
import json, sys, argparse
from collections import defaultdict

TP = {"TP-primary", "TP-human", "valid-other"}          # counts as a "good" finding
POS = {"TP-primary", "TP-human", "valid-other"}          # true/valid for precision

def rnd(x, n=2):
    return None if x is None else round(x, n)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("analysis"); ap.add_argument("costs")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()
    A = json.load(open(a.analysis)); C = json.load(open(a.costs))
    clusters = A.get("clusters", [])
    cells = C.get("cells", [])
    tools = sorted({c["tool"] for c in cells})
    reps_by_tool = defaultdict(set)
    cost = {}          # (tool,repeat) -> cell dict
    for c in cells:
        reps_by_tool[c["tool"]].add(c["repeat"])
        cost[(c["tool"], c["repeat"])] = c

    # --- attribute clusters to (tool, repeat) ---
    # found[(tool,repeat)] = list of cluster verdicts this cell reported (deduped at cluster level)
    found = defaultdict(list)
    # tool_clusters[tool] = set of cluster_ids the tool found in ANY repeat (for uniqueness/overlap)
    tool_clusters = defaultdict(set)
    tool_pos_clusters = defaultdict(set)   # TP/valid clusters per tool
    # per-tool subagent instances (for redundancy): tool -> list of (cluster_id, repeat, subagent)
    subagent_hits = defaultdict(list)
    for c in clusters:
        cid = c["cluster_id"]; verdict = c.get("verdict", "false-positive")
        seen_cell = set()
        for rb in c.get("reported_by", []):
            t, r = rb.get("tool"), rb.get("repeat")
            tool_clusters[t].add(cid)
            if verdict in POS:
                tool_pos_clusters[t].add(cid)
            subagent_hits[t].append((cid, r, rb.get("subagent")))
            if (t, r) not in seen_cell:
                seen_cell.add((t, r))
                found[(t, r)].append(verdict)

    # --- per-tool metrics ---
    out_tools = {}
    for t in tools:
        reps = sorted(reps_by_tool[t])
        rep_rows = []
        bug_hits = 0
        precisions = []; fps = []; valids = []; nits = []
        valid_counts = []
        for r in reps:
            vs = found.get((t, r), [])
            nfound = len(vs)
            cnt = lambda k: sum(1 for v in vs if v == k)
            tp_primary = cnt("TP-primary") > 0
            bug_hits += 1 if tp_primary else 0
            pos = sum(1 for v in vs if v in POS)   # distinct valid (worth-acting-on) findings this cell reported
            fp = cnt("false-positive"); nit = cnt("nitpick")
            prec = (pos / nfound) if nfound else None
            precisions.append(prec if prec is not None else 0.0)
            fps.append(fp); valids.append(cnt("valid-other")); nits.append(nit); valid_counts.append(pos)
            cc = cost.get((t, r), {})
            rep_rows.append({
                "repeat": r, "clusters_found": nfound, "valid_findings": pos,
                "tp_primary": tp_primary, "tp_human": cnt("TP-human"),
                "valid_other": cnt("valid-other"), "false_positive": fp, "nitpick": nit,
                "precision": rnd(prec), "cost_usd": cc.get("cost_usd"),
                "wall_s": cc.get("wall"), "ws_output": cc.get("ws_output"),
                "subagents": cc.get("subagents"),
            })
        nrep = len(reps) or 1
        # tool-level uniqueness: TP/valid clusters this tool found that NO other tool found
        others = set().union(*[tool_pos_clusters[o] for o in tools if o != t]) if len(tools) > 1 else set()
        unique_true = sorted(tool_pos_clusters[t] - others)
        # subagent distinctness (fan-out only): distinct clusters / subagent-instances
        hits = subagent_hits[t]
        n_inst = len(hits); n_distinct = len({h[0] for h in hits})
        distinctness = (n_distinct / n_inst) if n_inst else None
        mean_cost = _mean([rr["cost_usd"] for rr in rep_rows])
        n_tp_total = sum(rr["tp_primary"] + rr["tp_human"] + rr["valid_other"] for rr in rep_rows)
        out_tools[t] = {
            "repeats": rep_rows,
            "bug_catch_repeats": bug_hits, "n_repeats": len(reps),
            "bug_catch_rate": rnd(bug_hits / nrep),
            "precision_mean": rnd(_mean(precisions)),
            "valid_per_cell": rnd(_mean(valid_counts)),   # distinct valid (TP+valid-other) findings / cell
            "fp_per_cell": rnd(_mean(fps)),
            "valid_other_mean": rnd(_mean(valids)),
            "nitpick_per_cell": rnd(_mean(nits)),
            "unique_true": unique_true, "unique_true_n": len(unique_true),
            "mean_cost_usd": rnd(mean_cost),
            "cost_per_bug_caught": rnd(mean_cost / (bug_hits / nrep)) if bug_hits else None,
            "cost_per_true_finding": rnd((mean_cost * len(reps)) / n_tp_total) if n_tp_total else None,
            "subagent_distinctness": rnd(distinctness) if (out := _fanout(rep_rows)) else None,
            "mean_subagents": rnd(_mean([rr["subagents"] for rr in rep_rows])),
        }

    # --- pairwise overlap (Jaccard over TP/valid clusters) ---
    overlap = []
    for i in range(len(tools)):
        for j in range(i + 1, len(tools)):
            a1, b1 = tool_pos_clusters[tools[i]], tool_pos_clusters[tools[j]]
            uni = len(a1 | b1)
            overlap.append({"a": tools[i], "b": tools[j],
                            "jaccard": rnd(len(a1 & b1) / uni) if uni else 0.0,
                            "shared": len(a1 & b1)})

    metrics = {
        "subject_id": A.get("subject_id"), "lang": A.get("lang"), "size": A.get("size"),
        "repo": A.get("repo"), "pr": A.get("pr"), "judge_model": A.get("judge_model"),
        "n_clusters": len(clusters),
        "n_tp_primary_clusters": sum(1 for c in clusters if c.get("verdict") == "TP-primary"),
        "has_human_issues": bool(A.get("answer_key", {}).get("human_issues")),
        "tools": out_tools, "overlap": overlap,
    }
    js = json.dumps(metrics, indent=2)
    if a.out:
        open(a.out, "w").write(js)
        print(f"wrote {a.out}")
    else:
        print(js)

def _mean(xs):
    xs = [x for x in xs if x is not None]
    return (sum(xs) / len(xs)) if xs else None

def _fanout(rep_rows):
    ms = [rr["subagents"] for rr in rep_rows if rr.get("subagents") is not None]
    return ms and (sum(ms) / len(ms)) > 1

if __name__ == "__main__":
    main()
