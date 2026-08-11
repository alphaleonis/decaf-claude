#!/usr/bin/env node
// PreToolUse guard for benchmark v2 cells (nib dcc-suz4).
//
// THE PROBLEM. A cell runs `cd v2/pooled/<subject>/repo` and reviews the diff there. Its own
// scoring ground truth is three relative paths away:
//
//   ../threads.json                        the admitted human review threads — the thread axis's key
//   ../../*/threads.json                   every other subject's
//   ../../../analysis/*/answer-key.json    the anchor keys
//   ../../../runs/*/final-output.md        every earlier cell's output (the v1 dcc-2cxq shape)
//
// None of it is inside the checkout, so `reset_repo()` never touches it, and no network shim sees a
// local read. Cells run with `--dangerously-skip-permissions`, which removes path gating entirely.
//
// WHY A HOOK. Measured 2026-08-11 on Claude Code 2.1.226: a PreToolUse hook still fires under
// `--dangerously-skip-permissions` (the payload reports `permission_mode: bypassPermissions`), and
// exiting 2 blocks the call — verified against both the `Read` tool and the `Bash` fallback
// `cat ../notes-b.json`. A permission allowlist would also work but changes what the tools can do,
// and tool behavior is the thing being measured; this changes nothing a legitimate review does.
//
// THE RULE. Deny any path that resolves INSIDE the benchmark tree but OUTSIDE this cell's checkout.
// Everything else is allowed untouched — the toolchain, the system, the network shims, and the whole
// of the checkout including its git history. Nothing a review of the diff legitimately needs lives
// in the denied region.
//
// Required env (set by run_cell_v2.sh):
//   BENCH_CELL_REPO   absolute path to the checkout this cell may read
//   BENCH_ACCESS_LOG  file to append verdicts to, so the leak audit sees them

const fs = require("fs");
const path = require("path");

const BENCH_ROOT = path.resolve(__dirname, "..", "..");   // competition/benchmark
const CELL_REPO = process.env.BENCH_CELL_REPO || "";
const LOG = process.env.BENCH_ACCESS_LOG || "";

function record(verdict, detail) {
  if (!LOG) return;
  try {
    fs.appendFileSync(LOG, `${new Date().toISOString().replace(/\.\d+Z$/, "Z")}\tfs\t${verdict}\t${detail}\n`);
  } catch { /* the log is evidence, not a gate: never fail the cell over it */ }
}

function refuse(reason, detail) {
  record("DENY", detail);
  // stderr on exit 2 is what the model sees.
  console.error(
    `Out of bounds: ${reason}\n` +
    `This review covers the repository checked out at ${CELL_REPO} and nothing outside it. ` +
    `Work from that tree and its git history.`
  );
  process.exit(2);
}

function inside(child, parent) {
  const rel = path.relative(parent, child);
  return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}

// A path is denied when it lands in the benchmark tree but not in this cell's checkout.
function denied(p) {
  return inside(p, BENCH_ROOT) && !inside(p, CELL_REPO);
}

// Path-like tokens out of a shell command. Deliberately generous: anything containing a separator,
// after stripping quotes and the common `--flag=` prefix. Tokens that are not really paths resolve
// harmlessly inside the checkout (a URL becomes <cwd>/https:/…) and are allowed.
function shellPaths(cmd) {
  const out = [];
  for (let tok of String(cmd).split(/[\s;|&<>()`]+/)) {
    tok = tok.replace(/^['"]|['"]$/g, "");
    if (tok.startsWith("--") && tok.includes("=")) tok = tok.slice(tok.indexOf("=") + 1);
    tok = tok.replace(/^['"]|['"]$/g, "");
    if (!tok) continue;
    if (tok === ".." || tok.includes("/")) out.push(tok);
  }
  return out;
}

let raw = "";
process.stdin.on("data", (d) => (raw += d)).on("end", () => {
  let ev = {};
  try { ev = JSON.parse(raw); } catch { process.exit(0); }   // unparseable: not our call to block

  // Fail closed on misconfiguration. This hook is only ever installed for a benchmark cell, so an
  // absent CELL_REPO means the runner is wrong, not that the cell is unrestricted.
  if (!CELL_REPO) {
    console.error("BENCH_CELL_REPO is not set; refusing to run a cell without isolation bounds.");
    process.exit(2);
  }

  const cwd = ev.cwd || CELL_REPO;
  const ti = ev.tool_input || {};
  const tool = ev.tool_name || "";

  const candidates = [];
  for (const k of ["file_path", "path", "notebook_path"]) {
    if (typeof ti[k] === "string" && ti[k]) candidates.push(ti[k]);
  }
  if (tool === "Bash" && typeof ti.command === "string") {
    candidates.push(...shellPaths(ti.command));
  }

  for (const c of candidates) {
    const resolved = path.resolve(cwd, c);
    if (denied(resolved)) {
      refuse(
        `${tool} would reach ${resolved}, which is part of the benchmark harness rather than the ` +
        `code under review. The harness holds this subject's scoring data.`,
        `${tool} ${resolved}`
      );
    }
  }

  record("ALLOW", `${tool} ${candidates.length ? candidates.join(" ") : "(no path)"}`);
  process.exit(0);
});
