#!/usr/bin/env bash
# Keep a cell's temporary files off tmpfs, and clean up what it leaves (nib dcc-vkeh).
#
# Usage: cell_tmp.sh preflight <cell-dir> <repo-dir>   # refuse if tmpfs is already tight; snapshot
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
# Removal is scoped to what THIS cell created: a snapshot is taken before the run and only entries
# absent from it are touched, never a blanket wipe of /tmp. Everything removed is recorded.
set -uo pipefail

MODE="${1:?usage: cell_tmp.sh preflight|cleanup <cell-dir> <repo-dir>}"
D="${2:?cell-dir required}"
REPO="${3:?repo-dir required}"

# Refuse to start a cell with less than this free on tmpfs. A cell needs room for a checkout plus
# build output; starting one at 2G free buys a 40-minute hang instead of an immediate, legible stop.
# Overridable so the refusal path can be exercised without filling 7.8G of RAM to test it.
MIN_TMP_FREE_MB="${BENCH_MIN_TMP_FREE_MB:-4096}"

# Never remove these even if they appear during the cell: they belong to the system or to the
# harness driving the run.
PROTECT='^(systemd-private-|snap-private-tmp$|\.X11-unix$|\.ICE-unix$|\.font-unix$|\.XIM-unix$|\.Test-unix$|claude-)'

tmp_free_mb() { df -Pm /tmp | awk 'NR==2{print $4}'; }

case "$MODE" in
  preflight)
    free_mb="$(tmp_free_mb)"
    ls -A /tmp > "$D/tmp-before.txt" 2>/dev/null
    echo "$free_mb" > "$D/tmp-free-before.txt"
    if [ "${free_mb:-0}" -lt "$MIN_TMP_FREE_MB" ]; then
      echo "REFUSING: /tmp has ${free_mb}MB free, under the ${MIN_TMP_FREE_MB}MB floor." >&2
      echo "  /tmp is tmpfs (RAM). A cell started this tight will exhaust memory mid-build and abort" >&2
      echo "  after spending. Free it first: v2/cell_tmp.sh cleanup <any-cell-dir> <repo>, or reboot WSL." >&2
      exit 80
    fi
    ;;

  cleanup)
    MANIFEST="$D/tmp-cleanup.tsv"
    printf 'action\tpath\tsize_kb\n' > "$MANIFEST"
    before_mb="$(cat "$D/tmp-free-before.txt" 2>/dev/null || echo 0)"

    # 1. This cell's own TMPDIR, which the runner created on disk and owns outright.
    if [ -n "${BENCH_CELL_TMPDIR:-}" ] && [ -d "${BENCH_CELL_TMPDIR:-}" ]; then
      sz=$(du -sk "$BENCH_CELL_TMPDIR" 2>/dev/null | cut -f1)
      rm -rf "$BENCH_CELL_TMPDIR" && printf 'removed\t%s\t%s\n' "$BENCH_CELL_TMPDIR" "${sz:-?}" >> "$MANIFEST"
    fi

    # 2. The cell's own Claude Code scratchpad, keyed by its working directory. Named explicitly
    #    because it lives INSIDE /tmp/claude-*/ which the protect list keeps — the parent is the
    #    harness's, this child is the cell's.
    slug="$(cd "$REPO" 2>/dev/null && pwd -P | tr '/' '-')"
    if [ -n "$slug" ]; then
      for cs in /tmp/claude-*/"$slug"; do
        [ -d "$cs" ] || continue
        sz=$(du -sk "$cs" 2>/dev/null | cut -f1)
        rm -rf "$cs" && printf 'removed\t%s\t%s\n' "$cs" "${sz:-?}" >> "$MANIFEST"
      done
    fi

    # 3. Git worktrees the tool registered outside the checkout. reset_repo() also does this before
    #    the NEXT cell; doing it here too returns the RAM immediately rather than holding it until
    #    something else runs.
    main_wt="$(cd "$REPO" && pwd -P)"
    while read -r wt; do
      [ -z "$wt" ] && continue
      [ "$wt" = "$main_wt" ] && continue
      sz=$(du -sk "$wt" 2>/dev/null | cut -f1)
      git -C "$REPO" worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
      printf 'removed\t%s\t%s\tworktree\n' "$wt" "${sz:-0}" >> "$MANIFEST"
    done < <(git -C "$REPO" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}')
    git -C "$REPO" worktree prune 2>/dev/null || true

    # 4. Anything else this cell created at the top of /tmp. Scoped by diff against the pre-run
    #    snapshot, so a blanket wipe is impossible and another process's files are never in scope.
    if [ -f "$D/tmp-before.txt" ]; then
      while IFS= read -r name; do
        [ -z "$name" ] && continue
        printf '%s\n' "$name" | grep -qE "$PROTECT" && continue
        grep -qxF "$name" "$D/tmp-before.txt" && continue
        p="/tmp/$name"
        [ -O "$p" ] || { printf 'kept\t%s\t\tnot owned by this user\n' "$p" >> "$MANIFEST"; continue; }
        sz=$(du -sk "$p" 2>/dev/null | cut -f1)
        rm -rf "$p" && printf 'removed\t%s\t%s\tcreated during the cell\n' "$p" "${sz:-?}" >> "$MANIFEST"
      done < <(ls -A /tmp 2>/dev/null)
    else
      printf 'error\t\t\tno tmp-before.txt — preflight did not run, /tmp not swept\n' >> "$MANIFEST"
    fi

    after_mb="$(tmp_free_mb)"
    freed=$(( after_mb - before_mb ))
    n=$(grep -c '^removed' "$MANIFEST" || true)
    echo "[$(basename "$D")] tmp cleanup: ${n:-0} path(s) removed, /tmp free ${before_mb}MB -> ${after_mb}MB (+${freed}MB)"
    ;;

  *) echo "unknown mode: $MODE" >&2; exit 2 ;;
esac
