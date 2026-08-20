#!/usr/bin/env python3
"""Self-tests for build_note.py (nib dcc-9vta). Run: python3 test_build_note.py"""
from build_note import note

fails = []


def check(name, fn):
    try:
        fn(); print(f"  PASS  {name}")
    except AssertionError as e:
        fails.append(name); print(f"  FAIL  {name}: {e}")


def t_complete_toolchain_says_so():
    n = note({"languages": ["go"], "missing_toolchains": [],
              "restore_commands": ["GOFLAGS=-mod=readonly go mod download"]})
    assert "IS available for every detected language" in n
    assert "MISSING" not in n


def t_partial_toolchain_names_what_is_missing():
    """The defect: the prompt asserted a full toolchain while cargo was absent and Rust was the
    majority language. A partial state must be distinguishable from a complete one, and must name
    the languages the reviewer cannot verify."""
    n = note({"languages": ["js", "go", "python", "rust"], "missing_toolchains": ["cargo"],
              "restore_commands": ["pnpm install --frozen-lockfile"]})
    assert "NOT all of it" in n
    assert "cargo" in n
    assert "IS available for every detected language" not in n
    assert "reasoned about statically" in n


def t_partial_warns_about_the_silent_exit_zero():
    """A cell reported a backgrounded `cargo check` as exit 0 while cargo did not exist. The prompt
    has to say that out loud, or the next cell reports the same phantom success."""
    n = note({"languages": ["rust"], "missing_toolchains": ["cargo"], "restore_commands": []})
    assert "exit code 0" in n


def t_detection_failure_is_not_read_as_no_toolchain():
    """`error` and `no languages` are different states with different advice, and collapsing them
    is how "detection broke" comes to read as "this project has no build"."""
    err = note({"error": "build detection produced no JSON"})
    none = note({"languages": [], "missing_toolchains": [], "restore_commands": []})
    assert "could NOT be determined" in err
    assert "No package manifest was detected" in none
    assert err != none


for name, fn in sorted(globals().items()):
    if name.startswith("t_"):
        check(name[2:], fn)
print(f"\n{'FAILED: ' + ', '.join(fails) if fails else 'all guards fire correctly'}")
raise SystemExit(1 if fails else 0)
