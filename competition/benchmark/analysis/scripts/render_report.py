#!/usr/bin/env python3
"""Render a self-contained HTML report from metrics.json + a narrative report.md (+ analysis.json
for the auditable cluster drill-down). No external deps; inline CSS + inline-SVG charts; theme-aware.

Usage: render_report.py <metrics.json> <report.md> <analysis.json> -o report.html
"""
import json, sys, argparse, html, re

VERDICT_COLOR = {"TP-primary": "#16a34a", "TP-human": "#22c55e", "valid-other": "#0ea5e9",
                 "false-positive": "#dc2626", "nitpick": "#a1a1aa"}

def esc(s): return html.escape(str(s if s is not None else ""))

def md_to_html(md):
    """Minimal markdown -> HTML for narrative prose (headings, bold, code, bullet lists, paragraphs)."""
    out, in_ul = [], False
    def inline(t):
        t = esc(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
        return t
    for line in md.splitlines():
        if re.match(r"^\s*[-*] ", line):
            if not in_ul: out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(line.strip()[2:])}</li>"); continue
        if in_ul: out.append("</ul>"); in_ul = False
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m: out.append(f"<h{len(m.group(1))}>{inline(m.group(2))}</h{len(m.group(1))}>"); continue
        if line.strip(): out.append(f"<p>{inline(line)}</p>")
    if in_ul: out.append("</ul>")
    return "\n".join(out)

def pct(x): return "—" if x is None else f"{round(x*100)}%"
def money(x): return "—" if x is None else f"${x:,.2f}"
def num(x): return "—" if x is None else (f"{x:,}" if isinstance(x, int) else f"{x:,.0f}")

def scatter(tools, W=560, H=300, pad=48):
    pts = [(t, m["mean_cost_usd"], m["bug_catch_rate"]) for t, m in tools.items()
           if m["mean_cost_usd"] is not None]
    if not pts: return "<p><em>no cost data</em></p>"
    xmax = max(p[1] for p in pts) * 1.15 or 1
    def X(c): return pad + (c / xmax) * (W - 2*pad)
    def Y(r): return (H - pad) - r * (H - 2*pad)
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="cost vs bug-catch">']
    s.append(f'<line x1="{pad}" y1="{H-pad}" x2="{W-pad}" y2="{H-pad}" class="ax"/>')
    s.append(f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{H-pad}" class="ax"/>')
    for r in (0, .5, 1):
        s.append(f'<text x="{pad-8}" y="{Y(r)+4}" text-anchor="end" class="tick">{int(r*100)}%</text>')
        s.append(f'<line x1="{pad}" y1="{Y(r)}" x2="{W-pad}" y2="{Y(r)}" class="grid"/>')
    for t, c, r in pts:
        s.append(f'<circle cx="{X(c):.1f}" cy="{Y(r):.1f}" r="6" class="pt"/>')
        s.append(f'<text x="{X(c)+9:.1f}" y="{Y(r)+4:.1f}" class="lbl">{esc(t)}</text>')
    s.append(f'<text x="{W/2}" y="{H-8}" text-anchor="middle" class="axl">mean cost / cell (usage $) →</text>')
    s.append(f'<text x="14" y="{H/2}" transform="rotate(-90 14 {H/2})" text-anchor="middle" class="axl">bug-catch rate ↑</text>')
    s.append("</svg>")
    return "\n".join(s)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("metrics"); ap.add_argument("narrative"); ap.add_argument("analysis")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    M = json.load(open(a.metrics)); A = json.load(open(a.analysis))
    narrative = md_to_html(open(a.narrative).read()) if a.narrative else ""
    tools = M["tools"]
    order = sorted(tools, key=lambda t: (-(tools[t]["bug_catch_rate"] or 0),
                                         tools[t]["mean_cost_usd"] or 9e9))

    # leaderboard — plain-language columns (see glossary card below)
    def valid_pc(m):
        v = m.get("valid_per_cell")
        return "—" if v is None else f"{v:,.1f}"
    cols = [("escaped bug", lambda m: pct(m["bug_catch_rate"])),
            ("valid /run", valid_pc),
            ("unique valid", lambda m: num(m["unique_true_n"])),
            ("noise /run", lambda m: num(m["nitpick_per_cell"])),
            ("invalid /run", lambda m: num(m["fp_per_cell"])),
            ("precision", lambda m: pct(m["precision_mean"])),
            ("subagent distinct.", lambda m: pct(m["subagent_distinctness"])),
            ("cost /run", lambda m: money(m["mean_cost_usd"])),
            ("~agents", lambda m: num(m["mean_subagents"]))]
    lb = ["<table><thead><tr><th>tool</th>" + "".join(f"<th>{esc(c)}</th>" for c,_ in cols) + "</tr></thead><tbody>"]
    for t in order:
        m = tools[t]
        lb.append(f"<tr><td class='tool'>{esc(t)}</td>" + "".join(f"<td>{f(m)}</td>" for _,f in cols) + "</tr>")
    lb.append("</tbody></table>")

    # glossary — plain-language definitions of every column / term used
    glossary = """<div class="card glossary"><h3>How to read this</h3><dl>
<dt>run (cell)</dt><dd>one review = one tool running once. Each tool reviewed this PR twice, so 2 runs per tool; "/run" numbers are averaged across the two.</dd>
<dt>finding (issue)</dt><dd>one distinct problem a review raised. The same issue restated by many sub-agents / worded differently is collapsed into a single issue before counting.</dd>
<dt>escaped bug</dt><dd>the real defect that was bad enough to be reverted in a follow-up PR — the one a reviewer <em>must</em> catch. The column is the % of runs that caught it.</dd>
<dt>valid /run</dt><dd>real, worth-acting-on findings per run — the escaped bug plus any other genuine defects (excludes trivia and mistakes).</dd>
<dt>unique valid</dt><dd>valid findings that <em>only this tool</em> caught (nobody else did).</dd>
<dt>noise /run</dt><dd>nitpicks per run — real but trivial (naming, formatting, style, out-of-scope). Safe to ignore.</dd>
<dt>invalid /run</dt><dd>false positives per run — findings asserting a problem that isn't real (refuted against the code). Actively misleading.</dd>
<dt>precision</dt><dd>of everything the tool reported, the share that was valid = valid ÷ (valid + noise + invalid). Higher = less junk per real finding.</dd>
<dt>subagent distinct.</dt><dd>for multi-agent tools, distinct issues ÷ total sub-agent findings. Low = many agents re-finding the same things.</dd>
<dt>Jaccard (overlap, below)</dt><dd>how similar two tools' valid-finding sets are: shared ÷ combined. 1.00 = identical, 0.00 = no overlap.</dd>
<dt>verdict labels</dt><dd>each issue in the drill-down is graded: <strong>TP-primary</strong> = caught the escaped bug; <strong>valid-other</strong> = a different real defect; <strong>nitpick</strong> = trivial/noise; <strong>false-positive</strong> = not real. ("TP" = true positive; "valid" findings = TP-primary + valid-other.)</dd>
</dl></div>"""

    # overlap matrix
    tl = order
    jac = {(o["a"], o["b"]): o["jaccard"] for o in M["overlap"]}
    def jget(x, y):
        if x == y: return None
        return jac.get((x, y), jac.get((y, x)))
    om = ["<table class='matrix'><thead><tr><th></th>" + "".join(f"<th>{esc(t)}</th>" for t in tl) + "</tr></thead><tbody>"]
    for x in tl:
        row = [f"<th>{esc(x)}</th>"]
        for y in tl:
            v = jget(x, y)
            if v is None: row.append("<td class='diag'></td>")
            else:
                sh = int((v or 0) * 200)
                row.append(f"<td style='background:rgba(14,165,233,{v or 0:.2f})'>{v:.2f}</td>")
        om.append("<tr>" + "".join(row) + "</tr>")
    om.append("</tbody></table>")

    # cluster drill-down
    clu = ["<table class='clusters'><thead><tr><th>issue</th><th>file:line</th><th>verdict</th><th>found by</th></tr></thead><tbody>"]
    for c in sorted(A.get("clusters", []), key=lambda c: (0 if c.get("verdict")=="TP-primary" else 1, c.get("verdict",""))):
        v = c.get("verdict","")
        by = sorted({rb["tool"] for rb in c.get("reported_by",[])})
        clu.append("<tr>"
            f"<td>{esc(c.get('summary'))}</td>"
            f"<td class='mono'>{esc(c.get('file'))}:{esc(c.get('line'))}</td>"
            f"<td><span class='verdict' style='background:{VERDICT_COLOR.get(v,'#888')}'>{esc(v)}</span></td>"
            f"<td>{esc(', '.join(by))}</td></tr>")
    clu.append("</tbody></table>")

    title = f"Benchmark analysis — subject {M['subject_id']} ({esc(M['lang'])}/{esc(M['size'])})"
    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<style>
:root{{--bg:#fff;--fg:#18181b;--muted:#71717a;--line:#e4e4e7;--card:#fafafa;--accent:#0ea5e9}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0b0b0f;--fg:#e4e4e7;--muted:#a1a1aa;--line:#27272a;--card:#141418}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,sans-serif}}
.wrap{{max-width:980px;margin:0 auto;padding:28px 20px 80px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:17px;margin:34px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}}
h3{{font-size:15px;margin:20px 0 6px}} .sub{{color:var(--muted);margin:0 0 8px}}
table{{border-collapse:collapse;width:100%;font-size:13.5px;margin:6px 0}}
th,td{{border:1px solid var(--line);padding:6px 9px;text-align:right}} th{{background:var(--card);font-weight:600}}
td:first-child,th:first-child,.tool{{text-align:left}} .tool{{font-weight:600}}
.matrix td{{text-align:center}} .matrix .diag{{background:var(--card)}}
.mono,.clusters .mono{{font-family:ui-monospace,monospace;font-size:12px}}
.clusters td{{text-align:left}} .verdict{{color:#fff;padding:2px 7px;border-radius:10px;font-size:11px;white-space:nowrap}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}}
svg .ax{{stroke:var(--muted)}} svg .grid{{stroke:var(--line)}} svg .pt{{fill:var(--accent)}}
svg .lbl{{fill:var(--fg);font-size:11px}} svg .tick,svg .axl{{fill:var(--muted);font-size:11px}}
.wrap>section{{overflow-x:auto}} code{{background:var(--card);padding:1px 4px;border-radius:4px;font-size:12.5px}}
.legend{{color:var(--muted);font-size:12px;margin-top:4px}}
.glossary dl{{margin:6px 0 0;display:grid;grid-template-columns:auto 1fr;gap:4px 14px}}
.glossary dt{{font-weight:600;white-space:nowrap}} .glossary dd{{margin:0;color:var(--muted);font-size:13px}}
.glossary h3{{margin:0 0 8px}} @media(max-width:560px){{.glossary dl{{grid-template-columns:1fr}}.glossary dd{{margin:0 0 6px}}}}
</style></head><body><div class="wrap">
<h1>{esc(title)}</h1>
<p class="sub">{esc(M['repo'])}#{esc(M['pr'])} · judge: <code>{esc(M['judge_model'])}</code> ·
{M['n_clusters']} distinct issues · {'human threads present' if M['has_human_issues'] else 'no human threads (bug + FP discipline only)'}</p>

<section><h2>Leaderboard</h2>{''.join(lb)}
<p class="legend">Every tool reviewed the PR twice; "/run" columns are averaged across the two runs. Definitions below.</p>
{glossary}</section>

<section><h2>Cost vs. bug-catch</h2><div class="card">{scatter(tools)}</div>
<p class="legend">Upper-left = efficient (catches the bug cheaply). The benchmark's core question: does the fan-out premium buy the catch?</p></section>

<section><h2>Inter-tool overlap (Jaccard, true/valid findings)</h2>{''.join(om)}
<p class="legend">1.00 = identical valid findings · 0.00 = fully complementary.</p></section>

<section><h2>Narrative</h2>{narrative}</section>

<section><h2>Findings drill-down (auditable)</h2>{''.join(clu)}</section>
</div></body></html>"""
    open(a.out, "w").write(doc)
    print(f"wrote {a.out}")

if __name__ == "__main__":
    main()
