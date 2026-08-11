#!/usr/bin/env python3
"""Judge stability: how much does the blind grader agree with itself? (nib dcc-vkeh)

Usage: judge_stability.py <pass1.json> <pass2.json> [-o out.json]

The pilot's first question is whether the grader is stable at the `valid-other` / `trivia` boundary.
That boundary IS the metric: v1 put 58 of 98 clusters in the trivia bucket and only 6 in
false-positive, so precision is decided almost entirely by where a grader draws this one line. A
pooled-adjudication number is only as trustworthy as the reproducibility of that call.

Each input is one grading pass over the SAME sample:

    {"judge_model": "claude-opus-5", "pass": "1", "verdicts": [
        {"cluster_id": "c01", "verdict": "valid-other", "matches_thread": null}, ...]}

Both passes must be graded blind to tool identity AND blind to each other — run pass 2 in a separate
process, never as a continuation of the session that produced pass 1, or the number measures memory
rather than stability.

PRE-REGISTERED THRESHOLD (fixed before the pilot's first grading pass ran, so it cannot be tuned to
the result). The instrument is called stable when BOTH hold:

    real_vs_not.kappa >= 0.60     substantial agreement on the only collapse precision depends on
    exact_agreement   >= 0.70     the 6-way verdict reproduces more often than not

0.60 is the floor of Landis & Koch's "substantial" band. It is a convention, not a law of nature —
it is written down here so the pilot reports against a line drawn in advance rather than one drawn
around the number that came out.

Exits 3 on a data defect rather than emitting a number, on the same principle as score_pooled.py.
"""
import json, sys, argparse
from collections import Counter, defaultdict

# Imported rather than restated: a verdict vocabulary that drifts between the two scorers would let a
# pass validate here and fail there, or worse, agree with itself about the wrong categories.
from score_pooled import ALL_VERDICTS, REAL

KAPPA_FLOOR = 0.60
EXACT_FLOOR = 0.70


class DataDefect(Exception):
    """A pipeline defect, not a result."""


def _load(path):
    P = json.load(open(path))
    if not isinstance(P, dict) or "verdicts" not in P:
        raise DataDefect(f"{path}: expected an object with judge_model/pass/verdicts")
    return P


def validate(p1, p2):
    errs = []
    for label, P in (("pass1", p1), ("pass2", p2)):
        if not P.get("judge_model"):
            errs.append(f"{label}: judge_model absent — a stability figure must name the grader")
        vs = P.get("verdicts") or []
        if not vs:
            errs.append(f"{label}: no verdicts")
        ids = [v.get("cluster_id") for v in vs]
        if any(i is None for i in ids):
            errs.append(f"{label}: a verdict with no cluster_id")
        dupes = [i for i, n in Counter(ids).items() if n > 1]
        if dupes:
            errs.append(f"{label}: duplicate cluster_id(s) {sorted(map(str, dupes))[:5]}")
        bad = sorted({v.get("verdict") for v in vs} - ALL_VERDICTS)
        if bad:
            errs.append(f"{label}: verdict(s) outside the vocabulary: {bad}")

    i1 = {v.get("cluster_id") for v in (p1.get("verdicts") or [])}
    i2 = {v.get("cluster_id") for v in (p2.get("verdicts") or [])}
    # The disagreement rate is a fraction over a population. If the two passes covered different
    # clusters the denominator is undefined, and silently intersecting them would quietly re-scope
    # the sample to whatever both happened to cover.
    if i1 != i2:
        only1, only2 = sorted(map(str, i1 - i2)), sorted(map(str, i2 - i1))
        errs.append(f"the two passes graded different samples: {len(only1)} only in pass1 "
                    f"({only1[:3]}), {len(only2)} only in pass2 ({only2[:3]})")

    if p1.get("judge_model") and p2.get("judge_model") and p1["judge_model"] != p2["judge_model"]:
        # Not fatal — cross-model agreement is a legitimate and stronger question — but it is not
        # SELF-consistency, and reporting it under that name would overstate what was measured.
        pass

    if errs:
        raise DataDefect("; ".join(errs))


def kappa(pairs, collapse=None):
    """Cohen's kappa over (a, b) label pairs. None when chance agreement is total."""
    if collapse:
        pairs = [(collapse(a), collapse(b)) for a, b in pairs]
    n = len(pairs)
    if not n:
        return None, None
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    if pe >= 1.0:
        # Both passes put everything in one category: agreement is total but carries no information,
        # and (po-pe)/(1-pe) divides by zero. Say so rather than print 1.00 or 0.00.
        return po, None
    return po, (po - pe) / (1 - pe)


def score(p1, p2):
    v1 = {v["cluster_id"]: v for v in p1["verdicts"]}
    v2 = {v["cluster_id"]: v for v in p2["verdicts"]}
    ids = sorted(v1)
    pairs = [(v1[i]["verdict"], v2[i]["verdict"]) for i in ids]
    n = len(pairs)

    exact, k_full = kappa(pairs)
    real_po, real_k = kappa(pairs, collapse=lambda v: "real" if v in REAL else "not-real")

    # The load-bearing boundary, isolated: clusters EITHER pass placed at valid-other or trivia.
    # Restricting to it answers the pilot's actual question — full-sample agreement can look healthy
    # while every disagreement sits exactly here, which is the case that voids the precision axis.
    boundary_ids = [i for i in ids
                    if {v1[i]["verdict"], v2[i]["verdict"]} & {"valid-other", "trivia"}]
    b_pairs = [(v1[i]["verdict"], v2[i]["verdict"]) for i in boundary_ids]
    b_po, b_k = kappa(b_pairs)

    # A thread match that moves index is a different claim about the answer key, even when both
    # passes say matches-thread.
    mt_ids = [i for i in ids if "matches-thread" in (v1[i]["verdict"], v2[i]["verdict"])]
    mt_agree = sum(1 for i in mt_ids
                   if v1[i]["verdict"] == v2[i]["verdict"] == "matches-thread"
                   and v1[i].get("matches_thread") == v2[i].get("matches_thread"))

    confusion = defaultdict(int)
    for a, b in pairs:
        confusion[f"{a} -> {b}"] += 1

    disagreements = [{"cluster_id": i, "pass1": v1[i]["verdict"], "pass2": v2[i]["verdict"],
                      "crosses_real_boundary": (v1[i]["verdict"] in REAL) != (v2[i]["verdict"] in REAL)}
                     for i in ids if v1[i]["verdict"] != v2[i]["verdict"]]

    stable = (real_k is not None and real_k >= KAPPA_FLOOR and exact >= EXACT_FLOOR)

    return {
        "n_clusters": n,
        "judge_model": {"pass1": p1["judge_model"], "pass2": p2["judge_model"]},
        "same_model": p1["judge_model"] == p2["judge_model"],
        "exact_agreement": round(exact, 3),
        "disagreement_rate": round(1 - exact, 3),
        "kappa_6way": round(k_full, 3) if k_full is not None else None,
        "real_vs_not": {
            "agreement": round(real_po, 3),
            "kappa": round(real_k, 3) if real_k is not None else None,
        },
        "valid_other_vs_trivia_boundary": {
            "n": len(b_pairs),
            "agreement": round(b_po, 3) if b_po is not None else None,
            "kappa": round(b_k, 3) if b_k is not None else None,
        },
        "matches_thread": {
            "n_either_pass": len(mt_ids),
            "agree_same_index": mt_agree,
        },
        "confusion": dict(sorted(confusion.items())),
        "disagreements": disagreements,
        "threshold": {"kappa_floor": KAPPA_FLOOR, "exact_floor": EXACT_FLOOR,
                      "pre_registered": True},
        "stable": stable,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pass1"); ap.add_argument("pass2"); ap.add_argument("-o", "--out")
    a = ap.parse_args()
    try:
        p1, p2 = _load(a.pass1), _load(a.pass2)
        validate(p1, p2)
    except DataDefect as e:
        print(f"DATA DEFECT — refusing to emit a stability figure:\n  {e}", file=sys.stderr)
        sys.exit(3)
    m = score(p1, p2)
    s = json.dumps(m, indent=2)
    if a.out:
        open(a.out, "w").write(s + "\n"); print(f"wrote {a.out}")
    else:
        print(s)


if __name__ == "__main__":
    main()
