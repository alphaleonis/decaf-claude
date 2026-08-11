#!/usr/bin/env python3
"""Stamp `origin: bot|human` on every thread in the pooled corpus (nib dcc-qwt3).

Usage: annotate_thread_origin.py [--corpus v2/pooled] [--bot-list v2/pooled/bot-authors.json]

Applies the committed bot list (derive_bot_authors.py) to each subject's threads.json, in place.
Threads are annotated, never reordered or removed — `matches_thread` in every analysis.json is an
index into this file, so order is load-bearing.

Refuses to annotate an author the list does not classify: an unknown author defaulted to "human"
would contaminate the one axis the design treats as independent of tool output. Re-derive the list
first, then re-run this.
"""
import json, sys, argparse, pathlib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="v2/pooled")
    ap.add_argument("--bot-list", default=None)
    a = ap.parse_args()
    corpus = pathlib.Path(a.corpus)
    bl_path = pathlib.Path(a.bot_list or corpus / "bot-authors.json")

    bl = json.loads(bl_path.read_text())
    origin = {r["login"]: r["origin"] for r in bl["authors"]}

    files = sorted(corpus.glob("*/threads.json"))
    if not files:
        raise SystemExit(f"no */threads.json under {corpus} — wrong --corpus?")

    counts = {"bot": 0, "human": 0}
    for p in files:
        threads = json.loads(p.read_text())
        for i, t in enumerate(threads):
            au = t.get("author")
            if au not in origin:
                raise SystemExit(f"{p}: thread {i} author {au!r} not in {bl_path} — re-derive the "
                                 f"bot list before annotating")
            t["origin"] = origin[au]
            if t.get("admission") == "admitted":
                counts[t["origin"]] += 1
        p.write_text(json.dumps(threads, indent=2) + "\n")

    print(f"annotated {len(files)} subjects; admitted threads: "
          f"{counts['human']} human, {counts['bot']} bot")


if __name__ == "__main__":
    main()
