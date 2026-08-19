#!/usr/bin/env python3
"""Re-check the five 2026-08-19 reversals from the FACT TABLES alone (nib dcc-t83x).

The point of emitting facts was that a conclusion should be verifiable by someone who does not trust
the script that printed it. This file is that claim, tested: each of the five conclusions that
reversed during that session is re-derived here from `analysis/facts/*.jsonl` and nothing else — no
analysis.json, no metrics.json, no ad-hoc reshaping.

If a future change to the pipeline breaks one of these, the fix is not to edit the expectation. It
is to work out why the facts no longer say what they said, because a published figure depends on it.
"""
import json, os, sys, collections

V2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS = os.path.join(V2, "analysis", "facts")
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print(f"  PASS  {name}")
    else:
        fail += 1; print(f"  FAIL  {name}  {detail}")


def load(n):
    p = os.path.join(FACTS, f"{n}.jsonl")
    if not os.path.exists(p):
        sys.exit(f"no fact table at {p} — run emit_facts.py first")
    return [json.loads(l) for l in open(p) if l.strip()]


clusters = {(c["subject"], c["cluster_id"]): c for c in load("clusters")}
obs = load("observations")
cells = load("cells")
EF, PR = "dotnet-efcore-34127", "prometheus-prometheus-18081"
NARROW, NORM = "ours-bugs-narrow", "ours-bugs-reachnorm"


def reported(arm, subjects):
    return {(o["subject"], o["cluster_id"]) for o in obs
            if o["arm"] == arm and o["disposition"] == "reported" and o["subject"] in subjects}


def found(arm, subjects):
    return {(o["subject"], o["cluster_id"]) for o in obs
            if o["arm"] == arm and o["subject"] in subjects}


print("== REVERSAL 1: efcore's new clusters 'favour the exploration hypothesis' -> all trivia ==")
# LIMITATION, worth stating: "this cluster was NEW in fold-in X" is not derivable from the fact
# tables. `clusters.jsonl` records what a cluster IS, not when it entered the pool, and set
# arithmetic over `observations` cannot recover it — reported(norm) minus reported(narrow) also
# picks up long-standing clusters that narrow simply did not report. That difference is exactly the
# substitution that caused this reversal, so the check names the ids explicitly. They come from the
# committed grading artifact:
#   pooled/dotnet-efcore-34127/grading/foldin-2026-08-19-reach-arms/cluster-assignments-*.json
NEW_ON_EFCORE = [(EF, c) for c in ("e79", "e80", "e81", "e82", "e83")]
verdicts = collections.Counter(clusters[k]["verdict"] for k in NEW_ON_EFCORE)
real = sum(1 for k in NEW_ON_EFCORE if clusters[k]["is_real"])
check("none of the clusters new to the efcore pool is `real`",
      real == 0, f"{real} real among {len(NEW_ON_EFCORE)}: {dict(verdicts)}")
check("they are trivia and valid-minor — correct, but not the discovery the ratio suggested",
      verdicts["trivia"] + verdicts["valid-minor"] == len(NEW_ON_EFCORE), dict(verdicts))
check("and defect-CLASS does not imply real-VERDICT — the conflation that caused this reversal",
      any(clusters[k]["finding_class"] == "defect" and not clusters[k]["is_real"]
          for k in clusters), "no defect-class cluster is non-real anywhere")

print("\n== REVERSAL 2: 'norm never reached e02' -> both arms reported it ==")
e02 = [o for o in obs if (o["subject"], o["cluster_id"]) == (EF, "e02")]
by = {o["arm"]: [x["repeat"] for x in e02 if x["arm"] == o["arm"] and x["disposition"] == "reported"]
      for o in e02}
check("ours-bugs-narrow reported e02", bool(by.get(NARROW)), f"{by}")
check("ours-bugs-reachnorm reported e02", bool(by.get(NORM)), f"{by}")
check("e02 is in the real-defect pool, so a hit merges and leaves NO new cluster — "
      "which is why the new-cluster list is not a detection record",
      clusters[(EF, "e02")]["in_defect_pool"] is True)

print("\n== REVERSAL 3: 'reach is a null result' -> higher defect-pool hit rate per cell ==")
subs = {EF, PR}
pool = {k for k, c in clusters.items() if c["in_defect_pool"] and k[0] in subs}


def hits_per_cell(arm):
    n = sum(1 for c in cells if c["arm"] == arm and c["subject"] in subs)
    per_subj = n / len(subs)
    h = {(o["subject"], o["cluster_id"], o["repeat"]) for o in obs
         if o["arm"] == arm and (o["subject"], o["cluster_id"]) in pool}
    return len(h) / (len(pool) * per_subj)


hn, hr = hits_per_cell(NARROW), hits_per_cell(NORM)
check("reachnorm's per-cell defect-pool hit rate exceeds narrow's",
      hr > hn, f"narrow {hn:.3f} vs reachnorm {hr:.3f}")
check("the published figures reproduce (narrow 0.375, reachnorm 0.458)",
      abs(hn - 0.375) < 0.002 and abs(hr - 0.458) < 0.002, f"{hn:.3f} / {hr:.3f}")

print("\n== REVERSAL 4: 'half of reachnorm's output is not real' -> 22 of 24 correct ==")
shown = reported(NORM, {PR})
real_n = sum(1 for k in shown if clusters[k]["is_real"])
minor_n = sum(1 for k in shown if clusters[k]["is_valid_minor"])
noise_n = sum(1 for k in shown if clusters[k]["is_noise"])
check("precision on prometheus really is ~0.50 (so the number was read correctly)",
      abs(real_n / len(shown) - 0.5) < 0.02, f"{real_n}/{len(shown)}")
check("but correct-and-actionable is 22 of 24 — valid-minor is NOT noise",
      real_n + minor_n == 22 and len(shown) == 24, f"real {real_n} minor {minor_n} noise {noise_n}")
check("noise% is the number that answers 'is this worth reading'",
      abs(noise_n / len(shown) - 0.083) < 0.01, f"{noise_n}/{len(shown)}")

print("\n== REVERSAL 5: 'review buys almost nothing over bugs reach=norm' -> +30% all classes ==")
REV = "ours-review-postdduy"
five = {c["subject"] for c in cells if c["arm"] == REV}
rev_real = {k for k in reported(REV, five) if clusters[k]["is_real"]}
# scope reachnorm to the subjects it actually ran, then compare on the shared two
shared = {EF, PR}
rev_d = sum(1 for k in reported(REV, shared) if clusters[k]["is_real"]
            and clusters[k]["finding_class"] == "defect")
nrm_d = sum(1 for k in reported(NORM, shared) if clusters[k]["is_real"]
            and clusters[k]["finding_class"] == "defect")
rev_a = sum(1 for k in reported(REV, shared) if clusters[k]["is_real"])
nrm_a = sum(1 for k in reported(NORM, shared) if clusters[k]["is_real"])
check("on DEFECTS alone the gap is small — the original claim, correctly scoped",
      abs(rev_d - nrm_d) <= 2, f"review {rev_d} vs reachnorm {nrm_d}")
check("across ALL classes review reports materially more real findings — the correction",
      rev_a > nrm_a, f"review {rev_a} vs reachnorm {nrm_a}")

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
