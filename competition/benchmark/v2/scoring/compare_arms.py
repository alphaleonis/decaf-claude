#!/usr/bin/env python3
"""Compare arms side by side, as ONE view over the fact tables (nib dcc-t83x).

Usage: compare_arms.py [--facts <dir>] [--arms A B ...] [--subjects S ...] [--json out.json]

This is not a source of truth. It reads `analysis/facts/*.jsonl` (emit_facts.py) and groups them.
Every number it prints is re-derivable from those files by hand, which is the point: on 2026-08-19
four different ad-hoc scripts answered four versions of the same question with four different column
definitions, and the conclusions reversed five times.

What it refuses to do, and why each refusal exists:

  * no ratio below 10 reported clusters — a pilot precision moved 1.00 -> 0.60 when a second repeat
    took its denominator from 3 to 5 (PILOT-RESULTS.md)
  * no ranking across arms with different subject coverage — on 2026-08-19 the 2-subject arms sat
    against a 53-cluster pool and the 5-subject arms against 77; those are not the same denominator
  * no pooled figure for an arm whose cells used different model sets — that is the `ours-bugs`
    trap, where one id covers the four-seat wave AND the single seat
  * every recall prints its pool size and the arm set, because the pool is dynamic (nib dcc-dirp)
"""
import json, os, sys, argparse, collections

V2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLS = ["defect", "risk", "test-gap", "docs", "design", "style"]
SEV = ["critical", "high", "medium", "low", "nit", "info"]
N_FLOOR = 10

LEGEND = """\
LEGEND — definitions travel with the numbers (full text: scoring/METRICS.md)
  shown        clusters the arm REPORTED: what a developer is actually handed
  found        shown + demoted: everything the arm examined and formed a claim about
  real         verdict in {matches-thread, matches-key, valid-other}
  valid-minor  CORRECT AND ACTIONABLE but small. Excluded from `real`, therefore excluded from
               `precision`. It is NOT noise. Banded separately here for exactly that reason.
  noise%       (trivia + false-positive) / shown — the "is this worth reading" number.
               This is NOT 1-precision, because precision counts valid-minor as a miss.
  class        what a finding is ABOUT (defect/risk/test-gap/docs/design/style).
  verdict      whether it is RIGHT. The two are orthogonal: a "checked whether X crashes -- it
               cannot" note is defect-CLASS and trivia-VERDICT.
  defect pool  clusters that are real AND defect-class. DYNAMIC: adding an arm that finds something
               new enlarges it and retroactively lowers every other arm's recall (nib dcc-dirp)."""


def load(facts):
    def rd(n):
        p = os.path.join(facts, f"{n}.jsonl")
        if not os.path.exists(p):
            sys.exit(f"no fact table at {p} — run emit_facts.py first")
        return [json.loads(l) for l in open(p) if l.strip()]
    return rd("clusters"), rd("observations"), rd("cells")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", default=os.path.join(V2, "analysis", "facts"))
    ap.add_argument("--arms", nargs="*")
    ap.add_argument("--subjects", nargs="*")
    ap.add_argument("--json", help="also write the assembled view as JSON")
    ap.add_argument("--allow-mixed", action="store_true",
                    help="pool an arm whose cells used different model sets (default: refuse)")
    a = ap.parse_args()

    clusters, obs, cells = load(a.facts)
    if a.subjects:
        keep = set(a.subjects)
        clusters = [c for c in clusters if c["subject"] in keep]
        obs = [o for o in obs if o["subject"] in keep]
        cells = [c for c in cells if c["subject"] in keep]

    cl = {(c["subject"], c["cluster_id"]): c for c in clusters}
    arms = sorted({o["arm"] for o in obs})
    if a.arms:
        arms = [x for x in arms if x in set(a.arms)]

    # ---- coverage groups: an arm may only be ranked against arms with the same subject set ----
    cov = {}
    for arm in arms:
        cov[arm] = frozenset(c["subject"] for c in cells if c["arm"] == arm)
    groups = collections.defaultdict(list)
    for arm in arms:
        groups[cov[arm]].append(arm)

    # ---- an arm whose cells used INCOMPATIBLE model sets is more than one configuration ----
    # Nested sets ({opus} vs {opus,sonnet}) are incidental: a lane simply was not dispatched that
    # run. Non-nested sets ({opus,haiku} vs {opus,sonnet}) mean a MODEL POLICY changed under one arm
    # id — the `ours-bugs` trap, where the same id covers the pre-dduy Haiku wave and the post-dduy
    # Sonnet wave. Only the second is a refusal; the first is reported so it stays visible.
    refusals, warnings, mixed = [], [], {}
    for arm in arms:
        sets = {frozenset((c.get("models") or {}).keys()) for c in cells if c["arm"] == arm}
        sets = {s for s in sets if s}
        if len(sets) < 2:
            continue
        nested = all(x <= y or y <= x for x in sets for y in sets)
        shown = sorted(sorted(s) for s in sets)
        if nested:
            warnings.append(f"NOTE     {arm}: model sets vary across cells {shown} — nested, so read "
                            f"as a lane not dispatched on some runs, not a configuration change.")
        else:
            mixed[arm] = shown
            refusals.append(
                f"REFUSED  {arm}: cells used INCOMPATIBLE model sets {shown}. One arm id, more than "
                f"one model policy — split the arm or pass --allow-mixed.")
    if refusals and not a.allow_mixed:
        arms = [x for x in arms if x not in mixed]

    def cellcount(arm):
        return sum(1 for c in cells if c["arm"] == arm)

    def stats(arm):
        o = [x for x in obs if x["arm"] == arm and (x["subject"], x["cluster_id"]) in cl]
        found = {(x["subject"], x["cluster_id"]) for x in o}
        shown = {(x["subject"], x["cluster_id"]) for x in o if x["disposition"] == "reported"}
        g = lambda ks, f: sum(1 for k in ks if f(cl[k]))
        n = cellcount(arm) or 1
        pool = [k for k, c in cl.items() if c["in_defect_pool"] and c["subject"] in cov[arm]]
        # cell-level hits: a defect found in 2 of 3 cells counts twice, so this is a per-cell rate
        hits = collections.Counter()
        for x in o:
            k = (x["subject"], x["cluster_id"])
            if k in set(pool):
                hits[(k, x["repeat"])] += 1
        cells_per_subj = n / max(1, len(cov[arm]))
        denom = len(pool) * cells_per_subj
        return {
            "arm": arm, "cells": n, "subjects": len(cov[arm]),
            "shown": len(shown), "found": len(found),
            "real": g(shown, lambda c: c["is_real"]),
            "minor": g(shown, lambda c: c["is_valid_minor"]),
            "noise": g(shown, lambda c: c["is_noise"]),
            "pool": len(pool),
            "pool_found": sum(1 for k in pool if k in found),
            "pool_shown": sum(1 for k in pool if k in shown),
            "pool_hits_per_cell": round(len(hits) / denom, 3) if denom else None,
            "cost": round(sum(c["cost_usd"] or 0 for c in cells if c["arm"] == arm), 2),
        }

    rows = {arm: stats(arm) for arm in arms}
    print(LEGEND)
    if refusals or warnings:
        print()
        for r in refusals: print(r)
        for w in warnings: print(w)

    for group, garms in sorted(groups.items(), key=lambda kv: (-len(kv[0]), sorted(kv[0]))):
        garms = [x for x in garms if x in rows]
        if not garms:
            continue
        pool = rows[garms[0]]["pool"]
        print(f"\n{'='*104}\nCOVERAGE GROUP: {len(group)} subject(s) — {', '.join(sorted(group))}")
        print(f"real-defect pool for this group: {pool} clusters   |   arms in the pool's union: "
              f"{len({o['arm'] for o in obs if o['subject'] in group})}")
        print("Ranking is valid WITHIN this block only; other blocks sit against a different pool.\n")
        print(f"{'arm':<24}{'cells':>6}{'shown':>7}{'real':>6}{'minor':>7}{'noise':>7}{'noise%':>8}"
              f"{'precision':>11}{'found':>7}{'dem.gap':>9}{'pool hit/cell':>15}{'$/cell':>8}")
        for arm in sorted(garms, key=lambda x: -(rows[x]["pool_hits_per_cell"] or 0)):
            r = rows[arm]
            prec = (f"{r['real']/r['shown']:.3f}" if r["shown"] >= N_FLOOR
                    else f"n={r['shown']} WH")
            noisep = f"{r['noise']/r['shown']*100:.0f}%" if r["shown"] else "-"
            demgap = (f"{(r['found']-r['shown'])/r['found']:.2f}" if r["found"] else "-")
            print(f"{r['arm']:<24}{r['cells']:>6}{r['shown']:>7}{r['real']:>6}{r['minor']:>7}"
                  f"{r['noise']:>7}{noisep:>8}{prec:>11}{r['found']:>7}{demgap:>9}"
                  f"{str(r['pool_hits_per_cell']):>15}{r['cost']/r['cells']:>8.2f}")
        wh = [rows[x] for x in garms if rows[x]["shown"] < N_FLOOR]
        for r in wh:
            print(f"  WITHHELD  {r['arm']} precision: n={r['shown']} reported, floor is {N_FLOOR} "
                  f"(PILOT-RESULTS.md). Raw: {r['real']} real of {r['shown']} shown.")

    # ---- per-defect matrix, the view that showed e02 is a coin flip rather than a blind spot ----
    print(f"\n{'='*104}\nPER-DEFECT MATRIX — cells that found each real defect-class cluster")
    pool_keys = sorted([k for k, c in cl.items() if c["in_defect_pool"]])
    hdr = [x for x in arms]
    print(f"{'subject':<28}{'cluster':<9}{'sev':<9}" + "".join(f"{h[:14]:>16}" for h in hdr))
    for k in pool_keys:
        c = cl[k]
        cellstr = []
        for arm in hdr:
            if c["subject"] not in cov[arm]:
                cellstr.append("-")
                continue
            reps = {o["repeat"] for o in obs
                    if o["arm"] == arm and (o["subject"], o["cluster_id"]) == k}
            n = sum(1 for x in cells if x["arm"] == arm and x["subject"] == c["subject"])
            cellstr.append(f"{len(reps)}/{n}")
        print(f"{c['subject'][:27]:<28}{c['cluster_id']:<9}{str(c['judged_severity']):<9}"
              + "".join(f"{s:>16}" for s in cellstr))

    # ---- population, so a reader sees what the denominators are made of ----
    print(f"\n{'='*104}\nPOPULATION — real clusters by severity x class (the pool every recall divides by)")
    grid = collections.Counter()
    for c in clusters:
        if c["is_real"] and c["finding_class"]:
            grid[(c["judged_severity"], c["finding_class"])] += 1
    print(f"{'severity':<10}" + "".join(f"{x[:9]:>10}" for x in CLS) + f"{'total':>8}")
    for s in SEV:
        row = [grid[(s, x)] for x in CLS]
        if sum(row):
            print(f"{s:<10}" + "".join(f"{v:>10}" for v in row) + f"{sum(row):>8}")
    print(f"{'TOTAL':<10}" + "".join(f"{sum(grid[(s,x)] for s in SEV):>10}" for x in CLS)
          + f"{sum(grid.values()):>8}")

    if a.json:
        json.dump({"rows": rows, "refusals": refusals,
                   "coverage_groups": {",".join(sorted(g)): v for g, v in groups.items()}},
                  open(a.json, "w"), indent=1)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
