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

SECOND PASS OVER THE EXCLUSIONS ONLY (nib dcc-fm8s). `matchable = true` is the safe default
direction and the bulk of the work; the exclusions are the small, dangerous set, because each one
takes a thread out of every arm's denominator and on an axis of n=3 that is 33%. Measured on the
first single-pass annotation: 3 of 20 exclusions were wrong, and all three were the same shape — a
COMPOUND thread whose quoted suggestion targets code added after the checkpoint while another
sentence targets code that is present.

    THE COMPOUND-THREAD RULE: a thread is matchable if ANY claim in it targets present code.

Disagreement between the passes resolves toward MATCHABLE, and that direction is pre-registered
rather than chosen per case: including an unmatchable thread costs every arm equally and visibly
(it shows up as a thread nobody hit), while excluding a matchable one silently inflates every arm.
Both readings are recorded on the thread — `matchability_readings` — so a resolution can be audited
instead of taken on trust.
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


def second_pass_worksheet(d, threads):
    """One row per EXCLUDED thread, carrying the code but NOT the first pass's reasoning.

    Blind to the first reading on purpose: a second annotator shown "the quoted suggestion targets
    an absent block" will agree with it, and two passes that agree because one read the other are
    one pass wearing a hat.
    """
    repo = d / "repo"
    if not repo.exists():
        sys.exit(f"{repo} absent — rebuild the fixture checkout first (bench-init)")
    cache, rows = {}, []
    for i, t in enumerate(threads):
        if t.get("admission") != "admitted" or t.get("matchable_at_checkpoint") is not False:
            continue
        p = t.get("path")
        if p not in cache:
            f = repo / p if p else None
            cache[p] = f.read_text(errors="replace") if (f and f.is_file()) else None
        rows.append({"thread_index": i, "path": p, "line": t.get("line"), "body": t.get("body"),
                     "lexical_evidence": evidence(t, cache[p]),
                     "compound_thread_rule": "matchable if ANY claim in the thread targets code "
                                             "present at the checkpoint",
                     "matchable_at_checkpoint": "review", "reason": ""})
    out = d / "grading" / "matchability-second-pass-worksheet.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, indent=1))
    print(f"wrote {out} — {len(rows)} excluded threads to re-read")
    return rows


def apply_second_pass(d, threads, verdicts, date):
    excluded = [i for i, t in enumerate(threads)
                if t.get("admission") == "admitted" and t.get("matchable_at_checkpoint") is False]
    byidx = {x["thread_index"]: x for x in verdicts}
    missing = [i for i in excluded if i not in byidx]
    unresolved = [i for i, x in byidx.items() if x.get("matchable_at_checkpoint") not in VALID]
    if missing:
        sys.exit(f"REFUSING: {len(missing)} excluded thread(s) absent from the second pass: {missing}")
    if unresolved:
        sys.exit(f"REFUSING: {len(unresolved)} thread(s) still \"review\": {sorted(unresolved)}")
    flipped = []
    for i in excluded:
        t, x = threads[i], byidx[i]
        readings = t.get("matchability_readings") or [
            {"pass": 1, "verdict": False, "reason": t.get("matchable_reason", "")}]
        readings = [r for r in readings if r.get("pass") != 2]
        readings.append({"pass": 2, "date": date, "verdict": x["matchable_at_checkpoint"],
                         "reason": x.get("reason", "")})
        t["matchability_readings"] = readings
        if x["matchable_at_checkpoint"] is True:
            # Pre-registered direction: disagreement resolves toward matchable.
            t["matchable_at_checkpoint"] = True
            t["matchable_reason"] = x.get("reason", "")
            t["matchability_resolution"] = ("passes disagreed; resolved toward matchable "
                                            "(dcc-fm8s). Both readings above.")
            flipped.append(i)
        else:
            t["matchability_resolution"] = "both passes agree: unmatchable"
    (d / "threads.json").write_text(json.dumps(threads, indent=1))
    print(f"{d.name}: {len(excluded)} exclusion(s) second-read, {len(flipped)} flipped to "
          f"matchable {flipped}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subject_dir")
    ap.add_argument("--worksheet", action="store_true")
    ap.add_argument("--apply", metavar="VERDICTS_JSON")
    ap.add_argument("--second-pass-worksheet", action="store_true",
                    help="build the blind re-read worksheet for the EXCLUSIONS only (dcc-fm8s)")
    ap.add_argument("--second-pass", metavar="VERDICTS_JSON",
                    help="apply the second reading; disagreement resolves toward matchable")
    ap.add_argument("--date", default=None, help="date to stamp on the second reading")
    a = ap.parse_args()
    modes = [bool(a.worksheet), bool(a.apply), bool(a.second_pass_worksheet), bool(a.second_pass)]
    if sum(modes) != 1:
        sys.exit("choose exactly one of --worksheet / --apply / --second-pass-worksheet / --second-pass")

    d = pathlib.Path(a.subject_dir)
    threads = json.loads((d / "threads.json").read_text())
    admitted = [i for i, t in enumerate(threads) if t.get("admission") == "admitted"]
    if not admitted:
        sys.exit(f"{d.name}: no admitted threads")

    if a.second_pass_worksheet:
        second_pass_worksheet(d, threads)
        return
    if a.second_pass:
        if not a.date:
            sys.exit("--second-pass needs --date: a reading without a date cannot be placed in the "
                     "annotation history")
        apply_second_pass(d, threads, json.loads(pathlib.Path(a.second_pass).read_text()), a.date)
        return

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
