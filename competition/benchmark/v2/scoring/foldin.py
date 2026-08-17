#!/usr/bin/env python3
"""Fold a new tool arm into an already-graded v2 subject WITHOUT touching existing verdicts.
Usage: foldin.py <subject-dir> <tool> <cluster-out.json> [--verdicts1 v1.json --verdicts2 v2.json --classes cls.json --key key.json]
- appends reported_by entries (tool, repeat, severity, disposition, finding_index) to assigned clusters
- appends new clusters with pass-1 verdicts + class; pass-2 verdicts appended to grading/verdicts-pass2.json
- rebuilds findings.json from extract/*.json; adds cells from runs/*/meter.json + access.log
"""
import json,sys,os,glob,argparse,re
ap=argparse.ArgumentParser(); ap.add_argument('subject_dir'); ap.add_argument('tool'); ap.add_argument('cluster_out')
ap.add_argument('--verdicts1'); ap.add_argument('--verdicts2'); ap.add_argument('--classes'); ap.add_argument('--key')
ap.add_argument('--runs', default=None)
A=ap.parse_args(); d=A.subject_dir; tool=A.tool
runs=A.runs or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(d))),'runs')
subj=os.path.basename(os.path.abspath(d))
an=json.load(open(f'{d}/analysis.json'))
by={c['cluster_id']:c for c in an['clusters']}
co=json.load(open(A.cluster_out))
# 1. guard: tool not already folded in
assert not any(r['tool']==tool for c in an['clusters'] for r in c['reported_by']), f'{tool} already present in analysis.json'
assert not any(c['tool']==tool for c in an['cells']), f'{tool} cells already present'
# 2. load extracts, index by nid
ex={}
for r in sorted(int(re.search(r'__r(\d+)\.json$',p).group(1)) for p in glob.glob(f'{d}/extract/{tool}__r*.json')):
    for i,f in enumerate(json.load(open(f'{d}/extract/{tool}__r{r}.json'))):
        assert f['tool']==tool and f['repeat']==r
        ex[f'n{r}-{i:02d}']=(f,i)
asg={a['nid']:a for a in co['assignments']}
assert set(asg)==set(ex), (set(asg)^set(ex))
# 3. new clusters
key=json.load(open(A.key)) if A.key else {}
inv={v['cluster_id']:g for g,v in key.items()}   # real id -> blind id
v1={v['cluster_id']:v for v in json.load(open(A.verdicts1))} if A.verdicts1 else {}
v2={v['cluster_id']:v for v in json.load(open(A.verdicts2))} if A.verdicts2 else {}
cls={c['cluster_id']:c for c in json.load(open(A.classes))} if A.classes else {}
classed=any(c.get('finding_class') for c in an['clusters'])
for nc in co['new_clusters']:
    cid=nc['cluster_id']; assert cid not in by, cid
    g=inv.get(cid,cid)
    v=v1.get(g); assert v, f'no pass-1 verdict for new cluster {cid} (blind {g})'
    c={'cluster_id':cid,'summary':nc['summary'],'location':nc['location'],
       'verdict':v['verdict'],'matches_thread':v.get('matches_thread'),'judged_severity':v.get('judged_severity'),
       'code_citation':v.get('code_citation'),'confidence':v.get('confidence'),'rationale':v.get('rationale'),
       'reported_by':[]}
    if classed:
        k=cls.get(g); assert k, f'no class for new cluster {cid}'
        c['finding_class']=k['finding_class']; c['class_confidence']=k.get('class_confidence')
    an['clusters'].append(c); by[cid]=c
# 4. reported_by
for nid,a in asg.items():
    f,i=ex[nid]
    by[a['cluster_id']]['reported_by'].append({'tool':tool,'repeat':f['repeat'],'severity':f['severity'],'disposition':f['disposition'],'finding_index':i})
# 5. cells
for p in sorted(glob.glob(f'{runs}/{subj}__{tool}__shim-{an.get("shim","on")}__r[1-9]/meter.json')):
    m=json.load(open(p)); cell=os.path.dirname(p); rep=int(re.search(r'__r(\d+)$',cell).group(1))
    acc=open(f'{cell}/access.log').read().splitlines() if os.path.exists(f'{cell}/access.log') else []
    denied=sum(1 for l in acc if 'DENIED' in l.upper() or 'DENY' in l.upper())
    an['cells'].append({'tool':tool,'repeat':rep,'cost_usd':round(m['total_cost_usd'],4),'wall_s':int(m['duration_ms']/1000),'access_total':len(acc),'access_denied':denied})
an['cells'].sort(key=lambda c:(c['tool'],c['repeat']))
# 6. write findings.json = concat of extract/*.json in a stable order
allf=[]
for p in sorted(glob.glob(f'{d}/extract/*.json')): allf+=json.load(open(p))
json.dump(allf, open(f'{d}/findings.json','w'), indent=1)
json.dump(an, open(f'{d}/analysis.json','w'), indent=1)
# 7. pass-2 verdicts for new clusters
if v2 and co['new_clusters']:
    p2=f'{d}/grading/verdicts-pass2.json'; arr=json.load(open(p2))
    have={x['cluster_id'] for x in arr}
    for nc in co['new_clusters']:
        g=inv.get(nc['cluster_id'],nc['cluster_id']); v=dict(v2[g]); v['cluster_id']=nc['cluster_id']
        if nc['cluster_id'] not in have: arr.append(v)
    json.dump(arr, open(p2,'w'), indent=1)
    p1=f'{d}/grading/verdicts-pass1.json'
    if os.path.exists(p1):
        arr1=json.load(open(p1)); have1={x['cluster_id'] for x in arr1}
        for nc in co['new_clusters']:
            g=inv.get(nc['cluster_id'],nc['cluster_id']); v=dict(v1[g]); v['cluster_id']=nc['cluster_id']
            if nc['cluster_id'] not in have1: arr1.append(v)
        json.dump(arr1, open(p1,'w'), indent=1)
print(f'{subj}: +{len(ex)} findings, +{len(co["new_clusters"])} clusters, {len(an["clusters"])} total; cells {len(an["cells"])}; findings.json {len(allf)}')
