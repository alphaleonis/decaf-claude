#!/usr/bin/env bash
# Checks agent-spend.js against Claude Code's own meter: a headless Haiku session spawns one subagent,
# and the summed transcripts must equal the session's modelUsage on every token component.
# It spends a small amount of Haiku usage, so run it on demand, e.g. after a Claude Code update.
set -euo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

cd "$work"
echo "Use the Agent tool to spawn one general-purpose subagent whose task is to reply with the single word ok. When it returns, reply with its answer." |
  claude -p --model haiku --output-format json --allowedTools "Agent" > result.json

node - "$repo/decaf-quality/scripts/agent-spend.js" result.json <<'EOF'
const fs = require("fs");
const os = require("os");
const path = require("path");
const { sumTranscript } = require(process.argv[2]);
const result = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));

const projects = path.join(process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude"), "projects");
const files = [];
for (const project of fs.readdirSync(projects)) {
  const main = path.join(projects, project, `${result.session_id}.jsonl`);
  if (!fs.existsSync(main)) continue;
  files.push(main);
  const subagents = path.join(projects, project, result.session_id, "subagents");
  if (fs.existsSync(subagents)) {
    for (const name of fs.readdirSync(subagents)) if (name.endsWith(".jsonl")) files.push(path.join(subagents, name));
  }
}

const summed = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 };
for (const file of files) {
  const s = sumTranscript(file);
  for (const key of Object.keys(summed)) summed[key] += s[key];
}
const metered = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 };
for (const usage of Object.values(result.modelUsage || {})) {
  metered.input += usage.inputTokens || 0;
  metered.output += usage.outputTokens || 0;
  metered.cacheRead += usage.cacheReadInputTokens || 0;
  metered.cacheWrite += usage.cacheCreationInputTokens || 0;
}

console.log(`transcripts: ${files.length} (expect 2)`);
let ok = files.length === 2;
for (const key of Object.keys(summed)) {
  const same = summed[key] === metered[key];
  ok &&= same;
  console.log(`${key.padEnd(10)} transcripts ${summed[key]}  metered ${metered[key]}  ${same ? "ok" : "MISMATCH"}`);
}
process.exitCode = ok ? 0 : 1;
EOF
