#!/usr/bin/env bash
# Detect whether a subject can be built and tested, and whether restore stays date-neutral.
#
# Usage: detect_build.sh <v2/pooled/DIR>   # emits JSON on stdout
#
# Why date-neutrality matters (METHODOLOGY-v2 section 3): a package restore reaches the network, and
# an UNPINNED restore resolves "latest", which can pull a version published after the checkpoint —
# a time-boxing hole opened through the back door. A lockfile committed at the checkpoint pins exact
# versions, so a frozen restore is date-neutral by construction. Every restore command below is the
# frozen variant; a subject without a lockfile is reported `date_neutral: false` rather than built.
#
# Toolchain absence is reported, never worked around. A cell that could not build is weaker evidence
# than one that could — defects needing execution to confirm (races, ordering, hangs) are
# systematically harder to catch by reading — so the run must be identifiable, not silently degraded.
set -uo pipefail

D="${1:?usage: detect_build.sh <subject-dir|checkout-dir>}"
# Accept either the subject directory (pooled/null, which hold the checkout at <dir>/repo) or the
# checkout itself (the anchor layout puts it at v2/repos/<id>, with no wrapper). Callers used to have
# to know which, and run_cell_v2.sh guessed wrong for every cell it ran (dcc-3cm6).
if   [ -d "$D/repo/.git" ]; then R="$D/repo"
elif [ -d "$D/.git" ];      then R="$D"
else echo "{\"error\":\"no git checkout at $D or $D/repo\"}"; exit 2
fi

have() { command -v "$1" >/dev/null 2>&1; }
# corepack ships with node and provisions pnpm/yarn per-project — no system install needed.
have_pm() {
  case "$1" in
    pnpm|yarn) have "$1" || have corepack ;;
    *) have "$1" ;;
  esac
}
pm_cmd() {
  case "$1" in
    pnpm|yarn) have "$1" && echo "$1" || echo "corepack $1" ;;
    *) echo "$1" ;;
  esac
}

langs=(); managers=(); locks=(); restores=(); missing=()

# --- JavaScript / TypeScript -------------------------------------------------------------------
# Root first, then nested — a monorepo puts the lockfile beside the app, not at the top (dcc-9vta).
# Root wins when both exist: a root lockfile governs the workspace.
js_lock=""; js_pm=""
if   [ -f "$R/pnpm-lock.yaml" ];    then js_lock="pnpm-lock.yaml";    js_pm="pnpm"
elif [ -f "$R/yarn.lock" ];         then js_lock="yarn.lock";         js_pm="yarn"
elif [ -f "$R/package-lock.json" ]; then js_lock="package-lock.json"; js_pm="npm"
else
  for n in pnpm-lock.yaml yarn.lock package-lock.json; do
    found="$(find "$R" -maxdepth 3 -name "$n" 2>/dev/null | head -1)"
    if [ -n "$found" ]; then
      js_lock="${found#$R/}"
      case "$n" in pnpm-lock.yaml) js_pm="pnpm" ;; yarn.lock) js_pm="yarn" ;; *) js_pm="npm" ;; esac
      break
    fi
  done
fi
if [ -n "$js_pm" ]; then
  langs+=("js"); managers+=("$js_pm"); locks+=("$js_lock")
  case "$js_pm" in
    pnpm) restores+=("$(pm_cmd pnpm) install --frozen-lockfile") ;;
    yarn) restores+=("$(pm_cmd yarn) install --immutable") ;;
    npm)  restores+=("npm ci") ;;
  esac
  have_pm "$js_pm" || missing+=("$js_pm")
elif [ -f "$R/package.json" ]; then
  langs+=("js"); managers+=("npm"); locks+=(""); restores+=("")
fi

# --- Go ----------------------------------------------------------------------------------------
# Suppressions throughout this script are justified: `find` and `jq` here answer "does this
# project have X", and absence is the answer, not a failure. Every absence reaches the output
# as `date_neutral: false`, a `missing_toolchains` entry, or `build_possible: false` — the
# script reports what it could not do rather than degrading quietly (dcc-fhp1).
gosum="$(find "$R" -maxdepth 3 -name go.sum 2>/dev/null | head -1)"
if [ -n "$gosum" ]; then
  langs+=("go"); managers+=("go"); locks+=("${gosum#$R/}")
  # -mod=readonly refuses to mutate go.mod/go.sum, so the pinned set cannot drift during restore.
  restores+=("GOFLAGS=-mod=readonly go mod download")
  have go || missing+=("go")
fi

# --- .NET --------------------------------------------------------------------------------------
dotnet_pin=""
[ -f "$R/Directory.Packages.props" ] && dotnet_pin="Directory.Packages.props"
[ -z "$dotnet_pin" ] && [ -f "$R/eng/Versions.props" ] && dotnet_pin="eng/Versions.props"
[ -z "$dotnet_pin" ] && [ -n "$(find "$R" -maxdepth 3 -name packages.lock.json 2>/dev/null | head -1)" ] \
  && dotnet_pin="packages.lock.json"
if [ -n "$dotnet_pin" ] || [ -n "$(find "$R" -maxdepth 2 -name '*.slnx' -o -maxdepth 2 -name '*.sln' 2>/dev/null | head -1)" ]; then
  langs+=("dotnet"); managers+=("dotnet"); locks+=("$dotnet_pin")
  # Central package management pins exact versions; --locked-mode applies when a real lockfile exists.
  if [ "$dotnet_pin" = "packages.lock.json" ]; then
    restores+=("dotnet restore --locked-mode")
  else
    restores+=("dotnet restore")
  fi
  if have dotnet; then
    # Having `dotnet` is not the same as being able to build: global.json pins an SDK, and the
    # rollForward policy decides whether an installed SDK may serve it. Observed: jellyfin pins
    # 8.0.0 with rollForward=latestMinor, which SDK 10.0.203 cannot satisfy, while efcore pins a
    # 9.0 preview with latestMajor, which it can. A cell that discovers this at runtime silently
    # degrades to static analysis, so detect it here instead.
    if [ -f "$R/global.json" ] && ! (cd "$R" && dotnet --version >/dev/null 2>&1); then
      want="$(jq -r '"\(.sdk.version // "?") rollForward=\(.sdk.rollForward // "unset")"' "$R/global.json" 2>/dev/null)"
      missing+=("dotnet-sdk($want)")
    fi
  else
    missing+=("dotnet")
  fi
fi

# --- Python ------------------------------------------------------------------------------------
py_lock=""
[ -f "$R/uv.lock" ] && py_lock="uv.lock"
[ -z "$py_lock" ] && [ -f "$R/poetry.lock" ] && py_lock="poetry.lock"
# Nested, same reasoning as Rust and js above (dcc-9vta).
[ -z "$py_lock" ] && py_lock="$(find "$R" -maxdepth 3 \( -name uv.lock -o -name poetry.lock \) 2>/dev/null | head -1)"
py_lock="${py_lock#$R/}"
if [ -n "$py_lock" ]; then
  langs+=("python"); managers+=("$(basename "${py_lock%%.*}")"); locks+=("$py_lock")
  case "$(basename "$py_lock")" in
    uv.lock)     restores+=("uv sync --frozen");        have uv     || missing+=("uv") ;;
    poetry.lock) restores+=("poetry install --sync");   have poetry || missing+=("poetry") ;;
  esac
fi

# --- Rust --------------------------------------------------------------------------------------
# Nested-aware, matching the Go idiom above (dcc-9vta). Root-only detection reported
# `languages:[js,go,python]`, `missing_toolchains:[]` and `build_possible:true` for a subject whose
# Rust lives under `rust/` and is 13 of its 18 changed files — with cargo not installed. The cell
# prompt then told every reviewer a build toolchain was available for the majority language, and two
# cells independently recorded working around its absence.
cargolock="$(find "$R" -maxdepth 3 -name Cargo.lock 2>/dev/null | head -1)"
if [ -n "$cargolock" ]; then
  langs+=("rust"); managers+=("cargo"); locks+=("${cargolock#$R/}")
  restores+=("cargo fetch --locked")
  have cargo || missing+=("cargo")
fi

# date_neutral: every detected language has a pinned dependency set.
date_neutral=true
for l in ${locks[@]+"${locks[@]}"}; do [ -z "$l" ] && date_neutral=false; done
[ ${#langs[@]} -eq 0 ] && date_neutral=false

build_possible=true
[ ${#missing[@]} -gt 0 ] && build_possible=false
[ "$date_neutral" = false ] && build_possible=false

jq -n \
  --argjson langs    "$(printf '%s\n' ${langs[@]+"${langs[@]}"}    | jq -R 'select(length>0)' | jq -s .)" \
  --argjson managers "$(printf '%s\n' ${managers[@]+"${managers[@]}"} | jq -R 'select(length>0)' | jq -s .)" \
  --argjson locks    "$(printf '%s\n' ${locks[@]+"${locks[@]}"}    | jq -R 'select(length>0)' | jq -s .)" \
  --argjson restores "$(printf '%s\n' ${restores[@]+"${restores[@]}"} | jq -R 'select(length>0)' | jq -s .)" \
  --argjson missing  "$(printf '%s\n' ${missing[@]+"${missing[@]}"}  | jq -R 'select(length>0)' | jq -s .)" \
  --argjson dn "$date_neutral" --argjson bp "$build_possible" \
  '{languages:$langs, package_managers:$managers, lockfiles:$locks, restore_commands:$restores,
    missing_toolchains:$missing, date_neutral:$dn, build_possible:$bp}'
