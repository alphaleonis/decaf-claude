# Subject 6 — microsoft/vscode #320685 (typescript/large): findings-quality analysis

**The subject, and why it is shaped unlike every other.** A 688-line, 10-file rework of local↔native
and remote↔local copy/paste/DND: a new remote file-system IPC proxy (client/server/main-handler), a
rewritten `NativeClipboardService` with per-platform native clipboard formats, and an
`ExplorerService.setToCopy` that downloads remote resources to a temp directory so they can be pasted
natively. It was merged, reverted, re-landed, and reverted a **second** time — with no revert naming
a specific defect. The regressions were found by manual cross-platform test-plan testing, not by a
crash.

That makes the answer key an **aggregate**: `must_flag` enumerates several substantive
merged-and-live defects, and flagging any one counts. Judge: `claude-opus-5[1m]`, blind. 95 clusters
graded: **6 TP-primary, 19 valid-other, 21 valid-minor, 2 false-positive, 47 trivia.**

**This is a re-analysis, of a different failure mode than the other repaired subjects.** Only the
`anthropic-code-review` **r2** cell was quarantined here, and not for the `/code-review` naming
collision — it was *degenerate*: one sub-agent against a workflow mandating five reviewers plus
scorers, carrying no `code-review` plugin attribution at all. Its sibling **r1 was retained as
valid** and its extraction reused verbatim, as were all eight non-anthropic cells. The re-run
produced a healthy **19 sub-agents at $10.39** against the degenerate cell's 1 at $3.22. See nib
dcc-9kkz.

## Everyone caught it — because there were six ways to

All five tools scored 1.00. With six qualifying facets that is unsurprising and makes recall
uninformative here; the separation is entirely in what *else* each found and at what cost.

The six TP-primary facets: eager blocking download (`P_EAGER`), temp-path leak onto the system
clipboard (`P_PATHLEAK`), hard-coded `PathCaseSensitive` (`P_CASESENS`), the catch-block duplicate
push (`P_CATCHDUP`), clipboard reordering (`P_ORDER`), and the silent fallback on download failure
(`P_SILENTFALLBACK`).

## Four tools, five unique catches — the widest spread in the study

- **`ours` uniquely caught `P_PATHLEAK`** — a TP-primary facet, and mjbvz's actual unaddressed
  review thread. Nobody else flagged that the internal `cacheHome` temp path is written onto the
  system clipboard where native paste targets can read it.
- **`anthropic` uniquely caught `double_paste_regression`** — writing native OS formats for
  ordinary internal copies re-arms the dormant DOM paste listener. Graded `valid-other` at only 45
  confidence because the double-fire consequence depends on keybinding/DOM interaction the grader
  could not confirm from the diff; the premise itself is verified.
- **`superpowers` uniquely caught `gnome_copied_files_format`** — the Linux write path emits only
  `text/uri-list`, but GNOME/Nautilus paste keys off `x-special/gnome-copied-files`, so the headline
  Linux interop goal plausibly does not work. From a **single agent**.
- **`tag1` uniquely caught two** — `explorer_writeresources_blast_radius` (a shared
  `IClipboardService` method now publishes real file entries for every caller, not just the
  explorer) and `no_crash_cleanup_startup_sweep`.

This is the strongest evidence in the benchmark that different tools genuinely see different things:
five real findings, four tools, no overlap.

## Noise character

`pr-review-toolkit` again produced the most output and the least signal: **206 findings, 57
clusters, 18.0 trivia/cell, precision 0.23**, and no unique catch. `tag1` is close on volume (198
findings, 64 clusters — the most clusters touched) at 14.5 trivia/cell with 2 FP/cell.

`ours` sits mid-field on precision (0.37) but emitted **183 findings across 49 clusters at 13.0
trivia/cell** — its trivia rate is the second-highest here.

**`superpowers` and `anthropic` are the standouts on precision — 0.75 and 0.74**, roughly double
everyone else, at 48 and 59 findings. Both took ≤0.5 FP/cell.

Both false positives in the subject (`macos_binary_plist`, `stale_format_shadowing`) assert
platform-API behavior the diff's own symmetric write path refutes.

## Did the fan-out earn its agents?

Only partly. Ours ran **21 agents** — its largest roster in the study — for one unique catch;
`superpowers` got one unique catch from **one** agent, and `anthropic` one from 14.5. Distinctness
is 0.27–0.32 across the fan-out tools, so two-thirds of what each agent said restated a sibling.

The honest reading: on a diff this broad (10 files, three subsystems) breadth does buy coverage —
five unique findings across four tools proves the surface is wide — but ours' 21 agents did not buy
proportionally more of it than superpowers' one.

## Cost versus catch

superpowers **$2.80**, pr-review-toolkit **$7.32**, anthropic **$11.00**, tag1 **$21.79**, ours
**$29.50**.

Ours is **2.7× anthropic** and **10.5× superpowers**. It did buy a TP-primary facet nobody else
found — but so did superpowers, for a twenty-ninth of the price.

The corrected anthropic figure ($11.00) is consistent with its shallow cost curve across the study:
$5.58 (169-line diff) → $11.00 (688) → $10.19 (1,560).

## Caveats

- **All five caught the primary**, and with six qualifying facets that says little. Read this
  subject on precision, noise and unique catches, not recall.
- **`double_paste_regression` is graded at confidence 45** — the lowest verdict in the subject, and
  it is anthropic's only unique catch. If it were downgraded, anthropic's unique-true drops to zero.
- **Anthropic emits confidence scores, not severities**, so its calibration rests on 4 consolidated
  critical/high clusters against ours' 10 — not weight-comparable. The metric now counts only the
  consolidated report (#dcc-hmp6); the thin denominator is a separate, unresolved limitation.
- **Nine cells' extractions were reused** (all eight non-anthropic plus anthropic r1); only
  anthropic r2 was re-extracted.
- **The judge changed** from `claude-opus-4-8` to `claude-opus-5[1m]` between versions of this file,
  so verdict shifts are not purely attributable to the cell replacement.
- Fourteen clusters were graded at confidence ≤ 55; those plus all six TP-primary verdicts want a
  human eyeball.
