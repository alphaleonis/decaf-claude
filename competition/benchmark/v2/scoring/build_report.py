#!/usr/bin/env python3
"""Generate the personal cross-arm report from the fact tables (nib dcc-p3wg).

Usage: build_report.py [--facts <dir>] [-o <out.html>]

Reproducible by construction: the page is GENERATED, never hand-edited. Re-run after any fold-in and
it reflects the new facts, including the denominators — which move, because the real-defect pool is
the union of what tools found (nib dcc-dirp). The generator and the fact tables are both committed,
so the page can be rebuilt from the repo alone.

All grouping happens client-side over the inlined facts, so filtering recomputes every denominator
rather than slicing a pre-aggregated table. That is the whole point: on 2026-08-19 four ad-hoc
scripts answered four versions of one question with four different column definitions.

The guards from METRICS.md are enforced IN THE VIEW, not documented beside it:
  * ratios below n=10 render as WITHHELD with the raw counts, never as a number
  * arms with different subject coverage are separated and cannot be ranked against each other
  * `valid-minor` is its own band — it is correct and actionable, and folding it into either `real`
    or `noise` is what made an arm whose output was 92% correct read as "half of this is wrong"
  * an empty human thread axis renders n/a with its reason, never 0.00
"""
import json, os, sys, argparse, subprocess, hashlib, html

V2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(facts, name):
    p = os.path.join(facts, f"{name}.jsonl")
    if not os.path.exists(p):
        sys.exit(f"no fact table at {p} — run emit_facts.py first")
    return [json.loads(l) for l in open(p) if l.strip()]


def provenance(facts):
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=V2,
                             capture_output=True, text=True).stdout.strip() or "unknown"
    except Exception:
        sha = "unknown"
    h = hashlib.sha256()
    for n in ("clusters", "observations", "cells"):
        h.update(open(os.path.join(facts, f"{n}.jsonl"), "rb").read())
    return sha, h.hexdigest()[:12]


CSS = """
:root{
  --ground:#F7F8FA; --panel:#FFFFFF; --ink:#1A1F2B; --muted:#5A6478; --line:#DFE3EB;
  --accent:#B4722A; --accent-soft:#F2E4D3;
  --real:#2E7D6B; --minor:#5B7C99; --trivia:#9A8250; --wrong:#A64237; --void:#98A1B3;
}
:root:not([data-theme="light"]){ @media (prefers-color-scheme: dark){
  --ground:#11141B; --panel:#171B24; --ink:#E6E9F0; --muted:#96A0B4; --line:#262C38;
  --accent:#D79A54; --accent-soft:#3A2C1B;
  --real:#4FA891; --minor:#7FA3C4; --trivia:#C0A468; --wrong:#D2685A; --void:#6C7688;
}}
:root[data-theme="dark"]{
  --ground:#11141B; --panel:#171B24; --ink:#E6E9F0; --muted:#96A0B4; --line:#262C38;
  --accent:#D79A54; --accent-soft:#3A2C1B;
  --real:#4FA891; --minor:#7FA3C4; --trivia:#C0A468; --wrong:#D2685A; --void:#6C7688;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:"IBM Plex Sans",system-ui,-apple-system,sans-serif;font-size:14px;line-height:1.5}
.wrap{display:grid;grid-template-columns:230px minmax(0,1fr);gap:26px;
  max-width:1500px;margin:0 auto;padding:26px 22px 70px}
@media(max-width:900px){.wrap{grid-template-columns:1fr}aside{position:static!important}}
h1{font-size:19px;font-weight:600;margin:0 0 3px;letter-spacing:-.01em;text-wrap:balance}
.sub{color:var(--muted);font-size:12px;margin:0 0 18px}
aside{position:sticky;top:22px;align-self:start;max-height:calc(100vh - 44px);overflow-y:auto}
.fgroup{margin-bottom:16px}
.fgroup h3{font-size:10px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);
  margin:0 0 7px;font-weight:600}
label.f{display:flex;gap:7px;align-items:flex-start;padding:2px 0;cursor:pointer;font-size:12.5px}
label.f:hover{color:var(--accent)}
input[type=checkbox]{accent-color:var(--accent);margin-top:2px;flex:none}
.mini{background:none;border:1px solid var(--line);color:var(--muted);border-radius:4px;
  font:inherit;font-size:10.5px;padding:2px 7px;cursor:pointer;margin-right:5px}
.mini:hover{border-color:var(--accent);color:var(--accent)}
.mini:focus-visible,label.f:focus-within{outline:2px solid var(--accent);outline-offset:2px}
section{background:var(--panel);border:1px solid var(--line);border-radius:7px;
  padding:15px 17px;margin-bottom:16px}
section>h2{font-size:12px;text-transform:uppercase;letter-spacing:.08em;margin:0 0 3px;
  font-weight:600}
section>p.note{color:var(--muted);font-size:12px;margin:0 0 12px;max-width:66ch}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:5px 9px;border-bottom:1px solid var(--line);white-space:nowrap}
th{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600}
th:first-child,td:first-child{text-align:left}
td.arm{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12px}
tbody tr:hover{background:var(--accent-soft)}
.num{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12.5px}
.chip{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10.5px;
  font-family:"IBM Plex Mono",ui-monospace,monospace}
.wh{background:repeating-linear-gradient(45deg,transparent,transparent 3px,var(--line) 3px,var(--line) 4px);
  color:var(--muted);border:1px solid var(--line)}
.bar{display:flex;height:9px;border-radius:2px;overflow:hidden;min-width:110px;background:var(--line)}
.bar i{display:block}
.k{display:inline-flex;align-items:center;gap:5px;margin-right:13px;font-size:11px;color:var(--muted)}
.k b{width:9px;height:9px;border-radius:2px;display:inline-block}
.poolchip{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;color:var(--accent);
  border:1px solid var(--accent);border-radius:3px;padding:1px 7px}
.warn{border-left:3px solid var(--accent);padding-left:10px;color:var(--muted);font-size:12px;
  margin:10px 0}
.grouphdr{font-size:11.5px;color:var(--muted);margin:16px 0 7px;padding-top:12px;
  border-top:1px dashed var(--line)}
.grouphdr:first-of-type{border-top:none;padding-top:0;margin-top:0}
.prov{color:var(--muted);font-size:11px;font-family:"IBM Plex Mono",ui-monospace,monospace;
  margin-top:26px;padding-top:12px;border-top:1px solid var(--line)}
.hit{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11.5px}
.hit.full{color:var(--real);font-weight:600}
.hit.none{color:var(--void)}
.hit.na{color:var(--void);opacity:.5}
.warnflag{color:var(--wrong);margin-left:5px;cursor:help;font-size:12px}
th abbr{text-decoration:underline dotted var(--line);text-underline-offset:3px;cursor:help}
#gloss,#terms{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:5px 16px;margin:0}
#gloss dt,#terms dt{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12px;color:var(--accent)}
#gloss dd,#terms dd{margin:0;color:var(--muted);font-size:12.5px;max-width:78ch}
"""

JS = r"""
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const CL=FACTS.clusters, OB=FACTS.observations, CE=FACTS.cells;
const key=(s,c)=>s+"|"+c;
const CLM=new Map(CL.map(c=>[key(c.subject,c.cluster_id),c]));
const N_FLOOR=10;
const TERMS=[
 ["real-defect pool","EXACTLY two conditions — verdict in {matches-thread, matches-key, valid-other} AND finding_class == 'defect'. SEVERITY IS NOT ONE OF THEM: a low-severity cluster is in the pool if its verdict is real; a critical-sounding claim the judge called trivia is not. Of 138 defect-CLASS clusters only 33 survive as real; the other 105 are 89 trivia, 13 valid-minor, 3 false-positive."],
 ["finding_class","what a finding is ABOUT: defect / risk / test-gap / docs / design / style. A 'checked whether X could crash — it cannot' note is defect-CLASS because it concerns a defect, and trivia-VERDICT because it asserts none."],
 ["verdict","whether the claim is RIGHT AND SUBSTANTIVE: matches-thread, matches-key, valid-other (all 'real'), valid-minor, trivia, false-positive."],
 ["judged_severity","the judge's view of IMPACT IF REAL: critical / high / medium / low / nit / info. Independent of the other two."],
 ["valid-minor vs low severity","NOT the same thing. valid-minor is about SUBSTANCE — correct but too small to call substantive. low is about IMPACT. A low-severity finding can be fully substantive and sit in the pool; 5 pool clusters are low severity."],
 ["reported vs found","reported = shown to the developer. found = reported + demoted, i.e. everything the arm formed a claim about. Detection and disposition are different capabilities."],
 ["\u26a0 incomplete data","Two kinds, both marked. (1) An ARM that did not run on every selected subject: its whole row is computed over a subset, against a pool drawn from that subset. (2) A POOL assembled from few contributing arms, which is mechanically easier to hit — on prometheus 13 arms contributed and no arm exceeds 6/11 even across all repeats, while on the 4-contributor subjects arms reach 100%. Numbers either side of a warning are not comparable."],
 ["dynamic denominator","the pool is the union of what tools found, so adding an arm that finds something new ENLARGES it and lowers every other arm's recall without those arms changing. Filter the arm list here and watch the pool chip move."],
];
const COLS=[
 ["arm","the tool configuration. One arm id = one configuration; an id whose cells used different model policies is not one arm."],
 ["cells","how many runs of this arm are in scope. Everything to the right is computed over these."],
 ["shown","distinct clusters the arm REPORTED — what a developer is actually handed."],
 ["composition","what those shown clusters are: real / valid-minor / noise. Hover the bar for counts."],
 ["real","verdict is matches-thread, matches-key or valid-other — a substantive finding."],
 ["minor","valid-minor: CORRECT AND ACTIONABLE but small. Excluded from `real`, so it drags precision down even though it is right."],
 ["noise%","(trivia + false-positive) / shown. The 'is this worth reading' number. NOT 1 - precision."],
 ["precision","real / shown. Counts valid-minor as a MISS. Withheld below 10 shown clusters, because a pilot precision moved 1.00 -> 0.60 when its denominator went from 3 to 5."],
 ["found","shown + demoted — everything the arm formed a claim about, including what it decided not to show."],
 ["dem.gap","demotion gap = (found - shown) / found. The share of what it found that it hid from you. 0.00 means it shows everything it finds."],
 ["pool hit/cell","what fraction of the real-defect pool ONE cell finds, on average. Not the union across repeats: three cells each finding a different third gives a union of 1.00 but a pool hit/cell of 0.33. Answers 'if I run this once, how much do I get?'"],
 ["$/cell","mean cost of one run of this arm, over the cells in scope."],
];
const uniq=(a)=>[...new Set(a)].sort();

function sel(name){return $$(`input[data-g="${name}"]:checked`).map(i=>i.value);}
function build(name,vals,into){
  into.innerHTML=vals.map(v=>`<label class="f"><input type="checkbox" data-g="${name}" value="${v}" checked><span>${v}</span></label>`).join("");
}
function pct(n,d){return d?Math.round(n/d*100):0;}
function fmt(x,p=3){return x==null?"–":x.toFixed(p);}

function render(){
  const subs=new Set(sel("subject")), arms=new Set(sel("arm")),
        cls=new Set(sel("class")), sev=new Set(sel("sev"));
  // The population is recomputed from the CURRENT filters — the denominator is not fixed.
  const inScope=c=>subs.has(c.subject)&&(!c.finding_class||cls.has(c.finding_class))&&
                   (!c.judged_severity||sev.has(c.judged_severity));
  const pool=CL.filter(c=>c.in_defect_pool&&inScope(c)).map(c=>key(c.subject,c.cluster_id));
  const poolSet=new Set(pool);
  $("#poolsize").textContent=`real-defect pool: ${pool.length}`;

  const armList=[...arms].filter(a=>OB.some(o=>o.arm===a&&subs.has(o.subject)));
  // How many arms ran on each subject: a pool assembled from 4 arms is mechanically easier to hit
  // than one assembled from 13, because each arm supplied a larger share of the union itself.
  const contrib={}; [...subs].forEach(s=>contrib[s]=new Set(CE.filter(c=>c.subject===s).map(c=>c.arm)).size);
  const selN=subs.size;
  // coverage groups: an arm scored on 2 subjects sits against a different pool than one on 5
  const cov=new Map(armList.map(a=>[a,uniq(CE.filter(c=>c.arm===a&&subs.has(c.subject)).map(c=>c.subject)).join(", ")]));
  const groups=new Map();
  armList.forEach(a=>{const k=cov.get(a)||"(no cells)";(groups.get(k)||groups.set(k,[]).get(k)).push(a)});

  let out="";
  [...groups.entries()].sort((a,b)=>b[0].split(", ").length-a[0].split(", ").length).forEach(([gk,ga])=>{
    const gsubs=gk.split(", ").filter(Boolean);
    const gpool=CL.filter(c=>c.in_defect_pool&&gsubs.includes(c.subject)&&inScope(c)).length;
    const rows=ga.map(arm=>{
      const cells=CE.filter(c=>c.arm===arm&&subs.has(c.subject));
      const o=OB.filter(x=>x.arm===arm&&subs.has(x.subject)&&CLM.has(key(x.subject,x.cluster_id))&&inScope(CLM.get(key(x.subject,x.cluster_id))));
      const shown=uniq(o.filter(x=>x.disposition==="reported").map(x=>key(x.subject,x.cluster_id)));
      const found=uniq(o.map(x=>key(x.subject,x.cluster_id)));
      const g=(ks,f)=>ks.filter(k=>f(CLM.get(k))).length;
      const real=g(shown,c=>c.is_real), minor=g(shown,c=>c.is_valid_minor), noise=g(shown,c=>c.is_noise);
      const hits=new Set(o.filter(x=>poolSet.has(key(x.subject,x.cluster_id))).map(x=>key(x.subject,x.cluster_id)+"#"+x.repeat));
      const perSubj=cells.length/Math.max(1,gsubs.length);
      const denom=gpool*perSubj;
      const cost=cells.reduce((s,c)=>s+(c.cost_usd||0),0);
      const ranOn=new Set(cells.map(c=>c.subject));
      const absent=[...subs].filter(x=>!ranOn.has(x));
      return {arm,cells:cells.length,shown:shown.length,found:found.length,real,minor,noise,
              hit:denom?hits.size/denom:null,cost:cells.length?cost/cells.length:null,
              absent,ranOn:ranOn.size};
    }).sort((a,b)=>(b.hit||0)-(a.hit||0));

    const cmin=Math.min(...gsubs.map(x=>contrib[x]||0)), cmax=Math.max(...gsubs.map(x=>contrib[x]||0));
    const thin=cmin<=5;
    const cwarn=thin?`<span class="warnflag" title="INCOMPLETE POOL — subjects in this group had as few as ${cmin} arms contributing to the union. A pool assembled from few arms is mechanically EASIER to hit, because each arm supplied a large share of it. Measured: on prometheus (13 contributors, pool 11) no arm exceeds 6/11 even across all repeats, while on the 4-contributor subjects arms reach 100%.">&#9888;</span>`:"";
    out+=`<div class="grouphdr">COVERAGE GROUP · ${gsubs.length} subject${gsubs.length===1?"":"s"} · <span class="poolchip">pool ${gpool}${cwarn}</span> · ${cmin===cmax?cmin:cmin+"–"+cmax} arms contributed — ${gk||"none"}<br>
      Ranking is valid inside this block only; another block sits against a different denominator.</div>`;
    out+=`<div class="scroll"><table><thead><tr>`+
      COLS.map(([n,t])=>`<th title="${t.replace(/"/g,"&quot;")}"><abbr>${n}</abbr></th>`).join("")+
      `</tr></thead><tbody>`;
    rows.forEach(r=>{
      const w=x=>r.shown?(x/r.shown*100).toFixed(1):0;
      const bar=`<span class="bar" title="real ${r.real} · valid-minor ${r.minor} · noise ${r.noise}">
        <i style="width:${w(r.real)}%;background:var(--real)"></i>
        <i style="width:${w(r.minor)}%;background:var(--minor)"></i>
        <i style="width:${w(r.noise)}%;background:var(--trivia)"></i></span>`;
      const prec=r.shown>=N_FLOOR?`<span class="num">${(r.real/r.shown).toFixed(3)}</span>`
        :`<span class="chip wh" title="n=${r.shown} reported, floor is ${N_FLOOR}. Raw: ${r.real} real of ${r.shown}.">withheld n=${r.shown}</span>`;
      const gap=r.found?((r.found-r.shown)/r.found).toFixed(2):"–";
      const warn=r.absent.length
        ? `<span class="warnflag" title="INCOMPLETE — this arm never ran on ${r.absent.length} of the ${selN} selected subject(s): ${r.absent.join(", ")}. Every figure in this row is computed over the ${r.ranOn} subject(s) it did run, against a pool drawn from those only. Do not compare it with an arm of different coverage.">&#9888;</span>` : "";
      out+=`<tr><td class="arm">${r.arm}${warn}</td><td class="num">${r.cells}</td>
        <td class="num">${r.shown}</td><td>${bar}</td>
        <td class="num">${r.real}</td><td class="num">${r.minor}</td>
        <td class="num">${r.shown?pct(r.noise,r.shown)+"%":"–"}</td><td>${prec}</td>
        <td class="num">${r.found}</td><td class="num">${gap}</td>
        <td class="num">${fmt(r.hit)}</td>
        <td class="num">${r.cost==null?"–":"$"+r.cost.toFixed(2)}</td></tr>`;
    });
    out+=`</tbody></table></div>`;
  });
  $("#cmp").innerHTML=out||`<p class="note">No arm matches the current filters.</p>`;

  // ---- per-defect matrix ----
  const pk=pool.slice().sort();
  let m=`<div class="scroll"><table><thead><tr><th>subject</th><th>cluster</th><th>sev</th>`+
    armList.map(a=>`<th>${a}</th>`).join("")+`</tr></thead><tbody>`;
  pk.forEach(k=>{
    const c=CLM.get(k);
    m+=`<tr><td>${c.subject}</td><td class="arm">${c.cluster_id}</td><td>${c.judged_severity||"–"}</td>`;
    armList.forEach(a=>{
      const n=CE.filter(x=>x.arm===a&&x.subject===c.subject).length;
      if(!n){m+=`<td class="hit na" title="This arm never ran on ${c.subject} — no result is possible here. Not a miss.">–</td>`;return;}
      const r=new Set(OB.filter(x=>x.arm===a&&x.subject===c.subject&&x.cluster_id===c.cluster_id).map(x=>x.repeat));
      const cl=r.size===n?"full":(r.size===0?"none":"");
      m+=`<td class="hit ${cl}">${r.size}/${n}</td>`;
    });
    m+=`</tr>`;
  });
  $("#matrix").innerHTML=m+`</tbody></table></div>`;

  // ---- population grid ----
  const SEV=["critical","high","medium","low","nit","info"],
        CLS=["defect","risk","test-gap","docs","design","style"];
  const real=CL.filter(c=>c.is_real&&c.finding_class&&subs.has(c.subject));
  let p=`<div class="scroll"><table><thead><tr><th>severity</th>`+
    CLS.map(c=>`<th>${c}</th>`).join("")+`<th>total</th></tr></thead><tbody>`;
  SEV.forEach(s=>{
    const row=CLS.map(c=>real.filter(x=>x.judged_severity===s&&x.finding_class===c).length);
    if(!row.reduce((a,b)=>a+b,0))return;
    p+=`<tr><td>${s}</td>`+row.map(v=>`<td class="num">${v||""}</td>`).join("")+
       `<td class="num">${row.reduce((a,b)=>a+b,0)}</td></tr>`;
  });
  p+=`<tr><td><b>total</b></td>`+CLS.map(c=>`<td class="num"><b>${real.filter(x=>x.finding_class===c).length}</b></td>`).join("")+
     `<td class="num"><b>${real.length}</b></td></tr></tbody></table></div>`;
  $("#pop").innerHTML=p;
}

build("subject",uniq(CL.map(c=>c.subject)),$("#f-subject"));
build("arm",uniq(OB.map(o=>o.arm)),$("#f-arm"));
build("class",uniq(CL.map(c=>c.finding_class).filter(Boolean)),$("#f-class"));
build("sev",uniq(CL.map(c=>c.judged_severity).filter(Boolean)),$("#f-sev"));
document.addEventListener("change",e=>{if(e.target.matches("input[type=checkbox]"))render();});
$$(".mini").forEach(b=>b.addEventListener("click",()=>{
  $$(`input[data-g="${b.dataset.g}"]`).forEach(i=>i.checked=(b.dataset.act==="all"));render();}));
const dl=(el,rows)=>$(el).innerHTML=rows.map(([n,t])=>
  `<dt>${n}</dt><dd>${t.replace(/</g,"&lt;")}</dd>`).join("");
dl("#gloss",COLS); dl("#terms",TERMS);
render();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", default=os.path.join(V2, "analysis", "facts"))
    ap.add_argument("-o", "--out", default=os.path.join(V2, "analysis", "report", "index.html"))
    a = ap.parse_args()

    facts = {n: load(a.facts, n) for n in ("clusters", "observations", "cells")}
    sha, digest = provenance(a.facts)
    empties = sorted({c["subject"] for c in facts["clusters"]}) and []

    doc = f"""<title>Benchmark Fact Explorer</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
<aside>
  <div class="fgroup"><h3>Subjects</h3>
    <button class="mini" data-g="subject" data-act="all">all</button><button class="mini" data-g="subject" data-act="none">none</button>
    <div id="f-subject"></div></div>
  <div class="fgroup"><h3>Arms</h3>
    <button class="mini" data-g="arm" data-act="all">all</button><button class="mini" data-g="arm" data-act="none">none</button>
    <div id="f-arm"></div></div>
  <div class="fgroup"><h3>Finding class</h3>
    <button class="mini" data-g="class" data-act="all">all</button><button class="mini" data-g="class" data-act="none">none</button>
    <div id="f-class"></div></div>
  <div class="fgroup"><h3>Judged severity</h3>
    <button class="mini" data-g="sev" data-act="all">all</button><button class="mini" data-g="sev" data-act="none">none</button>
    <div id="f-sev"></div></div>
</aside>
<main>
  <h1>Benchmark Fact Explorer</h1>
  <p class="sub">Every figure is grouped live from the committed fact tables. Denominators recompute
  as you filter — the real-defect pool is the union of what tools found, so including or excluding an
  arm changes it.</p>

  <section>
    <h2>Arm comparison <span id="poolsize" class="poolchip"></span></h2>
    <p class="note">Composition bar splits what a developer is shown:
      <span class="k"><b style="background:var(--real)"></b>real</span>
      <span class="k"><b style="background:var(--minor)"></b>valid-minor — correct and actionable</span>
      <span class="k"><b style="background:var(--trivia)"></b>noise</span>
      <br><span class="warnflag">&#9888;</span> marks a figure resting on <b>incomplete data</b> —
      an arm that did not run on every selected subject, or a pool assembled from few contributing
      arms. Hover it for what is missing. Never rank across a warning boundary.
      <br><b>noise% is not 1 − precision.</b> Precision counts valid-minor as a miss, so an arm whose
      output is almost entirely correct can score 0.50. Use noise% for "is this worth reading".</p>
    <div id="cmp"></div>
  </section>

  <section>
    <h2>Per-defect matrix</h2>
    <p class="note">Cells that found each real defect-class cluster, out of that arm's cells on that
    subject. <span class="hit full">n/n</span> found every time,
    <span class="hit none">0/n</span> never, <span class="hit na">–</span> the arm never ran there.
    Detection of a given defect is often stochastic rather than all-or-nothing.</p>
    <div id="matrix"></div>
  </section>

  <section>
    <h2>Population</h2>
    <p class="note">Real clusters by judged severity and class — what every recall above divides by.
    Note how few are critical or high: any claim about catching serious bugs rests on that row.</p>
    <div id="pop"></div>
  </section>

  <section>
    <h2>Column glossary</h2>
    <p class="note">Hover any column header for the same text. Definitions travel with the numbers
    deliberately — reading <code>precision</code> without knowing it excludes valid-minor is how an
    arm whose output was 92% correct got described as "half of this is wrong".</p>
    <dl id="gloss"></dl>
    <h2 style="margin-top:20px">How the numbers are derived</h2>
    <p class="note">The terms the columns rest on. Severity, class and verdict are three
    <em>independent</em> axes — a cluster carries all three, and none implies another.</p>
    <dl id="terms"></dl>
  </section>

  <p class="prov">generated by scoring/build_report.py · repo {sha} · facts sha256 {digest}
    · {len(facts['clusters'])} clusters / {len(facts['observations'])} observations / {len(facts['cells'])} cells
    · rebuild: python3 scoring/emit_facts.py pooled/&lt;subjects&gt; &amp;&amp; python3 scoring/build_report.py</p>
</main>
</div>
<script>const FACTS={json.dumps(facts)};</script>
<script>{JS}</script>
"""
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write(doc)
    print(f"wrote {a.out}  ({len(doc)//1024} KB)")
    print(f"  repo {sha} · facts {digest} · "
          f"{len(facts['clusters'])} clusters / {len(facts['observations'])} observations / "
          f"{len(facts['cells'])} cells")


if __name__ == "__main__":
    main()
