#!/usr/bin/env bash
# Benchmark v2 progress: what has run, what it cost, and what must not be scored (nib dcc-j21q).
#
# Usage: status.sh [--arm on|off] [--json]
#
# Read-only. Reports per subject x repeat, and names every cell that is INELIGIBLE for scoring —
# an empty output, a non-zero exit, an API error, or an isolation verdict that is not CLEAN. Those
# four are distinct failures with distinct remedies, so they are never collapsed into one "failed"
# count (CLAUDE.md: empty is not the same as failed, and neither is partial).
set -uo pipefail
V2="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARM="on"; JSON=0
while [ $# -gt 0 ]; do
  case "$1" in
    --arm) ARM="${2:?--arm needs on|off}"; shift 2 ;;
    --json) JSON=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

python3 - "$V2" "$ARM" "$JSON" <<'PY'
import json, os, re, sys, glob
v2, arm, as_json = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
rows = []
for d in sorted(glob.glob(os.path.join(v2, "runs", f"*__shim-{arm}__r*"))):
    b = os.path.basename(d)
    m = re.match(rf"(.+?)__(.+?)__shim-{arm}__r(\d+)$", b)
    if not m:
        continue
    subj, tool, rep = m.group(1), m.group(2), int(m.group(3))
    meter = os.path.join(d, "meter.json")
    r = {"subject": subj, "tool": tool, "repeat": rep, "dir": b,
         "cost": None, "is_error": None, "api_error": None, "isolation": None,
         "report_chars": 0, "artifacts": 0, "eligible": False, "why": []}
    if os.path.exists(meter):
        try:
            j = json.load(open(meter))
            r["cost"] = j.get("total_cost_usd")
            r["is_error"] = bool(j.get("is_error"))
            r["api_error"] = j.get("api_error_status")
        except Exception:
            r["why"].append("meter.json unparseable")
    else:
        r["why"].append("no meter.json")
    for name, key in (("cell-report.md", "report_chars"),):
        p = os.path.join(d, name)
        r[key] = os.path.getsize(p) if os.path.exists(p) else 0
    fo = os.path.join(d, "final-output.md")
    if not (os.path.exists(fo) and os.path.getsize(fo) > 0):
        r["why"].append("empty final-output.md")
    iso = os.path.join(d, "isolation.txt")
    if os.path.exists(iso):
        head = open(iso, errors="ignore").read()
        r["isolation"] = ("CLEAN" if "\nCLEAN:" in head or head.startswith("CLEAN")
                          else "CONTAMINATED" if "CONTAMINATED" in head
                          else "NETWORK-GIT" if "NETWORK GIT" in head else "UNVERIFIED")
    else:
        r["isolation"] = "MISSING"
    tsv = os.path.join(d, "tool-artifacts.tsv")
    if os.path.exists(tsv):
        r["artifacts"] = sum(1 for l in open(tsv) if l.startswith("copied"))
    # r0 is the probe convention: a cell run to prove a tool's invocation works before the matrix
    # spends. Probes predate whatever fix the probing found, so they are never scored — and an
    # eligible-looking probe row is exactly how one would end up in a pooled analysis.
    if rep == 0:
        r["why"].append("probe cell (r0) — never scored")
    if r["is_error"]:
        r["why"].append(f"api {r['api_error']}" if r["api_error"] else "cell errored")
    if r["isolation"] not in ("CLEAN",):
        r["why"].append(f"isolation {r['isolation']}")
    r["eligible"] = not r["why"]
    rows.append(r)

if as_json:
    print(json.dumps(rows, indent=2)); sys.exit(0)

if not rows:
    print(f"No cells found for the shim-{arm} arm."); sys.exit(0)

blocks = {}
for r in rows:
    blocks.setdefault((r["subject"], r["repeat"]), []).append(r)
print(f"benchmark v2 — shim-{arm} arm\n")
print(f"{'subject':<32}{'rep':>4}{'cells':>7}{'ok':>5}{'bad':>5}{'cost':>10}")
tot = ok = bad = 0; cost = 0.0
for (subj, rep), rs in sorted(blocks.items()):
    o = sum(1 for r in rs if r["eligible"]); c = sum(r["cost"] or 0 for r in rs)
    print(f"{subj:<32}{rep:>4}{len(rs):>7}{o:>5}{len(rs)-o:>5}{c:>10.2f}")
    tot += len(rs); ok += o; bad += len(rs) - o; cost += c
print(f"{'TOTAL':<32}{'':>4}{tot:>7}{ok:>5}{bad:>5}{cost:>10.2f}")

ineligible = [r for r in rows if not r["eligible"]]
if ineligible:
    print(f"\nDO NOT SCORE — {len(ineligible)} cell(s):")
    for r in ineligible:
        print(f"  {r['dir']}\n      {'; '.join(r['why'])}")
else:
    print("\nevery cell is eligible to score")

scored = []
for sd in glob.glob(os.path.join(v2, "pooled", "*")) + glob.glob(os.path.join(v2, "null", "*")):
    if os.path.exists(os.path.join(sd, "metrics.json")):
        p2 = os.path.exists(os.path.join(sd, "grading", "metrics-pass2.json"))
        scored.append((os.path.basename(sd), 2 if p2 else 1))
if scored:
    print("\nscored subjects:")
    for s, passes in sorted(scored):
        warn = "" if passes >= 2 else "   <- single pass; per-tool figures not publishable"
        print(f"  {s:<34} {passes} grading pass(es){warn}")

# Which subjects may be POOLED, shown where a person planning a run will see it (dcc-856n). Vintage
# used to surface only at analysis time, after the money was gone. Both keys are shown (dcc-60qk):
# `merged_at` gates, `pr_created_at` is disclosure — an open PR's diff and threads were public from
# the day it opened, so a subject can clear the gate and still have been visible to the model.
sys.path.insert(0, os.path.join(v2, "scoring"))
try:
    import vintage
except Exception:
    vintage = None
if vintage:
    MODEL = os.environ.get("BENCH_MODEL", "claude-opus-5")
    fx = []
    for f in sorted(glob.glob(os.path.join(v2, "pooled", "*", "fixture.json"))):
        try:
            j = json.load(open(f))
        except Exception:
            continue
        if not j.get("merged_at"):
            continue
        d = vintage.describe(j["merged_at"], MODEL, j.get("pr_created_at"))
        fx.append((j.get("slug", os.path.basename(os.path.dirname(f))), j.get("role", "active"),
                   d["status"], d.get("status_by_pr_created_at", "unknown")))
    active = [x for x in fx if x[1] == "active"]
    blocked = [x for x in active if x[2] == "in-window"]
    exposed = [x for x in active if x[2] != "in-window" and x[3] == "in-window"]
    print(f"\nvintage vs {MODEL}  (gate: merged_at; disclosure: pr_created_at)")
    print(f"  active subjects:        {len(active)}")
    print(f"  NOT POOLABLE (in-window by merge date): "
          f"{', '.join(x[0] for x in blocked) if blocked else 'none'}")
    if exposed:
        print(f"  clears the gate but its PR was OPEN inside the window — dcc-60qk, disclosure only:")
        for x in exposed:
            print(f"      {x[0]}")
    non_active = [x for x in fx if x[1] != "active"]
    if non_active:
        print(f"  not in the grid ({len(non_active)}): "
              f"{', '.join(f'{x[0]} [{x[1]}]' for x in non_active)}")
PY
