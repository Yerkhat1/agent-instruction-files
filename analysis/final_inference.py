#!/usr/bin/env python3
"""PolicyProp final inference. 753 rule-instances, 410 repositories.
Stratified by rule family, because family composition differs between arms and
line_length sits near ceiling almost everywhere."""
import json, random, collections
from statistics import median
random.seed(20260908)
mean=lambda v: sum(v)/len(v) if v else None
R=[json.loads(l) for l in open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)),"..","data","measures.jsonl"))]

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
print(f"usable: {len(rows)}   repos: {len({x['repo'] for x in rows})}")

print("\n=== FINDING A — ceremonial vs prescriptive, BY FAMILY ===")
print(f"{'family':<13}{'n':>5}{'baseline':>10}{'at ceiling':>12}{'mean d':>9}")
for fam in ("line_length","type_hints","docstrings"):
    xs=[x for x in rows if x["family"]==fam]
    if not xs: continue
    ceil=sum(1 for x in xs if x["before"]>=0.90)
    print(f"{fam:<13}{len(xs):>5}{100*mean([x['before'] for x in xs]):>9.1f}%"
          f"{100*ceil/len(xs):>11.0f}%{100*mean([x['d'] for x in xs]):>8.2f}%")
allceil=sum(1 for x in rows if x["before"]>=0.90)
print(f"{'ALL':<13}{len(rows):>5}{100*mean([x['before'] for x in rows]):>9.1f}%"
      f"{100*allceil/len(rows):>11.0f}%{100*mean([x['d'] for x in rows]):>8.2f}%")

pres=[x for x in rows if x["before"]<0.90 and (1-x["before"])>0.02]
for x in pres: x["cap"]=x["d"]/(1-x["before"])
T=[x for x in pres if x["tool"]]; D=[x for x in pres if not x["tool"]]
print(f"\n=== FINDING C — prescriptive subset (n={len(pres)}: TOOL={len(T)}, DECL={len(D)}) ===")
print(f"{'metric':<24}{'TOOL':>11}{'DECL':>11}")
for k,lab,f in (("contact","contact fraction",lambda v:f"{v:.3f}"),
                ("d","whole-tree d",lambda v:f"{100*v:+.2f}%"),
                ("cap","headroom captured",lambda v:f"{100*v:+.2f}%")):
    print(f"{lab:<24}{f(mean([x[k] for x in T])):>11}{f(mean([x[k] for x in D])):>11}")
print(f"{'headroom (median)':<24}{100*median([x['cap'] for x in T]):>10.2f}%{100*median([x['cap'] for x in D]):>10.2f}%")

def strat_perm(key,B=20000):
    """Permute TOOL/DECL labels WITHIN family, so the test cannot be driven by
    arms differing in family composition."""
    byf=collections.defaultdict(list)
    for x in pres: byf[x["family"]].append(x)
    def stat(assign):
        t=[x[key] for x,lab in assign if lab]; d=[x[key] for x,lab in assign if not lab]
        if not t or not d: return None
        return mean(t)-mean(d)
    obs=stat([(x,x["tool"]) for x in pres])
    null=[]
    for _ in range(B):
        assign=[]
        for fam,xs in byf.items():
            labs=[x["tool"] for x in xs]; random.shuffle(labs)
            assign += list(zip(xs,labs))
        s=stat(assign)
        if s is not None: null.append(s)
    p=sum(1 for v in null if abs(v)>=abs(obs))/len(null)
    return obs,p

print("\n=== STRATIFIED PERMUTATION (labels shuffled within family, 20k draws) ===")
for k,lab in (("contact","contact fraction"),("d","whole-tree d"),("cap","headroom captured")):
    o,p=strat_perm(k)
    star=" *" if p<0.05 else ""
    print(f"  {lab:<22} diff={o:+.4f}   p={p:.4f}{star}")

print("\n=== PER-FAMILY, prescriptive only ===")
print(f"  {'family':<13}{'nT':>4}{'nD':>4}{'cap TOOL':>11}{'cap DECL':>11}")
for fam in ("line_length","type_hints","docstrings"):
    t=[x for x in pres if x["family"]==fam and x["tool"]]
    d=[x for x in pres if x["family"]==fam and not x["tool"]]
    if not t or not d: continue
    print(f"  {fam:<13}{len(t):>4}{len(d):>4}{100*mean([x['cap'] for x in t]):>10.2f}%{100*mean([x['cap'] for x in d]):>10.2f}%")

print("\n=== repo-clustered bootstrap on headroom captured ===")
byrepo=collections.defaultdict(list)
for x in pres: byrepo[x["repo"]].append(x)
keys=list(byrepo); boot=[]
for _ in range(4000):
    samp=[]
    for _ in keys: samp += byrepo[random.choice(keys)]
    t=[x["cap"] for x in samp if x["tool"]]; d=[x["cap"] for x in samp if not x["tool"]]
    if t and d: boot.append(mean(t)-mean(d))
boot.sort()
lo,hi=boot[int(.025*len(boot))],boot[int(.975*len(boot))]
print(f"  diff = {mean([x['cap'] for x in T])-mean([x['cap'] for x in D]):+.4f}   95% CI [{lo:+.4f}, {hi:+.4f}]"
      f"   {'excludes 0' if lo>0 or hi<0 else 'includes 0'}")
