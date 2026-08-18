#!/usr/bin/env python3
"""Per-lane emitted characters: thinking / text / tool_use input, plus tool-call classification for the seat."""
import json,sys,os,glob,collections,re
runs='/home/decaf/code/decaf-claude/competition/benchmark/v2/runs'
VERIFY=re.compile(r'\b(go test|go build|go run|go vet|dotnet build|dotnet test|dotnet run|dotnet msbuild|npm test|pytest|cargo test|make\b|benchstat|go tool)', re.I)
WORKTREE=re.compile(r'git worktree', re.I)
def emit(path):
    seen=set(); ch=collections.Counter(); calls=collections.Counter(); cmds=[]
    for l in open(path):
        try:o=json.loads(l)
        except: continue
        if o.get('type')!='assistant': continue
        m=o['message']; 
        for c in (m.get('content') or []):
            if not isinstance(c,dict): continue
            key=(o.get('requestId'), c.get('type'), (c.get('id') or c.get('signature') or c.get('text') or '')[:64])
            if key in seen: continue
            seen.add(key)
            t=c.get('type')
            if t=='thinking': ch['thinking']+=len(c.get('thinking') or '')
            elif t=='text': ch['text']+=len(c.get('text') or '')
            elif t=='tool_use':
                s=json.dumps(c.get('input') or {}); ch['tool_input']+=len(s); calls[c.get('name')]+=1
                if c.get('name')=='Bash': cmds.append((c['input'].get('command') or ''))
                if c.get('name')=='Write': ch['write_content']+=len((c['input'] or {}).get('content') or '')
    kinds=collections.Counter()
    for cmd in cmds:
        if WORKTREE.search(cmd): kinds['worktree']+=1
        elif VERIFY.search(cmd): kinds['build/test']+=1
        elif re.search(r'\b(cat|sed|grep|rg|head|tail|awk|find|ls|wc)\b', cmd) and not re.search(r'\bgit\b', cmd): kinds['read']+=1
        elif re.search(r'\bgit\b', cmd): kinds['git']+=1
        else: kinds['other']+=1
    return dict(ch), dict(calls), dict(kinds)
def cell(c):
    iso=open(f'{runs}/{c}/isolation.txt').read().splitlines()
    sess=[l.split(':',1)[1].strip() for l in iso if l.strip().startswith('session:')][0]
    main=glob.glob(os.path.expanduser(f'~/.claude/projects/*/{sess}.jsonl'))[0]
    subs=sorted(glob.glob(f'{os.path.splitext(main)[0]}/subagents/agent-*.jsonl'))
    return emit(main), [emit(s) for s in subs]
for c in sys.argv[1:]:
    (mch,mcalls,_),subs=cell(c)
    print(f"== {c.replace('__shim-on','')}")
    print(f"   orchestrator: think={mch.get('thinking',0):>6d} text={mch.get('text',0):>6d} tool_in={mch.get('tool_input',0):>6d} (of which Write content={mch.get('write_content',0)}) calls={mcalls}")
    for sch,scalls,skinds in subs:
        print(f"   seat:         think={sch.get('thinking',0):>6d} text={sch.get('text',0):>6d} tool_in={sch.get('tool_input',0):>6d} (Write content={sch.get('write_content',0)}) calls={scalls} bash-kinds={skinds}")
    tot_m=sum(v for k,v in mch.items() if k!='write_content'); tot_s=sum(sum(v for k,v in s[0].items() if k!='write_content') for s in subs)
    print(f"   emitted chars: orchestrator {tot_m} ({tot_m/(tot_m+tot_s)*100:.0f}%) | seat {tot_s} ({tot_s/(tot_m+tot_s)*100:.0f}%) | total {tot_m+tot_s}")
