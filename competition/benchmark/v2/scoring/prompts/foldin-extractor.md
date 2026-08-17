You are an extraction agent for a code-review benchmark. Extract EVERY finding from one run cell into a normalized JSON array. Return raw JSON only — your final message must be exactly one JSON array, no prose, no code fence.

CELL DIRECTORY: __CELL__

READ BOTH LAYERS:
1. `cell-report.md` in that directory — the tool's complete terminal output. (Do NOT use `final-output.md`; it is only the last message.)
2. `tool-artifacts/.decaf/code-reviews/CODE_REVIEW_*.md` — the review report the tool filed. For this tool the report is the finding set and the terminal is a summary. `tool-artifacts.tsv` lists what was captured.

Read the WHOLE report — every section: Findings (numbered #1, #2 …), Pre-existing Issues (if any), Minor Findings (if present), and Considered But Not Flagged. Dedupe by file:line + claim across the two layers — never count a finding twice because it appears in both the terminal and the report.

OUTPUT: a JSON array; one object per distinct finding:
{"tool":"__TOOL__", "repeat":__REP__, "subagent":"solo-reviewer", "severity":"critical|high|medium|low|nit|info",
 "file":"<repo-relative path>", "line":<int>, "category":"<short kebab-case category, e.g. correctness, double-counting, null-semantics, test-coverage, api-design, documentation, performance>", "claim":"<one or two sentences: the specific claim, precise enough to match against another tool's wording of the same issue>", "raw":"<the finding's title/first line as written by the tool>",
 "disposition":"reported|demoted"}

RULES:
- severity mapping: 🔴 Critical→critical, 🟠 High→high, 🟡 Medium→medium, 🟢 Low→low, 🔵 Minor / Minor Findings bucket items→nit, Considered But Not Flagged items→info.
- disposition: `reported` for anything in the primary Findings list, Pre-existing Issues, and Minor Findings (the reader is shown these). `demoted` ONLY for Considered But Not Flagged items — the tool explicitly decided not to show them as findings. Every item in Considered But Not Flagged that makes a concrete claim about a specific location MUST still be extracted (as `demoted`, severity `info`) — including items tagged `minor, out of reach` or `pre-existing, out of reach`; do not skip them. Skip only pure process notes ("no probe needed", "tree left clean") that make no claim about the code.
- Strengths / positive observations are NOT findings — skip them.
- line: the first line number cited; if a range, the start. If a file is cited without a line, use 0.
- Keep `claim` faithful to what the tool asserted; do not editorialize or judge correctness. If a finding carries a counter-argument (e.g. "documented as intended — but…"), keep the claim as the defect claim.
- Include the tool's own severity even for Minor bucket items (as `nit`).

Return ONLY the JSON array.
