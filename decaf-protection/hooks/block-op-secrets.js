#!/usr/bin/env node
// decaf-protection: PreToolUse hook that blocks 1Password CLI invocations
// whose output may surface secret values into the session transcript.
//
// Uses exit code 2 so the block is enforced even under
// --dangerously-skip-permissions / "bypass permissions on", which otherwise
// short-circuits the permission system (including permissionDecision: "deny").
//
// Policy (per global CLAUDE.md invariant): lean deny. Only a small allowlist
// of plainly-metadata `op` subcommands is permitted; everything else is
// blocked and routed to the operator via the `!` prompt prefix.

const SAFE_FIRST_ARGS = new Set([
  '',             // bare `op` just prints help
  '--version',
  '-v',
  'version',
  '--help',
  '-h',
  'help',
  'whoami',
]);

// Match `op` at a shell command-start position, optionally preceded by env
// assignments and sudo/env/xargs/time/nohup wrappers, optionally with a path
// prefix or surrounding quotes. Capture group 1 = first arg after `op`.
//
// Command-start boundaries include `"` and `'` so that `bash -c "op read ..."`
// and similar nested invocations are still caught.
const OP_INVOCATION_RE = new RegExp(
  String.raw`(?:^|[;&|(<>\n\`'"]|\$\()\s*` +
  String.raw`(?:(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)+)?` +
  String.raw`(?:sudo\s+(?:-\S+\s+)*)?` +
  String.raw`(?:(?:env|xargs|time|nohup)\s+(?:-\S+\s+)*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*)?` +
  String.raw`['"]?(?:\S*\/)?op\b['"]?` +
  String.raw`(?:\s+(\S+))?`,
  'g'
);

function firstArgOf(match) {
  return (match[1] || '').trim();
}

function blockMessage(firstArg) {
  const shown = firstArg || '(no args)';
  return [
    'Blocked by decaf-protection.',
    '',
    `Detected a 1Password CLI invocation ("op ${shown}") that may emit a secret`,
    'value into the session transcript. Any such value lands in tool results, the',
    'LLM context, and the on-disk session history — priming reads count too.',
    '',
    'Prohibited: op read, op item get, op inject, op run, op document get,',
    'op signin, op connect token create, op service-account token create, and',
    'anything else that could surface credentials. The allowlist is intentionally',
    'tiny: op --version, op --help, op whoami.',
    '',
    'If the operator needs this, ask them to run it themselves using the `!`',
    'prefix in the prompt (which bypasses the Bash tool entirely), e.g.:',
    '    ! op read "op://Vault/Item/field" > /dev/null',
    '',
    'Do not retry with a different invocation — escalate to the operator.',
  ].join('\n') + '\n';
}

function scan(cmd) {
  OP_INVOCATION_RE.lastIndex = 0;
  let m;
  while ((m = OP_INVOCATION_RE.exec(cmd)) !== null) {
    const firstArg = firstArgOf(m);
    if (!SAFE_FIRST_ARGS.has(firstArg)) return firstArg;
  }
  return null;
}

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { raw += chunk; });
process.stdin.on('end', () => {
  let payload;
  try { payload = JSON.parse(raw); } catch { process.exit(0); }

  if (payload?.tool_name !== 'Bash') process.exit(0);
  const cmd = payload?.tool_input?.command;
  if (typeof cmd !== 'string' || cmd.length === 0) process.exit(0);

  const offending = scan(cmd);
  if (offending === null) process.exit(0);

  process.stderr.write(blockMessage(offending));
  process.exit(2);
});
