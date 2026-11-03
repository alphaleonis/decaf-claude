#!/usr/bin/env node
// Prints the token spend of finished subagents, summed from their transcripts, as a Markdown table.
//
// Usage: node agent-spend.js <agent-id>...
// An agent id is the `agentId` an Agent tool result names; `agent-<id>` is accepted too.

const fs = require("fs");
const os = require("os");
const path = require("path");

const USAGE_FIELDS = ["input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"];

/**
 * Sums one transcript's API usage.
 *
 * Claude Code writes one API response as several records that share a `message.id` and repeat its
 * `usage`, so each id is counted once. The last record for an id carries the final output count.
 *
 * @param {string} file - Path to a transcript (`.jsonl`).
 * @returns {{agentType: string, requests: number, input: number, output: number, cacheRead: number,
 *   cacheWrite: number, total: number}} The summed usage. `agentType` is empty when the transcript
 *   names none.
 */
function sumTranscript(file) {
  const perRequest = new Map();
  let agentType = "";
  for (const line of fs.readFileSync(file, "utf8").split("\n")) {
    if (!line.trim()) continue;
    let record;
    try {
      record = JSON.parse(line);
    } catch {
      continue;
    }
    if (!agentType && typeof record.attributionAgent === "string") agentType = record.attributionAgent;
    const message = record.message;
    if (record.type === "assistant" && message && message.id && message.usage) {
      perRequest.set(message.id, USAGE_FIELDS.map((field) => Number(message.usage[field]) || 0));
    }
  }
  const sums = [0, 0, 0, 0];
  for (const usage of perRequest.values()) usage.forEach((value, i) => (sums[i] += value));
  const [input, output, cacheRead, cacheWrite] = sums;
  return { agentType, requests: perRequest.size, input, output, cacheRead, cacheWrite, total: input + output + cacheRead + cacheWrite };
}

/**
 * Returns the transcript paths of a subagent, or an empty array when none is on disk.
 *
 * Subagent transcripts sit at `<config>/projects/<project>/<session>/subagents/agent-<id>.jsonl`,
 * where `<config>` is `CLAUDE_CONFIG_DIR` or `~/.claude`.
 */
function findTranscripts(agentId) {
  const projects = path.join(process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude"), "projects");
  const name = `agent-${agentId}.jsonl`;
  const found = [];
  for (const project of readDirs(projects)) {
    for (const session of readDirs(path.join(projects, project))) {
      const file = path.join(projects, project, session, "subagents", name);
      if (fs.existsSync(file)) found.push(file);
    }
  }
  return found;
}

function readDirs(dir) {
  try {
    return fs.readdirSync(dir, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name);
  } catch {
    return [];
  }
}

function formatRow(agentId, file) {
  if (!file) return `| ${agentId} | not found | | | | | | |`;
  const s = sumTranscript(file);
  const n = (value) => value.toLocaleString("en-US");
  return `| ${agentId} | ${s.agentType || "unnamed"} | ${s.requests} | ${n(s.input)} | ${n(s.output)} | ${n(s.cacheRead)} | ${n(s.cacheWrite)} | ${n(s.total)} |`;
}

function main(args) {
  const ids = args.map((arg) => arg.replace(/^agent-/, "")).filter(Boolean);
  if (ids.length === 0) {
    process.stderr.write("usage: agent-spend.js <agent-id>...\n");
    return 2;
  }
  const lines = [
    "| Agent ID | Agent type | Requests | Input | Output | Cache read | Cache write | Spend |",
    "|---|---|---|---|---|---|---|---|",
  ];
  for (const id of ids) {
    const files = findTranscripts(id);
    // Two transcripts for one id cannot both be this agent's, so neither figure is reported.
    if (files.length > 1) lines.push(`| ${id} | ambiguous: ${files.length} transcripts | | | | | | |`);
    else lines.push(formatRow(id, files[0]));
  }
  process.stdout.write(lines.join("\n") + "\n");
  return 0;
}

module.exports = { sumTranscript, findTranscripts };

if (require.main === module) process.exitCode = main(process.argv.slice(2));
