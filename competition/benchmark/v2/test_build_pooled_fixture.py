#!/usr/bin/env python3
"""Self-tests for build_pooled_fixture.py. Run: python3 test_build_pooled_fixture.py

Same rule as the scoring suites: a guard without a test is a guard that has not been shown to fire.
"""
from build_pooled_fixture import require_nonempty_diff, changed_line_ranges

fails = []


def check(name, fn):
    try:
        fn(); print(f"  PASS  {name}")
    except AssertionError as e:
        fails.append(name); print(f"  FAIL  {name}: {e}")


def t_empty_checkpoint_diff_refuses_to_write_a_fixture():
    """The failure this exists for: a base that resolves to the checkpoint itself yields an empty
    compare, and the fixture that got written from it had 0 files and 0 admitted threads — which
    reads exactly like a real subject nobody reviewed."""
    try:
        require_nonempty_diff({}, "acme/widget#1", "a" * 40, "b" * 40)
    except SystemExit as e:
        assert "EMPTY" in str(e) and "ancestor of its own base" in str(e), str(e)
        return
    raise AssertionError("accepted an empty checkpoint diff")


def t_nonempty_diff_passes():
    require_nonempty_diff({"a.py": [(1, 5)]}, "acme/widget#1", "a" * 40, "b" * 40)


def t_changed_line_ranges_reads_the_new_file_side():
    """Admission tests the thread's line against the NEW file, so the ranges must come from the
    `+` side of each hunk header, not the `-` side."""
    patch = "@@ -10,3 +20,4 @@\n ctx\n+add\n@@ -50 +99 @@\n-x\n+y\n"
    assert changed_line_ranges(patch) == [(20, 23), (99, 99)], changed_line_ranges(patch)


for name, fn in sorted(globals().items()):
    if name.startswith("t_"):
        check(name[2:], fn)
print(f"\n{'FAILED: ' + ', '.join(fails) if fails else 'all guards fire correctly'}")
raise SystemExit(1 if fails else 0)
