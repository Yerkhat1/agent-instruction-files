#!/usr/bin/env python3
"""PolicyProp phase 2 — measure per-file compliance before/after the rule date,
split by whether anything touched the file, for tool-backed vs declaration-only rules.

Prediction under the contact hypothesis:
  DECLARATION-ONLY : compliance rises only in files that were edited after the rule.
  TOOL-BACKED      : compliance rises in untouched files too, because the linter
                     sweeps the whole tree regardless of what anyone opened.

Compliance is computed deterministically (Python AST / line scan). No model judging.
"""
import subprocess, json, os, sys, ast, io, tokenize, collections, shutil

HERE=os.path.dirname(os.path.abspath(__file__))
WORK=os.environ.get("PP_WORK",os.path.join(HERE,"..","clones"))
os.makedirs(WORK, exist_ok=True)

def sh(*a, cwd=None, t=600):
    p=subprocess.run(a,capture_output=True,text=True,cwd=cwd,timeout=t)
    return p.stdout if p.returncode==0 else ""

# ---------- deterministic compliance metrics ----------
def m_type_hints(src):
    try: tree=ast.parse(src)
    except SyntaxError: return None
    tot=ok=0
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            tot+=1
            args=[a for a in n.args.args+n.args.kwonlyargs if a.arg not in ("self","cls")]
            if n.returns is not None or any(a.annotation for a in args): ok+=1
    return (ok,tot)

def m_docstrings(src):
    try: tree=ast.parse(src)
    except SyntaxError: return None
    tot=ok=0
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            if n.name.startswith("_"): continue
            tot+=1
            if ast.get_docstring(n): ok+=1
    return (ok,tot)

def m_line_length(src, limit=88):
    lines=src.splitlines()
    if not lines: return None
    return (sum(1 for l in lines if len(l)<=limit), len(lines))

METRIC={"type_hints":m_type_hints,"docstrings":m_docstrings,"line_length":m_line_length}

# ---------- repo handling ----------
def clone(repo):
    dst=os.path.join(WORK, repo.replace("/","__"))
    if os.path.isdir(os.path.join(dst,".git")): return dst
    # blob-filtered: history only. `git archive` then batch-fetches just the two
    # trees we measure, instead of downloading every blob ever committed.
    ok=sh("git","clone","--filter=blob:none","--no-checkout","--quiet",
          f"https://github.com/{repo}.git", dst, t=300)
    return dst if os.path.isdir(os.path.join(dst,".git")) else None

def rev_at(d, cwd):
    return sh("git","rev-list","-1",f"--before={d} 23:59:59","HEAD",cwd=cwd).strip()

def pyfiles(rev,cwd):
    return [p for p in sh("git","ls-tree","-r","--name-only",rev,cwd=cwd).splitlines()
            if p.endswith(".py") and "/test" not in p and not p.startswith("test")]

def snapshot(rev, cwd):
    """Extract an entire revision once and return {path: source}. One subprocess,
    not one per file -- the difference between minutes and hours."""
    import tarfile, io as _io
    p=subprocess.run(["git","archive","--format=tar",rev],cwd=cwd,
                     capture_output=True,timeout=900)
    if p.returncode!=0: return {}
    out={}
    try:
        tf=tarfile.open(fileobj=_io.BytesIO(p.stdout))
    except Exception:
        return {}
    for m in tf.getmembers():
        if not m.isfile() or not m.name.endswith(".py"): continue
        if "/test" in m.name or m.name.startswith("test"): continue
        if m.size > 400_000: continue
        try: out[m.name]=tf.extractfile(m).read().decode("utf-8","replace")
        except Exception: pass
    return out

def touched_since(date,cwd):
    return {p.strip() for p in sh("git","log","--name-only","--format=",f"--since={date}",cwd=cwd).splitlines() if p.strip().endswith(".py")}

def run(entry):
    import time as _t; _t0=_t.time()
    repo=entry["repo"]; cwd=clone(repo)
    if not cwd: return []
    head=sh("git","rev-list","-1","HEAD",cwd=cwd).strip()
    if not head: return []
    out=[]; snap_cache={}
    for fam in entry["declared"]:
        d=entry["rule_date"].get(fam)
        if not d: continue
        r0=rev_at(d,cwd)
        if not r0 or r0==head: continue
        if _t.time()-_t0 > 240: break   # guard: skip slow repos
        for r in (r0,head):
            if r not in snap_cache: snap_cache[r]=snapshot(r,cwd)
        s0,s1=snap_cache[r0],snap_cache[head]
        surv=set(s0)&set(s1)
        if len(surv)<8: continue
        tch=touched_since(d,cwd)
        agg=collections.defaultdict(lambda: collections.Counter())
        for p in surv:
            grp="touched" if p in tch else "untouched"
            for src,when in ((s0[p],"before"),(s1[p],"after")):
                r=METRIC[fam](src)
                if not r: continue
                agg[(grp,when)]["ok"]+=r[0]; agg[(grp,when)]["tot"]+=r[1]
        rec={"repo":repo,"family":fam,"tool_backed":entry["tool_backed"].get(fam,False),
             "rule_date":d,"n_survivors":len(surv),"n_touched":len(surv&tch)}
        for k,v in agg.items():
            rec[f"{k[0]}_{k[1]}"]=(v["ok"]/v["tot"]) if v["tot"] else None
            rec[f"{k[0]}_{k[1]}_n"]=v["tot"]
        out.append(rec)
    shutil.rmtree(cwd, ignore_errors=True)
    return out

if __name__=="__main__":
    entries=[json.loads(l) for l in open(os.path.join(HERE,"..","data","classified_repos.jsonl"))]
    print(f"repos to measure: {len(entries)}", file=sys.stderr)
    res=[]
    for i,e in enumerate(entries):
        try:
            rs=run(e)
            res+=rs
            for r in rs:
                tb="TOOL" if r["tool_backed"] else "DECL"
                print(f"[{i+1}/{len(entries)}] {r['repo'][:38]:<38} {r['family']:<12} {tb} "
                      f"surv={r['n_survivors']:<4} touched={r['n_touched']}", file=sys.stderr)
            with open(os.path.join(HERE,"..","data","measures.rerun.jsonl"),"w") as f:
                for r in res: f.write(json.dumps(r)+"\n")
        except Exception as ex:
            print(f"  skip {e['repo']}: {type(ex).__name__} {ex}", file=sys.stderr)
    print(f"\nwrote policyprop_measures.jsonl rows={len(res)}", file=sys.stderr)
