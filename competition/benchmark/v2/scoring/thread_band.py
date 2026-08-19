#!/usr/bin/env python3
"""Thread recall as a BAND across grading passes, not a point (nib dcc-di47).

Usage: thread_band.py <subject-dir> [more ...]

Two independent blind passes over the SAME clusters moved per-tool thread recall by up to 0.20 on
the pilot's densest subject, while precision moved at most 0.11 and kept its ranking. That is not
judge sloppiness — the judge cleared every stability floor. It is quantization plus shared credit:

  * 10 human threads means each is worth 0.10 of recall;
  * a thread is credited to every tool in the cluster the judge matched it to, so re-matching one
    thread from a 3-tool cluster to a 1-tool cluster moves three tools by 0.10 each — without
    changing whether the thread was covered at all.

So this reports two different things, and only one of them is stable:

  CORPUS COVERAGE (`missed_by_every_tool`) — did ANY tool raise this thread. Barely moves between
  passes, and it is the axis METHODOLOGY-v2 section 2 actually justifies the thread set for.

  PER-TOOL ATTRIBUTION — which tool gets the credit. Unstable, and published as a range with n
  attached, never as a point.

Recall is computed over HUMAN threads only (dcc-qwt3); bot threads score `incumbent_agreement`,
which is a different axis and is never pooled with this one.
"""
import json, os, sys, argparse, collections

REAL_OR_ANY = None  # a thread is "hit" if any cluster matched it, whatever that cluster's verdict


def passes(subject_dir):
    """(pass_label, {cluster_id: matched_thread_index}) for every grading pass on disk."""
    an = json.load(open(os.path.join(subject_dir, "analysis.json")))
    out = [("pass1", {c["cluster_id"]: c.get("matches_thread") for c in an["clusters"]})]
    p2 = os.path.join(subject_dir, "grading", "verdicts-pass2.json")
    if os.path.exists(p2):
        out.append(("pass2", {v["cluster_id"]: v.get("matches_thread")
                              for v in json.load(open(p2))}))
    return an, out


def recall(an, match, human_idx, tool):
    """Fraction of HUMAN threads this tool raised, under one pass's matching."""
    hit = set()
    for c in an["clusters"]:
        t = match.get(c["cluster_id"])
        if not isinstance(t, int) or t not in human_idx:
            continue
        if any(r["tool"] == tool for r in c.get("reported_by", [])):
            hit.add(t)
    return len(hit) / len(human_idx) if human_idx else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subject_dirs", nargs="+")
    a = ap.parse_args()
    print("THREAD RECALL — reported as a band across grading passes (nib dcc-di47)")
    print("Human threads only. A point estimate is not publishable: per-tool attribution moved up")
    print("to 0.20 between two passes over identical clusters.\n")
    for d in a.subject_dirs:
        d = os.path.abspath(d.rstrip("/"))
        subject = os.path.basename(d)
        if not os.path.exists(os.path.join(d, "analysis.json")):
            # Not scored yet. Say so — an unscored subject and a subject with no coverage are
            # different things and must never look the same.
            print(f"=== {subject} — SKIPPED: no analysis.json (subject not scored)\n")
            continue
        an, ps = passes(d)
        th = [t for t in json.load(open(os.path.join(d, "threads.json")))
              if t.get("admission") == "admitted"]
        human_idx = {i for i, t in enumerate(th) if t.get("origin") == "human"}
        n = len(human_idx)
        thin = n <= 2
        print(f"=== {subject} — n={n} human thread(s) of {len(th)} admitted"
              f"{'   *** THIN: per-subject disclosure only, never poolable ***' if thin else ''}")
        if len(ps) < 2:
            print("    only one grading pass on disk — NO BAND CAN BE COMPUTED. Report nothing.\n")
            continue
        # corpus coverage: the stable axis
        cov = {}
        for label, m in ps:
            hit = set()
            for c in an["clusters"]:
                t = m.get(c["cluster_id"])
                if isinstance(t, int) and t in human_idx and c.get("reported_by"):
                    hit.add(t)
            cov[label] = hit
        lo, hi = sorted(len(v) for v in cov.values())
        missed = sorted(human_idx - set.union(*cov.values())) if cov else []
        print(f"    corpus coverage (any tool): {lo}-{hi} of {n} threads   "
              f"missed under BOTH passes: {missed if missed else 'none'}")
        # EMPTY is not a score of zero (nib dcc-7zyf). If no tool matched any human thread, every
        # arm reads 0.00 and the axis cannot separate them — pooling it drags every average down by
        # the same amount while saying nothing about any tool. Render n/a with the reason instead.
        if hi == 0:
            reason = os.path.join(d, "THREAD-AXIS-NOTE.md")
            why = ""
            if os.path.exists(reason):
                for line in open(reason):
                    if line.startswith("REASON:"):
                        why = line.split(":", 1)[1].strip(); break
            print(f"    *** HUMAN AXIS EMPTY — no tool matched any human thread under either pass.")
            print(f"        Per-tool recall is n/a, NOT 0.00, and must be excluded from any pooled")
            print(f"        thread figure. It cannot discriminate between arms.")
            print(f"        {'REASON: ' + why if why else 'REASON: not recorded — add THREAD-AXIS-NOTE.md'}\n")
            continue
        tools = sorted({r["tool"] for c in an["clusters"] for r in c.get("reported_by", [])})
        print(f"    {'arm':<24}{'pass1':>8}{'pass2':>8}{'band':>20}{'delta':>8}")
        for tool in tools:
            vals = [recall(an, m, human_idx, tool) for _, m in ps]
            if any(v is None for v in vals):
                continue
            lo_v, hi_v = min(vals), max(vals)
            flag = "  <-- unstable" if (hi_v - lo_v) >= 0.20 else ""
            print(f"    {tool:<24}{vals[0]:>8.2f}{vals[1]:>8.2f}"
                  f"{f'{lo_v:.2f}-{hi_v:.2f} (n={n})':>20}{hi_v-lo_v:>8.2f}{flag}")
        print()


if __name__ == "__main__":
    main()
