#!/usr/bin/env python3
"""Regenerate every headline figure in MANUSCRIPT.md from measures_all.jsonl.
Exits non-zero if any manuscript value disagrees with a fresh recompute."""
import json, collections, random, sys
from statistics import median
random.seed(20260908)
mean=lambda v: sum(v)/len(v) if v else None
R=[json.loads(l) for l in open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)),"data","measures.jsonl"))]
def pooled(r,w):
    n=d=0.0
    for g in ("touched","untouched"):
        v=r.get(f"{g}_{w}"); c=r.get(f"{g}_{w}_n")
        if v is None or not c: continue
        n+=v*c; d+=c
    return n/d if d else None
rows=[]
for r in R:
    b,a=pooled(r,"before"),pooled(r,"after")
    if b is None or a is None or not r["n_survivors"]: continue
    rows.append({"repo":r["repo"],"family":r["family"],"tool":bool(r["tool_backed"]),
                 "before":b,"d":a-b,"contact":r["n_touched"]/r["n_survivors"]})
pres=[x for x in rows if x["before"]<0.90 and (1-x["before"])>0.02]
for x in pres: x["cap"]=x["d"]/(1-x["before"])
T=[x for x in pres if x["tool"]]; D=[x for x in pres if not x["tool"]]
ok=[]
def chk(lab,claim,act,tol=0.06):
    good=abs(claim-act)<=tol; ok.append(good)
    print(f"[{'OK' if good else 'XX'}] {lab:<40} paper={claim} got={act:.2f}")
chk("instances",753,len(rows),0); chk("repositories",410,len({x['repo'] for x in rows}),0)
chk("ceiling share %",67,100*sum(1 for x in rows if x['before']>=.90)/len(rows),0.6)
chk("prescriptive n",251,len(pres),0)
chk("headroom tool %",10.21,100*mean([x['cap'] for x in T]))
chk("headroom decl %",3.64,100*mean([x['cap'] for x in D]))
chk("contact tool",0.472,mean([x['contact'] for x in T]),0.002)
chk("contact decl",0.516,mean([x['contact'] for x in D]),0.002)
byf=collections.defaultdict(list)
for x in pres: byf[x['family']].append(x)
obs=mean([x['cap'] for x in T])-mean([x['cap'] for x in D]); null=[]
for _ in range(20000):
    t=[];d=[]
    for fam,xs in byf.items():
        labs=[x['tool'] for x in xs]; random.shuffle(labs)
        for x,l in zip(xs,labs): (t if l else d).append(x['cap'])
    if t and d: null.append(mean(t)-mean(d))
chk("stratified permutation p",0.022,sum(1 for v in null if abs(v)>=abs(obs))/len(null),0.008)
print(f"\n{sum(ok)}/{len(ok)} verified")
sys.exit(0 if all(ok) else 1)
