#!/usr/bin/env python3
"""Stamp `matchable_at_checkpoint` on every ADMITTED thread in the pooled corpus (nib dcc-hw48).

Usage:
  annotate_thread_matchability.py <subject-dir> --worksheet          # build the judgment worksheet
  annotate_thread_matchability.py <subject-dir> --apply <verdicts>   # stamp threads.json

Admission tests line POSITION only ("line inside a changed hunk at the checkpoint"). It never asks
whether the code a thread DISCUSSES exists there. On PostHog-posthog-55149, 34 of 35 admitted threads
were written after the checkpoint against 12 different commits, and the blind grader independently
reported 10 of them as discussing code introduced later — a clamp "regressed in 6effa89f", a CodeQL
fix already applied, a test added two pushes on. A reviewer at the checkpoint cannot raise those, so
they inflate the recall denominator and deflate every arm equally, which is invisible in the result.

The test is PRESENCE, not date. A thread written weeks later about code that already existed is
perfectly matchable: T43 on that subject postdates the checkpoint by eleven days and its defect was
found by 6 of 7 cells. Anything keyed on `created_at` would wrongly exclude it.

WHY THIS IS A JUDGMENT PASS AND NOT A HEURISTIC. The obvious mechanical rule — look up the tokens a
thread quotes in the thread's own file at the checkpoint — was implemented and probed against this
subject's graded pool. It failed in both directions: it called T9, T32 and T36 unmatchable although
the pool credited all three, and T38 unmatchable although its duplicate was credited, while catching
only 2 of the 10 threads the grader identified. Threads quote error strings from earlier drafts, name
symbols that live in other files, and describe behavior without quoting anything at all. Token
presence measures the wrong thing, so it is retained here as EVIDENCE for a reader and never as a
verdict.

The fixture is a checkpoint-only checkout with no remote, so `against_commit` cannot be resolved and
an ancestor test is impossible offline. A body citing some OTHER commit is recorded as a signal, not a
verdict, because "regressed in <sha>" and "same bug as <sha>" read identically to a regex.

`--apply` refuses any verdict set that is incomplete or that contains "review": a thread whose
matchability is unresolved must not silently rejoin the denominator this script exists to correct.
"""
import json, re, argparse, pathlib, sys

TOKEN = re.compile(r"`([^`\n]{2,80})`|\"([^\"\n]{3,80})\"|'([^'\n]{3,80})'")
SHA = re.compile(r"\b(?:in|from|since|by|after|commit)\s+([0-9a-f]{7,40})\b", re.I)
CODEISH = re.compile(r"[_.(){}\[\]:=<>/]|[a-z][A-Z]")
VALID = (True, False)


def evidence(thread, file_text):
    body = thread.get("body") or ""
    toks = []
    for m in TOKEN.finditer(body):
        t = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        if len(t) >= 3 and CODEISH.search(t):
            toks.append(t)
    seen, uniq = set(), []
    for t in toks:
        if t not in seen:
            seen.add(t); uniq.append(t)
    if file_text is None:
        return {"file_readable_at_checkpoint": False, "quoted_tokens": uniq,
                "cites_other_commit": SHA.findall(body)}
    return {"file_readable_at_checkpoint": True,
            "quoted_tokens_present": [t for t in uniq if t in file_text],
            "quoted_tokens_absent": [t for t in uniq if t not in file_text],
            "cites_other_commit": SHA.findall(body)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subject_dir")
    ap.add_argument("--worksheet", action="store_true")
    ap.add_argument("--apply", metavar="VERDICTS_JSON")
    a = ap.parse_args()
    if bool(a.worksheet) == bool(a.apply):
        sys.exit("choose exactly one of --worksheet / --apply")

    d = pathlib.Path(a.subject_dir)
    threads = json.loads((d / "threads.json").read_text())
    admitted = [i for i, t in enumerate(threads) if t.get("admission") == "admitted"]
    if not admitted:
        sys.exit(f"{d.name}: no admitted threads")

    if a.worksheet:
        repo = d / "repo"
        if not repo.exists():
            sys.exit(f"{repo} absent — rebuild the fixture checkout first (bench-init)")
        cache, rows = {}, []
        for i in admitted:
            t = threads[i]
            p = t.get("path")
            if p not in cache:
                f = repo / p if p else None
                cache[p] = f.read_text(errors="replace") if (f and f.is_file()) else None
            rows.append({"thread_index": i, "path": p, "line": t.get("line"),
                         "body": t.get("body"), "lexical_evidence": evidence(t, cache[p]),
                         "matchable_at_checkpoint": "review"})
        out = d / "grading" / "matchability-worksheet.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(rows, indent=1))
        # `origin` is deliberately absent from the worksheet: matchability is a property of the code,
        # and a reader who knows a thread is bot-authored may weigh it differently.
        print(f"wrote {out} — {len(rows)} admitted threads, all \"review\"")
        print("Resolve every entry to true/false, then re-run with --apply.")
        return

    v = json.loads(pathlib.Path(a.apply).read_text())
    byidx = {x["thread_index"]: x for x in v}
    missing = [i for i in admitted if i not in byidx]
    unresolved = [i for i, x in byidx.items() if x.get("matchable_at_checkpoint") not in VALID]
    if missing:
        sys.exit(f"REFUSING: {len(missing)} admitted thread(s) absent from the verdict set: {missing}")
    if unresolved:
        sys.exit(f"REFUSING: {len(unresolved)} thread(s) still \"review\": {sorted(unresolved)}. "
                 f"An unresolved thread must not rejoin the denominator by default.")
    n_false = 0
    for i in admitted:
        x = byidx[i]
        threads[i]["matchable_at_checkpoint"] = x["matchable_at_checkpoint"]
        threads[i]["matchable_reason"] = x.get("reason", "")
        n_false += (x["matchable_at_checkpoint"] is False)
    (d / "threads.json").write_text(json.dumps(threads, indent=1))
    print(f"{d.name}: stamped {len(admitted)} admitted threads — "
          f"{len(admitted)-n_false} matchable, {n_false} unmatchable")


if __name__ == "__main__":
    main()
