#!/usr/bin/env python3
"""Per-persona yield and cost for `ours`, to inform roster reduction (nib dcc-e0wj, workstream 2).

Answers: which reviewer personas contribute clusters *no sibling in the same run also found*,
how valuable those clusters were judged to be, and what each persona costs in output tokens.

Two data-quality notes drive the implementation:

* ``analysis.json`` records a persona in ``reported_by[].subagent`` only for subjects extracted
  after the pipeline gained persona capture (1, 4, 5, 7, and half of 6). For the rest the field
  is a bare ``agent-<id>``. The persona is recovered from the raw transcript's
  ``attributionAgent`` field, which is present for every sub-agent of every run.
* Per-sub-agent output tokens were under-counted ~10x until #dcc-m8ar; this script needs those
  figures, so it refuses to run against un-backfilled data.

Usage:
    roster_yield.py            # table to stdout
    roster_yield.py --json     # machine-readable, for the synthesis page
"""

from __future__ import annotations

import collections
import glob
import json
import pathlib
import sys

BENCH = pathlib.Path(__file__).resolve().parent.parent.parent
PROJECTS = pathlib.Path.home() / ".claude" / "projects"

# Per METHODOLOGY.md: precision counts these three; valid-minor is real value but tracked apart.
SUBSTANTIVE = {"TP-primary", "TP-human", "valid-other"}
NOISE = {"trivia", "false-positive"}

# Validators re-verify findings the reviewers raised; they never originate one, so they are not
# candidates for roster reduction and must not be credited with sole-finding anything.
# "validator" is the same role under a name some extractions recorded. "Explore" is the built-in
# search agent, not a review persona.
NOT_A_FINDER = {"finding-validator", "validator", "Explore"}


def personas_from_transcripts(session_id: str) -> dict[str, str]:
    """Map agent id -> persona for one run, read from the raw sub-agent transcripts."""
    mapping: dict[str, str] = {}
    for subdir in PROJECTS.glob(f"*/{session_id}/subagents"):
        for path in subdir.glob("agent-*.jsonl"):
            agent = path.stem
            with path.open() as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    attribution = record.get("attributionAgent")
                    if attribution:
                        mapping[agent] = attribution.split(":", 1)[-1]
                        break
    return mapping


def personas_for_run(subject_id: int, repeat: int, session_id: str, refresh: bool) -> dict[str, str]:
    """Persona map for one run, cached beside the subject's analysis artifacts.

    Transcripts under ~/.claude/projects are pruned over time, and for subjects 2/3/9/10 (and
    half of 6) they are the ONLY record of which persona each agent was -- the extraction
    pipeline did not yet capture it into analysis.json. Persisting the map keeps this analysis
    reproducible after the transcripts are gone.
    """
    cache = BENCH / "analysis" / f"subject-{subject_id:02d}" / "agent-personas.json"
    key = f"{subject_id}__ours__r{repeat}"
    stored = json.loads(cache.read_text()) if cache.is_file() else {}
    if not refresh and key in stored:
        return stored[key]

    mapping = personas_from_transcripts(session_id)
    if mapping:
        stored[key] = mapping
        cache.write_text(json.dumps(stored, indent=2, sort_keys=True) + "\n")
    return mapping or stored.get(key, {})


def run_meta(subject_id: int, repeat: int) -> dict | None:
    path = BENCH / "runs" / f"{subject_id}__ours__r{repeat}" / "meta.json"
    return json.loads(path.read_text()) if path.is_file() else None


def main(argv: list[str]) -> int:
    as_json = "--json" in argv[1:]
    refresh = "--refresh-personas" in argv[1:]

    drop = set()
    for arg in argv[1:]:
        if arg.startswith("--simulate="):
            drop = {p.strip() for p in arg.split("=", 1)[1].split(",") if p.strip()}

    yields: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    dispatched: dict[str, set] = collections.defaultdict(set)
    tokens: dict[str, int] = collections.Counter()
    events: list[tuple[str, frozenset]] = []
    unresolved = 0

    for analysis_path in sorted((BENCH / "analysis").glob("subject-*/analysis.json")):
        analysis = json.loads(analysis_path.read_text())
        subject_id = analysis["subject_id"]

        # Persona map + token cost per run, keyed by repeat.
        maps, costs = {}, {}
        for repeat in (1, 2):
            meta = run_meta(subject_id, repeat)
            if not meta:
                continue
            maps[repeat] = personas_for_run(
                subject_id, repeat, meta.get("session_id", ""), refresh
            )
            per_sub = (meta.get("session_tokens") or {}).get("per_subagent") or []
            costs[repeat] = {entry["agent"]: entry.get("output", 0) for entry in per_sub}
            for agent, persona in maps[repeat].items():
                dispatched[persona].add((subject_id, repeat))
                tokens[persona] += costs[repeat].get(agent, 0)

        for cluster in analysis["clusters"]:
            verdict = cluster.get("verdict")
            finders: dict[int, set] = collections.defaultdict(set)
            for report in cluster.get("reported_by", []):
                if report["tool"] != "ours":
                    continue
                subagent = report.get("subagent")
                if not subagent:  # the consolidated report itself, not a finder
                    continue
                agent, _, suffix = subagent.partition("/")
                persona = suffix or maps.get(report["repeat"], {}).get(agent)
                if not persona:
                    unresolved += 1
                    continue
                if persona in NOT_A_FINDER:
                    continue
                finders[report["repeat"]].add(persona)

            for repeat, found_by in finders.items():
                events.append((verdict, frozenset(found_by)))
                for persona in found_by:
                    yields[persona]["reported"] += 1
                if len(found_by) == 1:
                    persona = next(iter(found_by))
                    yields[persona]["sole"] += 1
                    if verdict in SUBSTANTIVE:
                        yields[persona]["sole_substantive"] += 1
                    elif verdict == "valid-minor":
                        yields[persona]["sole_valid_minor"] += 1
                    elif verdict in NOISE:
                        yields[persona]["sole_noise"] += 1

    rows = []
    for persona in sorted(set(yields) | set(dispatched)):
        counts = yields[persona]
        runs = len(dispatched[persona])
        sole_useful = counts["sole_substantive"] + counts["sole_valid_minor"]
        rows.append(
            {
                "persona": persona,
                "runs_dispatched": runs,
                "output_tokens": tokens[persona],
                "tokens_per_run": round(tokens[persona] / runs) if runs else 0,
                "clusters_reported": counts["reported"],
                "sole_found": counts["sole"],
                "sole_substantive": counts["sole_substantive"],
                "sole_valid_minor": counts["sole_valid_minor"],
                "sole_noise": counts["sole_noise"],
                "tokens_per_sole_useful": (
                    round(tokens[persona] / sole_useful) if sole_useful else None
                ),
            }
        )
    rows.sort(key=lambda r: (-r["sole_substantive"], -r["sole_valid_minor"], r["persona"]))

    grand_total = sum(r["output_tokens"] for r in rows) or 1
    for row in rows:
        row["share_of_subagent_output"] = round(row["output_tokens"] / grand_total * 100, 1)

    if as_json:
        json.dump({"rows": rows, "unresolved_attributions": unresolved}, sys.stdout, indent=2)
        return 0

    print(
        f"{'persona':<28}{'runs':>5}{'tok/run':>9}{'share':>7}{'rep':>6}{'sole':>6}"
        f"{'subst':>7}{'vminor':>8}{'noise':>7}{'tok/useful':>12}"
    )
    for row in rows:
        per_useful = row["tokens_per_sole_useful"]
        print(
            f"{row['persona']:<28}{row['runs_dispatched']:>5}{row['tokens_per_run']:>9,}"
            f"{row['share_of_subagent_output']:>6}%{row['clusters_reported']:>6}"
            f"{row['sole_found']:>6}{row['sole_substantive']:>7}"
            f"{row['sole_valid_minor']:>8}{row['sole_noise']:>7}"
            f"{('—' if per_useful is None else format(per_useful, ',')):>12}"
        )
    if unresolved:
        print(f"\n{unresolved} report(s) could not be resolved to a persona")

    if drop:
        unknown = drop - set(tokens)
        if unknown:
            print(f"\nunknown persona(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        saved = sum(tokens[p] for p in drop)
        grand = sum(tokens.values()) or 1
        kept: collections.Counter = collections.Counter()
        lost: collections.Counter = collections.Counter()
        for verdict, found_by in events:
            # A cluster survives unless every persona that found it was dropped.
            (lost if found_by and found_by <= drop else kept)[verdict] += 1

        print(f"\nSIMULATED roster reduction — drop: {', '.join(sorted(drop))}")
        print(f"  sub-agent output saved: {saved:,} / {grand:,} = {saved / grand * 100:.1f}%")
        print(f"\n  {'verdict':<16}{'kept':>7}{'LOST':>7}")
        for verdict in ("TP-primary", "TP-human", "valid-other", "valid-minor",
                        "trivia", "false-positive"):
            print(f"  {verdict:<16}{kept[verdict]:>7}{lost[verdict]:>7}")
        print(
            f"\n  substantive lost: {sum(lost[v] for v in SUBSTANTIVE)}"
            f" · valid-minor lost: {lost['valid-minor']}"
            f" · noise removed: {sum(lost[v] for v in NOISE)}"
        )
        print(
            "\n  Simulation over recorded findings, NOT a re-run: it assumes the surviving\n"
            "  agents would report exactly what they reported. Removing corroborators can\n"
            "  also lower confidence anchors (consolidation promotes on agreement), which\n"
            "  may suppress findings this model still counts as kept. Re-run to confirm."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
