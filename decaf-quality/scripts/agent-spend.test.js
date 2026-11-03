// Covers agent-spend.js: summing a subagent transcript and finding it by agent id.
// Run: node --test decaf-quality/scripts/

const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const SCRIPT = path.join(__dirname, "agent-spend.js");
const { sumTranscript } = require(SCRIPT);

function assistant(id, usage) {
  return JSON.stringify({ type: "assistant", message: { id, usage } });
}

function writeTranscript(config, agentId, lines) {
  const dir = path.join(config, "projects", "-some-project", "session-1", "subagents");
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `agent-${agentId}.jsonl`);
  fs.writeFileSync(file, lines.join("\n") + "\n");
  return file;
}

function tempConfig() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "agent-spend-"));
}

test("one response written as several records counts once, with the last record's output", () => {
  const first = { input_tokens: 2, output_tokens: 16, cache_read_input_tokens: 100, cache_creation_input_tokens: 10 };
  const last = { ...first, output_tokens: 321 };
  const file = writeTranscript(tempConfig(), "a1", [
    JSON.stringify({ type: "user", attributionAgent: "decaf-quality:solo-reviewer", message: { content: "go" } }),
    assistant("msg_1", first),
    assistant("msg_1", first),
    assistant("msg_1", last),
    assistant("msg_2", { input_tokens: 1, output_tokens: 5, cache_read_input_tokens: 200, cache_creation_input_tokens: 0 }),
    "not json",
  ]);

  assert.deepEqual(sumTranscript(file), {
    agentType: "decaf-quality:solo-reviewer",
    requests: 2,
    input: 3,
    output: 326,
    cacheRead: 300,
    cacheWrite: 10,
    total: 639,
  });
});

test("the CLI finds a transcript by agent id, with or without the agent- prefix", () => {
  const config = tempConfig();
  writeTranscript(config, "abc123", [
    assistant("msg_1", { input_tokens: 1, output_tokens: 2, cache_read_input_tokens: 3, cache_creation_input_tokens: 4 }),
  ]);

  const out = execFileSync("node", [SCRIPT, "abc123", "agent-abc123", "missing"], {
    env: { ...process.env, CLAUDE_CONFIG_DIR: config },
    encoding: "utf8",
  });

  const rows = out.trim().split("\n").slice(2);
  assert.equal(rows[0], "| abc123 | unnamed | 1 | 1 | 2 | 3 | 4 | 10 |");
  assert.equal(rows[1], rows[0]);
  assert.equal(rows[2], "| missing | not found | | | | | | |");
});

test("the CLI exits 2 without an agent id", () => {
  assert.throws(() => execFileSync("node", [SCRIPT], { stdio: "pipe" }), (error) => error.status === 2);
});
