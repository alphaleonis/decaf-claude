#!/usr/bin/env python3
"""Build a pooled-adjudication fixture + admitted thread set for one subject (nib dcc-ixyy).

Usage: build_pooled_fixture.py <owner> <repo> <pr> <type> <size> [--out DIR]

Implements METHODOLOGY-v2 §4a-§4b for a POOLED subject (no answer key), plus the thread
admission that makes review threads a scored target.

Checkpoint rule: the commit the EARLIEST review comment was written against — the state at which
human review began, so tools and humans review the same starting state. Threads are dispersed across
many commits (measured: 4-15 per PR), so admission is applied mechanically per thread rather than by
assuming a single commit holds them all: a thread is admissible if its flagged file appears in the
checkpoint diff AND its line falls inside a changed hunk.

AUDITOR tool: uses the real `gh` deliberately. Never run inside a review cell.
"""
import json, subprocess, sys, re, pathlib, argparse


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"gh failed: {' '.join(args)}\n{r.stderr[:400]}")
    return r.stdout


def graphql(query):
    out = gh("api", "graphql", "-f", f"query={query}")
    d = json.loads(out)
    if "errors" in d:
        raise SystemExit(f"graphql errors: {d['errors']}")
    return d


def changed_line_ranges(patch):
    """New-file line ranges touched by a unified diff patch."""
    ranges = []
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", patch or "", re.M):
        start = int(m.group(1))
        count = int(m.group(2) or 1)
        ranges.append((start, start + max(count, 1) - 1))
    return ranges


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("owner"); ap.add_argument("repo"); ap.add_argument("pr", type=int)
    ap.add_argument("type"); ap.add_argument("size")
    ap.add_argument("--out", default=None)
    ap.add_argument("--null", action="store_true",
                    help="Build a NULL subject: checkpoint at the MERGE commit, not the first-review "
                         "commit. A scored subject is checkpointed pre-review so the thread-flagged "
                         "issues are still present and findable — which is exactly what would make it "
                         "non-null. The null arm needs the post-review state that shipped and has no "
                         "known defect since.")
    a = ap.parse_args()
    slug = f"{a.owner}/{a.repo}"

    q = f"""
    {{ repository(owner:"{a.owner}", name:"{a.repo}") {{ pullRequest(number:{a.pr}) {{
      title createdAt mergedAt baseRefName additions deletions changedFiles
      reviewThreads(first:100) {{ nodes {{
        path line originalLine isResolved isOutdated
        comments(first:3) {{ nodes {{ createdAt author{{login __typename}} originalCommit{{oid}} bodyText }} }}
      }} }} }} }} }}"""
    pr = graphql(q)["data"]["repository"]["pullRequest"]

    threads = []
    for n in pr["reviewThreads"]["nodes"]:
        c = (n.get("comments") or {}).get("nodes") or []
        if not c:
            continue
        first = c[0]
        # Origin splits the thread axis (dcc-qwt3): 28% of the first corpus's admitted threads were
        # written by competing review tools, and none of their logins contains "bot" — the GraphQL
        # actor __typename is the mechanical signal a name regex is not. Scored as a SEPARATE axis
        # (agreement with incumbent automated review), never pooled with the human one.
        # A deleted author has no typename and gets origin null, which score_pooled refuses on an
        # admitted thread — classify it by hand rather than let it default into either axis.
        # Audit the stamped values per corpus with derive_bot_authors.py.
        atype = (first.get("author") or {}).get("__typename")
        threads.append({
            "path": n.get("path"),
            "line": n.get("originalLine") or n.get("line"),
            "is_resolved": n.get("isResolved"),
            "is_outdated": n.get("isOutdated"),
            "author": (first.get("author") or {}).get("login"),
            "author_type": atype,
            "origin": None if atype is None else ("bot" if atype == "Bot" else "human"),
            "created_at": first.get("createdAt"),
            "against_commit": (first.get("originalCommit") or {}).get("oid"),
            "body": (first.get("bodyText") or "").strip(),
        })
    if not threads:
        raise SystemExit(f"{slug}#{a.pr}: no review threads")

    if a.null:
        mc = graphql(f'{{ repository(owner:"{a.owner}", name:"{a.repo}") {{ pullRequest(number:{a.pr}) '
                     f'{{ mergeCommit{{oid}} }} }} }}')["data"]["repository"]["pullRequest"]
        checkpoint = mc["mergeCommit"]["oid"]
        cp_date = pr["mergedAt"]
        # Threads are recorded for provenance but never scored on a null subject: whatever they
        # raised was resolved before this checkpoint, which is the point of using the merged state.
        for th in threads:
            th["admission"] = "not-scored"
            th["admission_reason"] = "null subject — checkpoint is the merged state, after review"
    else:
        # Checkpoint: the commit the earliest review comment was written against.
        dated = sorted([t for t in threads if t["against_commit"]], key=lambda t: t["created_at"])
        checkpoint = dated[0]["against_commit"]
        cp_date = dated[0]["created_at"]

    if a.null:
        # The merge commit is already ON the base branch, so comparing baseRef...merge yields an
        # EMPTY diff — observed 0 files on all three null fixtures. The reviewable change is what the
        # merge introduced: first parent (base branch before the merge) to the merge commit.
        parents = json.loads(gh("api", f"repos/{slug}/commits/{checkpoint}")).get("parents", [])
        if not parents:
            raise SystemExit(f"{slug}#{a.pr}: merge commit has no parents")
        base = parents[0]["sha"]
    else:
        cmp_ = json.loads(gh("api", f"repos/{slug}/compare/{pr['baseRefName']}...{checkpoint}"))
        base = cmp_["merge_base_commit"]["sha"]

    diff = json.loads(gh("api", f"repos/{slug}/compare/{base}...{checkpoint}"))
    files = {f["filename"]: changed_line_ranges(f.get("patch", "")) for f in diff.get("files", [])}
    add = sum(f.get("additions", 0) for f in diff.get("files", []))
    dele = sum(f.get("deletions", 0) for f in diff.get("files", []))

    # Mechanical admission (METHODOLOGY-v2 §4b): file in the checkpoint diff, line inside a changed hunk.
    for t in ([] if a.null else threads):
        if t["path"] not in files:
            t["admission"] = "rejected"; t["admission_reason"] = "file absent from the checkpoint diff"
        elif t["line"] is None:
            t["admission"] = "needs-review"; t["admission_reason"] = "no line anchor; adjudicate by hand"
        elif any(lo <= t["line"] <= hi for lo, hi in files[t["path"]]):
            t["admission"] = "admitted"; t["admission_reason"] = "line inside a changed hunk at the checkpoint"
        else:
            t["admission"] = "rejected"; t["admission_reason"] = "line outside every changed hunk at the checkpoint"

    counts = {}
    for t in threads:
        counts[t["admission"]] = counts.get(t["admission"], 0) + 1

    out = pathlib.Path(a.out or f"v2/pooled/{a.owner}-{a.repo}-{a.pr}")
    out.mkdir(parents=True, exist_ok=True)
    fixture = {
        "slug": f"{slug}#{a.pr}", "repo": slug, "pr": a.pr,
        "title": pr["title"], "app_type": a.type, "size": a.size,
        "instrument": "null-arm" if a.null else "pooled-adjudication",
        "checkpoint": {
            "sha": checkpoint, "base": base, "base_ref": pr["baseRefName"],
            "date": cp_date,
            "selection": ("merge commit — post-review state that shipped with no known defect"
                          if a.null else "commit the earliest review comment was written against"),
            "diff_stat": {"files": len(files), "additions": add, "deletions": dele},
        },
        "merged_at": pr["mergedAt"], "pr_created_at": pr["createdAt"],
        "vintage": {"merged": (pr["mergedAt"] or "")[:10],
                    "note": "status is computed per model at analysis time; see METHODOLOGY-v2 section 5"},
        "threads": {"total": len(threads), **counts},
    }
    (out / "fixture.json").write_text(json.dumps(fixture, indent=2) + "\n")
    (out / "threads.json").write_text(json.dumps(threads, indent=2) + "\n")
    print(f"  {slug}#{a.pr:<7} {a.type}/{a.size:<2} cp={checkpoint[:9]} "
          f"diff={len(files)}f +{add}/-{dele}  threads: {counts.get('admitted',0)} admitted, "
          f"{counts.get('rejected',0)} rejected, {counts.get('needs-review',0)} by-hand  -> {out}")


if __name__ == "__main__":
    main()
