#!/usr/bin/env python3
"""Backfill an inline cluster_id into a subject's findings.json from its cluster-assign.json.

Most subjects carry their reference clustering inline on each finding. A few instead recorded it
in a separate cluster-assign.json keyed by the composite finding_id the per-run extracts use
(`<tool>__r<N>__<i>`), while their findings.json was rebuilt with positional `f00NN` ids — so the
two do not join. cluster_replay.py only picks up subjects carrying an inline cluster_id, which
makes those subjects invisible to it.

The bridge is extract/<tool>__r<N>.json: it carries the composite id AND sits in the same order as
findings.json. That order is the whole basis of the re-key, so it is verified position by position
on file+line, and a run whose order disagrees anywhere is skipped entirely rather than guessed at.

Writes cluster_id plus cluster_id_source for audit. Dry-run unless --write.

Usage: backfill_cluster_ids.py <subject-dir> [--write]
"""
import json, os, re, sys

SOURCE = "cluster-assign.json@extract-order"
RUN = re.compile(r"^(?P<tool>.+)__r(?P<repeat>\d+)\.json$")


def load_list(path):
    d = json.load(open(path))
    return d if isinstance(d, list) else d.get("findings", d)


def main(subject, write):
    findings_path = os.path.join(subject, "findings.json")
    F = load_list(findings_path)
    assign = json.load(open(os.path.join(subject, "cluster-assign.json")))["assign"]
    known = {c["cluster_id"] for c in json.load(open(os.path.join(subject, "analysis.json")))["clusters"]}

    unknown = sorted(set(assign.values()) - known)
    if unknown:
        sys.exit(f"cluster-assign.json references {len(unknown)} cluster_id(s) absent from "
                 f"analysis.json: {unknown[:5]} — refusing to write an unjoinable reference")

    by_run = {}
    for x in F:
        by_run.setdefault((x["tool"], x["repeat"]), []).append(x)

    assigned = skipped = 0
    print(f"{'run':32} {'extract':>8} {'findings':>9} {'verified':>9} {'assigned':>9}  note")
    for name in sorted(os.listdir(os.path.join(subject, "extract"))):
        m = RUN.match(name)
        if not m:
            continue
        tool, repeat = m["tool"], int(m["repeat"])
        E = load_list(os.path.join(subject, "extract", name))
        S = by_run.get((tool, repeat), [])
        overlap = min(len(E), len(S))

        bad = [i for i in range(overlap)
               if (E[i].get("file"), E[i].get("line")) != (S[i].get("file"), S[i].get("line"))]
        note = ""
        if bad:
            skipped += 1
            note = f"SKIPPED — order disagrees at {len(bad)} position(s), first at {bad[0] + 1}"
            n = 0
        else:
            n = 0
            for i in range(overlap):
                cid = assign.get(E[i]["finding_id"])
                if cid:
                    S[i]["cluster_id"] = cid
                    S[i]["cluster_id_source"] = SOURCE
                    n += 1
            assigned += n
            if len(S) > overlap:
                note = f"{len(S) - overlap} finding(s) beyond the extract left unassigned"
            elif n < overlap:
                note = f"{overlap - n} finding(s) absent from the assign map"

        print(f"{tool + '/r' + str(repeat):32} {len(E):>8} {len(S):>9} {overlap - len(bad):>9} {n:>9}  {note}")

    covered = sum(1 for x in F if x.get("cluster_id"))
    print(f"\n{assigned} assigned, {covered}/{len(F)} findings now carry a cluster_id, {skipped} run(s) skipped")
    if write:
        json.dump(F, open(findings_path, "w"), indent=1)
        print(f"wrote {findings_path}")
    else:
        print("dry run — pass --write to apply")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--write"]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    main(args[0].rstrip("/"), "--write" in sys.argv[1:])
