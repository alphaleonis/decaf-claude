#!/usr/bin/env bash
# Resolve a v2 subject id to its fixture, checkout and thread set, whatever kind it is.
#
# Source it, then: resolve_subject <id>
#
# v2 grew three fixture layouts, and every consumer that hard-coded one could address only a third of
# the corpus — run_cell_v2.sh resolved `v2/subjects/NN-*.json` + `v2/repos/<id>` and so could not run
# any of the 12 pooled subjects the pilot is for (dcc-3cm6).
#
#   kind    directory                      fixture              checkout          threads
#   anchor  v2/subjects/NN-<lang>-<size>   the file itself      v2/repos/<id>     none (answer key)
#   pooled  v2/pooled/<owner>-<repo>-<pr>  <dir>/fixture.json   <dir>/repo        <dir>/threads.json
#   null    v2/null/<repo>-<pr>            <dir>/fixture.json   <dir>/repo        <dir>/threads.json
#
# They differ in more than location: anchor fixtures carry `id`/`lang` and a `review` block, pooled
# carry `slug`/`app_type`/`threads.{total,admitted,rejected}`, null carry `threads.{total,not-scored}`.
# Only the fields every consumer needs are normalized here; the rest stay readable from $FIXTURE.
#
# Accepted ids: an anchor number (`2`), a pooled/null directory name (`sveltejs-kit-15685`), a slug
# (`sveltejs/kit#15685`), or a path to any of the above.

# Set by resolve_subject.
SUBJ_ID=""; SUBJ_KIND=""; SUBJ_DIR=""; FIXTURE=""; REPO_DIR=""; THREADS=""
SUBJ_REPO=""; SUBJ_PR=""; SUBJ_CP=""; SUBJ_BASE=""; SUBJ_DATE=""

resolve_subject() {
  local want="${1:?resolve_subject <id>}"
  local V2 d
  V2="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  # `owner/repo#pr` -> `owner-repo-pr`, the directory convention.
  case "$want" in */*\#*) want="$(printf '%s' "$want" | tr '/#' '--')" ;; esac
  want="${want%/}"; want="$(basename "$want")"

  SUBJ_ID="$want"; SUBJ_DIR=""; SUBJ_KIND=""
  for d in "$V2/pooled/$want" "$V2/null/$want"; do
    if [ -f "$d/fixture.json" ]; then
      SUBJ_DIR="$d"; FIXTURE="$d/fixture.json"; REPO_DIR="$d/repo"
      [ -f "$d/threads.json" ] && THREADS="$d/threads.json" || THREADS=""
      case "$d" in *"/null/"*) SUBJ_KIND="null" ;; *) SUBJ_KIND="pooled" ;; esac
      break
    fi
  done

  if [ -z "$SUBJ_DIR" ] && printf '%s' "$want" | grep -qE '^[0-9]+$'; then
    local f
    # `ls` on a glob with no match exits non-zero and prints nothing; take the first hit explicitly
    # so an absent fixture is reported as absent rather than as an empty variable downstream.
    f="$(find "$V2/subjects" -maxdepth 1 -name "$(printf %02d "$want")-*.json" 2>/dev/null | sort | head -1)"
    if [ -n "$f" ]; then
      SUBJ_KIND="anchor"; SUBJ_DIR="$V2/subjects"; FIXTURE="$f"
      REPO_DIR="$V2/repos/$want"; THREADS=""
    fi
  fi

  if [ -z "$SUBJ_KIND" ]; then
    echo "resolve_subject: no fixture for '$1'." >&2
    echo "  pooled: $(ls "$V2/pooled" 2>/dev/null | tr '\n' ' ')" >&2
    echo "  null:   $(ls "$V2/null" 2>/dev/null | tr '\n' ' ')" >&2
    echo "  anchor: $(ls "$V2/subjects" 2>/dev/null | tr '\n' ' ')" >&2
    return 4
  fi

  SUBJ_REPO="$(jq -r '.repo'            "$FIXTURE")"
  SUBJ_PR="$(  jq -r '.pr'              "$FIXTURE")"
  SUBJ_CP="$(  jq -r '.checkpoint.sha'  "$FIXTURE")"
  SUBJ_BASE="$(jq -r '.checkpoint.base' "$FIXTURE")"
  SUBJ_DATE="$(jq -r '.checkpoint.date' "$FIXTURE" | cut -c1-10)"

  local k
  for k in SUBJ_REPO SUBJ_PR SUBJ_CP SUBJ_BASE SUBJ_DATE; do
    case "${!k}" in ""|null)
      echo "resolve_subject: $FIXTURE is missing the field behind $k" >&2; return 5 ;;
    esac
  done
  return 0
}

# Every subject of every kind, one id per line — for sweeps that must not silently cover a subset.
all_subjects() {
  local V2; V2="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ls "$V2/pooled" 2>/dev/null
  ls "$V2/null" 2>/dev/null
  find "$V2/subjects" -maxdepth 1 -name '*.json' 2>/dev/null \
    | sed 's|.*/||; s|^0*||; s|-.*||' | sort -n
}
