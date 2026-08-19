#!/usr/bin/env python3
"""One self-test per guard in emit_facts.py / compare_arms.py (nib dcc-t83x).

Every check here corresponds to a specific way the 2026-08-19 analysis went wrong. Run these rather
than trusting the scripts read correctly — the failure they exist to prevent looked like a working
analysis right up until the conclusions reversed.
"""
import json, os, sys, tempfile, subprocess, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.dirname(HERE)
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS  {name}")
    else:
        fail += 1
        print(f"  FAIL  {name}  {detail}")


def fixture(tmp, cells, clusters, metrics=None):
    """Minimal subject dir: analysis.json (+metrics.json) and matching run dirs with meters."""
    d = os.path.join(tmp, "pooled", "subj-x")
    os.makedirs(d, exist_ok=True)
    an = {"subject": "subj-x", "shim": "on", "judge_model": "claude-opus-5",
          "cells": cells, "clusters": clusters}
    json.dump(an, open(os.path.join(d, "analysis.json"), "w"))
    if metrics is not None:
        json.dump(metrics, open(os.path.join(d, "metrics.json"), "w"))
    for c in cells:
        rd = os.path.join(V2, "runs", f"subj-x__{c['tool']}__shim-on__r{c['repeat']}")
        os.makedirs(rd, exist_ok=True)
        json.dump({"is_error": False, "modelUsage": {m: {"costUSD": 1.0} for m in c["_models"]}},
                  open(os.path.join(rd, "meter.json"), "w"))
        open(os.path.join(rd, "isolation.txt"), "w").write("CLEAN: nothing\n")
    return d


def cluster(cid, verdict, cls, sev="medium", by=()):
    return {"cluster_id": cid, "summary": f"s {cid}", "location": "f.go:1",
            "verdict": verdict, "judged_severity": sev, "finding_class": cls,
            "matches_thread": None,
            "reported_by": [{"tool": t, "repeat": r, "severity": "high", "disposition": d,
                             "finding_index": 0} for t, r, d in by]}


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(HERE, script), *args],
                          capture_output=True, text=True)


print("== emit_facts: the facts must reproduce the metrics they claim to summarise ==")
tmp = tempfile.mkdtemp()
made = []
try:
    cells = [{"tool": "arm-a", "repeat": 1, "cost_usd": 2.0, "wall_s": 10,
              "access_total": 0, "access_denied": 0, "_models": ["claude-opus-5"]}]
    cl = [cluster("x01", "valid-other", "defect", by=[("arm-a", 1, "reported")]),
          cluster("x02", "trivia", "defect", by=[("arm-a", 1, "demoted")])]
    met = {"tools": {"arm-a": {"clusters_reported": 1, "clusters_found": 2}}}
    d = fixture(tmp, cells, cl, met)
    made = [os.path.join(V2, "runs", "subj-x__arm-a__shim-on__r1")]
    out = os.path.join(tmp, "facts")
    r = run("emit_facts.py", d, "-o", out)
    check("round-trip passes when facts agree with metrics.json", r.returncode == 0, r.stderr[:200])
    rows = [json.loads(l) for l in open(os.path.join(out, "clusters.jsonl"))]
    check("in_defect_pool is real AND defect-class",
          [x["in_defect_pool"] for x in rows] == [True, False])
    check("valid-minor carried as its own flag, not folded into real or noise",
          all("is_valid_minor" in x for x in rows))
    obs = [json.loads(l) for l in open(os.path.join(out, "observations.jsonl"))]
    check("one observation row per cluster x arm x repeat", len(obs) == 2)
    check("disposition preserved verbatim",
          sorted(o["disposition"] for o in obs) == ["demoted", "reported"])

    # break the metrics so the facts and the scorer disagree
    met["tools"]["arm-a"]["clusters_reported"] = 99
    json.dump(met, open(os.path.join(d, "metrics.json"), "w"))
    r = run("emit_facts.py", d, "-o", out)
    check("round-trip FAILS loudly when facts disagree with metrics.json",
          r.returncode == 3 and "ROUND-TRIP FAILED" in r.stderr, f"rc={r.returncode}")

    # a verdict outside the closed set must stop the pipeline, not pass through
    cl2 = [cluster("x03", "sort-of-real", "defect")]
    d2 = fixture(tmp, cells, cl2, None)
    r = run("emit_facts.py", d2, "-o", out, "--no-roundtrip")
    check("refuses a verdict outside the closed set",
          r.returncode != 0 and "outside the closed set" in (r.stdout + r.stderr))
finally:
    for m in made:
        shutil.rmtree(m, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)

print("\n== compare_arms: the guards that would have caught the 2026-08-19 reversals ==")
tmp = tempfile.mkdtemp()
try:
    facts = os.path.join(tmp, "facts")
    os.makedirs(facts)

    def write(name, rows):
        with open(os.path.join(facts, f"{name}.jsonl"), "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    # arm-mixed has non-nested model sets (the ours-bugs trap); arm-nested is merely a lane
    # not dispatched on one run; arm-narrow reports too little to earn a ratio.
    write("cells", [
        {"subject": "s1", "arm": "arm-mixed", "repeat": 1, "cost_usd": 1, "wall_s": 1,
         "models": {"claude-opus-5": 1, "claude-haiku-4-5-20251001": 1}, "isolation": "CLEAN"},
        {"subject": "s1", "arm": "arm-mixed", "repeat": 2, "cost_usd": 1, "wall_s": 1,
         "models": {"claude-opus-5": 1, "claude-sonnet-5": 1}, "isolation": "CLEAN"},
        {"subject": "s1", "arm": "arm-nested", "repeat": 1, "cost_usd": 1, "wall_s": 1,
         "models": {"claude-opus-5": 1}, "isolation": "CLEAN"},
        {"subject": "s1", "arm": "arm-nested", "repeat": 2, "cost_usd": 1, "wall_s": 1,
         "models": {"claude-opus-5": 1, "claude-sonnet-5": 1}, "isolation": "CLEAN"},
        {"subject": "s1", "arm": "arm-narrow", "repeat": 1, "cost_usd": 1, "wall_s": 1,
         "models": {"claude-opus-5": 1}, "isolation": "CLEAN"},
        {"subject": "s2", "arm": "arm-wide", "repeat": 1, "cost_usd": 1, "wall_s": 1,
         "models": {"claude-opus-5": 1}, "isolation": "CLEAN"},
    ])
    cls = []
    for i in range(12):
        cls.append({"subject": "s1", "cluster_id": f"c{i:02d}", "verdict": "valid-other",
                    "judged_severity": "medium", "finding_class": "defect", "matches_thread": None,
                    "location": "f:1", "graded": True, "is_real": True, "is_valid_minor": False,
                    "is_noise": False, "in_defect_pool": True})
    cls.append({"subject": "s2", "cluster_id": "d00", "verdict": "valid-other",
                "judged_severity": "medium", "finding_class": "defect", "matches_thread": None,
                "location": "f:1", "graded": True, "is_real": True, "is_valid_minor": False,
                "is_noise": False, "in_defect_pool": True})
    write("clusters", cls)
    obs = []
    for i in range(12):
        obs.append({"subject": "s1", "cluster_id": f"c{i:02d}", "arm": "arm-nested",
                    "repeat": 1, "disposition": "reported", "tool_severity": "high"})
    for i in range(3):
        obs.append({"subject": "s1", "cluster_id": f"c{i:02d}", "arm": "arm-narrow",
                    "repeat": 1, "disposition": "reported", "tool_severity": "high"})
    obs.append({"subject": "s1", "cluster_id": "c00", "arm": "arm-mixed",
                "repeat": 1, "disposition": "reported", "tool_severity": "high"})
    obs.append({"subject": "s2", "cluster_id": "d00", "arm": "arm-wide",
                "repeat": 1, "disposition": "reported", "tool_severity": "high"})
    write("observations", obs)

    r = run("compare_arms.py", "--facts", facts)
    o = r.stdout
    check("refuses an arm with INCOMPATIBLE model sets (the ours-bugs trap)",
          "REFUSED  arm-mixed" in o)
    check("does NOT refuse merely nested model sets", "REFUSED  arm-nested" not in o)
    check("reports nested variation as a visible NOTE", "NOTE     arm-nested" in o)
    check("withholds a ratio below the n>=10 floor", "WITHHELD  arm-narrow" in o)
    check("emits a precision for an arm at or above the floor", "1.000" in o)
    check("separates coverage groups so cross-pool ranking is impossible",
          o.count("COVERAGE GROUP") >= 2)
    check("prints the pool size beside the group", "real-defect pool for this group" in o)
    check("legend states valid-minor is excluded from precision",
          "Excluded from `real`" in o and "NOT noise" in o)
    check("legend states class and verdict are orthogonal",
          "defect-CLASS and trivia-VERDICT" in o)
    check("states the pool is dynamic", "DYNAMIC" in o)

    r2 = run("compare_arms.py", "--facts", facts, "--allow-mixed")
    check("--allow-mixed lets the mixed arm through when asked explicitly",
          "arm-mixed" in r2.stdout.split("COVERAGE GROUP")[1])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n== assert_foldin_movements: benign vs unexplained (nib dcc-dirp) ==")
tmp = tempfile.mkdtemp()
try:
    def mt(path, tools):
        json.dump({"subject": "s", "tools": tools}, open(os.path.join(tmp, path), "w"))

    # benign: unique_real falls because a second arm now reports it; pool grows because the new arm
    # found a real defect nobody had recorded.
    mt("b1.json", {"old": {"unique_real": 3, "unique_real_ids": ["a", "b", "c"],
                           "defect_recall": {"pool": 4, "reported": 4, "found": 4,
                                             "recall_reported": 1.0, "recall_found": 1.0}}})
    mt("a1.json", {"old": {"unique_real": 2, "unique_real_ids": ["b", "c"],
                           "defect_recall": {"pool": 6, "reported": 4, "found": 4,
                                             "recall_reported": 0.667, "recall_found": 0.667}},
                   "new": {"unique_real": 1}})
    r = run("assert_foldin_movements.py", os.path.join(tmp, "b1.json"), os.path.join(tmp, "a1.json"))
    check("accepts unique_real falling to a second reporter",
          r.returncode == 0 and "unique_real-lost" in r.stdout, f"rc={r.returncode}")
    check("accepts a pool that grew, naming the arm that did not change",
          "pool-grew" in r.stdout and "WITHOUT this arm changing" in r.stdout)

    # unexplained: a pre-existing arm's OWN counts moved, which a fold-in must not cause
    mt("b2.json", {"old": {"defect_recall": {"pool": 4, "reported": 4, "found": 4,
                                             "recall_reported": 1.0, "recall_found": 1.0}}})
    mt("a2.json", {"old": {"defect_recall": {"pool": 4, "reported": 2, "found": 4,
                                             "recall_reported": 0.5, "recall_found": 1.0}}})
    r = run("assert_foldin_movements.py", os.path.join(tmp, "b2.json"), os.path.join(tmp, "a2.json"))
    check("REFUSES when a pre-existing arm's own counts moved",
          r.returncode == 3 and "UNEXPLAINED" in r.stderr, f"rc={r.returncode}")

    # unexplained: unique_real rising is impossible from a fold-in
    mt("b3.json", {"old": {"unique_real": 1}})
    mt("a3.json", {"old": {"unique_real": 4}})
    r = run("assert_foldin_movements.py", os.path.join(tmp, "b3.json"), os.path.join(tmp, "a3.json"))
    check("REFUSES unique_real rising, which a fold-in cannot cause", r.returncode == 3)

    # a tool vanishing is never benign
    mt("b4.json", {"old": {"unique_real": 1}})
    mt("a4.json", {})
    r = run("assert_foldin_movements.py", os.path.join(tmp, "b4.json"), os.path.join(tmp, "a4.json"))
    check("REFUSES a pre-existing arm disappearing", r.returncode == 3 and "DISAPPEARED" in r.stderr)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
