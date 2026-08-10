#!/usr/bin/env python3
"""Self-tests for score_pooled.py (nib dcc-y2e6). Run: python3 test_score_pooled.py

Every guard here corresponds to a defect that already produced a wrong published number, or to a
metric property the scoring-model decision requires. A guard without a test is a guard that has not
been shown to fire.
"""
import copy, sys
from score_pooled import validate, score, DataDefect

BASE = {
    "subject": "acme/widget#1", "instrument": "pooled-adjudication", "judge_model": "claude-opus-5",
    "cells": [{"tool": "alpha", "repeat": 1, "cost_usd": 1.0},
              {"tool": "beta", "repeat": 1, "cost_usd": 2.0}],
    "clusters": [
        {"cluster_id": "c1", "verdict": "matches-thread", "matches_thread": 0,
         "judged_severity": "high", "code_citation": "a.py:10",
         "reported_by": [{"tool": "alpha", "repeat": 1, "severity": "high"}]},
        {"cluster_id": "c2", "verdict": "valid-other", "judged_severity": "medium",
         "code_citation": "a.py:20",
         "reported_by": [{"tool": "alpha", "repeat": 1, "severity": "medium"},
                         {"tool": "beta", "repeat": 1, "severity": "low"}]},
        {"cluster_id": "c3", "verdict": "trivia", "judged_severity": "nit",
         "reported_by": [{"tool": "beta", "repeat": 1, "severity": "low"}]},
        {"cluster_id": "c4", "verdict": "false-positive", "judged_severity": "info",
         "reported_by": [{"tool": "beta", "repeat": 1, "severity": "high"}]},
    ],
}
THREADS = [
    {"path": "a.py", "line": 10, "admission": "admitted"},
    {"path": "b.py", "line": 5, "admission": "admitted"},
    {"path": "c.py", "line": 1, "admission": "rejected"},
]

fails = []


def check(name, fn):
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as e:
        fails.append(name); print(f"  FAIL  {name}: {e}")


def expect_defect(a, threads, substr):
    try:
        validate(a, threads, None)
    except DataDefect as e:
        assert substr in str(e), f"expected {substr!r} in {e}"
        return
    raise AssertionError(f"expected a DataDefect mentioning {substr!r}, got none")


def t_happy():
    validate(BASE, THREADS, None)
    m = score(BASE, THREADS, None)
    a, b = m["tools"]["alpha"], m["tools"]["beta"]
    assert a["precision"] == 1.0, a["precision"]                 # c1, c2 both real
    assert b["precision"] == round(1 / 3, 3), b["precision"]     # c2 real; c3 trivia; c4 fp
    assert a["unique_real"] == 1, a["unique_real"]               # c1 only alpha; c2 shared
    assert m["threads"]["admitted"] == 2                         # the rejected one is excluded
    assert m["threads"]["hit_by_any_tool"] == 1
    assert m["threads"]["missed_by_every_tool"] == 1             # thread 1 found by nobody
    assert a["thread_recall"] == 0.5, a["thread_recall"]
    assert b["thread_recall"] == 0.0, b["thread_recall"]


def t_severity_weighting_separates():
    """v1's unweighted precision let four minor findings outscore one revert-forcing defect."""
    a = copy.deepcopy(BASE)
    a["cells"] = [{"tool": "deep", "repeat": 1, "cost_usd": 1.0}, {"tool": "shallow", "repeat": 1, "cost_usd": 1.0}]
    a["clusters"] = [
        {"cluster_id": "d1", "verdict": "valid-other", "judged_severity": "critical",
         "code_citation": "x:1", "reported_by": [{"tool": "deep", "repeat": 1, "severity": "critical"}]},
    ] + [
        {"cluster_id": f"s{i}", "verdict": "valid-other", "judged_severity": "low",
         "code_citation": f"y:{i}", "reported_by": [{"tool": "shallow", "repeat": 1, "severity": "low"}]}
        for i in range(4)
    ]
    validate(a, None, None)
    m = score(a, None, None)
    d, s = m["tools"]["deep"], m["tools"]["shallow"]
    assert d["precision"] == s["precision"] == 1.0, "unweighted precision should tie"
    assert d["real"] == 1 and s["real"] == 4
    # Weighted precision ties too (both all-real) — the separation shows in severity, so assert the
    # weight actually differs where verdicts are mixed, which is the case that matters.
    mixed = copy.deepcopy(a)
    mixed["clusters"].append({"cluster_id": "d2", "verdict": "trivia", "judged_severity": "nit",
                              "reported_by": [{"tool": "deep", "repeat": 1, "severity": "nit"}]})
    mixed["clusters"].append({"cluster_id": "s9", "verdict": "trivia", "judged_severity": "nit",
                              "reported_by": [{"tool": "shallow", "repeat": 1, "severity": "nit"}]})
    m2 = score(mixed, None, None)
    dw, sw = m2["tools"]["deep"]["precision_severity_weighted"], m2["tools"]["shallow"]["precision_severity_weighted"]
    assert dw > sw, f"one critical should outweigh four lows: deep={dw} shallow={sw}"


def t_empty_severity_whole_tool():
    """dcc-3v3m: severities captured on 2 of 78 entries; a stray `critical` gave a free 1.00."""
    a = copy.deepcopy(BASE)
    for c in a["clusters"]:
        for r in c["reported_by"]:
            if r["tool"] == "beta":
                r["severity"] = None
    expect_defect(a, THREADS, "severity empty on all")


def t_sparse_severity():
    a = copy.deepcopy(BASE)
    a["cells"].append({"tool": "gamma", "repeat": 1, "cost_usd": 1.0})
    for i in range(10):
        a["clusters"].append({"cluster_id": f"g{i}", "verdict": "trivia", "judged_severity": "nit",
                              "reported_by": [{"tool": "gamma", "repeat": 1,
                                               "severity": "low" if i == 0 else None}]})
    expect_defect(a, THREADS, "severity present on only")


def t_cell_with_zero_clusters():
    a = copy.deepcopy(BASE)
    a["cells"].append({"tool": "silent", "repeat": 1, "cost_usd": 5.0})
    expect_defect(a, THREADS, "zero clusters")


def t_orphan_cell_reference():
    a = copy.deepcopy(BASE)
    a["clusters"][0]["reported_by"].append({"tool": "ghost", "repeat": 9, "severity": "high"})
    expect_defect(a, THREADS, "absent from the cell list")


def t_real_without_citation():
    a = copy.deepcopy(BASE)
    del a["clusters"][1]["code_citation"]
    expect_defect(a, THREADS, "without code_citation")


def t_thread_verdict_without_index():
    a = copy.deepcopy(BASE)
    a["clusters"][0]["matches_thread"] = None
    expect_defect(a, THREADS, "no matches_thread index")


def t_thread_index_out_of_range():
    a = copy.deepcopy(BASE)
    a["clusters"][0]["matches_thread"] = 99
    expect_defect(a, THREADS, "out of range")


def t_bad_verdict():
    a = copy.deepcopy(BASE)
    a["clusters"][0]["verdict"] = "TP-primary"      # the v1 vocabulary must not silently pass
    expect_defect(a, THREADS, "not in")


def t_no_judge_model():
    a = copy.deepcopy(BASE); del a["judge_model"]
    expect_defect(a, THREADS, "judge_model absent")


def t_judge_dismissed_thread_is_flagged():
    """A tool reported an admitted thread and the judge called it trivia — calibration failure."""
    a = copy.deepcopy(BASE)
    a["clusters"].append({"cluster_id": "c5", "verdict": "trivia", "matches_thread": 1,
                          "judged_severity": "nit",
                          "reported_by": [{"tool": "beta", "repeat": 1, "severity": "low"}]})
    validate(a, THREADS, None)
    m = score(a, THREADS, None)
    d = m["threads"]["judge_dismissed_reported_threads"]
    assert len(d) == 1 and d[0]["thread"] == 1, d


for name, fn in list(globals().items()):
    if name.startswith("t_"):
        check(name[2:], fn)

print()
if fails:
    print(f"{len(fails)} FAILED: {', '.join(fails)}"); sys.exit(1)
print("all guards fire correctly")
