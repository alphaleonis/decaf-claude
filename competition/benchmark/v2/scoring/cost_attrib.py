#!/usr/bin/env python3
"""Attribute a cell's Opus usage between orchestrator (main transcript) and subagents, deduping
per-message usage by requestId, and check the sum against meter.json's modelUsage."""
import json,sys,os,glob,collections
runs='/home/decaf/code/decaf-claude/competition/benchmark/v2/runs'
def usage_of(path):
    seen={}; tools=collections.Counter(); text_out_lines=0
    for l in open(path):
        try:o=json.loads(l)
        except: continue
        if o.get('type')!='assistant': continue
        m=o.get('message') or {}
        u=m.get('usage') or {}
        rid=o.get('requestId') or m.get('id') or o.get('uuid')
        if u and rid not in seen: seen[rid]=(m.get('model'),u)
        for c in (m.get('content') or []):
            if isinstance(c,dict) and c.get('type')=='tool_use': tools[c['name']]+=1
    tot=collections.Counter(); models=collections.Counter()
    for model,u in seen.values():
        models[model]+=1
        for k in ('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens'): tot[k]+=u.get(k,0)
    return len(seen), dict(tot), dict(models), dict(tools)
def cell(c):
    iso=open(f'{runs}/{c}/isolation.txt').read().splitlines()
    sess=[l.split(':',1)[1].strip() for l in iso if l.strip().startswith('session:')][0]
    main=glob.glob(os.path.expanduser(f'~/.claude/projects/*/{sess}.jsonl'))[0]
    subs=sorted(glob.glob(f'{os.path.splitext(main)[0]}/subagents/agent-*.jsonl'))
    m=json.load(open(f'{runs}/{c}/meter.json'))
    meter={k:v for k,v in m['modelUsage'].items()}
    out={'cell':c,'meter':{k:{'out':v['outputTokens'],'in':v['inputTokens'],'cache_r':v.get('cacheReadInputTokens'),'cache_w':v.get('cacheCreationInputTokens'),'cost':round(v['costUSD'],2)} for k,v in meter.items()},'main':None,'subagents':[]}
    n,tot,models,tools=usage_of(main); out['main']={'turns':n,'usage':tot,'models':models,'tools':tools}
    for s in subs:
        meta=json.load(open(s.replace('.jsonl','.meta.json'))) if os.path.exists(s.replace('.jsonl','.meta.json')) else {}
        n,tot,models,tools=usage_of(s); out['subagents'].append({'agent':meta.get('agentType') or meta.get('name') or os.path.basename(s),'turns':n,'usage':tot,'models':models,'tools':tools})
    return out
if __name__=='__main__':
    for c in sys.argv[1:]:
        r=cell(c)
        mo=r['meter']; main=r['main']; subs=r['subagents']
        so=sum(s['usage'].get('output_tokens',0) for s in subs); scr=sum(s['usage'].get('cache_read_input_tokens',0) for s in subs)
        print(f"\n== {c}")
        for k,v in mo.items(): print(f"   meter {k}: out={v['out']} cache_r={v['cache_r']} cache_w={v['cache_w']} ${v['cost']}")
        print(f"   main: turns={main['turns']} out={main['usage'].get('output_tokens')} cache_r={main['usage'].get('cache_read_input_tokens')} cache_w={main['usage'].get('cache_creation_input_tokens')} tools={main['tools']}")
        for s in subs: print(f"   sub {s['agent']}: turns={s['turns']} out={s['usage'].get('output_tokens')} cache_r={s['usage'].get('cache_read_input_tokens')} cache_w={s['usage'].get('cache_creation_input_tokens')} tools={s['tools']}")
        mout=sum(v['out'] for v in mo.values()); mcr=sum((v['cache_r'] or 0) for v in mo.values())
        print(f"   CHECK out: main+subs={main['usage'].get('output_tokens',0)+so} vs meter={mout} ({(main['usage'].get('output_tokens',0)+so)/mout*100:.0f}%) | cache_r: {main['usage'].get('cache_read_input_tokens',0)+scr} vs {mcr} ({(main['usage'].get('cache_read_input_tokens',0)+scr)/mcr*100:.0f}%)")
