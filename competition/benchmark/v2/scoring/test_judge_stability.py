#!/usr/bin/env python3
"""Self-tests for judge_stability.py (nib dcc-vkeh). Run: python3 test_judge_stability.py

Same rule as test_score_pooled.py: a guard without a test is a guard that has not been shown to fire.
The arithmetic tests matter as much as the guards here — a stability figure that is quietly wrong is
worse than none, because it is the thing that licenses every other number in the pilot.
"""
import copy
from judge_stability import (validate, score, kappa, DataDefect, KAPPA_FLOOR,
                             EXACT_FLOOR, calibration)


def P(label, verdicts, model="claude-opus-5"):
    return {"judge_model": model, "pass": label,
            "verdicts": [dict(cluster_id=c, verdict=v, **extra)
                         for c, v, extra in verdicts]}


PASS1 = P("1", [("c1", "matches-thread", {"matches_thread": 0}),
                ("c2", "valid-other", {}),
                ("c3", "trivia", {}),
                ("c4", "false-positive", {})])
PASS2 = P("2", [("c1", "matches-thread", {"matches_thread": 0}),
                ("c2", "valid-other", {}),
                ("c3", "trivia", {}),
                ("c4", "false-positive", {})])

fails = []


def check(name, fn):
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as e:
        fails.append(name); print(f"  FAIL  {name}: {e}")


def expect_defect(p1, p2, substr):
    try:
        validate(p1, p2)
    except DataDefect as e:
        assert substr in str(e), f"expected {substr!r} in {e}"
        return
    raise AssertionError(f"expected a DataDefect mentioning {substr!r}, got none")


def t_perfect():
    validate(PASS1, PASS2)
    m = score(PASS1, PASS2)
    assert m["exact_agreement"] == 1.0
    assert m["disagreement_rate"] == 0.0
    assert m["disagreements"] == []
    assert m["stable"] is True
    assert m["n_clusters"] == 4


def t_boundary_isolated():
    """Full-sample agreement can look healthy while every disagreement sits on the one boundary
    precision depends on. The boundary block exists to make that visible, so it must be scoped to
    clusters either pass placed at valid-other or trivia — not to the whole sample."""
    p2 = P("2", [("c1", "matches-thread", {"matches_thread": 0}),
                 ("c2", "trivia", {}),          # valid-other -> trivia: the load-bearing flip
                 ("c3", "trivia", {}),
                 ("c4", "false-positive", {})])
    m = score(PASS1, p2)
    assert m["exact_agreement"] == 0.75, m["exact_agreement"]
    assert m["valid_other_vs_trivia_boundary"]["n"] == 2, m["valid_other_vs_trivia_boundary"]
    assert m["valid_other_vs_trivia_boundary"]["agreement"] == 0.5
    assert m["disagreements"][0]["crosses_real_boundary"] is True


def t_real_collapse_ignores_harmless_moves():
    """valid-minor -> trivia moves nothing across the real/not-real line, so the collapse must not
    charge for it even though the 6-way verdict changed."""
    p1 = P("1", [("c1", "valid-minor", {}), ("c2", "valid-other", {})])
    p2 = P("2", [("c1", "trivia", {}), ("c2", "valid-other", {})])
    m = score(p1, p2)
    assert m["exact_agreement"] == 0.5
    assert m["real_vs_not"]["agreement"] == 1.0, m["real_vs_not"]


def t_kappa_none_when_chance_is_total():
    """Both passes putting everything in one bucket is total agreement carrying no information, and
    (po-pe)/(1-pe) divides by zero there. It must report None, never 1.00."""
    po, k = kappa([("trivia", "trivia"), ("trivia", "trivia")])
    assert po == 1.0 and k is None, (po, k)
    m = score(P("1", [("c1", "trivia", {})]), P("2", [("c1", "trivia", {})]))
    assert m["kappa_6way"] is None
    assert m["stable"] is False, "kappa is unmeasurable, so stability is not established"


def t_kappa_value():
    """Hand-checked: 3 of 4 agree; marginals pass1 {real:2, not:2}, pass2 {real:3, not:1}.
    pe = .5*.75 + .5*.25 = .5 ; kappa = (.75-.5)/.5 = .5"""
    p1 = P("1", [("c1", "valid-other", {}), ("c2", "valid-other", {}),
                 ("c3", "trivia", {}), ("c4", "trivia", {})])
    p2 = P("2", [("c1", "valid-other", {}), ("c2", "valid-other", {}),
                 ("c3", "valid-other", {}), ("c4", "trivia", {})])
    m = score(p1, p2)
    assert m["real_vs_not"]["kappa"] == 0.5, m["real_vs_not"]
    assert m["stable"] is False, "kappa 0.5 is below the pre-registered floor"


def t_thread_index_move_is_a_disagreement():
    """Both passes saying matches-thread while pointing at different threads is not agreement about
    the answer — it must not be counted as an index match."""
    p1 = P("1", [("c1", "matches-thread", {"matches_thread": 0})])
    p2 = P("2", [("c1", "matches-thread", {"matches_thread": 3})])
    m = score(p1, p2)
    assert m["matches_thread"]["n_either_pass"] == 1
    assert m["matches_thread"]["agree_same_index"] == 0, m["matches_thread"]


def t_different_samples_refused():
    expect_defect(PASS1, P("2", [("c1", "trivia", {})]), "graded different samples")


def t_missing_judge_model():
    p = copy.deepcopy(PASS2); p["judge_model"] = ""
    expect_defect(PASS1, p, "judge_model absent")


def t_stale_verdict_vocabulary():
    """v1's TP-primary/TP-human must fail loudly rather than be scored as an unknown category."""
    p = P("2", [("c1", "TP-human", {}), ("c2", "valid-other", {}),
                ("c3", "trivia", {}), ("c4", "false-positive", {})])
    expect_defect(PASS1, p, "outside the vocabulary")


def t_duplicate_cluster_id():
    p = P("2", [("c1", "trivia", {}), ("c1", "valid-other", {}),
                ("c2", "valid-other", {}), ("c3", "trivia", {}), ("c4", "false-positive", {})])
    expect_defect(PASS1, p, "duplicate cluster_id")


def t_empty_pass():
    expect_defect(P("1", []), P("2", []), "no verdicts")


def t_thresholds_are_the_documented_ones():
    """The floors are pre-registered; a silent edit would let the pilot's verdict be tuned to its
    result. Pin them so a change has to be deliberate."""
    assert (KAPPA_FLOOR, EXACT_FLOOR) == (0.60, 0.70)


def t_cross_model_is_flagged_not_refused():
    p = copy.deepcopy(PASS2); p["judge_model"] = "claude-sonnet-5"
    validate(PASS1, p)
    m = score(PASS1, p)
    assert m["same_model"] is False


def t_calibration_measures_against_the_pilot_not_itself():
    # Self-agreement and agreement-with-the-baseline are different properties. On 2026-08-19 the
    # judge was 24/24 with itself while 9/15 and 6/15 against the pilot (nib dcc-n4nf).
    import tempfile, os, json as _j
    d = tempfile.mkdtemp(); sample = os.path.join(d, "s.json")
    _j.dump({"subject": "s", "n": 3, "clusters": [
        {"cluster_id": "c1", "pilot_pass1": "valid-other", "pilot_pass2": "valid-other"},
        {"cluster_id": "c2", "pilot_pass1": "valid-other", "pilot_pass2": "trivia"},
        {"cluster_id": "c3", "pilot_pass1": "trivia", "pilot_pass2": "trivia"}]}, open(sample, "w"))
    m = calibration(sample, {"c1": "valid-other", "c2": "trivia", "c3": "trivia"})
    assert m["vs_pilot_pass1"] == {"agree": 2, "n": 3}, m["vs_pilot_pass1"]
    assert m["vs_pilot_pass2"] == {"agree": 3, "n": 3}, m["vs_pilot_pass2"]
    assert m["direction_vs_pilot_pass1"] == {"harsher": 1, "softer": 0, "same": 2}, m


def t_calibration_refuses_an_ungraded_sample():
    # An ungraded sample is a MISSING measurement, not a calibration of zero.
    import tempfile, os, json as _j
    d = tempfile.mkdtemp(); sample = os.path.join(d, "s.json")
    _j.dump({"subject": "s", "n": 1, "clusters": [
        {"cluster_id": "c1", "pilot_pass1": "trivia", "pilot_pass2": "trivia"}]}, open(sample, "w"))
    try:
        calibration(sample, {"g01": "trivia"})     # blind ids, never mapped back
    except DataDefect as e:
        assert "not a calibration of 0" in str(e), str(e)
        return
    assert False, "accepted a sample that was never graded"

for name, fn in sorted(globals().items()):
    if name.startswith("t_"):
        check(name[2:], fn)
print(f"\n{'FAILED: ' + ', '.join(fails) if fails else 'all pass'}")
raise SystemExit(1 if fails else 0)
