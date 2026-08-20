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

PRE-REGISTERED THRESHOLDS (each fixed before the grading run it judges, so none can be tuned to the
result). There are THREE, and they are reported SEPARATELY because they license different claims:

    real_vs_not.kappa                    >= 0.60   the coarse collapse: is this cluster real at all
    exact_agreement                      >= 0.70   the 6-way verdict reproduces more often than not
    valid_other_vs_trivia.kappa          >= 0.60   the boundary that decides `precision`
      ... measured over at least BOUNDARY_MIN_N = 50 boundary clusters

0.60 is the floor of Landis & Koch's "substantial" band. It is a convention, not a law of nature —
it is written down here so a run reports against a line drawn in advance rather than one drawn
around the number that came out.

WHY THE BOUNDARY GETS ITS OWN FLOOR (nib dcc-sfny). The first two floors are the ones the judge
clears; the boundary is the one the design says carries the metric, and until 2026-08-20 it was
computed and held to nothing. Measured that day: prometheus calibration (n=10) kappa 0.403,
PostHog over two full passes (n=62) kappa 0.598 — both runs reported `stable: true`, because the
floors that existed were not the load-bearing one.

So `stable` is no longer one flag. Two claims are separated, because the evidence separates:

    stable_for_rankings          real_vs_not + exact_agreement. Which arm beats which survives a
                                 judge that shifts the whole field in one direction.
    stable_for_precision_levels  the boundary floor as well. A precision LEVEL — "this tool is 0.62
                                 precise" — inherits the reproducibility of the one call that
                                 decides it, and a run that fails here may still rank arms.

Under BOUNDARY_MIN_N the boundary result is `None`, not `False`: an underpowered sample is a missing
measurement, not a failed one (the same distinction score_pooled.py draws everywhere else). Overall
`stable` requires both claims to be established, so a `None` leaves it False with a stated reason.

Exits 3 on a data defect rather than emitting a number, on the same principle as score_pooled.py.
"""
import json, sys, argparse
from collections import Counter, defaultdict

# Imported rather than restated: a verdict vocabulary that drifts between the two scorers would let a
# pass validate here and fail there, or worse, agree with itself about the wrong categories.
from score_pooled import ALL_VERDICTS, REAL

KAPPA_FLOOR = 0.60
EXACT_FLOOR = 0.70
# The load-bearing boundary (nib dcc-sfny). Same 0.60 convention as the coarse collapse; the extra
# `MIN_N` exists because this figure is computed over a SUBSET (clusters either pass put at
# valid-other or trivia) and that subset is routinely tiny. n=10 produced 0.403 and n=62 produced
# 0.598 on the same judge in the same week — the small number is not a worse judge, it is no
# measurement.
BOUNDARY_KAPPA_FLOOR = 0.60
BOUNDARY_MIN_N = 50


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

    # Per-boundary verdicts (nib dcc-sfny). Each floor is reported with the value it judged and
    # whether it passed, so a reader never has to reconstruct which check a single flag folded in.
    #
    # `passes: None` means NOT ESTABLISHED, and only the boundary can produce it: its n is a subset
    # count that is routinely far below what a kappa needs. False means measured and failed.
    def _check(value, floor, n=None, min_n=None):
        c = {"value": value, "floor": floor, "passes": value is not None and value >= floor}
        if min_n is not None:
            c["n"] = n
            c["min_n"] = min_n
            if n < min_n:
                c["passes"] = None
                c["note"] = (f"n={n} < {min_n}: underpowered, not a measurement — an unestablished "
                             f"boundary is not the same as a failed one")
        return c

    checks = {
        "real_vs_not_kappa": _check(real_k, KAPPA_FLOOR),
        "exact_agreement": _check(exact, EXACT_FLOOR),
        "valid_other_vs_trivia_kappa": _check(b_k, BOUNDARY_KAPPA_FLOOR,
                                              n=len(b_pairs), min_n=BOUNDARY_MIN_N),
    }
    rankings_ok = all(checks[k]["passes"] is True
                      for k in ("real_vs_not_kappa", "exact_agreement"))
    boundary = checks["valid_other_vs_trivia_kappa"]["passes"]
    # None propagates: rankings can be established while precision levels are not measured at all.
    precision_ok = None if boundary is None else (rankings_ok and boundary)
    stable = rankings_ok and boundary is True

    if stable:
        reason = "all three pre-registered floors cleared"
    elif not rankings_ok:
        failed = [k for k in ("real_vs_not_kappa", "exact_agreement") if checks[k]["passes"] is not True]
        reason = f"below the floor on {', '.join(failed)} — neither rankings nor levels are licensed"
    elif boundary is None:
        reason = (f"rankings are licensed; the valid-other/trivia boundary was measured over "
                  f"n={len(b_pairs)} < {BOUNDARY_MIN_N}, so precision LEVELS are not established. "
                  f"Publish precision as a band across both passes, not as a point.")
    else:
        reason = (f"rankings are licensed; the valid-other/trivia boundary is "
                  f"{b_k:.3f} < {BOUNDARY_KAPPA_FLOOR}, so precision LEVELS are not licensed. "
                  f"Publish precision as a band across both passes, not as a point.")

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
                      "boundary_kappa_floor": BOUNDARY_KAPPA_FLOOR,
                      "boundary_min_n": BOUNDARY_MIN_N,
                      "pre_registered": True},
        # Per-boundary, never one flag: a weak boundary used to pass because the two floors that
        # existed were the coarse ones.
        "checks": checks,
        "stable_for_rankings": rankings_ok,
        "stable_for_precision_levels": precision_ok,
        "stable": stable,
        "stable_reason": reason,
    }


# ---------------------------------------------------------------------------------------------
# Calibration mode (nib dcc-n4nf): today's verdicts against the PILOT's, on a standing sample.
#
# Self-agreement and agreement-with-the-baseline are different properties, and a run can have the
# first without the second. Measured 2026-08-19 on prometheus: today's two passes agreed 24/24
# (kappa 1.0) while agreeing with the pilot on 9/15 and 6/15. A pipeline reporting only kappa would
# have called that a flawless grading day.
# ---------------------------------------------------------------------------------------------
RANK = {"matches-thread": 5, "matches-key": 5, "valid-other": 4,
        "valid-minor": 3, "trivia": 2, "false-positive": 1}


def calibration(sample_path, today1, today2=None):
    """Agreement of today's verdicts with the pilot's, on the standing sample.

    `today1`/`today2` map REAL cluster_id -> verdict. Callers holding blind ids must map back
    through the grading key first; a blind id here would silently match nothing and report 0/0,
    so an empty overlap is an error rather than a result.
    """
    doc = json.load(open(sample_path))
    rows = doc["clusters"]
    seen = [r for r in rows if r["cluster_id"] in today1]
    if not seen:
        raise DataDefect(
            f"none of the {len(rows)} standing-sample clusters appear in today's verdicts. "
            f"Either the sample was not graded today, or blind ids were passed without mapping "
            f"them back. An ungraded sample is not a calibration of 0 — it is a missing measurement.")
    def agree(key):
        pairs = [(r[key], today1[r["cluster_id"]]) for r in seen if r.get(key)]
        return {"agree": sum(1 for a, b in pairs if a == b), "n": len(pairs)}
    out = {"subject": doc["subject"], "sample_n": len(rows), "graded_today": len(seen),
           "vs_pilot_pass1": agree("pilot_pass1"), "vs_pilot_pass2": agree("pilot_pass2")}
    # direction of disagreement: a judge that is uniformly harsher suppresses every arm equally, so
    # comparative claims survive it while absolute counts do not. Report which it is.
    d = {"harsher": 0, "softer": 0, "same": 0}
    for r in seen:
        base, now = r.get("pilot_pass1"), today1[r["cluster_id"]]
        if not base:
            continue
        if base == now:
            d["same"] += 1
        elif RANK.get(now, 0) < RANK.get(base, 0):
            d["harsher"] += 1
        else:
            d["softer"] += 1
    out["direction_vs_pilot_pass1"] = d
    if today2:
        both = [r["cluster_id"] for r in seen if r["cluster_id"] in today2]
        out["today_pass1_vs_pass2"] = {
            "agree": sum(1 for c in both if today1[c] == today2[c]), "n": len(both)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pass1"); ap.add_argument("pass2", nargs="?"); ap.add_argument("-o", "--out")
    ap.add_argument("--calibration", metavar="SAMPLE",
                    help="path to grading/calibration-sample.json; compares today's verdicts "
                         "against the pilot's on the standing sample")
    a = ap.parse_args()

    if a.calibration:
        t1 = {v["cluster_id"]: v.get("verdict") for v in _load(a.pass1)["verdicts"]}
        t2 = ({v["cluster_id"]: v.get("verdict") for v in _load(a.pass2)["verdicts"]}
              if a.pass2 else None)
        try:
            m = calibration(a.calibration, t1, t2)
        except DataDefect as e:
            print(f"DATA DEFECT — refusing to emit a calibration figure:\n  {e}", file=sys.stderr)
            sys.exit(3)
        s = json.dumps(m, indent=2)
        if a.out:
            open(a.out, "w").write(s + "\n"); print(f"wrote {a.out}")
        else:
            print(s)
        return

    if not a.pass2:
        print("stability mode needs two passes", file=sys.stderr); sys.exit(2)
    try:
        p1, p2 = _load(a.pass1), _load(a.pass2)
        validate(p1, p2)
    except DataDefect as e:
        print(f"DATA DEFECT — refusing to emit a stability figure:\n  {e}", file=sys.stderr)
        sys.exit(3)
    m = score(p1, p2)
    s = json.dumps(m, indent=2)
    # The precision caveat has to reach a caller who only reads the exit line. A run whose boundary
    # is unestablished still writes its file and exits 0 — the figure is real, the LEVEL is not.
    if m["stable_for_precision_levels"] is not True:
        print(f"NOTE: {m['stable_reason']}", file=sys.stderr)
    if a.out:
        open(a.out, "w").write(s + "\n"); print(f"wrote {a.out}")
    else:
        print(s)


if __name__ == "__main__":
    main()
