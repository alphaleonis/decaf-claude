#!/usr/bin/env python3
"""Deterministic scoring for a v2 pooled-adjudication subject (nib dcc-y2e6).

Usage: score_pooled.py <analysis.json> [--threads threads.json] [--key answer-key.json] [-o out.json]

All arithmetic lives here, never in the LLM. The LLM stages produce `analysis.json` (extraction,
clustering, blind grading); this turns it into numbers.

Three axes, deliberately never merged into one "recall" (METHODOLOGY-v2 section 2):

  pooled    — precision, trivia ratio, unique real findings, noise per cell. Scored against the
              union of what the tools said, so it CANNOT see what everything missed.
  threads   — recall against admitted HUMAN review threads. The miss detector: an independent
              statement that something was worth raising. Human-only by construction (dcc-qwt3):
              every admitted thread must carry origin human|bot, and hits on bot threads score a
              separate `incumbent_agreement` axis — agreement with incumbent automated review —
              never pooled with this one. Agreement with expert review is related to, but not the
              same as, finding real bugs.
  anchor    — recall against an answer key, when the subject has one. Only for anchor subjects.

Exits non-zero on a data defect rather than emitting a null metric. Two specific failures are
guarded because both already produced published numbers that were wrong:
  - a field that is empty for an entire tool (scrapped dcc-3v3m: severities captured on 2 of 78
    entries, and one stray sub-agent `critical` handed a tool a free 1.00 on n=1)
  - artifacts describing different finding sets (scrapped dcc-z13k: 20 findings in the extract, 33
    in findings.json, 1 in common, and analysis.json clustering the stale set)
"""
import json, sys, argparse, os, glob
from collections import defaultdict
import vintage

# Verdicts. `matches-thread` and `matches-key` are v1's TP-human / TP-primary, renamed so nothing
# presupposes a key — pooled subjects have none.
REAL = {"matches-key", "matches-thread", "valid-other"}   # substantive: counts toward precision
MINOR = {"valid-minor"}                                    # correct but small
NOISE = {"trivia"}                                         # attention cost, not an error
WRONG = {"false-positive"}
ALL_VERDICTS = REAL | MINOR | NOISE | WRONG

SEV_WEIGHT = {"critical": 5.0, "high": 4.0, "medium": 2.0, "low": 1.0, "nit": 0.5, "info": 0.25}

# What KIND of thing a finding is, orthogonal to how substantial it is (dcc-opdr). The verdict axis
# grades substance — a wrong-results defect and a naming suggestion both land in `valid-other`, and
# on one subject all ten human threads scored `matches-thread` whether they were the single
# correctness question or one of nine style preferences. This axis separates them.
#
# A CLOSED set, deliberately. v1 carried a free-text cluster `category` and accumulated `bug`,
# `logic` and `correctness` as three labels for one thing, which nothing could aggregate.
FINDING_CLASSES = {"defect", "risk", "test-gap", "docs", "design", "style"}

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

# A human axis of 1-2 threads yields recall quantized to 0/0.5/1.0 — reportable per subject with n
# shown, never poolable. Four of the seven citable subjects sit at or under this (dcc-qwt3).
THIN_HUMAN_AXIS_MAX = 2

# A `matches-thread` verdict must quote the span of the thread it matched (dcc-on93). Same principle
# as `code_citation` on a real verdict: a claim that cannot point at its evidence is not evidence.
#
# The check this enables is the one `credited_to_unmatchable_thread` cannot make. That cross-check
# only fires when the thread is UNMATCHABLE; a loose match onto a perfectly matchable thread inflates
# thread_recall with nothing to detect it. Three of the four contradictions found on its first run
# (e15, ma11, c108) were that shape and were visible only by the accident of the thread also being
# unmatchable.
#
# 12 characters, or the whole body when the body is shorter — real threads in this corpus go down to
# "Bool?" (5 chars), and a floor that cannot be met by quoting everything is a floor that refuses
# valid evidence.
MIN_QUOTE_CHARS = 12


def normalize_quote(text):
    """Whitespace-collapsed, case-folded. A grader re-typing a span across a line wrap has still
    quoted it; a grader inventing one has not, and no amount of normalization rescues that."""
    return " ".join((text or "").split()).casefold()


class DataDefect(Exception):
    """A pipeline defect, not a result. Never degrade to a null metric."""


def quote_errors(cid, cluster, threads):
    """Errors for a `matches-thread` cluster's `matched_thread_quote` (dcc-on93).

    Presence is checked here, but so is CORRESPONDENCE: the quote has to actually occur in the body
    of the thread the cluster claims to match. A fabricated or misattributed quote is exactly the
    failure mode the field exists to expose, so accepting any string would leave the guard cosmetic.
    """
    q = cluster.get("matched_thread_quote")
    if not (isinstance(q, str) and q.strip()):
        return [f"{cid}: verdict matches-thread without matched_thread_quote — a match that cannot "
                f"quote the thread it matched is not auditable"]
    mt = cluster.get("matches_thread")
    if mt is None or threads is None or not (0 <= mt < len(threads)):
        return []          # index problems are reported by their own checks; don't double-report
    body = normalize_quote((threads[mt] or {}).get("body"))
    nq = normalize_quote(q)
    if nq not in body:
        return [f"{cid}: matched_thread_quote does not appear in T{mt}'s body: {q[:60]!r}"]
    if len(nq) < MIN_QUOTE_CHARS and nq != body:
        return [f"{cid}: matched_thread_quote is {len(nq)} chars — under {MIN_QUOTE_CHARS}, and not "
                f"the whole of T{mt}'s body. Quote the span the cluster corresponds to."]
    return []


def admission_errors(cid, cluster, threads):
    """A `matches-thread` credited to a thread that was never admitted (dcc-on93).

    The grader is shown ADMITTED threads only, so this index cannot be a legitimate match — it is a
    stale absolute index, a hallucinated one, or a thread the assembler leaked into the input. It was
    silent until now in both directions: recall groups only admitted threads, so the credit buys the
    tool nothing there, while `precision` still counts the cluster as REAL on the strength of a match
    that does not exist. Found on four clusters across two already-scored subjects the first time it
    ran (efcore e01/e13/e32 -> T10, mattermost ma36 -> T3).
    """
    mt = cluster.get("matches_thread")
    if mt is None or threads is None or not (0 <= mt < len(threads)):
        return []
    adm = (threads[mt] or {}).get("admission")
    if adm == "admitted":
        return []
    return [f"{cid}: matches-thread credited to T{mt}, which is {adm!r}, not admitted — the grader "
            f"is shown admitted threads only, so this index cannot name a legitimate match"]


def validate(A, threads, key, allow_silent_cells=False):
    errs = []
    clusters = A.get("clusters") or []
    cells = A.get("cells") or []
    if not clusters:
        errs.append("no clusters — extraction or clustering produced nothing")
    if not cells:
        errs.append("no cells — costs/telemetry missing")

    if not A.get("judge_model"):
        errs.append("judge_model absent: results are not attributable to a grader")

    # Vintage is load-bearing for how a result may be reported (METHODOLOGY-v2 section 5), so a
    # subject that cannot be classified must say so rather than emit an unqualified number.
    if not A.get("merged_at"):
        errs.append("merged_at absent: vintage cannot be computed, so the result cannot be shown "
                    "to be safe to pool — copy it from the subject's fixture.json")
    elif A.get("judge_model") and vintage.classify(A["merged_at"], A["judge_model"]) == vintage.UNKNOWN:
        errs.append(f"no published training cutoff for judge_model {A['judge_model']!r}: add it to "
                    f"scoring/vintage.py MODEL_CUTOFFS before scoring against this judge")
    # Required on the same footing as merged_at (dcc-60qk). Absent, the conservative key reports
    # "unknown", and a reader cannot tell that from "the two keys agree" — which is the whole
    # difference between a disclosed assumption and a hidden one.
    if not A.get("pr_created_at"):
        errs.append("pr_created_at absent: the conservative vintage key cannot be evaluated, so the "
                    "figure cannot say whether it rests on the permissive reading — copy it from "
                    "the subject's fixture.json")

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
        if v == "matches-thread":
            errs.extend(quote_errors(cid, c, threads))
            errs.extend(admission_errors(cid, c, threads))
        if c.get("matches_thread") is not None and threads is None:
            errs.append(f"{cid}: matches_thread set but no threads.json supplied")
        # Symmetric with matches-thread. Without this a `matches-key` cluster carrying no
        # `matches_key` is silently dropped by krecall's None filter and contributes 0 to anchor
        # recall, which is indistinguishable from the tool having missed the entry.
        if v == "matches-key" and c.get("matches_key") is None:
            errs.append(f"{cid}: verdict matches-key but no matches_key index")
        if c.get("matches_key") is not None and not key:
            errs.append(f"{cid}: matches_key set but no answer key supplied")

    orphans = seen - declared
    if orphans:
        errs.append(f"clusters reference cells absent from the cell list: {sorted(orphans)}")
    silent = declared - seen
    if silent and not allow_silent_cells:
        # A cell that contributed no cluster at all is usually an extraction failure, not a tool
        # that found nothing — the tool still wrote a report.
        #
        # On the NULL ARM the opposite is true: a tool that reported nothing against a change with
        # no known defect is the best possible result and the headline number (dcc-mjj5). Scoring a
        # null subject therefore requires --allow-silent-cells, which is refused by default so the
        # guard still fires everywhere it was designed to.
        errs.append(f"cells contributing zero clusters (extraction defect?): {sorted(silent)}"
                    " — if this is the null arm, pass --allow-silent-cells")

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

    # The two guards above cover the TOOL-REPORTED severity, which /bench-synthesize uses for its
    # calibration axis but which no metric here reads. `precision_severity_weighted` is computed from
    # the JUDGED severity, and an absent one silently defaults to weight 1.0 — the same weight as
    # `low` — so a cluster the judge never rated was indistinguishable from one rated low. Guard the
    # field the metric actually depends on (dcc-3cm6).
    ungraded = [c.get("cluster_id", "?") for c in clusters if not c.get("judged_severity")]
    if ungraded:
        errs.append(f"{len(ungraded)} cluster(s) with no judged_severity, which "
                    f"precision_severity_weighted would silently weight as 'low': "
                    f"{sorted(ungraded)[:5]}")
    badsev = sorted({(c.get("judged_severity") or "").lower() for c in clusters
                     if c.get("judged_severity")} - set(SEV_WEIGHT))
    if badsev:
        errs.append(f"judged_severity values outside {sorted(SEV_WEIGHT)}: {badsev}")

    # finding_class is optional — analyses graded before dcc-opdr carry none — but it is all-or
    # nothing. A partially classified set silently reports a class mix over whichever subset happened
    # to be graded, which reads exactly like a mix over the whole population.
    classed = [c for c in clusters if c.get("finding_class")]
    if classed:
        badcls = sorted({c["finding_class"] for c in classed} - FINDING_CLASSES)
        if badcls:
            errs.append(f"finding_class values outside the closed set {sorted(FINDING_CLASSES)}: "
                        f"{badcls}")
        if len(classed) != len(clusters):
            missing = [c.get("cluster_id", "?") for c in clusters if not c.get("finding_class")]
            errs.append(f"finding_class on {len(classed)} of {len(clusters)} clusters — a partial "
                        f"classification reports a mix over a subset as though it covered the whole "
                        f"population; missing e.g. {sorted(missing)[:5]}")

    if threads is not None:
        admitted = [t for t in threads if t.get("admission") == "admitted"]
        if not admitted:
            errs.append("threads.json supplied but no thread is admitted")
        # dcc-qwt3: 28% of the first corpus's admitted threads were written by competing review
        # tools. Thread recall is defined over the HUMAN population only, so an admitted thread
        # whose population is unknown makes every thread-recall figure unprovable — refuse rather
        # than emit a number that may mix the populations.
        unstamped = [i for i, t in enumerate(threads) if t.get("admission") == "admitted"
                     and t.get("origin") not in ("human", "bot")]
        if unstamped:
            errs.append(f"admitted thread(s) {unstamped} have no origin (human|bot) — annotate the "
                        f"corpus (annotate_thread_origin.py) so thread recall cannot mix human "
                        f"threads with competing-tool output")
        idxs = {c.get("matches_thread") for c in clusters if c.get("matches_thread") is not None}
        bad = {i for i in idxs if not isinstance(i, int) or i < 0 or i >= len(threads)}
        if bad:
            errs.append(f"matches_thread indexes out of range: {sorted(bad)}")
        # An EXCLUSION needs two independent readings (dcc-fm8s). `matchable = true` is the safe
        # default direction and the bulk of the annotation; the exclusions are the small dangerous
        # set, because each one removes a thread from the denominator and on an axis of n=3 that is
        # 33%. Measured error rate on the first single-pass annotation: 3 of 20 exclusions were
        # wrong, all three the same compound-thread shape (a thread whose quoted suggestion targets
        # absent code while another sentence targets code that is present).
        unreviewed = [i for i, t in enumerate(threads)
                      if t.get("admission") == "admitted"
                      and t.get("matchable_at_checkpoint") is False
                      and len(t.get("matchability_readings") or []) < 2]
        if unreviewed:
            errs.append(f"admitted thread(s) {unreviewed} are excluded as unmatchable on a SINGLE "
                        f"reading — an exclusion removes a thread from every arm's denominator, so "
                        f"it needs two (annotate_thread_matchability.py --second-pass)")

    if key:
        ids = {e.get("id") for e in (key.get("entries") or [])}
        unknown = {c.get("matches_key") for c in clusters if c.get("matches_key") is not None} - ids
        if unknown:
            errs.append(f"matches_key values naming no entry in the key: {sorted(map(str, unknown))}")

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

    # Two populations, two axes, never merged (dcc-qwt3): `human` threads are the miss detector;
    # `bot` threads measure agreement with incumbent automated review — several of those incumbents
    # are peers or direct competitors of the tools under test.
    human_idx = {i for i, t in enumerate(threads or [])
                 if t.get("admission") == "admitted" and t.get("origin") == "human"}
    bot_idx = {i for i, t in enumerate(threads or [])
               if t.get("admission") == "admitted" and t.get("origin") == "bot"}

    # A thread discussing code the checkpoint predates cannot be raised by a reviewer looking at the
    # checkpoint, so counting it as a miss deflates every arm equally and invisibly (nib dcc-hw48).
    # Absent annotation is NOT treated as matchable-by-default; it makes the axis unpublishable, which
    # travels in the metrics rather than being assumed away.
    unmatchable = {i for i, t in enumerate(threads or [])
                   if t.get("admission") == "admitted" and t.get("matchable_at_checkpoint") is False}
    annotated = {i for i, t in enumerate(threads or [])
                 if t.get("admission") == "admitted" and t.get("matchable_at_checkpoint") is not None}
    matchability_annotated = bool(threads) and annotated == (human_idx | bot_idx)

    # Two threads asserting ONE defect are one ground-truth item. Crediting a single index makes the
    # other read as missed, and because the axes are split by origin, a bot/human duplicate pair moves
    # credit from the human axis to the incumbent axis (nib dcc-qfr5). Recall is therefore computed
    # over GROUPS, not raw indices. An unstamped thread is its own group, so a corpus without grouping
    # behaves exactly as before.
    grp = {i: (t.get("thread_group") or f"t{i}") for i, t in enumerate(threads or [])}
    live = (human_idx | bot_idx) - unmatchable
    _bygroup = defaultdict(list)
    for i in live:
        _bygroup[grp[i]].append(i)
    human_groups = {grp[i] for i in live if threads[i].get("origin") == "human"}
    bot_groups = {grp[i] for i in live if threads[i].get("origin") == "bot"}

    # Which clusters a tool REPORTED versus merely FOUND (reported + demoted below its own bar).
    tool_reported = defaultdict(set)
    for c in clusters:
        for r in c["reported_by"]:
            if r.get("disposition", "reported") == "reported":
                tool_reported[r["tool"]].add(c["cluster_id"])

    # Class axis presence, decided once for the whole analysis (validate() has already refused a
    # partial classification, so "any" and "all" agree here).
    classed = any(c.get("finding_class") for c in clusters)
    real_defect_pool = [c for c in clusters if c["verdict"] in REAL and c.get("finding_class") == "defect"]

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
        # Computed over HUMAN threads only; hits on bot threads land in incumbent_agreement below.
        def hits(pool):
            return {grp[c["matches_thread"]] for c in pool
                    if c["verdict"] == "matches-thread" and c.get("matches_thread") is not None}
        hit, hit_found = hits(cs), hits(cs_found)
        thread_recall = (len(hit & human_groups) / len(human_groups)) if human_groups else None
        thread_recall_found = (len(hit_found & human_groups) / len(human_groups)) if human_groups else None
        incumbent = (len(hit & bot_groups) / len(bot_groups)) if bot_groups else None
        incumbent_found = (len(hit_found & bot_groups) / len(bot_groups)) if bot_groups else None

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
            # The caveat travels with the number: `precision` counts valid-minor as a MISS, so an
            # arm whose output is 92% correct can score 0.50. Reading it as "half is wrong" is a
            # factual error that has been made (nib dcc-t83x). Use noise% for that question.
            "precision_note": "excludes valid_minor (correct but small); see scoring/METRICS.md",
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
            "threads_hit": len(hit & human_groups) if human_groups else None,
            "incumbent_agreement": round(incumbent, 3) if incumbent is not None else None,
            "incumbent_agreement_found": round(incumbent_found, 3) if incumbent_found is not None else None,
            "real_found": len([c for c in cs_found if c["verdict"] in REAL]),
            "demoted_real": len([c for c in cs_found if c["verdict"] in REAL]) - len(real),
            "anchor_recall": round(anchor_recall, 3) if anchor_recall is not None else None,
            "anchor_recall_found": round(anchor_recall_found, 3) if anchor_recall_found is not None else None,
            "cost_usd": round(sum(cells[(t, r)].get("cost_usd", 0) for (t, r) in cells if t == tool), 4),
        }
        # Cost, three ways, because the obvious one is repeat-dependent (dcc-8dtt).
        #
        # `cost_per_real_finding` divides an arm's TOTAL cost by its DEDUPLICATED real pool, so an
        # arm that ran twice pays twice for a pool that barely grows. Measured on PostHog-55149:
        # `ours-review` reads 2.5x worse than `ours-audit` on this field and 23% worse per cell, and
        # almost the whole gap is that one ran twice and the other once — a scheduling decision.
        #
        # It is kept, because it answers "what did this arm cost me in total", and paired with the
        # two fields that make it readable: `n_cells`, so it can never be read without its divisor,
        # and `cost_per_real_finding_per_cell`, the mean over cells of (cell cost / real clusters
        # that cell contributed), which is what one RUN costs per real finding and does not move
        # when repeats are added.
        arm_cells = [(t, r) for (t, r) in cells if t == tool]
        cu = out_tools[tool]["cost_usd"]
        out_tools[tool]["n_cells"] = len(arm_cells)
        out_tools[tool]["cost_per_real_finding"] = round(cu / len(real), 4) if real else None
        out_tools[tool]["cost_per_real_finding_repeat_dependent"] = True
        per_cell = []
        for (t, r) in arm_cells:
            cell_real = {c["cluster_id"] for c in clusters if c["verdict"] in REAL
                         and any(rb["tool"] == t and rb["repeat"] == r
                                 and rb.get("disposition", "reported") == "reported"
                                 for rb in c["reported_by"])}
            if cell_real:
                per_cell.append(cells[(t, r)].get("cost_usd", 0) / len(cell_real))
        out_tools[tool]["cost_per_real_finding_per_cell"] = (
            round(sum(per_cell) / len(per_cell), 4) if per_cell else None)
        out_tools[tool]["cost_per_cell"] = round(cu / len(arm_cells), 4) if arm_cells else None

        # Per-tool class mix and defect recall (dcc-opdr, dcc-1sbc). The class axis is graded blind
        # to verdict and tool, so this is the one per-tool composition figure that does not depend on
        # the substance call. Reported and found are split like every other per-tool figure: what a
        # user was shown against what the tool is capable of. defect_recall's denominator is the pool
        # of REAL defect-class clusters any tool found — the same "16 real defects" TUNING-SIGNALS
        # counted by hand — and is null when the analysis carries no class axis at all.
        if classed:
            out_tools[tool]["class_distribution"] = {
                "reported": {k: sum(1 for c in cs if c.get("finding_class") == k) for k in sorted(FINDING_CLASSES)},
                "found": {k: sum(1 for c in cs_found if c.get("finding_class") == k) for k in sorted(FINDING_CLASSES)},
            }
            rd = [c for c in real if c.get("finding_class") == "defect"]
            fd = [c for c in cs_found if c["verdict"] in REAL and c.get("finding_class") == "defect"]
            out_tools[tool]["defect_recall"] = {
                "pool": len(real_defect_pool),
                "reported": len(rd), "found": len(fd),
                "recall_reported": round(len(rd) / len(real_defect_pool), 3) if real_defect_pool else None,
                "recall_found": round(len(fd) / len(real_defect_pool), 3) if real_defect_pool else None,
            }
        else:
            out_tools[tool]["class_distribution"] = None
            out_tools[tool]["defect_recall"] = None

    # Judge calibration: an admitted HUMAN thread that a tool DID report, but the judge called
    # not-real. Human only — the judge disagreeing with a bot is a disagreement between tools, not a
    # calibration failure against expert review, which is what this check exists to catch.
    dismissed = []
    for c in clusters:
        mt = c.get("matches_thread")
        if mt is not None and mt in human_idx and c["verdict"] in (NOISE | WRONG):
            dismissed.append({"cluster_id": c["cluster_id"], "thread": mt, "verdict": c["verdict"],
                              "thread_path": (threads[mt] or {}).get("path")})

    # A cluster credited to a thread judged unmatchable is a CONTRADICTION: a tool cannot legitimately
    # match a comment about code that does not exist at the checkpoint. It means one of the two
    # judgments is wrong, and which one differs case by case, so this reports rather than refuses.
    #
    # Found four on first run (dcc-hw48). Two were loose grading matches — a `== true` style cluster
    # credited to a thread asking for `is null` on a line with no `== null`, and a logger-context
    # request credited to a cluster about decoder placement. One was a real annotation error: an
    # efcore thread whose quoted suggestion targeted an absent block, while its closing sentence
    # ("move nullPropagatedOperands below") described the exact ordering seven arms reported. Without
    # this check that thread's exclusion silently cost seven arms a legitimate hit.
    contradictions = []
    for c in clusters:
        mt = c.get("matches_thread")
        if mt is not None and (threads[mt] or {}).get("matchable_at_checkpoint") is False:
            contradictions.append({"cluster_id": c["cluster_id"], "thread": mt,
                                   "thread_path": (threads[mt] or {}).get("path"),
                                   "arms": sorted({r["tool"] for r in c["reported_by"]})})

    # Threads no tool reported at all — the miss detector's actual output.
    #
    # Split by disposition for the same reason every per-tool recall is (dcc-c92m): computed over all
    # clusters, a thread that every tool FOUND and every tool DEMOTED counts as hit, so the field
    # that answers "what did the whole field miss" was silently giving the `found` reading. Both are
    # true of different questions; neither may stand alone.
    def hit_any_over(pred):
        return {grp[c["matches_thread"]] for c in clusters
                if c["verdict"] == "matches-thread" and c.get("matches_thread") is not None
                and any(pred(r) for r in c["reported_by"])}
    hit_any_found = hit_any_over(lambda r: True)
    hit_any = hit_any_over(lambda r: r.get("disposition", "reported") == "reported")
    # Reported as thread indices, since that is what a reader looks up, but decided per GROUP: a
    # duplicate pair is missed only if NEITHER of its threads was credited.
    missed = sorted(i for i in live if threads[i].get("origin") == "human" and grp[i] not in hit_any)
    missed_found = sorted(i for i in live if threads[i].get("origin") == "human"
                          and grp[i] not in hit_any_found)

    # Vintage travels with the metrics so a downstream synthesis cannot pool an in-window subject
    # into a headline without seeing it (dcc-vvf0). Computed here, never read from the fixture:
    # status is a property of the (subject, model) pair and changes when a model ships.
    # Both keys, always (dcc-60qk): `merged_at` gates, `pr_created_at` is reported beside it so a
    # figure states which reading licenses it. A missing pr_created_at reports "unknown", not
    # "agrees" — copy it from fixture.json into analysis.json.
    vin = None
    if A.get("merged_at") and A.get("judge_model"):
        vin = vintage.describe(A["merged_at"], A["judge_model"], A.get("pr_created_at"))

    return {
        "subject": A.get("subject"),
        "instrument": A.get("instrument", "pooled-adjudication"),
        "judge_model": A.get("judge_model"),
        "vintage": vin,
        "n_clusters": len(clusters),
        "n_cells": len(cells),
        "threads": {
            "admitted": len(human_idx) + len(bot_idx),
            "admitted_human": len(human_idx),
            "admitted_bot": len(bot_idx),
            # The denominators actually used. `admitted_*` counts what the corpus holds; these count
            # what a reviewer at the checkpoint could have raised, after removing threads about code
            # that did not exist (dcc-hw48) and collapsing duplicate threads into one defect
            # (dcc-qfr5). A reader comparing the two sees exactly what was excluded and why.
            "denominator_human": len(human_groups),
            "denominator_bot": len(bot_groups),
            "excluded_unmatchable": sorted(unmatchable),
            "excluded_unmatchable_human": sorted(i for i in unmatchable if i in human_idx),
            "duplicate_groups": sorted([sorted(v) for k, v in _bygroup.items() if len(v) > 1]),
            # False when any admitted thread lacks a matchability verdict. The axis is then computed
            # over an unaudited denominator and MUST NOT be published — the flag exists so a
            # synthesis gates on it instead of assuming the annotation happened.
            "matchability_annotated": matchability_annotated,
            "thread_axis_publishable": matchability_annotated,
            # Four of the seven citable subjects hold <=2 human threads (THREAD-AXIS.md); a recall
            # there is 0/0.5/1.0 quantization, not a measurement. The flag travels with the metrics
            # so a synthesis must show n and may not pool or headline a thin cell's recall.
            "human_axis_thin": 0 < len(human_groups) <= THIN_HUMAN_AXIS_MAX,
            # THIN and EMPTY are different failures and must not read the same (nib dcc-7zyf).
            # Empty = no tool matched ANY human thread, so every arm scores 0.00 and the axis cannot
            # discriminate between them — yet pooled naively it still drags every average down by
            # the same amount, making the corpus look worse at matching human review than the
            # evidence supports. Measured on grafana-117615: both its human threads are non-defect
            # comments (a reviewer saying they are unfamiliar with the area; a naming request about
            # fixture data), so 0.00 is the right answer to a question that cannot separate tools.
            # A view must render this as n/a WITH THE REASON, never as a score of zero, and exclude
            # it from any pooled thread figure.
            "human_axis_empty": len(human_groups) > 0 and len(hit_any_found & human_groups) == 0,
            # Everything below is the HUMAN axis — the miss detector.
            # "reported": what a user would have been shown. "found": what the field is capable of.
            "hit_by_any_tool": len(hit_any & human_groups),
            "hit_by_any_tool_found": len(hit_any_found & human_groups),
            "missed_by_every_tool": len(missed),
            "missed_by_every_tool_found": len(missed_found),
            "missed_index": missed,
            "missed_index_found": missed_found,
            # Reported by nobody, though somebody found it — a threshold problem, not a blind spot.
            "demoted_by_every_tool_that_found_it": sorted(set(missed) - set(missed_found)),
            "judge_dismissed_reported_threads": dismissed,
            # Clusters credited to a thread judged unmatchable — see the comment above. Non-empty
            # means the grading and the matchability annotation disagree and one of them is wrong.
            "credited_to_unmatchable_thread": contradictions,
            # Agreement with incumbent automated review — a real measurement, but not a miss
            # detector, and never pooled with the human axis. "missed" framing is deliberately
            # absent: a bot thread nobody repeated is not evidence anything was missed.
            "incumbent": {
                "hit_by_any_tool": len(hit_any & bot_groups) if bot_groups else None,
                "hit_by_any_tool_found": len(hit_any_found & bot_groups) if bot_groups else None,
            },
        },
        "tools": out_tools,
        "verdict_distribution": {v: sum(1 for c in clusters if c["verdict"] == v)
                                 for v in sorted(ALL_VERDICTS)},
        # Absent when the analysis predates dcc-opdr; null rather than an empty dict, so a consumer
        # can tell "not classified" from "classified, none of anything".
        "class_distribution": ({k: sum(1 for c in clusters if c.get("finding_class") == k)
                                for k in sorted(FINDING_CLASSES)}
                               if any(c.get("finding_class") for c in clusters) else None),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("analysis")
    ap.add_argument("--threads"); ap.add_argument("--key"); ap.add_argument("-o", "--out")
    ap.add_argument("--allow-silent-cells", action="store_true",
                    help="permit a cell that produced no cluster — required for the NULL ARM, where "
                         "a tool reporting nothing is the result, not an extraction failure")
    ap.add_argument("--no-calibration", action="store_true",
                    help="emit metrics for a subject with no calibration record (nib dcc-n4nf). "
                         "Only for a subject being scored for the very first time.")
    a = ap.parse_args()
    A = json.load(open(a.analysis))

    # Every verdict-derived number depends on the grading day. A subject whose verdicts have never
    # been calibrated against the pilot's has an unmeasured baseline: on 2026-08-17 the same model
    # with the same prompt agreed with the pilot at 3/12 on one subject, and self-agreement could
    # not see it. Refuse rather than emit a number whose judge is unaccounted for (nib dcc-n4nf).
    if not a.no_calibration:
        gd = os.path.join(os.path.dirname(os.path.abspath(a.analysis)), "grading")
        recs = sorted(glob.glob(os.path.join(gd, "calibration-2*.json")))
        if not recs:
            print(f"DATA DEFECT — refusing to emit metrics:\n  no calibration record under {gd}. "
                  f"Grade this subject's standing sample and record it with\n"
                  f"    judge_stability.py <p1> <p2> --calibration {gd}/calibration-sample.json "
                  f"-o {gd}/calibration-<date>.json\n"
                  f"  or pass --no-calibration if this subject is being scored for the first time.",
                  file=sys.stderr)
            sys.exit(3)
    threads = json.load(open(a.threads)) if a.threads else None
    key = json.load(open(a.key)) if a.key else None
    try:
        validate(A, threads, key, allow_silent_cells=a.allow_silent_cells)
    except DataDefect as e:
        print(f"DATA DEFECT — refusing to emit metrics:\n  {e}", file=sys.stderr)
        sys.exit(3)
    m = score(A, threads, key)
    s = json.dumps(m, indent=2)
    ctr = (m.get("threads") or {}).get("credited_to_unmatchable_thread") or []
    if ctr:
        print(f"WARNING: {len(ctr)} cluster(s) credited to a thread judged unmatchable at the "
              f"checkpoint — the grading and the matchability annotation disagree:", file=sys.stderr)
        for x in ctr:
            print(f"  {x['cluster_id']} -> T{x['thread']} ({x['thread_path']}) arms={x['arms']}",
                  file=sys.stderr)
        print("  Resolve each: re-grade the cluster, or revise the thread's matchability verdict.",
              file=sys.stderr)
    if a.out:
        open(a.out, "w").write(s + "\n"); print(f"wrote {a.out}")
    else:
        print(s)


if __name__ == "__main__":
    main()
