#!/usr/bin/env python3
"""Deterministic scoring for a v2 pooled-adjudication subject (nib dcc-y2e6).

Usage: score_pooled.py <analysis.json> [--threads threads.json] [--key answer-key.json] [-o out.json]

All arithmetic lives here, never in the LLM. The LLM stages produce `analysis.json` (extraction,
clustering, blind grading); this turns it into numbers.

Three axes, deliberately never merged into one "recall" (METHODOLOGY-v2 section 3):

  pooled    — precision, trivia ratio, unique real findings, noise per cell. Scored against the
              union of what the tools said, so it CANNOT see what everything missed.
  threads   — recall against admitted human review threads. The miss detector: an independent
              statement that something was worth raising, not derived from tool output. Agreement
              with expert review is related to, but not the same as, finding real bugs.
  anchor    — recall against an answer key, when the subject has one. Only for anchor subjects.

Exits non-zero on a data defect rather than emitting a null metric. Two specific failures are
guarded because both already produced published numbers that were wrong:
  - a field that is empty for an entire tool (scrapped dcc-3v3m: severities captured on 2 of 78
    entries, and one stray sub-agent `critical` handed a tool a free 1.00 on n=1)
  - artifacts describing different finding sets (scrapped dcc-z13k: 20 findings in the extract, 33
    in findings.json, 1 in common, and analysis.json clustering the stale set)
"""
import json, sys, argparse
from collections import defaultdict

# Verdicts. `matches-thread` and `matches-key` are v1's TP-human / TP-primary, renamed so nothing
# presupposes a key — pooled subjects have none.
REAL = {"matches-key", "matches-thread", "valid-other"}   # substantive: counts toward precision
MINOR = {"valid-minor"}                                    # correct but small
NOISE = {"trivia"}                                         # attention cost, not an error
WRONG = {"false-positive"}
ALL_VERDICTS = REAL | MINOR | NOISE | WRONG

SEV_WEIGHT = {"critical": 5.0, "high": 4.0, "medium": 2.0, "low": 1.0, "nit": 0.5, "info": 0.25}

# A tool can FIND a defect and then suppress it below its own reporting bar (dcc-c92m). Measured:
# an anthropic cell headlined "Verdict: No blocking issues found" while its "Sub-threshold
# observations (verified real, but scored below the reporting bar — not posted)" section described
# the defect exactly, "verified empirically", scored 0 as a pre-existing limitation.
#
# Scoring the headline makes that a miss; scoring everything it wrote makes it a catch. Both are
# true of different questions, so both are reported and neither is allowed to stand alone.
# Precision-style metrics count REPORTED findings only, because a demoted finding costs the reader
# no attention — it was never shown.
DISPOSITIONS = {"reported", "demoted"}


class DataDefect(Exception):
    """A pipeline defect, not a result. Never degrade to a null metric."""


def validate(A, threads, key):
    errs = []
    clusters = A.get("clusters") or []
    cells = A.get("cells") or []
    if not clusters:
        errs.append("no clusters — extraction or clustering produced nothing")
    if not cells:
        errs.append("no cells — costs/telemetry missing")

    if not A.get("judge_model"):
        errs.append("judge_model absent: results are not attributable to a grader")

    declared = {(c["tool"], c["repeat"]) for c in cells}
    seen = set()
    for c in clusters:
        cid = c.get("cluster_id", "?")
        v = c.get("verdict")
        if v not in ALL_VERDICTS:
            errs.append(f"{cid}: verdict {v!r} not in {sorted(ALL_VERDICTS)}")
        if v in REAL and not c.get("code_citation"):
            # Required by the judge-contamination mitigation: a verdict of "real" must point at code.
            errs.append(f"{cid}: verdict {v} without code_citation")
        rb = c.get("reported_by") or []
        if not rb:
            errs.append(f"{cid}: no reported_by — cluster belongs to no cell")
        for r in rb:
            seen.add((r.get("tool"), r.get("repeat")))
        for r in rb:
            d = r.get("disposition", "reported")
            if d not in DISPOSITIONS:
                errs.append(f"{cid}: disposition {d!r} not in {sorted(DISPOSITIONS)}")
        if v == "matches-thread" and c.get("matches_thread") is None:
            errs.append(f"{cid}: verdict matches-thread but no matches_thread index")
        if c.get("matches_thread") is not None and threads is None:
            errs.append(f"{cid}: matches_thread set but no threads.json supplied")

    orphans = seen - declared
    if orphans:
        errs.append(f"clusters reference cells absent from the cell list: {sorted(orphans)}")
    silent = declared - seen
    if silent:
        # A cell that contributed no cluster at all is usually an extraction failure, not a tool
        # that found nothing — the tool still wrote a report.
        errs.append(f"cells contributing zero clusters (extraction defect?): {sorted(silent)}")

    # Per-tool empty-field guard.
    by_tool = defaultdict(list)
    for c in clusters:
        for r in c.get("reported_by") or []:
            by_tool[r.get("tool")].append(r)
    for tool, rows in by_tool.items():
        if not any(r.get("severity") for r in rows):
            errs.append(f"tool {tool!r}: severity empty on all {len(rows)} reported findings")
    for tool, rows in by_tool.items():
        got = sum(1 for r in rows if r.get("severity"))
        if rows and got / len(rows) < 0.2:
            errs.append(f"tool {tool!r}: severity present on only {got}/{len(rows)} findings (<20%)")

    if threads is not None:
        admitted = [t for t in threads if t.get("admission") == "admitted"]
        if not admitted:
            errs.append("threads.json supplied but no thread is admitted")
        idxs = {c.get("matches_thread") for c in clusters if c.get("matches_thread") is not None}
        bad = {i for i in idxs if not isinstance(i, int) or i < 0 or i >= len(threads)}
        if bad:
            errs.append(f"matches_thread indexes out of range: {sorted(bad)}")

    if errs:
        raise DataDefect("; ".join(errs))


def score(A, threads, key):
    clusters = A["clusters"]
    cells = {(c["tool"], c["repeat"]): c for c in A["cells"]}
    tools = sorted({t for t, _ in cells})

    tool_clusters = defaultdict(set)
    for c in clusters:
        for r in c["reported_by"]:
            tool_clusters[r["tool"]].add(c["cluster_id"])
    by_id = {c["cluster_id"]: c for c in clusters}

    admitted_idx = [i for i, t in enumerate(threads or []) if t.get("admission") == "admitted"]

    # Which clusters a tool REPORTED versus merely FOUND (reported + demoted below its own bar).
    tool_reported = defaultdict(set)
    for c in clusters:
        for r in c["reported_by"]:
            if r.get("disposition", "reported") == "reported":
                tool_reported[r["tool"]].add(c["cluster_id"])

    out_tools = {}
    for tool in tools:
        ids = tool_clusters[tool]                      # found: reported + demoted
        rep_ids = tool_reported[tool]                  # reported only
        cs_found = [by_id[i] for i in ids]
        cs = [by_id[i] for i in rep_ids]               # precision-style metrics use reported only
        real = [c for c in cs if c["verdict"] in REAL]
        minor = [c for c in cs if c["verdict"] in MINOR]
        noise = [c for c in cs if c["verdict"] in NOISE]
        wrong = [c for c in cs if c["verdict"] in WRONG]
        n_reps = len({r for (t, r) in cells if t == tool})

        # Severity-weighted precision: v1's was unweighted, so four minor findings outscored one
        # revert-forcing defect. Weight by JUDGED severity, never by the tool's self-assigned one.
        def w(c):
            return SEV_WEIGHT.get((c.get("judged_severity") or "").lower(), 1.0)
        wr = sum(w(c) for c in real)
        wall = sum(w(c) for c in cs) or 1.0

        # Unique: real clusters no other tool reported.
        uniq = [c for c in real if {r["tool"] for r in c["reported_by"]} == {tool}]

        # Thread recall — its own axis, never folded into pooled precision, and split by disposition.
        def hits(pool):
            return {c["matches_thread"] for c in pool
                    if c["verdict"] == "matches-thread" and c.get("matches_thread") is not None}
        hit, hit_found = hits(cs), hits(cs_found)
        thread_recall = (len(hit & set(admitted_idx)) / len(admitted_idx)) if admitted_idx else None
        thread_recall_found = (len(hit_found & set(admitted_idx)) / len(admitted_idx)) if admitted_idx else None

        # Anchor recall gets the same reported/found split: a tool can find a key entry and demote it.
        anchor_recall = anchor_recall_found = None
        if key:
            entries = key.get("entries") or []
            if entries:
                def krecall(pool):
                    got = {c.get("matches_key") for c in pool if c["verdict"] == "matches-key"}
                    return len({g for g in got if g is not None}) / len(entries)
                anchor_recall, anchor_recall_found = krecall(cs), krecall(cs_found)

        out_tools[tool] = {
            "clusters_reported": len(cs),
            "clusters_found": len(cs_found),
            "real": len(real), "valid_minor": len(minor), "trivia": len(noise), "false_positive": len(wrong),
            "precision": round(len(real) / len(cs), 3) if cs else None,
            "precision_severity_weighted": round(wr / wall, 3) if cs else None,
            "trivia_ratio": round(len(noise) / len(cs), 3) if cs else None,
            "unique_real": len(uniq),
            "unique_real_ids": sorted(c["cluster_id"] for c in uniq),
            "per_cell": {
                "findings": round(len(cs) / n_reps, 2) if n_reps else None,
                "false_positive": round(len(wrong) / n_reps, 2) if n_reps else None,
                "trivia": round(len(noise) / n_reps, 2) if n_reps else None,
            },
            "thread_recall": round(thread_recall, 3) if thread_recall is not None else None,
            "thread_recall_found": round(thread_recall_found, 3) if thread_recall_found is not None else None,
            "demotion_gap": (round(thread_recall_found - thread_recall, 3)
                             if thread_recall is not None and thread_recall_found is not None else None),
            "threads_hit": len(hit & set(admitted_idx)) if admitted_idx else None,
            "real_found": len([c for c in cs_found if c["verdict"] in REAL]),
            "demoted_real": len([c for c in cs_found if c["verdict"] in REAL]) - len(real),
            "anchor_recall": round(anchor_recall, 3) if anchor_recall is not None else None,
            "anchor_recall_found": round(anchor_recall_found, 3) if anchor_recall_found is not None else None,
            "cost_usd": round(sum(cells[(t, r)].get("cost_usd", 0) for (t, r) in cells if t == tool), 4),
        }
        cu = out_tools[tool]["cost_usd"]
        out_tools[tool]["cost_per_real_finding"] = round(cu / len(real), 4) if real else None

    # Judge calibration: an admitted thread that a tool DID report, but the judge called not-real.
    # This check exists only because subjects come from review-disciplined repos.
    dismissed = []
    for c in clusters:
        mt = c.get("matches_thread")
        if mt is not None and mt in admitted_idx and c["verdict"] in (NOISE | WRONG):
            dismissed.append({"cluster_id": c["cluster_id"], "thread": mt, "verdict": c["verdict"],
                              "thread_path": (threads[mt] or {}).get("path")})

    # Threads no tool reported at all — the miss detector's actual output.
    hit_any = {c["matches_thread"] for c in clusters
               if c["verdict"] == "matches-thread" and c.get("matches_thread") is not None}
    missed = [i for i in admitted_idx if i not in hit_any]

    return {
        "subject": A.get("subject"),
        "instrument": A.get("instrument", "pooled-adjudication"),
        "judge_model": A.get("judge_model"),
        "n_clusters": len(clusters),
        "n_cells": len(cells),
        "threads": {
            "admitted": len(admitted_idx),
            "hit_by_any_tool": len(hit_any & set(admitted_idx)),
            "missed_by_every_tool": len(missed),
            "missed_index": missed,
            "judge_dismissed_reported_threads": dismissed,
        },
        "tools": out_tools,
        "verdict_distribution": {v: sum(1 for c in clusters if c["verdict"] == v)
                                 for v in sorted(ALL_VERDICTS)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("analysis")
    ap.add_argument("--threads"); ap.add_argument("--key"); ap.add_argument("-o", "--out")
    a = ap.parse_args()
    A = json.load(open(a.analysis))
    threads = json.load(open(a.threads)) if a.threads else None
    key = json.load(open(a.key)) if a.key else None
    try:
        validate(A, threads, key)
    except DataDefect as e:
        print(f"DATA DEFECT — refusing to emit metrics:\n  {e}", file=sys.stderr)
        sys.exit(3)
    m = score(A, threads, key)
    s = json.dumps(m, indent=2)
    if a.out:
        open(a.out, "w").write(s + "\n"); print(f"wrote {a.out}")
    else:
        print(s)


if __name__ == "__main__":
    main()
