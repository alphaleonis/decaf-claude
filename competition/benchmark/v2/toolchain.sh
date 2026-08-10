#!/usr/bin/env bash
# Make the build toolchains reachable from a benchmark cell (nib dcc-fhp1). Source, do not execute.
#
# The toolchains are installed via mise, which activates per interactive shell. A cell launched by
# the harness gets a NON-interactive shell, so it inherits a PATH where `go` and `dotnet` are absent
# even though both are installed — observed exactly that: /usr/local/go/bin is on PATH and empty,
# while the real go lives in the mise shims, and ~/.dotnet/tools is on PATH while the dotnet binary
# sits one level up in ~/.dotnet.
#
# Left unfixed, every cell reports "no toolchain" and the benchmark silently measures static-analysis
# review only — biasing against defects that need execution to confirm.
#
# ORDERING: these paths are PREPENDED, because appending let a node already on PATH win and the pin
# silently did nothing. Callers must therefore source this FIRST and add the benchmark shim dir
# afterwards, so the time-boxed `gh` still resolves to the shim. None of these dirs provides `gh`.

# Node is pinned deliberately, not inherited. mise shims do NOT honour a project's .nvmrc — every
# checkout resolves to the mise default (observed: v25.9.0 everywhere) — while grafana and PostHog
# declare engines ">=22 <25" and would be built by a Node their own CI rejects. 24.19.0 is the
# newest installed version satisfying all 12 subjects' constraints, so it is held constant across
# the corpus for the same reason BENCH_MODEL and BENCH_EFFORT are.
BENCH_NODE_VERSION="${BENCH_NODE_VERSION:-24.19.0}"
_node_dir="$HOME/.local/share/mise/installs/node/$BENCH_NODE_VERSION/bin"

_tc=()
[ -d "$_node_dir" ] && _tc+=("$_node_dir")                                        # pinned node first
[ -d "$HOME/.local/share/mise/shims" ] && _tc+=("$HOME/.local/share/mise/shims")   # go, python, uv
[ -x "$HOME/.dotnet/dotnet" ]          && _tc+=("$HOME/.dotnet")                    # dotnet SDK
[ -d "$HOME/.cargo/bin" ]              && _tc+=("$HOME/.cargo/bin")                 # cargo, rustc

if [ ${#_tc[@]} -gt 0 ]; then
  BENCH_TOOLCHAIN_PATH="$(IFS=:; echo "${_tc[*]}")"
  export BENCH_TOOLCHAIN_PATH
  export PATH="$BENCH_TOOLCHAIN_PATH:$PATH"
fi
export BENCH_NODE_VERSION
unset _tc _node_dir
