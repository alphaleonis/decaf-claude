#!/usr/bin/env python3
"""Assert a subject's scoring artifacts describe the SAME finding set (nib dcc-y2e6).

Usage: check_artifacts.py <subject-dir>   # expects extract/*.json, findings.json, analysis.json

Why this exists: on v1 subject 6, `anthropic r2` had 20 findings in the extract and 33 in
findings.json with exactly 1 pair in common, while analysis.json clustered the stale set — so a
published number rested on findings the pipeline no longer contained (scrapped dcc-z13k). Nothing
detected it, because each artifact was individually well-formed.

Re-extraction must therefore never leave the three layers disagreeing. This fails the run instead.
"""
import json, sys, glob, os, argparse
from collections import defaultdict


def fid(f):
    """Stable identity for a finding across layers."""
    return (f.get("tool"), f.get("repeat"), (f.get("file") or "").strip(),
            f.get("line"), (f.get("claim") or "")[:80].strip().lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subject_dir")
    a = ap.parse_args()
    d = a.subject_dir
    errs, warns = [], []

    extract_files = sorted(glob.glob(os.path.join(d, "extract", "*.json")))
    fpath, apath = os.path.join(d, "findings.json"), os.path.join(d, "analysis.json")
    for p in (fpath, apath):
        if not os.path.exists(p):
            print(f"MISSING: {p}", file=sys.stderr); sys.exit(2)
    if not extract_files:
        print(f"MISSING: {d}/extract/*.json", file=sys.stderr); sys.exit(2)

    extracted, per_cell = [], defaultdict(int)
    for p in extract_files:
        for f in json.load(open(p)):
            extracted.append(f); per_cell[(f.get("tool"), f.get("repeat"))] += 1
    findings = json.load(open(fpath))
    A = json.load(open(apath))
    clusters = A.get("clusters", [])

    e_ids, f_ids = {fid(x) for x in extracted}, {fid(x) for x in findings}

    only_e, only_f = e_ids - f_ids, f_ids - e_ids
    if only_e:
        errs.append(f"{len(only_e)} findings in extract/ are absent from findings.json "
                    f"(e.g. {sorted(only_e)[0]})")
    if only_f:
        errs.append(f"{len(only_f)} findings in findings.json are absent from extract/ "
                    f"(e.g. {sorted(only_f)[0]}) — stale pool from an earlier extraction?")

    # Overlap ratio catches the z13k shape even when both directions are non-empty.
    if e_ids and f_ids:
        ov = len(e_ids & f_ids) / max(len(e_ids), len(f_ids))
        if ov < 0.9:
            errs.append(f"extract/ and findings.json overlap only {ov:.0%} — different finding sets")

    # Every cell present in the extract must be attributed in the clustering, and vice versa.
    cl_cells = {(r.get("tool"), r.get("repeat")) for c in clusters for r in c.get("reported_by", [])}
    ex_cells = set(per_cell)
    if ex_cells - cl_cells:
        errs.append(f"cells extracted but absent from analysis.json clusters: {sorted(ex_cells - cl_cells)}")
    if cl_cells - ex_cells:
        errs.append(f"cells clustered but absent from extract/: {sorted(cl_cells - ex_cells)}")

    # A cluster set far smaller than the finding pool usually means clustering ran on a stale file.
    if clusters and findings and len(clusters) > len(findings):
        errs.append(f"{len(clusters)} clusters from {len(findings)} findings — clustering cannot expand the pool")

    for cell, n in sorted(per_cell.items()):
        got = sum(1 for c in clusters for r in c.get("reported_by", []) if (r.get("tool"), r.get("repeat")) == cell)
        if n and got == 0:
            errs.append(f"cell {cell} extracted {n} findings but appears in no cluster")
        elif n and got / n < 0.5:
            warns.append(f"cell {cell}: {got} cluster memberships from {n} extracted findings")

    print(f"  extract/: {len(extracted)} findings across {len(extract_files)} cells")
    print(f"  findings.json: {len(findings)}   analysis.json: {len(clusters)} clusters")
    for w in warns:
        print(f"  WARN  {w}")
    if errs:
        print("\nARTIFACT INCONSISTENCY — refusing to score:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(3)
    print("  consistent")


if __name__ == "__main__":
    main()
