#!/usr/bin/env python3
"""The cell prompt's toolchain paragraph, DERIVED from build-capability.json (nib dcc-9vta).

Usage: build_note.py <build-capability.json>

The prompt used to assert, on every cell, that "a build toolchain IS available (node, go, dotnet,
python, cargo as the project requires)". On PostHog-posthog-55149 that was false for the majority
language — cargo absent, 13 of 18 changed files Rust — and two cells independently recorded working
around it. A reviewer told it can build, that then cannot, spends the difference finding out.

So the sentence is generated from what detection actually found, and the three states are distinct:
toolchain complete, toolchain partial (which languages are missing, named), and detection failed.
"""
import json, sys


def note(cap):
    if cap.get("error"):
        return ("- Build capability could NOT be determined for this checkout, so do not assume a "
                "toolchain is present. Verify before relying on a build, and report a finding you "
                "could only reason about statically as exactly that.")
    langs = cap.get("languages") or []
    missing = cap.get("missing_toolchains") or []
    restores = [r for r in (cap.get("restore_commands") or []) if r]
    if not langs:
        return "- No package manifest was detected in this checkout; treat it as read-only source."

    if missing:
        lines = [
            f"- A build toolchain is available for SOME of this project but NOT all of it. Detected "
            f"languages: {', '.join(langs)}. MISSING and unusable here: {', '.join(missing)}.",
            f"  Code in the missing languages can only be reasoned about statically — say so in the "
            f"finding rather than implying you verified it.",
            f"  Do not report a command as having succeeded without reading its output: a "
            f"backgrounded run of an absent binary has been observed recording exit code 0 while "
            f"its real output was \"No such file or directory\".",
        ]
    else:
        lines = [f"- A build toolchain IS available for every detected language "
                 f"({', '.join(langs)}). You may build the project and run its tests to confirm or "
                 f"refute a finding."]
    if restores:
        lines.append(f"  Restore dependencies with the project's frozen/locked command "
                     f"({'; '.join(restores)}) so nothing resolves to a version published after "
                     f"this change. Full suites can take many minutes; prefer the tests covering "
                     f"the changed code.")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: build_note.py <build-capability.json>")
    try:
        cap = json.load(open(sys.argv[1]))
    except Exception as e:
        cap = {"error": f"unreadable build-capability.json: {e}"}
    print(note(cap))
