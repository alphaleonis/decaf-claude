// SessionStart / SubagentStart hook: points every agent that may write code at the write-comments skill.
// SessionStart context does not reach subagents, so SubagentStart repeats the pointer for each one.

const READ_ONLY_AGENTS = new Set(["Explore", "Plan", "claude-code-guide", "statusline-setup"]);

const POINTER =
  "Before your first edit to a source file, invoke the `decaf-quality:write-comments` skill with no arguments, " +
  "and follow its rules in every comment and doc comment you write. Invoke it again if its rules are no longer in your context.";

let raw = "";
process.stdin.on("data", (chunk) => (raw += chunk));
process.stdin.on("end", () => {
  let input = {};
  try {
    input = JSON.parse(raw);
  } catch {
    // Without parseable input, still give the pointer to whatever started.
  }

  const event = input.hook_event_name || "SessionStart";
  if (event === "SubagentStart" && READ_ONLY_AGENTS.has(input.agent_type)) return;

  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: event, additionalContext: POINTER } }));
});
