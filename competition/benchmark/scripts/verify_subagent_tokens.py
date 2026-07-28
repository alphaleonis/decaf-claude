#!/usr/bin/env python3
"""Verify that recorded sub-agent output tokens are physically possible.

A sub-agent cannot report fewer output tokens than the text it demonstrably emitted.
The archived transcript in ``findings/subagent-NN-<agent>.md`` is an independent record
of that text, so comparing the two catches under-counting in ``meta.json``.

This exists because ``session_tokens.sh`` originally summed the FIRST usage record per
message id. A transcript writes one line per content block, and on streamed responses
each line carries the usage as it stood when that block was emitted -- a single message
reads e.g. ``[5, 5, 278]`` and only the last entry is cumulative. Picking the first
under-counted sub-agent output by ~10x while leaving the orchestrator untouched.

Usage:
    verify_subagent_tokens.py [<run-dir> ...]      # defaults to every runs/*/

Exit status:
    0  every recorded figure is physically possible
    1  at least one run records fewer output tokens than its transcripts contain
"""

from __future__ import annotations

import json
import pathlib
import sys

# Rough bytes-per-token for English prose and markdown. Deliberately conservative: a real
# under-count shows up as an order of magnitude, so precision here does not matter.
BYTES_PER_TOKEN = 4

# How far below the transcript estimate a recorded figure must fall before it counts as a
# defect rather than noise in BYTES_PER_TOKEN. Markdown with tables and indentation drifts
# well past 4 bytes/token, so anything under this ratio is unactionable; the real defect this
# script exists to catch ran 10x-250x.
FAIL_RATIO = 3.0

# Sub-agents whose transcript never received a final cumulative usage record: a single message
# id whose usage lines are all partial (e.g. [5, 5]) despite the agent emitting a full report.
# That is an upstream capture gap, not an aggregation error -- nothing on our side can recover
# the true figure. Listed so a regression of the aggregation bug still fails loudly.
KNOWN_UPSTREAM_GAPS = {
    "agent-a1658cd2c7bb11202": "5__tag1-comprehensive-review__r1 -- 1 message id, usage [5, 5]",
    "agent-adf245456e17409d3": "7__tag1-comprehensive-review__r2 -- 1 message id, usage [5, 5]",
}


def transcript_tokens(findings: pathlib.Path, agent: str) -> int | None:
    """Approximate tokens in an agent's archived transcript, or None if not archived."""
    for path in findings.glob(f"subagent-*-{agent}.md"):
        # The file opens with a "# subagent <id>" header that is not model output.
        return max(path.stat().st_size - len(agent) - 12, 0) // BYTES_PER_TOKEN
    return None


def check_run(run_dir: pathlib.Path) -> tuple[int, int]:
    """Report one run. Returns (rows_checked, rows_impossible)."""
    meta_path = run_dir / "meta.json"
    if not meta_path.is_file():
        print(f"{run_dir.name}: no meta.json -- skipped")
        return 0, 0

    meta = json.loads(meta_path.read_text())
    if meta.get("status") != "done":
        print(f"{run_dir.name}: status={meta.get('status')} -- skipped")
        return 0, 0

    per_subagent = (meta.get("session_tokens") or {}).get("per_subagent") or []
    if not per_subagent:
        print(f"{run_dir.name}: no per_subagent data -- skipped")
        return 0, 0

    findings = run_dir / "findings"
    rows, bad = 0, 0
    print(f"\n{run_dir.name}  ({len(per_subagent)} sub-agents, ${meta.get('cost_usd', '?')})")
    print(f"  {'agent':<26}{'recorded':>10}{'transcript':>12}  verdict")

    for entry in per_subagent:
        agent = entry.get("agent", "?")
        recorded = entry.get("output", 0)
        visible = transcript_tokens(findings, agent) if findings.is_dir() else None
        ratio = visible / max(recorded, 1) if visible is not None else 0.0

        if visible is None:
            verdict = "no transcript archived"
        elif agent in KNOWN_UPSTREAM_GAPS and ratio >= FAIL_RATIO:
            verdict = f"known upstream gap ({ratio:.0f}x) -- no final usage record"
            rows += 1
        elif ratio >= FAIL_RATIO:
            verdict = f"IMPOSSIBLE -- recorded is {ratio:.0f}x too low"
            bad += 1
            rows += 1
        elif recorded < visible:
            verdict = f"marginal ({ratio:.1f}x) -- within bytes/token estimate error"
            rows += 1
        else:
            verdict = "ok"
            rows += 1
        shown = "-" if visible is None else f"{visible:,}"
        print(f"  {agent:<26}{recorded:>10,}{shown:>12}  {verdict}")

    return rows, bad


def main(argv: list[str]) -> int:
    bench = pathlib.Path(__file__).resolve().parent.parent
    targets = [pathlib.Path(a) for a in argv[1:]] or sorted((bench / "runs").glob("*/"))
    if not targets:
        print("no run directories found", file=sys.stderr)
        return 1

    total, impossible = 0, 0
    for run_dir in targets:
        rows, bad = check_run(run_dir)
        total += rows
        impossible += bad

    print(f"\n{total} sub-agent rows checked, {impossible} physically impossible")
    if impossible:
        print(
            "Recorded output is below the text the agent emitted. Re-run "
            "scripts/backfill_tokens.sh; if that does not fix it, the aggregation in "
            "scripts/session_tokens.sh has regressed to picking a non-final usage record."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
