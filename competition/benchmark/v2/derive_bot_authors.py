#!/usr/bin/env python3
"""Derive the thread-author bot list for the pooled corpus (nib dcc-qwt3).

Usage: derive_bot_authors.py [--corpus v2/pooled] [--out v2/pooled/bot-authors.json]

Queries GitHub for the __typename of every review-thread author across the corpus and writes an
explicit, committed bot list. The GraphQL actor type is the mechanical signal: an app-posted comment
has __typename `Bot` even when its login contains no "bot" substring — which is why the name regex in
find_candidates.sh matched none of the nine bot logins in this corpus (THREAD-AXIS.md). The REST
`users/<login>` endpoint is NOT usable for this: it resolves same-named orgs (`coderabbitai` ->
Organization) or nothing at all (`github-code-quality` -> 404), while GraphQL types the actual actor.

Re-run against any corpus; the committed output is the audit record, never hand-maintained lore.
Every author in the committed threads.json files must be classified or this exits non-zero — an
author the API no longer returns (deleted thread, renamed account) is a defect to resolve by hand,
not a silent default to "human". Hand resolutions go in the output file's `manual` section — a
mapping login -> {github_type, reason} that re-runs read back and preserve, so an audited exception
survives re-derivation while any NEW unresolved author still fails loud. First use: the app
`hex-security-app` was renamed `parameter-app` after the fixtures were built; its two committed
threads sit at the exact path:line of the live parameter-app/Bot threads on PostHog#55149.

AUDITOR tool: uses the real `gh` deliberately. Never run inside a review cell.
"""
import json, subprocess, sys, argparse, pathlib
from collections import defaultdict


def graphql(query):
    r = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"gh failed:\n{r.stderr[:400]}")
    d = json.loads(r.stdout)
    if "errors" in d:
        raise SystemExit(f"graphql errors: {d['errors']}")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="v2/pooled")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    corpus = pathlib.Path(a.corpus)
    out_path = pathlib.Path(a.out or corpus / "bot-authors.json")

    fixtures = sorted(corpus.glob("*/fixture.json"))
    if not fixtures:
        raise SystemExit(f"no */fixture.json under {corpus} — wrong --corpus?")

    manual = {}
    if out_path.exists():
        manual = json.loads(out_path.read_text()).get("manual") or {}

    authors = defaultdict(lambda: {"github_type": None, "threads": 0, "subjects": set()})
    unresolved = []

    for fx in fixtures:
        f = json.loads(fx.read_text())
        owner, repo = f["repo"].split("/")
        q = (f'{{ repository(owner:"{owner}", name:"{repo}") {{ pullRequest(number:{f["pr"]}) {{'
             f' reviewThreads(first:100) {{ nodes {{'
             f' comments(first:1) {{ nodes {{ author {{ login __typename }} }} }} }} }} }} }} }}')
        nodes = graphql(q)["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
        live = {}
        for n in nodes:
            c = (n.get("comments") or {}).get("nodes") or []
            au = c[0].get("author") if c else None
            if au and au.get("login"):
                live[au["login"]] = au["__typename"]

        # The committed threads.json is the ground the list must cover — not just what is live now.
        committed = [t["author"] for t in json.loads((fx.parent / "threads.json").read_text())
                     if t.get("author")]
        for login in sorted(set(committed)):
            rec = authors[login]
            rec["threads"] += committed.count(login)
            rec["subjects"].add(f["slug"])
            if login in live:
                rec["github_type"] = live[login]
            elif login in manual:
                rec["github_type"] = manual[login]["github_type"]
            elif rec["github_type"] is None:
                unresolved.append((f["slug"], login))

    if unresolved:
        # Distinguish "the API says human" from "the API said nothing": an author the live query no
        # longer returns cannot be typed, and defaulting it would contaminate whichever axis it lands
        # in. Resolve by hand and record it in the output's `manual` section with the evidence.
        for slug, login in unresolved:
            print(f"UNRESOLVED: {login!r} in committed threads of {slug} but absent from the live "
                  f"query and from `manual` — classify by hand", file=sys.stderr)
        sys.exit(3)

    rows = [{"login": k, "github_type": v["github_type"],
             "origin": "bot" if v["github_type"] == "Bot" else "human",
             "threads": v["threads"], "subjects": sorted(v["subjects"]),
             **({"manual": True} if k in manual else {})}
            for k, v in sorted(authors.items())]
    out = {
        "method": "GraphQL reviewThreads author __typename per subject; origin=bot iff type is Bot. "
                  "Re-derive with derive_bot_authors.py; do not hand-edit `authors` — hand-audited "
                  "exceptions go in `manual` and are preserved across re-runs.",
        "corpus": [json.loads(fx.read_text())["slug"] for fx in fixtures],
        "bots": [r["login"] for r in rows if r["origin"] == "bot"],
        "manual": manual,
        "authors": rows,
    }
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    nb = len(out["bots"])
    print(f"{len(rows)} distinct thread authors across {len(fixtures)} subjects: "
          f"{nb} bot, {len(rows) - nb} human -> {out_path}")


if __name__ == "__main__":
    main()
