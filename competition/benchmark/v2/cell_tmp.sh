#!/usr/bin/env bash
# Keep a cell's temporary files off tmpfs, and clean up what it leaves (nibs dcc-vkeh, dcc-xhku).
#
# Usage: cell_tmp.sh preflight <cell-dir> <repo-dir>   # refuse if tmpfs is already tight; register; snapshot
#        cell_tmp.sh cleanup   <cell-dir> <repo-dir>   # remove what this cell created; report freed
#
# WHY THIS EXISTS
#
# On WSL `/tmp` is tmpfs — RAM, 7.8G against 15Gi total. Review tools build the subject there: the
# comprehensive-review cell on prometheus checked out TWO full worktrees of a 14,360-commit repo
# (/tmp/cr-base, /tmp/cr-head) and built Go output beside them. tmpfs filled, the machine ran out of
# memory, Claude Code stopped responding and the cell aborted after 62 minutes with $18.68 spent and
# no output at all.
#
# Nothing in the harness could see it coming, and the failure does not look like resource exhaustion
# from the artifacts — it looks like a cell that produced nothing.
#
# Two defenses, because neither is sufficient alone:
#   TMPDIR    points at disk, which redirects every tool that respects it (most do).
#   cleanup   removes what is left anyway, because a tool that hard-codes `/tmp/cr-base` — as
#             comprehensive-review does — ignores TMPDIR entirely.
#
# CONCURRENCY (dcc-xhku)
#
# The first version scoped the top-of-/tmp sweep by differencing a per-cell snapshot: anything absent
# from "what /tmp held when this cell started" was treated as this cell's. That is only true when one
# cell runs at a time. With two cells overlapping, the first to finish deleted the other's live build
# artifacts (efcore's cleanup removed prometheus's /tmp/baserepo, its probes and its diffs; the
# prometheus cell was lost after $17.61). Nothing at the top of /tmp records which process created it,
# so ownership cannot be reconstructed after the fact.
#
# The sweep is therefore scoped by a LIVE-CELL REGISTRY instead of a per-cell snapshot:
#   - preflight registers the cell (pid, cell dir). If no other cell is live, it takes the QUIESCENT
#     BASELINE — what /tmp holds when nothing is running — into the shared registry dir. Cells that
#     join a running group inherit that baseline.
#   - cleanup steps 1–3 remove only what is provably the cell's own (its TMPDIR, its Claude
#     scratchpad keyed by repo slug, its repo's worktrees). Step 4 — the top-of-/tmp sweep — runs only
#     when this cell is the LAST live cell, and then removes everything absent from the quiescent
#     baseline: the whole group's leftovers, once the group is done. A cell that finishes while
#     siblings are live DEFERS the sweep and says so in its manifest; it never touches a path it
#     cannot attribute.
#   - Registrations whose pid is dead are dropped on every lookup, so a cell that crashed without
#     cleanup cannot pin the sweep off forever. If /tmp is not tmpfs (disk-backed), leftovers only
#     cost disk, and the sweep is still correct — it just matters less.
#
# Everything removed, kept, or deferred is recorded in the cell's tmp-cleanup.tsv.
#
# BENCH_TMP_ROOT (default /tmp) and BENCH_TMP_REGISTRY (default /var/tmp/bench-v2/live-cells) exist so
# the two-cell case can be tested against a scratch directory (test_cell_tmp.sh).
set -uo pipefail

MODE="${1:?usage: cell_tmp.sh preflight|cleanup <cell-dir> <repo-dir>}"
D="${2:?cell-dir required}"
REPO="${3:?repo-dir required}"

TMPROOT="${BENCH_TMP_ROOT:-/tmp}"
REG="${BENCH_TMP_REGISTRY:-/var/tmp/bench-v2/live-cells}"
BASELINE="$REG/baseline.txt"
LOCK="$REG/.lock"

# Refuse to start a cell with less than this free on tmpfs. A cell needs room for a checkout plus
# build output; starting one at 2G free buys a 40-minute hang instead of an immediate, legible stop.
# Overridable so the refusal path can be exercised without filling 7.8G of RAM to test it.
MIN_TMP_FREE_MB="${BENCH_MIN_TMP_FREE_MB:-4096}"

# Never remove these even if they appear during the cell: they belong to the system or to the
# harness driving the run.
PROTECT='^(systemd-private-|snap-private-tmp$|\.X11-unix$|\.ICE-unix$|\.font-unix$|\.XIM-unix$|\.Test-unix$|claude-)'

tmp_free_mb() { df -Pm "$TMPROOT" | awk 'NR==2{print $4}'; }

# A cell's registration file. Cell dirs are unique per (subject, tool, shim, repeat).
cell_id() { basename "$D"; }
reg_file() { echo "$REG/$(cell_id).cell"; }

# Drop registrations whose recorded pid is gone. Runs under the lock. Prints the ids still live,
# excluding this cell's own.
other_live_cells() {
  local f pid id
  for f in "$REG"/*.cell; do
    [ -e "$f" ] || continue
    id="$(basename "$f" .cell)"
    pid="$(head -1 "$f" 2>/dev/null)"
    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$f"; continue
    fi
    [ "$id" = "$(cell_id)" ] && continue
    echo "$id"
  done
}

with_lock() {
  mkdir -p "$REG"
  if command -v flock >/dev/null 2>&1; then
    ( flock -w 30 9 || { echo "cell_tmp: could not take $LOCK within 30s" >&2; exit 1; }; "$@" ) 9>"$LOCK"
  else
    "$@"
  fi
}

do_preflight() {
  local free_mb others
  free_mb="$(tmp_free_mb)"
  ls -A "$TMPROOT" > "$D/tmp-before.txt" 2>/dev/null
  echo "$free_mb" > "$D/tmp-free-before.txt"
  if [ "${free_mb:-0}" -lt "$MIN_TMP_FREE_MB" ]; then
    echo "REFUSING: $TMPROOT has ${free_mb}MB free, under the ${MIN_TMP_FREE_MB}MB floor." >&2
    echo "  A cell started this tight will exhaust the filesystem mid-build and abort after spending." >&2
    echo "  Free it first: v2/cell_tmp.sh cleanup <any-cell-dir> <repo>, or reboot WSL." >&2
    exit 80
  fi
  others="$(other_live_cells)"
  if [ -z "$others" ]; then
    # Nothing else is running: this is the quiescent state. Everything present now is not ours.
    cp "$D/tmp-before.txt" "$BASELINE"
    echo "quiescent" > "$D/tmp-group.txt"
  else
    # Joining a running group: inherit its baseline; anything we create is swept by the last one out.
    printf 'joined\t%s\n' "$(echo "$others" | tr '\n' ',')" > "$D/tmp-group.txt"
  fi
  # BENCH_CELL_PID lets the runner register the process that will outlive this helper (the runner
  # itself); the helper's own pid dies immediately and would read as a stale registration.
  printf '%s\n%s\n' "${BENCH_CELL_PID:-$PPID}" "$D" > "$(reg_file)"
}

do_cleanup() {
  MANIFEST="$D/tmp-cleanup.tsv"
  printf 'action\tpath\tsize_kb\tnote\n' > "$MANIFEST"
  before_mb="$(cat "$D/tmp-free-before.txt" 2>/dev/null || echo 0)"

  # 1. This cell's own TMPDIR, which the runner created on disk and owns outright.
  if [ -n "${BENCH_CELL_TMPDIR:-}" ] && [ -d "${BENCH_CELL_TMPDIR:-}" ]; then
    sz=$(du -sk "$BENCH_CELL_TMPDIR" 2>/dev/null | cut -f1)
    rm -rf "$BENCH_CELL_TMPDIR" && printf 'removed\t%s\t%s\town TMPDIR\n' "$BENCH_CELL_TMPDIR" "${sz:-?}" >> "$MANIFEST"
  fi

  # 2. The cell's own Claude Code scratchpad, keyed by its working directory. Named explicitly
  #    because it lives INSIDE $TMPROOT/claude-*/ which the protect list keeps — the parent is the
  #    harness's, this child is the cell's. Two cells never share a repo checkout (the runner
  #    refuses same-subject overlap), so the slug is cell-specific.
  slug="$(cd "$REPO" 2>/dev/null && pwd -P | tr '/' '-')"
  if [ -n "$slug" ]; then
    for cs in "$TMPROOT"/claude-*/"$slug"; do
      [ -d "$cs" ] || continue
      sz=$(du -sk "$cs" 2>/dev/null | cut -f1)
      rm -rf "$cs" && printf 'removed\t%s\t%s\town scratchpad\n' "$cs" "${sz:-?}" >> "$MANIFEST"
    done
  fi

  # 3. Git worktrees the tool registered outside the checkout. reset_repo() also does this before
  #    the NEXT cell; doing it here too returns the space immediately rather than holding it until
  #    something else runs. Scoped to this cell's own repo, so concurrency-safe.
  main_wt="$(cd "$REPO" 2>/dev/null && pwd -P)"
  if [ -n "$main_wt" ]; then
    while read -r wt; do
      [ -z "$wt" ] && continue
      [ "$wt" = "$main_wt" ] && continue
      sz=$(du -sk "$wt" 2>/dev/null | cut -f1)
      git -C "$REPO" worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
      printf 'removed\t%s\t%s\tworktree\n' "$wt" "${sz:-0}" >> "$MANIFEST"
    done < <(git -C "$REPO" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}')
    git -C "$REPO" worktree prune 2>/dev/null || true
  fi

  # 4. Anything else the GROUP created at the top of $TMPROOT — only when this cell is the last one
  #    live, and only against the quiescent baseline. Deregister first so a crash mid-sweep does not
  #    leave us counted as live.
  rm -f "$(reg_file)"
  others="$(other_live_cells)"
  if [ -n "$others" ]; then
    printf 'deferred\t%s\t\ttop-of-%s sweep skipped: %s still live — the last cell out sweeps the group\n' \
      "$TMPROOT" "$TMPROOT" "$(echo "$others" | tr '\n' ',')" >> "$MANIFEST"
  elif [ -f "$BASELINE" ]; then
    while IFS= read -r name; do
      [ -z "$name" ] && continue
      printf '%s\n' "$name" | grep -qE "$PROTECT" && continue
      grep -qxF "$name" "$BASELINE" && continue
      p="$TMPROOT/$name"
      [ -O "$p" ] || { printf 'kept\t%s\t\tnot owned by this user\n' "$p" >> "$MANIFEST"; continue; }
      sz=$(du -sk "$p" 2>/dev/null | cut -f1)
      rm -rf "$p" && printf 'removed\t%s\t%s\tcreated during the group (absent from quiescent baseline)\n' "$p" "${sz:-?}" >> "$MANIFEST"
    done < <(ls -A "$TMPROOT" 2>/dev/null)
    rm -f "$BASELINE"
  else
    printf 'error\t\t\tno quiescent baseline — preflight did not run, %s not swept\n' "$TMPROOT" >> "$MANIFEST"
  fi

  after_mb="$(tmp_free_mb)"
  freed=$(( after_mb - before_mb ))
  n=$(grep -c '^removed' "$MANIFEST" || true)
  d=$(grep -c '^deferred' "$MANIFEST" || true)
  suffix=""; [ "${d:-0}" -gt 0 ] && suffix=", top-level sweep deferred (siblings live)"
  echo "[$(basename "$D")] tmp cleanup: ${n:-0} path(s) removed${suffix}, $TMPROOT free ${before_mb}MB -> ${after_mb}MB (+${freed}MB)"
}

case "$MODE" in
  preflight) with_lock do_preflight ;;
  cleanup)   with_lock do_cleanup ;;
  *) echo "unknown mode: $MODE" >&2; exit 2 ;;
esac
