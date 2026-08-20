#!/usr/bin/env python3
"""Stamp `thread_group` on admitted threads so one defect is one ground-truth item (nib dcc-qfr5).

Usage: annotate_thread_groups.py <subject-dir> --apply <thread-groups.json>

Several defects are raised twice on a review-disciplined PR: a scanner comments within days, a human
reviewer arrives later, both at the same line. Scoring credits one `matches_thread` per cluster, so
the other thread reads as missed — and because the axes are split by origin, a bot/human pair moves
credit off the human axis (`thread_recall`) and onto the incumbent axis (`incumbent_agreement`).
Measured on PostHog-posthog-55149: three human threads read as missed although two of their defects
were found by all four arms.

Grouping is a judgment: two threads belong together when one fix resolves both. It is made by a pass
that reads the code and is blind to the pool, because grouping threads by whether tools found them
would decide the answer from the measurement.

Refuses a grouping that does not cover every admitted thread exactly once. A thread silently missing
from the map would fall back to its own group and quietly restore the defect this corrects.
"""
import json, argparse, pathlib, sys
from collections import Counter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subject_dir")
    ap.add_argument("--apply", required=True, metavar="THREAD_GROUPS_JSON")
    a = ap.parse_args()

    d = pathlib.Path(a.subject_dir)
    threads = json.loads((d / "threads.json").read_text())
    groups = json.loads(pathlib.Path(a.apply).read_text())
    admitted = [i for i, t in enumerate(threads) if t.get("admission") == "admitted"]

    seen = [i for g in groups for i in g["thread_indices"]]
    dupes = [i for i, n in Counter(seen).items() if n > 1]
    if dupes:
        sys.exit(f"REFUSING: thread(s) in more than one group: {sorted(dupes)}")
    if set(seen) != set(admitted):
        missing, extra = sorted(set(admitted) - set(seen)), sorted(set(seen) - set(admitted))
        sys.exit(f"REFUSING: grouping does not cover the admitted set exactly — "
                 f"missing {missing}, not-admitted {extra}")
    ids = [g["group_id"] for g in groups]
    if len(set(ids)) != len(ids):
        sys.exit("REFUSING: duplicate group_id values")

    multi = 0
    for g in groups:
        for i in g["thread_indices"]:
            threads[i]["thread_group"] = g["group_id"]
            threads[i]["thread_group_defect"] = g.get("defect", "")
        multi += len(g["thread_indices"]) > 1
    (d / "threads.json").write_text(json.dumps(threads, indent=1))
    print(f"{d.name}: {len(groups)} groups over {len(admitted)} admitted threads "
          f"({multi} multi-thread)")
    for g in groups:
        if len(g["thread_indices"]) > 1:
            origins = [threads[i].get("origin", "?") for i in g["thread_indices"]]
            print(f"  {g['group_id']}: {g['thread_indices']} [{', '.join(origins)}] — {g.get('defect','')[:90]}")


if __name__ == "__main__":
    main()
