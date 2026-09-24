#!/usr/bin/env bash
# Checks drive.sh's decisions against a fake `claude` that writes scripted
# state.json outcomes. Needs bash and jq; makes no model calls.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
driver="$here/drive.sh"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

mkdir -p "$work/bin"
cat >"$work/bin/claude" <<'FAKE'
#!/usr/bin/env bash
# Performs the next scripted action from $FAKE_DIR/script and records its arguments.
set -euo pipefail
n=$(( $(cat "$FAKE_DIR/calls" 2>/dev/null || echo 0) + 1 ))
echo "$n" >"$FAKE_DIR/calls"
printf '%s\n' "$*" >>"$FAKE_DIR/args"
action=$(sed -n "${n}p" "$FAKE_DIR/script")
mkdir -p .decaf/auto-deliver
case $action in
  lap-limit | complete | escalated)
    printf '{"step":"SELECT","exit":"%s","updated_at":"t%s"}\n' "$action" "$n" >.decaf/auto-deliver/state.json ;;
  noexit)
    printf '{"step":"SELECT","updated_at":"t%s"}\n' "$n" >.decaf/auto-deliver/state.json ;;
  nochange) ;;
  fail)
    echo '{"total_cost_usd":0.01,"is_error":true}'
    exit 1 ;;
  *)
    echo "fake claude: no scripted action for call $n" >&2
    exit 99 ;;
esac
echo '{"total_cost_usd":0.01,"result":"ok"}'
FAKE
chmod +x "$work/bin/claude"

passed=0
failed=0
check() {
  local name=$1 ok=$2 detail=$3
  if [[ $ok == yes ]]; then
    passed=$((passed + 1))
    echo "ok   $name"
  else
    failed=$((failed + 1))
    echo "FAIL $name: $detail"
  fi
}

# run_case NAME WANT_RC WANT_CALLS "ACTIONS" INITIAL_STATE [driver args...]
run_case() {
  local name=$1 want_rc=$2 want_calls=$3 actions=$4 initial=$5
  shift 5
  local dir="$work/$name"
  mkdir -p "$dir/proj"
  tr ' ' '\n' <<<"$actions" >"$dir/script"
  if [[ -n $initial ]]; then
    mkdir -p "$dir/proj/.decaf/auto-deliver"
    printf '%s\n' "$initial" >"$dir/proj/.decaf/auto-deliver/state.json"
  fi
  local rc=0
  (cd "$dir/proj" && FAKE_DIR="$dir" PATH="$work/bin:$PATH" bash "$driver" "$@" 2>/dev/null) || rc=$?
  local calls
  calls=$(cat "$dir/calls" 2>/dev/null || echo 0)
  if [[ $rc == "$want_rc" && $calls == "$want_calls" ]]; then
    check "$name" yes ""
  else
    check "$name" no "exit $rc (want $want_rc), claude runs $calls (want $want_calls)"
  fi
}

run_case lap-then-complete   0 2 "lap-limit complete"            "" P1
run_case escalated           2 1 "escalated"                     "" P1
run_case stale-state         3 1 "nochange" '{"exit":"complete","updated_at":"old"}' P1
run_case no-exit-field       3 1 "noexit"                        "" P1
run_case claude-fails        5 1 "fail"                          "" P1
run_case max-laps            4 2 "lap-limit lap-limit lap-limit" "" P1 --max-laps 2
run_case no-plan             1 0 ""                              ""
run_case bad-max-laps        1 0 ""                              "" P1 --max-laps 0
run_case forwarding          0 1 "complete"                      "" P1 --tracker ado --models low \
  --review "review roster=4" --lap-budget 5 --max-turns 40

args=$(cat "$work/forwarding/args")
for want in "-p" "--laps 1" "--tracker ado" "--models low" '--review "review roster=4"' \
  "--permission-prompts none" "--output-format json" "--max-budget-usd 5" "--max-turns 40"; do
  if grep -qF -- "$want" <<<"$args"; then
    check "forwards $want" yes ""
  else
    check "forwards $want" no "missing from: $args"
  fi
done
if grep -qF -- "--bare" <<<"$args"; then
  check "never passes --bare" no "found in: $args"
else
  check "never passes --bare" yes ""
fi

echo "$passed passed, $failed failed"
((failed == 0))
