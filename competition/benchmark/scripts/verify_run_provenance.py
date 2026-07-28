#!/usr/bin/env python3
"""Verify each run actually executed the tool it is recorded as.

Several plugins ship a skill or command with the same bare name (`code-review` exists in both
`decaf-quality` and `code-review@claude-plugins-official`), so an unqualified invocation can
silently resolve to the wrong tool. That happened: 7 cells recorded as `anthropic-code-review`
ran `decaf-quality` instead, and it went unnoticed for months because nothing checked. See
nib dcc-9kkz.

Each sub-agent transcript carries `attributionPlugin`, naming the plugin that spawned it. That
is the ground truth this compares against `tools.json`'s `requires_plugin`.

Usage:
    verify_run_provenance.py [<run-id> ...]     # defaults to every done run

Exit status:
    0  every checked run matches, or differs only by missing attribution (reported as WARN)
    1  at least one run executed a different plugin than recorded
"""

from __future__ import annotations

import collections
import glob
import json
import pathlib
import sys

BENCH = pathlib.Path(__file__).resolve().parent.parent
PROJECTS = pathlib.Path.home() / ".claude" / "projects"


def expected_plugins() -> dict[str, str]:
    tools = json.loads((BENCH / "tools.json").read_text())
    return {t["id"]: t.get("requires_plugin", "") for t in tools}


def dominant_plugin(session_id: str) -> tuple[str | None, int]:
    """The plugin that spawned most of a run's sub-agents, and how many transcripts were seen."""
    counts: collections.Counter = collections.Counter()
    for subdir in PROJECTS.glob(f"*/{session_id}/subagents"):
        for path in subdir.glob("agent-*.jsonl"):
            plugin = None
            with path.open() as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("attributionPlugin"):
                        plugin = record["attributionPlugin"]
                        break
            counts[plugin] += 1
    if not counts:
        return None, 0
    total = sum(counts.values())
    named = {k: v for k, v in counts.items() if k}
    return (max(named, key=named.get) if named else None), total


def main(argv: list[str]) -> int:
    expected = expected_plugins()
    wanted = set(argv[1:])

    metas = sorted(BENCH.glob("runs/*/meta.json"))
    if not metas:
        print("no runs found", file=sys.stderr)
        return 1

    mismatches, warnings, checked = [], [], 0
    print(f"  {'run':<40}{'recorded':<26}{'executed':<22}verdict")
    for meta_path in metas:
        meta = json.loads(meta_path.read_text())
        run_id = meta.get("run_id", meta_path.parent.name)
        if wanted and run_id not in wanted:
            continue
        if meta.get("status") != "done":
            continue

        tool = meta.get("tool", "?")
        want = expected.get(tool, "")
        got, seen = dominant_plugin(meta.get("session_id", ""))
        checked += 1

        if got is None:
            verdict = "WARN — no attribution" if seen else "WARN — no transcript"
            warnings.append(run_id)
        elif got == want:
            verdict = "ok"
        else:
            verdict = "MISMATCH"
            mismatches.append((run_id, tool, got))
        print(f"  {run_id:<40}{tool:<26}{(got or '(none)'):<22}{verdict}")

    print(f"\n{checked} run(s) checked · {len(mismatches)} mismatched · {len(warnings)} warned")
    if warnings:
        print(
            "\nWARN means the sub-agents carry no plugin attribution — the orchestrator may have\n"
            "executed the workflow directly. Inspect the sub-agent prompts before trusting the\n"
            "cell; a faithful run shows the tool's own agent roles."
        )
    if mismatches:
        print("\nMISMATCH — these cells did not run the tool they are recorded as:")
        for run_id, tool, got in mismatches:
            print(f"  {run_id}: recorded {tool}, executed {got}")
        print(
            "\nQuarantine them (see runs-invalid/README.md), reset the manifest entries to "
            "pending,\nand fix the invocation in tools.json to be plugin-qualified before re-running."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
