#!/usr/bin/env python3
"""Price the "Considered But Not Flagged" channel against what Step 5.5 recovers from it.

Every reviewer emits a CBNF section and the orchestrator reasons over all of them (Step 5.5) to
promote wrongly-dismissed items. This measures both sides on the 18 archived `ours` runs:

  COST  — CBNF bullets emitted per run, and the share of sub-agent report text they occupy.
  YIELD — clusters the consolidated report carries that NO sub-agent flagged in the same run
          ("orphans"), joined to the judge's verdict. A Step 5.5 promotion can only look like
          this: the item reached the report without any reviewer flagging it.

An orphan is a *candidate*, not a confirmed promotion — the orchestrator can also synthesize a
finding across agents, and extraction can miss a sub-agent finding. Telling those apart needs the
run's actual CBNF bullets read against the cluster, which is a judgement, so it lives in a
committed file (analysis/cbnf-adjudication.json) rather than in a similarity threshold. Token
containment was tried as the decision rule and rejected — see that file's _README. It is still
computed and printed, as a pointer to the nearest bullet for anyone re-checking the call.

A candidate with no entry in the adjudication file is reported as UNADJUDICATED and counted
separately, so a re-run that surfaces new orphans cannot quietly drop them.

Usage: cbnf_yield.py [--json] [--bench-dir DIR]
"""
import json, glob, os, re, argparse, sys

STOP = set("""a an the and or but if of to in on for with without from by as at is are was were be been
being this that these those it its their there here not no than then so such can could may might will
would should must do does did done have has had which who whom whose what when where why how all any
each every both few more most other some only own same too very s t just now new use used using into
over under again further once still yet also per via""".split())

CBNF_RE = re.compile(r'^##+[ \t]*Considered But Not Flagged.*?$(.*?)(?=^##+[ \t]|\Z)', re.M | re.S)
BULLET_RE = re.compile(r'^[ \t]*[-*][ \t]+(.*)$', re.M)


def words(s):
    return {w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", (s or "").lower()) if w not in STOP}


def overlap(a, b):
    """Asymmetric containment: how much of the cluster summary the bullet accounts for.

    Jaccard punishes the length mismatch between a one-line summary and a discursive bullet, so
    score against the smaller set instead.
    """
    wa, wb = words(a), words(b)
    return (len(wa & wb) / min(len(wa), len(wb))) if wa and wb else 0.0


def cbnf_sections(run_dir):
    """[(agent_file, [bullet, ...], section_chars, report_chars)] for each sub-agent report."""
    out = []
    for path in sorted(glob.glob(os.path.join(run_dir, "findings", "subagent-*.md"))):
        text = open(path, encoding="utf-8", errors="replace").read()
        m = CBNF_RE.search(text)
        if not m:
            out.append((os.path.basename(path), [], 0, len(text)))
            continue
        body = m.group(1)
        bullets = [re.sub(r"\s+", " ", b).strip() for b in BULLET_RE.findall(body)]
        out.append((os.path.basename(path), bullets, len(body), len(text)))
    return out


def orphans(clusters, repeat):
    """Clusters the consolidated report carried with no same-run sub-agent flag."""
    out = []
    for c in clusters:
        rb = [r for r in c.get("reported_by", []) if r.get("tool") == "ours" and r.get("repeat") == repeat]
        if not any(r.get("subagent") is None for r in rb):
            continue
        if any(r.get("subagent") for r in rb):
            continue
        out.append(c)
    return out


def consolidated_clusters(clusters, repeat):
    return [c for c in clusters
            if any(r.get("tool") == "ours" and r.get("repeat") == repeat and r.get("subagent") is None
                   for r in c.get("reported_by", []))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--bench-dir", default=os.path.join(os.path.dirname(__file__), "..", ".."))
    a = ap.parse_args()
    bench = os.path.abspath(a.bench_dir)
    analysis_dir = os.path.join(bench, "analysis")
    adj_path = os.path.join(analysis_dir, "cbnf-adjudication.json")
    adj = json.load(open(adj_path))["adjudications"] if os.path.exists(adj_path) else {}

    rows, all_orphans = [], []
    for path in sorted(glob.glob(os.path.join(analysis_dir, "subject-*", "analysis.json"))):
        sid = int(os.path.basename(os.path.dirname(path)).split("-")[1])
        clusters = json.load(open(path))["clusters"]
        costs_path = os.path.join(os.path.dirname(path), "costs.json")
        ws_output = {}
        if os.path.exists(costs_path):
            ws_output = {c["repeat"]: c.get("ws_output") for c in json.load(open(costs_path))["cells"]
                         if c.get("tool") == "ours"}
        for repeat in (1, 2):
            run_dir = os.path.join(bench, "runs", f"{sid}__ours__r{repeat}")
            if not os.path.isdir(run_dir):
                print(f"warning: no run dir for subject {sid} repeat {repeat}", file=sys.stderr)
                continue
            sections = cbnf_sections(run_dir)
            bullets = [(f, b) for f, bs, _, _ in sections for b in bs]
            cbnf_chars = sum(s[2] for s in sections)
            report_chars = sum(s[3] for s in sections)

            cons = consolidated_clusters(clusters, repeat)
            orph = orphans(clusters, repeat)
            matched = []
            for c in orph:
                best, score = None, 0.0
                for fname, b in bullets:
                    s = overlap(c.get("summary"), b)
                    if s > score:
                        best, score = (fname, b), s
                key = f"{sid}/{repeat}/{c.get('cluster_id')}"
                verdict = adj.get(key)
                rec = {"subject": sid, "repeat": repeat, "cluster_id": c.get("cluster_id"),
                       "verdict": c.get("verdict"), "category": c.get("category"),
                       "summary": c.get("summary"), "nearest_bullet_score": round(score, 2),
                       "nearest_bullet_agent": best[0] if best else None,
                       "nearest_bullet": best[1] if best else None,
                       "promotion": verdict.get("promotion") if verdict else None,
                       "adjudication": verdict}
                matched.append(rec)
                all_orphans.append(rec)

            rows.append({
                "subject": sid, "repeat": repeat,
                "subagent_reports": len(sections),
                "reports_with_cbnf": sum(1 for s in sections if s[1]),
                "cbnf_bullets": len(bullets),
                "cbnf_chars": cbnf_chars, "report_chars": report_chars,
                "cbnf_share_of_report": round(cbnf_chars / report_chars, 4) if report_chars else None,
                # chars/4 is the usual rough token ratio for English prose; the point is the order of
                # magnitude against the run's whole output budget, not a billing figure
                "cbnf_tokens_est": round(cbnf_chars / 4),
                "run_output_tokens": ws_output.get(repeat),
                "cbnf_share_of_run_output": (round((cbnf_chars / 4) / ws_output[repeat], 4)
                                             if ws_output.get(repeat) else None),
                "consolidated_clusters": len(cons),
                "orphan_clusters": len(orph),
                "promotions": sum(1 for m in matched if m["promotion"] is True),
                "unadjudicated": sum(1 for m in matched if m["promotion"] is None),
            })

    promos = [o for o in all_orphans if o["promotion"] is True]
    pv = {}
    for o in promos:
        pv[o["verdict"]] = pv.get(o["verdict"], 0) + 1
    SUBSTANTIVE = ("TP-primary", "TP-human", "valid-other")
    totals = {
        "runs": len(rows),
        "cbnf_bullets": sum(r["cbnf_bullets"] for r in rows),
        "cbnf_bullets_per_run": round(sum(r["cbnf_bullets"] for r in rows) / len(rows), 1) if rows else None,
        "cbnf_share_of_subagent_text": round(sum(r["cbnf_chars"] for r in rows) / sum(r["report_chars"] for r in rows), 4) if rows else None,
        "cbnf_share_of_run_output": (round(sum(r["cbnf_tokens_est"] for r in rows) / sum(r["run_output_tokens"] for r in rows if r["run_output_tokens"]), 4)
                                     if any(r["run_output_tokens"] for r in rows) else None),
        "consolidated_clusters": sum(r["consolidated_clusters"] for r in rows),
        "orphan_clusters": sum(r["orphan_clusters"] for r in rows),
        "promotions": len(promos),
        "promotions_per_run": round(len(promos) / len(rows), 2) if rows else None,
        "unadjudicated": sum(r["unadjudicated"] for r in rows),
        "promotion_verdicts": pv,
        "substantive_promotions": sum(v for k, v in pv.items() if k in SUBSTANTIVE),
        "bullets_per_promotion": round(sum(r["cbnf_bullets"] for r in rows) / len(promos), 1) if promos else None,
    }

    if a.json:
        json.dump({"runs": rows, "orphans": all_orphans, "totals": totals}, sys.stdout, indent=1)
        print()
        return

    print(f"{'subj':>4} {'rep':>3} {'agents':>6} {'w/CBNF':>6} {'bullets':>7} {'CBNF%':>6} "
          f"{'cons':>5} {'cand':>4} {'promoted':>8}")
    for r in rows:
        flag = f"  ({r['unadjudicated']} UNADJUDICATED)" if r["unadjudicated"] else ""
        print(f"{r['subject']:>4} {r['repeat']:>3} {r['subagent_reports']:>6} {r['reports_with_cbnf']:>6} "
              f"{r['cbnf_bullets']:>7} {r['cbnf_share_of_report']*100:>5.1f}% {r['consolidated_clusters']:>5} "
              f"{r['orphan_clusters']:>4} {r['promotions']:>8}{flag}")

    print(f"\nCOST   {totals['cbnf_bullets']} CBNF bullets over {totals['runs']} runs "
          f"({totals['cbnf_bullets_per_run']}/run): "
          f"{totals['cbnf_share_of_subagent_text']*100:.1f}% of sub-agent report text, but only "
          f"~{totals['cbnf_share_of_run_output']*100:.1f}% of the run's output tokens")
    print(f"       the reviewer-side cost is small. The Step 5.5 orchestrator pass over all "
          f"{totals['cbnf_bullets_per_run']} bullets/run is NOT measured here and is the larger unknown.")
    print(f"YIELD  {totals['orphan_clusters']} of {totals['consolidated_clusters']} consolidated clusters had no "
          f"sub-agent flag; {totals['promotions']} adjudicated as Step 5.5 promotions "
          f"({totals['promotions_per_run']}/run, one per {totals['bullets_per_promotion']} bullets)")
    print(f"       what they were judged to be: {totals['promotion_verdicts']}")
    print(f"       substantive (TP-primary/TP-human/valid-other): {totals['substantive_promotions']}")
    if totals["unadjudicated"]:
        print(f"\n!! {totals['unadjudicated']} candidate(s) have no entry in cbnf-adjudication.json — "
              f"read them against the run's CBNF bullets and record the call before quoting these totals.")

    print("\n--- candidates ---")
    for o in sorted(all_orphans, key=lambda x: (x["promotion"] is not True, -x["nearest_bullet_score"])):
        state = "PROMOTED" if o["promotion"] is True else ("—" if o["promotion"] is False else "UNADJUDICATED")
        conf = (o["adjudication"] or {}).get("confidence", "")
        print(f"\n  s{o['subject']} r{o['repeat']} {o['cluster_id']}  [{o['verdict']}/{o['category']}]  "
              f"{state}{' (' + conf + ')' if conf else ''}   nearest bullet {o['nearest_bullet_score']:.2f}")
        print(f"    report:  {o['summary'][:150]}")
        print(f"    nearest: {(o['nearest_bullet'] or '')[:150]}")
        print(f"    from:    {o['nearest_bullet_agent']}")
        if o["adjudication"]:
            print(f"    call:    {o['adjudication']['note']}")


if __name__ == "__main__":
    main()
