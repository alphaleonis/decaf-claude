"""Assemble a fresh subject's analysis.json from: clusters (from-scratch), pass-1 verdicts, class, cells.
Usage: assemble.py <subject-dir> <clusters.json> <verdicts-pass1.json> <verdicts-pass2.json> <classes.json> <key.json>
Cluster ids in verdict/class files are BLIND ids; key maps blind -> real."""
import json,sys,os,glob,re
d,cl,v1,v2,cls,key=sys.argv[1:7]
runs=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(d))),'runs'); subj=os.path.basename(os.path.abspath(d))
fx=json.load(open(f'{d}/fixture.json'))
clusters=json.load(open(cl))['clusters']
K={g:(v['cluster_id'] if isinstance(v,dict) else v) for g,v in json.load(open(key)).items()}; inv={v:k for k,v in K.items()}   # real -> blind
V1={x['cluster_id']:x for x in json.load(open(v1))}; V2={x['cluster_id']:x for x in json.load(open(v2))}; C={x['cluster_id']:x for x in json.load(open(cls))}
# findings index by nid
ex={}
for p in sorted(glob.glob(f'{d}/extract/*.json')):
    for i,f in enumerate(json.load(open(p))): ex[f"{f['tool']}__r{f['repeat']}__{i:02d}"]=(f,i)
out=[]
for c in clusters:
    g=inv[c['cluster_id']]; v=V1[g]; k=C[g]
    rb=[]
    for nid in c['members']:
        f,i=ex[nid]; rb.append({'tool':f['tool'],'repeat':f['repeat'],'severity':f['severity'],'disposition':f['disposition'],'finding_index':i})
    out.append({'cluster_id':c['cluster_id'],'summary':c['summary'],'location':c['location'],'verdict':v['verdict'],'matches_thread':v.get('matches_thread'),'judged_severity':v.get('judged_severity'),'code_citation':v.get('code_citation'),'confidence':v.get('confidence'),'rationale':v.get('rationale'),'reported_by':rb,'finding_class':k['finding_class'],'class_confidence':k.get('class_confidence')})
assert sum(len(c['reported_by']) for c in out)==len(ex), (sum(len(c['reported_by']) for c in out), len(ex))
cells=[]
for p in sorted(glob.glob(f'{runs}/{subj}__*__shim-on__r[1-9]/meter.json')):
    cell=os.path.dirname(p); m=json.load(open(p)); tool=re.search(rf'{re.escape(subj)}__(.+?)__shim-on__r(\d+)$',cell); 
    acc=open(f'{cell}/access.log').read().splitlines() if os.path.exists(f'{cell}/access.log') else []
    cells.append({'tool':tool.group(1),'repeat':int(tool.group(2)),'cost_usd':round(m['total_cost_usd'],4),'wall_s':int(m['duration_ms']/1000),'access_total':len(acc),'access_denied':sum(1 for l in acc if 'DENIED' in l.upper() or 'DENY' in l.upper())})
an={'subject':fx['slug'],'instrument':'pooled-adjudication','judge_model':'claude-opus-5','merged_at':fx['merged_at'],'shim':'on','repeats':2,'grading_pass':1,'cells':cells,'clusters':out}
os.makedirs(f'{d}/grading',exist_ok=True)
json.dump(an,open(f'{d}/analysis.json','w'),indent=1)
allf=[]
for p in sorted(glob.glob(f'{d}/extract/*.json')): allf+=json.load(open(p))
json.dump(allf,open(f'{d}/findings.json','w'),indent=1)
# pass files (real ids)
def real(vd): 
    r=[]
    for g,x in vd.items(): y=dict(x); y['cluster_id']=K[g]; r.append(y)
    return r
json.dump(real(V1),open(f'{d}/grading/verdicts-pass1.json','w'),indent=1); json.dump(real(V2),open(f'{d}/grading/verdicts-pass2.json','w'),indent=1)
an2=dict(an); an2['grading_pass']=2; an2['clusters']=[]
for c in out:
    g=inv[c['cluster_id']]; v=V2[g]; cc=dict(c)
    for f_ in ('verdict','matches_thread','judged_severity','code_citation','confidence','rationale'): cc[f_]=v.get(f_)
    an2['clusters'].append(cc)
json.dump(an2,open(f'{d}/grading/analysis-pass2.json','w'),indent=1)
print(f'{subj}: {len(out)} clusters, {len(ex)} findings, {len(cells)} cells → analysis.json, findings.json, grading/*')
