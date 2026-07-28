# Subject 6 — microsoft/vscode #320685 (typescript/large): findings-quality analysis

**The subject, and why it is shaped unlike every other.** A 688-line, 10-file rework of local↔native
and remote↔local copy/paste/DND: a new remote file-system IPC proxy (client/server/main-handler), a
rewritten `NativeClipboardService` with per-platform native clipboard formats, and an
`ExplorerService.setToCopy` that downloads remote resources to a temp directory so they can be pasted
into native file managers. There is **no single escaped bug**. The feature was merged, reverted
(#321516), re-landed, and reverted a **second** time (#323490). The stated reason is not a crash or a
stack trace but *"TPI indicated more than normal regressions"* — manual cross-platform testing on
issue #321354, where a tester wrote "Several regressions, maybe better revert?" and the author agreed.

That forced a different answer key. A reviewer cannot "catch the revert"; it can only catch the
concrete defects that produced it. So `primary_bug` was authored as an **aggregate** of six live
facets verified against the merged code, with a catch requiring a named consequence — explicitly
excluding the vague "large refactor, regressions are likely, needs more testing" hedge that would
otherwise let any tool claim credit.

**All five tools caught the aggregate primary, in every repeat — 10/10 cells.** But the interesting
result is *which* facets each found, because the six decompose very unevenly:

- **P_CATCHDUP** (8 cells) — `resolveClipboardResources`' catch block does `result.push(...remoteResources)`
  after the loop may already have pushed temp targets, so a mid-loop failure puts *both* the temp copies
  and the original remote URIs for the same files on the clipboard.
- **P_ORDER** (8 cells) — locals are pushed first and remote temp targets appended, so a mixed
  selection loses the user's ordering.
- **P_EAGER** (7 cells) — `setToCopy` awaits the full download before writing the clipboard: Ctrl+C on
  a remote selection blocks on a sequential network copy with no size cap, progress, or cancellation.
- **P_CASESENS** (4 cells) — the proxy client unconditionally ORs in `PathCaseSensitive` while its
  sibling derives it from the remote OS.
- **P_SILENTFALLBACK** (3 cells) — on download failure the code falls back to remote URIs behind a bare
  `logService.warn`, so native paste silently does nothing.
- **P_PATHLEAK** (1 cell — `ours` only) — the `cacheHome/remote-clipboard/<uuid>/<uuid>` path is written
  onto the system clipboard, exposing internal cache layout to any native paste target.

Two of these were the human/bot review threads left unaddressed at merge (P_EAGER + P_PATHLEAK are
mjbvz's thread; P_CASESENS is the surviving Copilot thread); the other three I derived by reading
`resolveClipboardResources` in the merged checkout, and multiple tools found them independently —
a useful check that the key was not built to flatter anyone.

**The trap discipline was perfect, and it is the headline.** Three of the PR's five review threads
were **addressed before merge**: `text/uri-list` *is* filtered to `file://`, the proxy main handler
*does* reject non-`vscode-remote` schemes, and temp copies *do* get per-item UUID subfolders. Across
**all 681 findings, zero asserted any of them as a live defect** — verified by an independent regex
hunt over every claim, not just by the grader. On subject 5 one tool fell for the analogous bait; here
none did. Better still, several tools showed their work: `ours` wrote *"raised by a bot reviewer and
marked resolved but unchanged"* about `PathCaseSensitive` and *"marked resolved on GitHub but the
merged capabilities getter still returns a static bitmask"* — it retrieved the threads, checked each
against the merged code, and reported only the one that genuinely survived. That is precisely the
behavior these trap subjects exist to measure. Only **two false positives** in the whole subject, both
refuted with in-repo citations to sibling providers.

**A deep valid-other layer (21 clusters) is where the tools earned their keep.** The best of it goes
well beyond the answer key: the **double-paste regression** (anthropic, unique) — writing native OS
formats on ordinary *local* copies makes `clipboardData.files` non-empty so the explorer DOM paste
handler fires a second time, explicitly cross-referenced to the PR #200601 fix that removed exactly
that ambiguity; the **`hasResources`/`readResources` divergence** — Paste is enabled on mere format
presence while the read filters to `file://`, lighting up an affordance that no-ops; the **macOS
binary-plist assumption** — `plistToFiles` parses XML plist by regex while Finder writes binary plist,
which would make the headline "paste from Finder" a silent no-op; the **Windows multi-file gap** —
`FileNameW` is emitted only when `resources.length === 1`; and **proxy missing caller authorization** —
the main handler routes on the payload URI's authority without checking the *caller's* connection
context (a confused-deputy shape distinct from the scheme-check that was fixed).

**Noise separates sharply on a large diff.** This is where the size axis bites. anthropic stayed
disciplined — 9.5 valid and only 0.5 trivia per cell, precision **0.81**, at $7.42 — and superpowers
was the efficiency standout: precision 0.62 and 1.5 trivia/cell for **$2.80**, while still catching
three primary facets and contributing two unique-true findings. The verbose tools inflated hard:
pr-review-toolkit ran 21.5 valid-minor and 8.0 trivia per cell (precision 0.25, severity calibration
0.35 — its critical/high band is mostly comment nits), and tag1 21.5/9.0 (precision 0.36). `ours` sat
between on noise (14.5 minor, 6.0 trivia, precision 0.45) with zero FPs and the richest per-finding
reasoning — but at **$29.50/cell**, 10.5× superpowers.

**Subagent economics.** Distinctness rose relative to small subjects (0.27–0.39) because a 10-file diff
genuinely gives agents different territory — the fan-out is better justified here than anywhere else in
the benchmark. It still bought no recall advantage: superpowers, on one agent at $2.80, matched the
$29.50 fan-out on bug-catch and beat it on precision. What the fan-out bought was *coverage breadth*
(tag1 47 clusters/cell, prt 40, ours 33–41 vs superpowers 12) — most of which graded valid-minor or
trivia. Pairwise Jaccard over valid clusters is highest for ours~tag1 (0.71), the two most expensive
tools converging on the same ground.

**Cost–quality verdict.** Recall is saturated, so the frontier is precision-per-dollar and it is
unusually clear: **superpowers ($2.80, precision 0.62, calibration 0.88) and anthropic ($7.42,
precision 0.81, calibration 0.80)** dominate. tag1 at $21.79 and `ours` at $29.50 delivered more
*material* — including genuinely good unique findings — but a maintainer reading their output faces
~30 findings per cell to reach the same conclusions. On the largest PR in the set, the premium tools'
extra spend converted into breadth and noise rather than better top-of-list judgment.

**Caveats.** (1) This is an aggregate-primary subject; "bug-catch 10/10" means every cell named at
least one live facet with a consequence, which is a materially easier bar than subjects 4 or 7 where a
single specific mechanism had to be identified — do not compare the 10/10 here directly against those.
(2) The facet distribution is the more informative signal: only `ours` found P_PATHLEAK, and only 3–4
cells found P_SILENTFALLBACK/P_CASESENS. (3) `human_issues` is empty by construction — mjbvz's single
human thread *is* primary facet (a)/(b), so it grades TP-primary rather than TP-human (same convention
as subject 2). (4) Clustering was delegated to a dedicated agent given the 681-finding scale, then
verified: full assignment coverage, hand-sampled key clusters, and an independent trap hunt; the
95-cluster granularity is finer than earlier subjects, which inflates per-cell cluster counts and
should be kept in mind when comparing trivia/cell across subjects. (5) One cluster sits below
confidence 60 (`stale_format_shadowing`, 55) — the grader declined to call it a false positive because
the refutation depends on Electron internals it could not cite in-repo, and graded it trivia instead;
that is the right call but leaves the claim genuinely unresolved. (6) `anthropic r2` ran anomalously
cheap ($3.22, 93K tokens, a single subagent vs r1's ten) yet still produced 20 findings and caught the
primary — worth noting as a repeat-variance datapoint rather than a failure.
