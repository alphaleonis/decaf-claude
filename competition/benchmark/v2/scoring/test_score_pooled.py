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
    "merged_at": "2026-07-02T00:08:13Z",
    "cells": [{"tool": "alpha", "repeat": 1, "cost_usd": 1.0},
              {"tool": "beta", "repeat": 1, "cost_usd": 2.0}],
    "clusters": [
        {"cluster_id": "c1", "verdict": "matches-thread", "matches_thread": 0,
         "judged_severity": "high", "code_citation": "a.py:10",
         "matched_thread_quote": "never backs off between attempts",
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
    {"path": "a.py", "line": 10, "admission": "admitted", "origin": "human",
     "body": "The retry loop never backs off between attempts, so a flapping upstream gets hammered."},
    {"path": "b.py", "line": 5, "admission": "admitted", "origin": "human",
     "body": "This ignores the cancellation token once the batch has started."},
    {"path": "c.py", "line": 1, "admission": "rejected"},
]

fails = []


def check(name, fn):
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as e:
        fails.append(name); print(f"  FAIL  {name}: {e}")


def expect_defect(a, threads, substr, key=None, **kw):
    try:
        validate(a, threads, key, **kw)
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


def t_match_without_a_quote_is_refused():
    """dcc-on93: `matches_thread: <index>` records nothing about WHY. Without a quote there is no
    way to tell a substantive match from a same-line coincidence, and a loose match onto a
    MATCHABLE thread inflates thread_recall with nothing to detect it."""
    a = copy.deepcopy(BASE)
    del a["clusters"][0]["matched_thread_quote"]
    expect_defect(a, THREADS, "without matched_thread_quote")


def t_fabricated_quote_is_refused():
    """Presence alone would make the guard cosmetic — the quote has to occur in the body of the
    thread the cluster claims to match."""
    a = copy.deepcopy(BASE)
    a["clusters"][0]["matched_thread_quote"] = "this text is nowhere in that thread"
    expect_defect(a, THREADS, "does not appear in T0's body")


def t_quote_from_the_wrong_thread_is_refused():
    """The e15/ma11/c108 shape: a real quote, lifted from a DIFFERENT thread than the one credited."""
    a = copy.deepcopy(BASE)
    a["clusters"][0]["matched_thread_quote"] = "ignores the cancellation token"   # that is T1
    expect_defect(a, THREADS, "does not appear in T0's body")


def t_quote_tolerates_reflowed_whitespace_and_case():
    """A grader quoting a span that wrapped across lines has still quoted it. Normalization must not
    be so strict that it refuses valid evidence — only fabrication."""
    a = copy.deepcopy(BASE)
    a["clusters"][0]["matched_thread_quote"] = "Never   backs off\n  between attempts"
    validate(a, THREADS, None)


def t_token_length_quote_is_refused():
    """A two-word quote matches almost any body, so it is not evidence of correspondence."""
    a = copy.deepcopy(BASE)
    a["clusters"][0]["matched_thread_quote"] = "retry"
    expect_defect(a, THREADS, "under 12")


def t_whole_body_satisfies_the_length_floor():
    """Real threads in this corpus go down to five characters. A floor that cannot be met by quoting
    the entire thread would refuse the shortest legitimate matches."""
    ts = copy.deepcopy(THREADS)
    ts[0]["body"] = "Bool?"
    a = copy.deepcopy(BASE)
    a["clusters"][0]["matched_thread_quote"] = "Bool?"
    validate(a, ts, None)


def t_match_to_a_non_admitted_thread_is_refused():
    """dcc-on93: the grader only ever sees admitted threads, so an index naming a rejected one is a
    stale or invented match. It was silent in both directions — recall ignores it, precision counts
    it as REAL — and four clusters on two scored subjects had it."""
    a = copy.deepcopy(BASE)
    a["clusters"][0]["matches_thread"] = 2          # the rejected thread in THREADS
    a["clusters"][0]["matched_thread_quote"] = "anything at all here"
    expect_defect(a, THREADS, "not admitted")


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


def t_demotion_gap():
    """dcc-c92m: a tool that finds a defect and suppresses it below its own bar.

    Modelled on the real cell: anthropic headlined "Verdict: No blocking issues found" while its
    sub-threshold section described the defect exactly, verified empirically, scored 0.
    """
    a = copy.deepcopy(BASE)
    a["cells"] = [{"tool": "suppressor", "repeat": 1, "cost_usd": 1.0}]
    a["clusters"] = [
        # Found, verified, and demoted below the reporting bar.
        {"cluster_id": "s1", "verdict": "matches-thread", "matches_thread": 0,
         "judged_severity": "critical", "code_citation": "a.py:10",
         "matched_thread_quote": "never backs off between attempts",
         "reported_by": [{"tool": "suppressor", "repeat": 1, "severity": "high",
                          "disposition": "demoted"}]},
        # Actually reported.
        {"cluster_id": "s2", "verdict": "trivia", "judged_severity": "nit",
         "reported_by": [{"tool": "suppressor", "repeat": 1, "severity": "nit",
                          "disposition": "reported"}]},
    ]
    validate(a, THREADS, None)
    m = score(a, THREADS, None)
    s = m["tools"]["suppressor"]
    assert s["thread_recall"] == 0.0, f"as reported it is a MISS, got {s['thread_recall']}"
    assert s["thread_recall_found"] == 0.5, f"as found it is a CATCH, got {s['thread_recall_found']}"
    assert s["demotion_gap"] == 0.5, s["demotion_gap"]
    assert s["demoted_real"] == 1, s["demoted_real"]
    assert s["clusters_reported"] == 1 and s["clusters_found"] == 2
    # Precision counts reported only — a demoted finding costs the reader no attention.
    assert s["precision"] == 0.0, s["precision"]


def t_bad_disposition():
    a = copy.deepcopy(BASE)
    a["clusters"][0]["reported_by"][0]["disposition"] = "hidden"
    expect_defect(a, THREADS, "disposition")


def t_disposition_defaults_to_reported():
    """Existing analyses without the field must keep scoring as before."""
    m = score(BASE, THREADS, None)
    assert m["tools"]["alpha"]["thread_recall"] == m["tools"]["alpha"]["thread_recall_found"]
    assert m["tools"]["alpha"]["demotion_gap"] == 0.0


def t_missing_judged_severity():
    """The field precision_severity_weighted is computed from, previously unguarded.

    An absent judged_severity defaults to weight 1.0 — the same as `low` — so a cluster the judge
    never rated was indistinguishable from one rated low. The guard that already existed covered the
    TOOL-reported severity, which no metric here reads.
    """
    a = copy.deepcopy(BASE)
    del a["clusters"][1]["judged_severity"]
    expect_defect(a, THREADS, "no judged_severity")


def t_bad_judged_severity_value():
    a = copy.deepcopy(BASE)
    a["clusters"][1]["judged_severity"] = "blocker"      # not in SEV_WEIGHT; would weight 1.0
    expect_defect(a, THREADS, "outside")


def t_key_verdict_without_index():
    """Symmetric with matches-thread: krecall's None filter drops it silently otherwise."""
    a = copy.deepcopy(BASE)
    a["clusters"][1].update({"verdict": "matches-key"})   # no matches_key
    expect_defect(a, THREADS, "no matches_key index", key={"entries": [{"id": "e1"}]})


def t_key_index_names_no_entry():
    a = copy.deepcopy(BASE)
    a["clusters"][1].update({"verdict": "matches-key", "matches_key": "e9"})
    expect_defect(a, THREADS, "naming no entry", key={"entries": [{"id": "e1"}]})


def t_null_arm_silent_cell_is_allowed_explicitly():
    """dcc-mjj5: on the null arm a tool that reported nothing is the RESULT, not a defect.

    The guard must still fire by default — a silent cell on a scored subject is an extraction
    failure — so the null arm has to ask for the exemption rather than get it silently.
    """
    a = copy.deepcopy(BASE)
    a["cells"].append({"tool": "quiet", "repeat": 1, "cost_usd": 3.0})
    expect_defect(a, THREADS, "zero clusters")                       # default: still a defect
    validate(a, THREADS, None, allow_silent_cells=True)              # null arm: permitted
    m = score(a, THREADS, None)
    assert m["tools"]["quiet"]["clusters_reported"] == 0, m["tools"]["quiet"]
    assert m["tools"]["quiet"]["precision"] is None
    assert m["tools"]["quiet"]["cost_usd"] == 3.0


def t_corpus_miss_detector_splits_by_disposition():
    """A thread every tool FOUND and every tool DEMOTED is not a blind spot — but it is a miss."""
    a = copy.deepcopy(BASE)
    a["cells"] = [{"tool": "one", "repeat": 1, "cost_usd": 1.0}]
    a["clusters"] = [
        {"cluster_id": "x1", "verdict": "matches-thread", "matches_thread": 0,
         "judged_severity": "high", "code_citation": "a.py:10",
         "matched_thread_quote": "never backs off between attempts",
         "reported_by": [{"tool": "one", "repeat": 1, "severity": "high",
                          "disposition": "demoted"}]},
    ]
    validate(a, THREADS, None)
    t = score(a, THREADS, None)["threads"]
    assert t["hit_by_any_tool"] == 0, t            # nobody SHOWED it
    assert t["hit_by_any_tool_found"] == 1, t      # somebody FOUND it
    assert t["missed_by_every_tool"] == 2, t
    assert t["missed_by_every_tool_found"] == 1, t
    assert t["demoted_by_every_tool_that_found_it"] == [0], t


def t_admitted_thread_without_origin_is_a_defect():
    """dcc-qwt3: 28% of the first corpus's admitted threads were competing-tool output.

    An admitted thread whose population is unknown makes every thread-recall figure unprovable as
    human-only, so the scorer must refuse rather than emit a number that may mix the populations.
    """
    ts = copy.deepcopy(THREADS)
    del ts[1]["origin"]
    expect_defect(BASE, ts, "origin")


def t_bad_origin_value():
    ts = copy.deepcopy(THREADS)
    ts[1]["origin"] = "robot"
    expect_defect(BASE, ts, "origin")


def t_bot_threads_never_enter_thread_recall():
    """The refusal itself: thread_recall is computed over the human population ONLY.

    A tool that matched only the bot thread scores 0.0 on the human axis and 1.0 on the incumbent
    axis — the figures are never merged.
    """
    ts = copy.deepcopy(THREADS)
    ts.append({"path": "d.py", "line": 7, "admission": "admitted", "origin": "bot",
               "body": "Consider extracting this into a helper for readability."})
    a = copy.deepcopy(BASE)
    a["clusters"].append({"cluster_id": "c5", "verdict": "matches-thread", "matches_thread": 3,
                          "judged_severity": "medium", "code_citation": "d.py:7",
                          "matched_thread_quote": "extracting this into a helper",
                          "reported_by": [{"tool": "beta", "repeat": 1, "severity": "medium"}]})
    validate(a, ts, None)
    m = score(a, ts, None)
    al, be = m["tools"]["alpha"], m["tools"]["beta"]
    assert al["thread_recall"] == 0.5, al["thread_recall"]     # 1 of 2 HUMAN; bot thread invisible
    assert be["thread_recall"] == 0.0, be["thread_recall"]     # its hit was a bot thread
    assert be["incumbent_agreement"] == 1.0, be["incumbent_agreement"]
    assert al["incumbent_agreement"] == 0.0, al["incumbent_agreement"]
    t = m["threads"]
    assert t["admitted_human"] == 2 and t["admitted_bot"] == 1, t
    assert t["missed_by_every_tool"] == 1 and t["missed_index"] == [1], t   # human misses only
    assert t["incumbent"]["hit_by_any_tool"] == 1, t["incumbent"]


def t_incumbent_axis_absent_without_bot_threads():
    m = score(BASE, THREADS, None)
    assert m["tools"]["alpha"]["incumbent_agreement"] is None
    assert m["threads"]["admitted_bot"] == 0
    assert m["threads"]["incumbent"]["hit_by_any_tool"] is None


def t_thin_human_axis_is_flagged():
    """Four of the seven citable subjects hold <=2 human threads; a recall there is 0/0.5/1.0
    quantization noise. The flag travels with the metrics so a synthesis cannot headline it."""
    m = score(BASE, THREADS, None)
    assert m["threads"]["human_axis_thin"] is True, m["threads"]           # n=2
    ts = copy.deepcopy(THREADS)
    ts.append({"path": "e.py", "line": 2, "admission": "admitted", "origin": "human"})
    m3 = score(BASE, ts, None)
    assert m3["threads"]["human_axis_thin"] is False, m3["threads"]        # n=3


def t_judge_dismissal_calibrates_against_humans_only():
    """A judge calling a bot thread trivia is a disagreement between tools, not a calibration
    failure against expert review — it must not appear in judge_dismissed_reported_threads."""
    ts = copy.deepcopy(THREADS)
    ts.append({"path": "d.py", "line": 7, "admission": "admitted", "origin": "bot"})
    a = copy.deepcopy(BASE)
    a["clusters"].append({"cluster_id": "c5", "verdict": "trivia", "matches_thread": 3,
                          "judged_severity": "nit",
                          "reported_by": [{"tool": "beta", "repeat": 1, "severity": "low"}]})
    validate(a, ts, None)
    m = score(a, ts, None)
    assert m["threads"]["judge_dismissed_reported_threads"] == [], m["threads"]


def t_vintage_month_cutoff_resolves_conservatively():
    """dcc-vvf0: Anthropic publishes no day-level cutoff, so "2026-05" must mean end-of-May.

    Reading it as 2026-05-01 would call a subject that merged on 2026-05-06 provably clean, which
    the published data does not support. The five May-2026 subjects are in-window by this rule.
    """
    import vintage
    assert vintage.classify("2026-05-31", "claude-opus-5") == vintage.IN_WINDOW
    assert vintage.classify("2026-06-01", "claude-opus-5") == vintage.OUT_OF_WINDOW
    # The real corpus: the five kept-and-flagged subjects, and one that is genuinely clean.
    for merged in ("2026-05-06", "2026-05-08", "2026-05-11", "2026-05-21"):
        assert vintage.classify(merged, "claude-opus-5") == vintage.IN_WINDOW, merged
    assert vintage.classify("2026-07-02", "claude-opus-5") == vintage.OUT_OF_WINDOW
    # Weaker models have older cutoffs, so more of the corpus is clean for them (section 5).
    assert vintage.classify("2026-05-06", "claude-haiku-4-5") == vintage.OUT_OF_WINDOW
    # December cutoffs must roll the year, not produce month 13.
    assert vintage.classify("2027-01-01", "x") == vintage.UNKNOWN
    vintage.MODEL_CUTOFFS["t-dec"] = "2026-12"
    try:
        assert vintage.classify("2026-12-31", "t-dec") == vintage.IN_WINDOW
        assert vintage.classify("2027-01-01", "t-dec") == vintage.OUT_OF_WINDOW
    finally:
        del vintage.MODEL_CUTOFFS["t-dec"]


def t_vintage_refuses_silent_pooling():
    """A headline may not mix in-window and out-of-window subjects without showing the split."""
    import vintage
    mixed = [{"subject": "a", "status": vintage.IN_WINDOW},
             {"subject": "b", "status": vintage.OUT_OF_WINDOW}]
    err = vintage.check_pooling(mixed)
    assert err and "without showing the split" in err, err
    assert vintage.check_pooling([{"subject": "b", "status": vintage.OUT_OF_WINDOW}]) is None


def t_missing_merged_at_is_a_defect():
    """Without merged_at the result cannot be shown safe to pool, so it must not be emitted."""
    a = copy.deepcopy(BASE); del a["merged_at"]
    expect_defect(a, THREADS, "vintage cannot be computed")


def t_vintage_reaches_the_metrics():
    m = score(BASE, THREADS, None)
    assert m["vintage"]["status"] == "out-of-window", m["vintage"]
    assert m["vintage"]["provably_clean_from"] == "2026-06-01", m["vintage"]





def t_finding_class_closed_set():
    """A free-text class axis is what v1 had; it accumulated bug/logic/correctness as three labels
    for one thing and nothing could aggregate it."""
    a = copy.deepcopy(BASE)
    for c in a["clusters"]:
        c["finding_class"] = "defect"
    a["clusters"][1]["finding_class"] = "regression"
    expect_defect(a, THREADS, "outside the closed set")


def t_finding_class_all_or_nothing():
    """Partial classification reports a mix over a subset as though it covered the population."""
    a = copy.deepcopy(BASE)
    a["clusters"][0]["finding_class"] = "defect"
    expect_defect(a, THREADS, "partial classification")


def t_finding_class_optional_and_distributed():
    """Absent on a pre-dcc-opdr analysis: valid, and class_distribution says so with null."""
    m = score(BASE, THREADS, None)
    assert m["class_distribution"] is None, m["class_distribution"]
    a = copy.deepcopy(BASE)
    for c, k in zip(a["clusters"], ("defect", "test-gap", "style", "docs")):
        c["finding_class"] = k
    validate(a, THREADS, None)
    d = score(a, THREADS, None)["class_distribution"]
    assert d["defect"] == 1 and d["test-gap"] == 1 and d["risk"] == 0, d


def t_per_tool_class_and_defect_recall():
    """Per-tool class mix and defect recall (dcc-1sbc): reported vs found split, pool = real
    defect-class clusters any tool found; null everywhere when the analysis carries no class axis."""
    m = score(BASE, THREADS, None)
    assert m["tools"]["alpha"]["class_distribution"] is None
    assert m["tools"]["alpha"]["defect_recall"] is None
    a = copy.deepcopy(BASE)
    # c1 real defect (alpha reported); c2 real defect (alpha reported, beta reported);
    # c3 trivia style (beta); c4 false-positive defect claim (beta) — NOT in the real-defect pool.
    for c, k in zip(a["clusters"], ("defect", "defect", "style", "defect")):
        c["finding_class"] = k
    # beta also FOUND c1 but demoted it — must count in found, not reported.
    a["clusters"][0]["reported_by"].append({"tool": "beta", "repeat": 1, "severity": "low",
                                            "disposition": "demoted"})
    validate(a, THREADS, None)
    m = score(a, THREADS, None)
    al, be = m["tools"]["alpha"], m["tools"]["beta"]
    assert al["class_distribution"]["reported"]["defect"] == 2, al["class_distribution"]
    assert be["class_distribution"]["reported"] == {"defect": 2, "design": 0, "docs": 0, "risk": 0, "style": 1, "test-gap": 0}, be["class_distribution"]
    assert be["class_distribution"]["found"]["defect"] == 3, be["class_distribution"]
    assert al["defect_recall"] == {"pool": 2, "reported": 2, "found": 2, "recall_reported": 1.0, "recall_found": 1.0}, al["defect_recall"]
    # beta reported c2 (real defect) and c4 (false-positive: not real, excluded); found c1 demoted.
    assert be["defect_recall"] == {"pool": 2, "reported": 1, "found": 2, "recall_reported": 0.5, "recall_found": 1.0}, be["defect_recall"]



def t_precision_note_travels_with_the_number():
    # precision counts valid-minor as a MISS, so an arm whose output is almost entirely correct can
    # score 0.50. That was read as "half is wrong" on 2026-08-19 (nib dcc-t83x). The caveat must ship
    # inside metrics.json, not only in a code comment.
    m = score(BASE, THREADS, None)
    for tool, t in m["tools"].items():
        assert "precision_note" in t, f"{tool} has no precision_note"
        assert "valid_minor" in t["precision_note"], t["precision_note"]
        assert "METRICS.md" in t["precision_note"], t["precision_note"]

def t_refuses_metrics_without_a_calibration_record():
    # Every verdict-derived number depends on the grading day. A subject whose verdicts were never
    # calibrated against the pilot has an unmeasured baseline — on 2026-08-17 the same model agreed
    # with the pilot at 3/12 on one subject, and self-agreement could not see it (nib dcc-n4nf).
    import tempfile, os, subprocess, sys as _s, json as _j
    d = tempfile.mkdtemp()
    ap = os.path.join(d, "analysis.json"); tp = os.path.join(d, "threads.json")
    _j.dump(BASE, open(ap, "w")); _j.dump(THREADS, open(tp, "w"))
    here = os.path.dirname(os.path.abspath(__file__))
    run = lambda *x: subprocess.run([_s.executable, os.path.join(here, "score_pooled.py"), ap,
                                     "--threads", tp, "-o", os.path.join(d, "m.json"), *x],
                                    capture_output=True, text=True)
    r = run()
    assert r.returncode == 3, f"expected refusal, got {r.returncode}"
    assert "no calibration record" in r.stderr, r.stderr[:200]
    r = run("--no-calibration")
    assert r.returncode == 0, f"--no-calibration should permit a first scoring: {r.stderr[:200]}"
    os.makedirs(os.path.join(d, "grading"), exist_ok=True)
    _j.dump({"subject": "x"}, open(os.path.join(d, "grading", "calibration-2026-01-01.json"), "w"))
    r = run()
    assert r.returncode == 0, f"a present calibration record should satisfy the guard: {r.stderr[:200]}"

def t_empty_human_axis_is_distinct_from_thin():
    # THIN = too few threads to trust a ratio. EMPTY = no tool matched ANY of them, so the axis
    # cannot separate tools at all and must never be pooled as a score of zero (nib dcc-7zyf).
    import copy as _c
    a = _c.deepcopy(BASE)
    # nobody matches any thread
    for c in a["clusters"]:
        c["matches_thread"] = None
        if c.get("verdict") == "matches-thread":
            c["verdict"] = "valid-other"
    m = score(a, THREADS, None)
    assert m["threads"]["human_axis_empty"] is True, m["threads"]
    assert m["threads"]["hit_by_any_tool_found"] == 0, m["threads"]
    # the baseline fixture DOES have a match, so empty must be false there
    m2 = score(BASE, THREADS, None)
    assert m2["threads"]["human_axis_empty"] is False, m2["threads"]
    # thin and empty are independent: BASE is thin (2 human threads) but not empty
    assert m2["threads"]["human_axis_thin"] is True, m2["threads"]


def t_unmatchable_threads_leave_the_denominator():
    """dcc-hw48: a thread about code the checkpoint predates is not a miss anybody could avoid.

    Measured on PostHog-posthog-55149: 6 of 20 admitted human threads discussed code introduced by
    later commits, deflating every arm's recall by 30% with nothing in the output to show it.
    """
    th = copy.deepcopy(THREADS)
    for t in th:
        if t["admission"] == "admitted":
            t["matchable_at_checkpoint"] = True
    m = score(BASE, th, None)
    assert m["threads"]["denominator_human"] == 2, m["threads"]
    assert m["threads"]["matchability_annotated"] is True
    assert m["threads"]["thread_axis_publishable"] is True
    assert m["tools"]["alpha"]["thread_recall"] == 0.5, m["tools"]["alpha"]

    # Mark the unhit thread unmatchable: the denominator drops and recall rises to 1.00 without any
    # tool behaving differently.
    th[1]["matchable_at_checkpoint"] = False
    m2 = score(BASE, th, None)
    assert m2["threads"]["denominator_human"] == 1, m2["threads"]
    assert m2["threads"]["excluded_unmatchable_human"] == [1], m2["threads"]
    assert m2["tools"]["alpha"]["thread_recall"] == 1.0, m2["tools"]["alpha"]
    assert m2["threads"]["missed_by_every_tool"] == 0, m2["threads"]


def t_unannotated_matchability_is_not_publishable():
    """Absent annotation must not read as 'all matchable'. It makes the axis unpublishable."""
    m = score(BASE, THREADS, None)          # THREADS carries no matchable_at_checkpoint
    assert m["threads"]["matchability_annotated"] is False, m["threads"]
    assert m["threads"]["thread_axis_publishable"] is False, m["threads"]
    # The number is still computed — a synthesis gates on the flag rather than on a null.
    assert m["threads"]["denominator_human"] == 2, m["threads"]


def t_partial_annotation_is_not_publishable():
    """One annotated thread and one not is the dangerous middle, and must not pass as annotated."""
    th = copy.deepcopy(THREADS)
    th[0]["matchable_at_checkpoint"] = True
    m = score(BASE, th, None)
    assert m["threads"]["matchability_annotated"] is False, m["threads"]


def t_duplicate_threads_are_one_ground_truth_item():
    """dcc-qfr5: two threads asserting one defect are one item, and credit BOTH origin axes.

    Measured on PostHog-posthog-55149: three human threads read as missed because a bot duplicate of
    the same defect absorbed the credit, understating thread_recall and overstating
    incumbent_agreement from the same three clusters.
    """
    th = copy.deepcopy(THREADS)
    # A bot thread duplicating human thread 0, as a scanner and a reviewer both raising one defect.
    th.append({"path": "a.py", "line": 10, "admission": "admitted", "origin": "bot",
               "matchable_at_checkpoint": True, "thread_group": "tg1"})
    th[0]["thread_group"] = "tg1"
    for t in th:
        if t["admission"] == "admitted":
            t.setdefault("matchable_at_checkpoint", True)
    m = score(BASE, th, None)
    # One defect, not two: the human denominator stays at 2 and the bot denominator is 1.
    assert m["threads"]["denominator_human"] == 2, m["threads"]
    assert m["threads"]["denominator_bot"] == 1, m["threads"]
    assert m["threads"]["duplicate_groups"] == [[0, 3]], m["threads"]
    # c1 credits index 0, and the SAME credit lands on the bot axis, because the group holds both.
    assert m["tools"]["alpha"]["thread_recall"] == 0.5, m["tools"]["alpha"]
    assert m["tools"]["alpha"]["incumbent_agreement"] == 1.0, m["tools"]["alpha"]


def t_crediting_either_duplicate_gives_the_same_answer():
    """The whole point: which index the judge happens to name must not change the result."""
    th = copy.deepcopy(THREADS)
    th.append({"path": "a.py", "line": 10, "admission": "admitted", "origin": "bot",
               "matchable_at_checkpoint": True, "thread_group": "tg1"})
    th[0]["thread_group"] = "tg1"
    for t in th:
        if t["admission"] == "admitted":
            t.setdefault("matchable_at_checkpoint", True)
    a = copy.deepcopy(BASE)
    m_human = score(a, th, None)
    a2 = copy.deepcopy(BASE)
    a2["clusters"][0]["matches_thread"] = 3          # credit the bot duplicate instead
    m_bot = score(a2, th, None)
    for axis in ("thread_recall", "incumbent_agreement"):
        assert m_human["tools"]["alpha"][axis] == m_bot["tools"]["alpha"][axis], \
            f"{axis}: {m_human['tools']['alpha'][axis]} vs {m_bot['tools']['alpha'][axis]}"


for name, fn in list(globals().items()):
    if name.startswith("t_"):
        check(name[2:], fn)

print()
if fails:
    print(f"{len(fails)} FAILED: {', '.join(fails)}"); sys.exit(1)
print("all guards fire correctly")
