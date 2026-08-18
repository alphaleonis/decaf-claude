#!/usr/bin/env bash
# Tests for cell_tmp.sh (nib dcc-xhku): the top-of-/tmp sweep must never remove a path belonging to
# a concurrently running cell, and must still clean the group's leftovers once the group is done.
# Runs against scratch directories via BENCH_TMP_ROOT / BENCH_TMP_REGISTRY — never touches /tmp.
set -uo pipefail
V2="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
W="$(mktemp -d)"; trap 'rm -rf "$W"; kill $(jobs -p) 2>/dev/null' EXIT
export BENCH_TMP_ROOT="$W/tmp" BENCH_TMP_REGISTRY="$W/reg" BENCH_MIN_TMP_FREE_MB=0
mkdir -p "$BENCH_TMP_ROOT"
# a repo for step 3 (worktree handling); every cell here uses its own copy
mkrepo() { local r="$1"; mkdir -p "$r"; git -C "$r" init -q; git -C "$r" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init; }
# a "live cell" = a background sleep whose pid we register
live() { sleep 600 </dev/null >/dev/null 2>&1 & echo $!; }
fails=0; pass() { echo "  PASS  $1"; }; fail() { echo "  FAIL  $1"; fails=$((fails+1)); }
pre()   { BENCH_CELL_PID="$2" bash "$V2/cell_tmp.sh" preflight "$1" "$3" >/dev/null; }
clean() { bash "$V2/cell_tmp.sh" cleanup "$1" "$2" >/dev/null; }

echo "== two concurrent cells: the first to finish must not touch the other's files"
touch "$BENCH_TMP_ROOT/preexisting"                       # in the quiescent baseline — never removed
A="$W/cellA"; B="$W/cellB"; mkdir -p "$A" "$B"; mkrepo "$W/repoA"; mkrepo "$W/repoB"
pa=$(live); pb=$(live)
pre "$A" "$pa" "$W/repoA";  touch "$BENCH_TMP_ROOT/fileA"; mkdir -p "$BENCH_TMP_ROOT/baserepoA"
pre "$B" "$pb" "$W/repoB";  touch "$BENCH_TMP_ROOT/fileB"; mkdir -p "$BENCH_TMP_ROOT/claude-harness"
grep -q '^quiescent' "$A/tmp-group.txt" && pass "first cell takes the quiescent baseline" || fail "first cell baseline"
grep -q '^joined' "$B/tmp-group.txt"    && pass "second cell joins the group"              || fail "second cell join"
clean "$A" "$W/repoA"; kill "$pa" 2>/dev/null
[ -e "$BENCH_TMP_ROOT/fileB" ]     && pass "A's cleanup left B's fileB alone"           || fail "A removed B's fileB"
[ -e "$BENCH_TMP_ROOT/fileA" ]     && pass "A deferred even its own top-level fileA (cannot attribute; B live)" || fail "A swept while B live"
grep -q '^deferred' "$A/tmp-cleanup.tsv" && pass "A's manifest records the deferral"     || fail "no deferral record"
clean "$B" "$W/repoB"; kill "$pb" 2>/dev/null
[ ! -e "$BENCH_TMP_ROOT/fileA" ] && [ ! -e "$BENCH_TMP_ROOT/fileB" ] && [ ! -e "$BENCH_TMP_ROOT/baserepoA" ] \
  && pass "B (last out) swept the whole group's leftovers"                                || fail "B did not sweep group leftovers"
[ -e "$BENCH_TMP_ROOT/preexisting" ]    && pass "baseline entry preserved"                 || fail "baseline entry removed"
[ -e "$BENCH_TMP_ROOT/claude-harness" ] && pass "PROTECT pattern honored"                  || fail "protected path removed"
[ ! -e "$BENCH_TMP_REGISTRY/baseline.txt" ] && pass "baseline consumed when the group ends" || fail "stale baseline left"

echo "== stale registration (dead pid) must not pin the sweep off"
C="$W/cellC"; mkdir -p "$C"; mkrepo "$W/repoC"
printf '%s\n%s\n' 999999 "$W/ghost" > "$BENCH_TMP_REGISTRY/ghost.cell"
pc=$(live); pre "$C" "$pc" "$W/repoC"; touch "$BENCH_TMP_ROOT/fileC"
grep -q '^quiescent' "$C/tmp-group.txt" && pass "dead registration ignored at preflight"  || fail "dead pid counted as live"
[ ! -e "$BENCH_TMP_REGISTRY/ghost.cell" ] && pass "dead registration dropped"              || fail "dead registration kept"
clean "$C" "$W/repoC"; kill "$pc" 2>/dev/null
[ ! -e "$BENCH_TMP_ROOT/fileC" ] && pass "single cell sweeps its own leftovers"           || fail "single cell did not sweep"

echo "== a cell's own TMPDIR and worktree are removed regardless of siblings"
Dd="$W/cellD"; mkdir -p "$Dd"; mkrepo "$W/repoD"; export BENCH_CELL_TMPDIR="$W/tmpdirD"; mkdir -p "$BENCH_CELL_TMPDIR/x"
git -C "$W/repoD" worktree add -q "$W/wtD" HEAD 2>/dev/null
pd=$(live); pe=$(live); pre "$Dd" "$pd" "$W/repoD"; E="$W/cellE"; mkdir -p "$E"; mkrepo "$W/repoE"; pre "$E" "$pe" "$W/repoE"
clean "$Dd" "$W/repoD"; kill "$pd" "$pe" 2>/dev/null; unset BENCH_CELL_TMPDIR
[ ! -e "$W/tmpdirD" ] && pass "own TMPDIR removed while a sibling is live"                || fail "own TMPDIR kept"
[ ! -e "$W/wtD" ]     && pass "own worktree removed while a sibling is live"              || fail "own worktree kept"
clean "$E" "$W/repoE"

echo; [ "$fails" -eq 0 ] && echo "all cell_tmp checks pass" || { echo "$fails FAILED"; exit 1; }
