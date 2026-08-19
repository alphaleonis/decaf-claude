#!/usr/bin/env python3
"""Classify what a fold-in did to the EXISTING arms' figures (nib dcc-dirp).

Usage: assert_foldin_movements.py <before-metrics.json> <after-metrics.json> [...pairs]

`dcc-u10u` asked that existing per-tool figures be "asserted unchanged". That criterion is not
achievable by any arm that finds something new, and as a pass/fail gate it rewards a weak arm: an
arm contributing nothing novel passes trivially, while one that finds a real defect no other tool
found necessarily fails.

So the gate is not "no movement". It is "every movement is EXPLAINED". Two movement classes are
expected and benign; anything else stops the pipeline.

  unique_real-lost   an arm's `unique_real` fell because the new arm also reported that cluster.
                     "Unique" means only-that-tool, so a second reporter correctly removes it.

  pool-grew          `defect_recall.pool` rose because the new arm found a real defect-class cluster
                     nobody had recorded. Every existing arm's recall falls WITHOUT those arms
                     changing — the pooled axis is bounded by the union of tool output
                     (METHODOLOGY-v2 section 2), so this is inherent, not drift.

                     Consequence, and it must be published with the number: a defect-recall figure is
                     only comparable against figures computed from the SAME pool. Print the pool size
                     beside it, always.

  unexplained        anything else. Exits 3.
"""
import json, sys, argparse

BENIGN = ("unique_real-lost", "pool-grew")


def classify(arm, field, before, after):
    if field in ("unique_real", "unique_real_ids"):
        b = before if field == "unique_real" else len(before or [])
        a = after if field == "unique_real" else len(after or [])
        if a < b:
            return "unique_real-lost", f"{b} -> {a}: another arm now reports it too"
        return "unexplained", f"{field} ROSE {before} -> {after}, which a fold-in cannot cause"
    if field == "defect_recall":
        b, a = before or {}, after or {}
        if a.get("pool", 0) > b.get("pool", 0):
            return "pool-grew", (f"pool {b.get('pool')} -> {a.get('pool')}; recall "
                                 f"{b.get('recall_reported')} -> {a.get('recall_reported')} "
                                 f"WITHOUT this arm changing")
        if a.get("reported") != b.get("reported") or a.get("found") != b.get("found"):
            return "unexplained", (f"this arm's own counts moved: reported "
                                   f"{b.get('reported')} -> {a.get('reported')}, found "
                                   f"{b.get('found')} -> {a.get('found')}")
        return "unexplained", f"{b} -> {a}"
    return "unexplained", f"{before} -> {after}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="+", help="before.json after.json [before.json after.json ...]")
    a = ap.parse_args()
    if len(a.pairs) % 2:
        sys.exit("give metrics.json files in before/after pairs")

    total = {k: 0 for k in BENIGN}
    unexplained = []
    for i in range(0, len(a.pairs), 2):
        before = json.load(open(a.pairs[i]))
        after = json.load(open(a.pairs[i + 1]))
        subj = after.get("subject", a.pairs[i + 1])
        tb, ta = before.get("tools") or {}, after.get("tools") or {}
        new_arms = sorted(set(ta) - set(tb))
        print(f"\n=== {subj}   new arm(s): {', '.join(new_arms) or 'none'}")
        moved = False
        for arm in sorted(tb):
            if arm not in ta:
                unexplained.append(f"{subj}/{arm}: DISAPPEARED from metrics.json")
                continue
            for f in sorted(set(tb[arm]) | set(ta[arm])):
                if f == "precision_note":
                    continue
                x, y = tb[arm].get(f), ta[arm].get(f)
                if x == y:
                    continue
                moved = True
                kind, why = classify(arm, f, x, y)
                if kind in BENIGN:
                    total[kind] += 1
                    print(f"  {kind:<18} {arm}.{f}: {why}")
                else:
                    unexplained.append(f"{subj}/{arm}.{f}: {why}")
        if not moved:
            print("  no movement in any pre-existing arm")

    print(f"\nbenign movements: " + ", ".join(f"{k}={v}" for k, v in total.items()))
    if unexplained:
        print(f"\nUNEXPLAINED MOVEMENTS ({len(unexplained)}) — the fold-in changed something it "
              f"should not have:", file=sys.stderr)
        for u in unexplained:
            print(f"  {u}", file=sys.stderr)
        sys.exit(3)
    print("every movement is explained; no unexplained change to a pre-existing arm")


if __name__ == "__main__":
    main()
