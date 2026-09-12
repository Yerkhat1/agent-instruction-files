#!/usr/bin/env python3
"""Step 1 - discover and classify.

Find public repositories whose CLAUDE.md or AGENTS.md states a rule in one of three
statically checkable families (type annotations, docstrings, line length), date the
rule by binary search over the instruction file's history, and label it tool-backed
if the repository ships configuration that enforces it.

Discovery searches for the rule vocabulary directly and partitions each query by file
size, because GitHub code search caps results per query and random sampling of the
filenames yields few prescriptive rules. Requires an authenticated `gh` CLI.

Search results drift as repositories change, so re-running this will not reproduce
data/classified_repos.jsonl exactly. The released data files are the authoritative corpus.
"""
import subprocess, json, re, sys, time, os
HERE=os.path.dirname(os.path.abspath(__file__))
OUT=os.path.join(HERE,"..","data","classified_repos.rerun.jsonl")

RULES = {
 "type_hints": re.compile(r"(type[- ]?hints?|type annotations?|\bmypy\b|\bpyright\b|annotate .{0,15}signature)", re.I),
 "docstrings": re.compile(r"(docstrings?|\bpydocstyle\b|document (all|every) (public )?(function|method|class))", re.I),
 "line_length":re.compile(r"(line[- ]length|max[- ]line|\b(79|88|100|120) characters|\bblack\b|ruff format)", re.I),
}
# a rule is TOOL-BACKED if the repo ships config that enforces it mechanically
TOOLCFG = {
 "type_hints": [("pyproject.toml", r"\[tool\.(mypy|pyright)\]"), ("mypy.ini", r"."),
                ("setup.cfg", r"\[mypy\]"), (".pre-commit-config.yaml", r"(mypy|pyright)")],
 "docstrings": [("pyproject.toml", r"(pydocstyle|\"D[0-9]|'D[0-9]|select.*\bD\b)"),
                (".pre-commit-config.yaml", r"pydocstyle")],
 "line_length":[("pyproject.toml", r"(line-length|line_length|\[tool\.black\]|\[tool\.ruff\])"),
                ("setup.cfg", r"max-line-length"), (".flake8", r"max-line-length"),
                (".pre-commit-config.yaml", r"(black|ruff)")],
}
LANG = re.compile(r"\b(python|\.py\b|pytest|mypy|ruff|black)\b", re.I)

def gh(*a, t=90):
    p=subprocess.run(["gh",*a],capture_output=True,text=True,timeout=t)
    return p.stdout if p.returncode==0 else ""

def raw(repo, path, ref=None):
    q=f"repos/{repo}/contents/{path}" + (f"?ref={ref}" if ref else "")
    return gh("api", q, "-H", "Accept: application/vnd.github.raw")

def classify(repo, path):
    txt = raw(repo, path)
    if not txt or not LANG.search(txt): return None
    declared = [f for f,p in RULES.items() if p.search(txt)]
    if not declared: return None
    backed = {}
    cfg_cache = {}
    for fam in declared:
        b = False
        for fn, pat in TOOLCFG[fam]:
            if fn not in cfg_cache: cfg_cache[fn] = raw(repo, fn) or ""
            if cfg_cache[fn] and re.search(pat, cfg_cache[fn], re.I): b = True; break
        backed[fam] = b
    # rule date: first revision of the instruction file mentioning the family
    try: cs = json.loads(gh("api","-X","GET",f"repos/{repo}/commits","-f",f"path={path}","-f","per_page=100"))
    except Exception: cs = []
    if not isinstance(cs, list) or not cs: return None
    cs = list(reversed(cs))
    dates = {}
    for fam in declared:
        lo, hi = 0, len(cs)-1
        while lo < hi:                                  # binary search: rule present at hi
            mid=(lo+hi)//2
            c = raw(repo, path, cs[mid]["sha"])
            if c and RULES[fam].search(c): hi=mid
            else: lo=mid+1
            time.sleep(0.15)
        dates[fam] = cs[hi]["commit"]["committer"]["date"][:10]
    return {"repo":repo,"path":path,"declared":declared,"tool_backed":backed,
            "rule_date":dates,"n_revs":len(cs)}


TERMS=["mypy","pyright","docstring","pydocstyle","\"type hints\"","ruff","black","\"line length\""]
SIZES=["<1500","1500..4000","4000..9000",">9000"]

def discover():
    seen={}
    for fname in ("CLAUDE.md","AGENTS.md"):
        for term in TERMS:
            for sz in SIZES:
                for pg in (1,2):
                    q=f"filename:{fname} {term} size:{sz}"
                    try: r=json.loads(gh("api","-X","GET","search/code","-f",f"q={q}",
                                         "-f","per_page=100","-f",f"page={pg}"))
                    except Exception: break
                    items=r.get("items",[])
                    if not items: break
                    for it in items: seen.setdefault(it["repository"]["full_name"], it["path"])
                    time.sleep(2.2)
                print(f"  {fname} {term:<16} size:{sz:<12} total={len(seen)}", file=sys.stderr)
    return seen

if __name__ == "__main__":
    found=discover()
    print(f"discovered {len(found)}", file=sys.stderr)
    with open(OUT,"w") as fh:
        for i,(r,p) in enumerate(found.items()):
            try:
                c=classify(r,p)
                if c:
                    fh.write(json.dumps(c)+"\n"); fh.flush()
                    print(f"[{i+1}/{len(found)}] {r}", file=sys.stderr)
            except Exception as e:
                print(f"  skip {r}: {type(e).__name__}", file=sys.stderr)
            time.sleep(0.3)
