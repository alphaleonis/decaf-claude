#!/usr/bin/env python3
"""Can a cheap model do the dedup the orchestrator currently spends frontier thinking on?

The gating experiment for #dcc-xewu. `cluster-then-screen` (see #dcc-9q01) only works if
clustering can be moved off the expensive model — so replay archived sub-agent findings through a
cheap-model clustering pass and score it against the committed reference clustering.

What matters is NOT raw clustering accuracy. It is whether the corroboration signal survives:
substantive clusters carry more finders than trivia, and that gap is what a screen would rank on.
A clusterer that splits aggressively still works if it splits trivia harder than it splits real
findings.

  build  — emit one task per run: shuffled findings, ground truth held out separately
  score  — score result files against the truth, and report corroboration survival by verdict tier

Usage:
  cluster_replay.py build <workdir>
  cluster_replay.py score <workdir>

Between the two, a cheap-model agent reads each `<run>.input.json` and writes
`<run>.result.json` as {"groups": [["F00","F07"], ["F03"], ...]}. Ground truth is only available
for runs whose findings.json carries an inline `cluster_id` (subjects 1, 4, 5, 7).
"""
import json, glob, os, sys, random, collections, itertools

POS = {"TP-primary", "TP-human", "valid-other"}
MINOR = {"valid-minor"}
ANALYSIS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def band(v):
    return "substantive" if v in POS else ("valid-minor" if v in MINOR else "trivia/FP")


def build(work):
    os.makedirs(work, exist_ok=True)
    random.seed(20260729)          # fixed: the shuffle must not vary between builds
    manifest = []
    for f in sorted(glob.glob(os.path.join(ANALYSIS, "subject-*", "findings.json"))):
        F = json.load(open(f))
        sid = os.path.basename(os.path.dirname(f))
        if not any(x.get("cluster_id") for x in F):
            continue               # no inline ground truth for this subject
        for rep in (1, 2):
            sub = [x for x in F if x["tool"] == "ours" and x["repeat"] == rep
                   and x.get("subagent") and x.get("cluster_id")]
            if len(sub) < 10:
                continue
            items = [{"id": f"F{i:02d}", "file": x.get("file"), "line": x.get("line"),
                      "category": x.get("category"), "claim": x.get("claim")}
                     for i, x in enumerate(sub)]
            truth = {f"F{i:02d}": x["cluster_id"] for i, x in enumerate(sub)}
            random.shuffle(items)  # order must not leak the grouping
            name = f"{sid}-r{rep}"
            json.dump(items, open(f"{work}/{name}.input.json", "w"), indent=1)
            json.dump(truth, open(f"{work}/{name}.truth.json", "w"))
            manifest.append({"name": name, "subject": sid, "repeat": rep,
                             "n": len(items), "ref_clusters": len(set(truth.values()))})
    json.dump(manifest, open(f"{work}/manifest.json", "w"), indent=1)
    for m in manifest:
        print(f"  {m['name']:14} {m['n']:3} findings, {m['ref_clusters']:2} reference clusters")
    print(f"\n{len(manifest)} tasks -> {work}")


def score(work):
    manifest = json.load(open(f"{work}/manifest.json"))
    tp = fp = fn = 0
    before, after = collections.defaultdict(list), collections.defaultdict(list)
    print(f"{'run':14} {'n':>3} {'ref':>4} {'got':>4} {'dropped':>7} {'pairP':>6} {'pairR':>6} {'F1':>6}")
    for m in manifest:
        name = m["name"]
        truth = json.load(open(f"{work}/{name}.truth.json"))
        rp = f"{work}/{name}.result.json"
        if not os.path.exists(rp):
            print(f"{name:14} MISSING RESULT")
            continue
        groups = json.load(open(rp))["groups"]
        pred = {fid: gi for gi, g in enumerate(groups) for fid in g}
        dropped = [k for k in truth if k not in pred]

        ids = sorted(k for k in truth if k in pred)
        a = b = c = 0
        for x, y in itertools.combinations(ids, 2):
            st, sp = truth[x] == truth[y], pred[x] == pred[y]
            if st and sp: a += 1
            elif sp: b += 1
            elif st: c += 1
        tp += a; fp += b; fn += c
        P = a / (a + b) if a + b else 1.0
        R = a / (a + c) if a + c else 1.0
        F = 2 * P * R / (P + R) if P + R else 0.0
        print(f"{name:14} {m['n']:>3} {m['ref_clusters']:>4} {len(groups):>4} {len(dropped):>7} "
              f"{P:>6.2f} {R:>6.2f} {F:>6.2f}")

        verd = {cl["cluster_id"]: cl.get("verdict")
                for cl in json.load(open(os.path.join(ANALYSIS, m["subject"], "analysis.json")))["clusters"]}
        ref = collections.defaultdict(list)
        for fid, cid in truth.items():
            ref[cid].append(fid)
        for cid, fids in ref.items():
            t = band(verd.get(cid))
            before[t].append(len(fids))
            placed = [f for f in fids if f in pred]
            # the largest predicted group drawn from one reference cluster is the corroboration
            # that survives — a screen downstream can only see agreement the clusterer preserved
            after[t].append(max(collections.Counter(pred[f] for f in placed).values()) if placed else 0)

    P = tp / (tp + fp) if tp + fp else 0
    R = tp / (tp + fn) if tp + fn else 0
    print(f"\nPOOLED  precision {P:.2f}  recall {R:.2f}  F1 {2*P*R/(P+R):.2f}")
    print(f"  {tp} pairs correctly merged, {fp} wrongly merged, {fn} wrongly split")

    print(f"\nCORROBORATION SURVIVAL — the number that decides the experiment")
    print(f"{'tier':14} {'clusters':>8} {'finders before':>15} {'after':>7} {'2+ before':>10} {'2+ after':>9}")
    for t in ("substantive", "valid-minor", "trivia/FP"):
        b, a_ = before[t], after[t]
        if not b:
            continue
        print(f"{t:14} {len(b):>8} {sum(b)/len(b):>15.2f} {sum(a_)/len(a_):>7.2f} "
              f"{sum(1 for x in b if x >= 2)/len(b):>9.0%} {sum(1 for x in a_ if x >= 2)/len(a_):>8.0%}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("build", "score"):
        print(__doc__)
        sys.exit(2)
    (build if sys.argv[1] == "build" else score)(sys.argv[2])
