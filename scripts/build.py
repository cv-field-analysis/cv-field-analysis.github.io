#!/usr/bin/env python3
"""Pipeline: extract a research field (VAD/VAU) from CVF Open Access + Paper Copilot + DBLP,
enrich with Semantic Scholar (abstract, citations), then merge an abstract-based multi-axis
tag layer (tags.json, produced by reading each paper's abstract) and emit data.json.

Two-pass design for the abstract-based stage:
  pass 1 (no tags.json)  -> writes data/corpus.json  {id,title,abstract,venue,year}  for tagging
  (read abstracts -> write tags.json keyed by id, optional tags_manual.json override)
  pass 2 (tags present)  -> merges tags + derived analytics into data.json

Field definition lives in FIELD below — swap it to analyse RE-ID, Crowd, etc."""
import re, html, json, sys, time, urllib.request, urllib.parse, ssl, os
from collections import Counter, defaultdict

CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE

# ---------------------------------------------------------------- field config
FIELD = {
    "key": "vad",
    "name": "Video Anomaly Detection",
    "tagline": "VAD / VAU — anomalous event detection, grounding, understanding & reasoning in video",
    "include": re.compile(
        r"video anomal|anomal\w* (event|action|behavio|video)|"
        r"violen\w* (detection|recognition|anticipation|localiz)|"
        r"abnormal\w* (event|behavio|action|activit)|unusual event|"
        r"traffic anomal|skeleton[- \w]*anomal|anomal[- \w]*skeleton", re.I),
    "ctx": re.compile(r"(video|surveillance|crowd|cctv|pedestrian|traffic)", re.I),
    "anom": re.compile(r"anomal", re.I),
    "neg": re.compile(r"\b(industrial|mvtec|visa\b|texture defect|medical image|wafer|manufactur|"
                      r"forgery|deepfake|face[- ]swap|multi[- ]class|graph|time[- ]?series|tabular|"
                      r"hyperspectral|node[- ]level|log anomal|intrusion|sensor network|point cloud)\b", re.I),
}

# Inclusion / exclusion criteria — surfaced on the page so coverage is auditable.
CRITERIA = {
    "include": ("Papers are included if their title/abstract explicitly targets video anomaly "
                "detection, understanding, grounding or reasoning, video violence detection, "
                "traffic/road anomaly detection, or closely related abnormal-event analysis in video."),
    "exclude": ("Generic image anomaly detection, industrial defect detection, medical-image "
                "anomaly, graph/tabular/time-series anomaly, and deepfake/forgery detection are "
                "excluded unless the paper explicitly addresses a video anomaly task."),
}

# ------------------------------------------------- venue × year edition calendar
# status: ok=accepted list available/expected (count is real, may be 0)
#         soon=venue runs this year but the list is not released yet (as of BUILD_DATE)
#         pending=released, but only reachable via DBLP (not collectable in this environment yet)
# A cell absent from the calendar renders blank (venue not held that year: ICCV even, ECCV odd).
BUILD_DATE = (2026, 6)   # (year, month) — anchors "not released yet" + citations/month
CALENDAR = [
    ("CVPR",2024,"ok"),   ("CVPR",2025,"ok"),   ("CVPR",2026,"ok"),
    ("ICCV",2025,"ok"),
    ("ECCV",2024,"ok"),                          ("ECCV",2026,"soon"),
    ("BMVC",2024,"ok"),   ("BMVC",2025,"pending"),("BMVC",2026,"soon"),
    ("AAAI",2024,"ok"),   ("AAAI",2025,"ok"),   ("AAAI",2026,"ok"),
    ("NeurIPS",2024,"ok"),("NeurIPS",2025,"ok"),("NeurIPS",2026,"soon"),
    ("ICLR",2024,"ok"),   ("ICLR",2025,"ok"),   ("ICLR",2026,"ok"),
    ("ICML",2024,"ok"),   ("ICML",2025,"ok"),   ("ICML",2026,"soon"),
    ("TPAMI",2024,"ok"),  ("TPAMI",2025,"ok"),("TPAMI",2026,"ok"),
    ("TIP",2024,"ok"),    ("TIP",2025,"ok"),  ("TIP",2026,"ok"),
]
STATUS = {(v,y):s for v,y,s in CALENDAR}
# typical publication month per venue — for the citations/month age estimate
VENUE_MONTH = {"CVPR":6,"ICCV":10,"ECCV":10,"BMVC":11,"AAAI":2,"NeurIPS":12,
               "ICLR":4,"ICML":7,"TPAMI":6,"TIP":6}

VENUES = [("CVPR","2025","data/cvpr2025_oa.html","CVPR2025","CVPR_2025"),
          ("CVPR","2026","data/cvpr2026_oa.html","CVPR2026","CVPR_2026"),
          ("ICCV","2025","data/iccv2025_oa.html","ICCV2025","ICCV_2025")]
CVF = "https://openaccess.thecvf.com/content/{slug}/html/{stub}_{ptag}_paper.html"

# axis display order (rendering); labels not listed still appear, after these
AXES = [
    ("task",         "Task"),
    ("supervision",  "Supervision"),
    ("model_family", "Model family"),
    ("modality",     "Modality"),
    ("domain",       "Domain"),
    ("method",       "Method"),
]

def is_field(t):
    low=t.lower()
    if FIELD["include"].search(low): return "strong"
    if FIELD["anom"].search(low) and FIELD["ctx"].search(low): return "weak"
    return None

def parse(path, slug, ptag):
    doc=open(path,encoding="utf-8",errors="ignore").read()
    out=[]
    for block in re.split(r'<dt class="ptitle">',doc)[1:]:
        m=re.search(r'href="/content/'+slug+r'/html/(.*?)_'+ptag+r'_paper\.html"[^>]*>(.*?)</a>',block,re.S)
        if not m: continue
        stub=m.group(1)
        title=html.unescape(re.sub(r'\s+',' ',m.group(2)).strip())
        authors=", ".join(re.findall(r'name="query_author" value="(.*?)"',block))
        out.append({"title":title,"stub":stub,"authors":authors,"slug":slug,"ptag":ptag})
    return out

S2CACHE_PATH="data/s2_cache.json"
try: S2CACHE=json.load(open(S2CACHE_PATH))
except Exception: S2CACHE={}

# arXiv-backfilled abstracts for papers Semantic Scholar missed (keyed by normalised title;
# see scripts/fetch_arxiv_abs.py) + a manual exclude list (paper id -> reason).
def _norm(s): return re.sub(r"[^a-z0-9]+"," ",html.unescape(s).lower()).strip()
try: ARXIV_ABS=json.load(open("data/arxiv_abs.json"))
except Exception: ARXIV_ABS={}
try: EXCLUDE=json.load(open("data/exclude.json"))
except Exception: EXCLUDE={}

def s2(title):
    if title in S2CACHE: return S2CACHE[title]
    r=_s2_fetch(title); time.sleep(1.1)
    S2CACHE[title]=r; json.dump(S2CACHE,open(S2CACHE_PATH,"w"),ensure_ascii=False)
    return r

def _s2_fetch(title):
    try:
        url="https://api.semanticscholar.org/graph/v1/paper/search/match?"+urllib.parse.urlencode(
            {"query":title,"fields":"title,abstract,citationCount,year,venue,externalIds"})
        req=urllib.request.Request(url,headers={"User-Agent":"cv-field-analysis"})
        with urllib.request.urlopen(req,context=CTX,timeout=30) as r:
            d=json.load(r)
        m=(d.get("data") or [None])[0]
        if not m: return {}
        return {"abstract":m.get("abstract") or "","citations":m.get("citationCount") or 0,
                "arxiv":(m.get("externalIds") or {}).get("ArXiv","")}
    except Exception:
        return {}

def confirm(p):
    title=p["title"].lower(); ab=(p.get("abstract") or "").lower(); blob=title+" "+ab
    clearly_vad=bool(re.search(r"video anomal|anomal\w* (event|video)", title))
    if FIELD["neg"].search(blob) and not (clearly_vad or re.search(r"\bsurveillance\b", blob)):
        return False
    if p["_match"]=="strong" or clearly_vad:
        return True
    if ab:
        return bool(re.search(r"\b(surveillance|frame|clip|cctv|crowd)\b|video anomal", ab)
                    and re.search(r"anomal|abnormal|violen|unusual", ab))
    return False

def slugify(s,n=46):
    return re.sub(r"-+","-",re.sub(r"[^a-z0-9]+","-",s.lower())).strip("-")[:n].strip("-")

def make_id(p, used):
    base=f"{p['venue'].lower()}{p['year']}-{slugify(p['title'])}"
    pid=base; i=2
    while pid in used: pid=f"{base}-{i}"; i+=1
    used.add(pid); return pid

# ------------------------------------------------------- abstract-based tag layer
def load_tags():
    def _load(path):
        try: return json.load(open(path))
        except Exception: return {}
    return _load("data/tags.json"), _load("data/tags_manual.json")

# minimal rule fallback so an untagged new paper still renders (flagged needs_review)
RULE=[("supervision","Weakly-sup", r"weakly[- ]?supervised|weak label|video[- ]level label|\bmil\b|multiple instance"),
      ("supervision","Unsupervised", r"unsupervised|one[- ]class|normality"),
      ("supervision","Open-vocab", r"open[- ]vocabular|open[- ]set|open[- ]world"),
      ("supervision","Zero-shot",  r"zero[- ]shot|training[- ]free|tuning[- ]free"),
      ("model_family","VLM",        r"\b(vlm|mllm|lvlm)\b|vision[- ]language|visual[- ]language"),
      ("model_family","LLM",        r"\bllm\b|large language model"),
      ("model_family","Diffusion",  r"\bdiffusion|score matching|flow matching"),
      ("model_family","Reconstruction", r"reconstruct|auto[- ]?encoder|memory bank|future frame|predict"),
      ("modality","Pose/Skeleton",  r"\bskeleton|\bpose\b|\bkeypoint|\bgait\b"),
      ("modality","Audio",          r"\baudio\b|audio[- ]visual|\bsound\b"),
      ("modality","Text",           r"\bcaption|text|language"),
      ("domain","Traffic/Driving",  r"\btraffic|\bdriving|\baccident|\broad\b"),
      ("domain","Violence",         r"violen"),
      ("task","Understanding",      r"understand|explain|caption|describe"),
      ("task","Reasoning",          r"reason|chain[- ]of[- ]thought|causal|intention"),
      ("task","Localization/Grounding", r"ground|localiz|temporal segment|spatio"),
      ("task","Retrieval/QA",       r"retrieval|question answering|\bqa\b"),
      ("task","Anticipation",       r"anticipat|forecast|early detection")]
def rule_axes(p):
    blob=(p["title"]+" "+(p.get("abstract") or "")).lower()
    ax=defaultdict(list)
    for axis,label,pat in RULE:
        if re.search(pat,blob) and label not in ax[axis]: ax[axis].append(label)
    ax["task"]=ax.get("task") or ["Detection"]
    return {"task":ax.get("task",[]),"supervision":ax.get("supervision",[]),
            "model_family":ax.get("model_family",[]),"modality":ax.get("modality",["RGB"]),
            "domain":ax.get("domain",["Surveillance"]),"method":ax.get("method",[]),
            "contribution":"method","confidence":0.3,"evidence":"","needs_review":True,
            "source":"rules"}

def months_since(venue,year):
    bm=BUILD_DATE[0]*12+BUILD_DATE[1]
    pm=year*12+VENUE_MONTH.get(venue,6)
    return max(1, bm-pm)

# ----------------------------------------------------------------------- main
def main():
    cand=[]; totals={}; have=set()           # have = (venue,year) editions already sourced
    # --- CVF Open Access (complete CVPR/ICCV title lists) ---
    for venue,year,path,slug,ptag in VENUES:
        if not os.path.exists(path): continue
        papers=parse(path,slug,ptag); y=int(year)
        totals[(venue,y)]=len(papers); have.add((venue,y))
        for p in papers:
            mt=is_field(p["title"])
            if mt:
                p["venue"]=venue; p["year"]=y; p["_match"]=mt
                p["url"]=CVF.format(slug=p["slug"],stub=p["stub"],ptag=p["ptag"]); cand.append(p)
    # --- Paper Copilot (OpenReview + CVPR/AAAI proceedings; carries abstracts) ---
    if os.path.exists("data/papercopilot_raw.json"):
        pcv=json.load(open("data/papercopilot_verify.json")) if os.path.exists("data/papercopilot_verify.json") else {}
        pc_eds=set()
        for ed, rows in json.load(open("data/papercopilot_raw.json")).items():
            for p in rows:
                v,y=p["venue"],int(p["year"]); key=(v,y)
                if key in have: continue           # CVF Open Access is authoritative for this edition
                pc_eds.add(key); totals.setdefault(key,(pcv.get(ed,{}) or {}).get("accepted"))
                mt=is_field(p["title"])
                if mt:
                    q=dict(p); q["year"]=y; q["_match"]=mt; q["_src"]="pc"; cand.append(q)
        have|=pc_eds
    # --- DBLP (remaining conferences/journals); skip editions already sourced above ---
    if os.path.exists("data/dblp_raw.json"):
        dblp_eds=set()
        for ed, rows in json.load(open("data/dblp_raw.json")).items():
            for p in rows:
                v,y=p["venue"],int(p["year"]); key=(v,y)
                if key in have: continue
                dblp_eds.add(key); totals.setdefault(key,None)
                mt=is_field(p["title"]+" "+(p.get("abstract") or ""))  # abstract-aware when a row carries one (e.g. web-collected)
                if mt:
                    q=dict(p); q["year"]=y; q["_match"]=mt; cand.append(q)
        have|=dblp_eds                          # editions we now hold data for
    print(f"candidates: {len(cand)}", file=sys.stderr)

    # filter / confirm
    kept=[]
    for p in cand:
        if p.get("_src")!="pc":
            p.update(s2(p["title"]))
        if not (p.get("abstract") or "").strip():        # arXiv backfill for missing abstracts
            a=ARXIV_ABS.get(_norm(p["title"]))
            if a and a.get("abstract"):
                p["abstract"]=a["abstract"]
                if not p.get("arxiv"): p["arxiv"]=a.get("arxiv","")
        if confirm(p):
            kept.append(p)
            print(f"  KEEP {p['venue']}{p['year']} [{p.get('citations',0)}c] {p['title'][:56]}", file=sys.stderr)
    # de-dupe across sources
    uniq={}
    for p in kept:
        k=re.sub(r"[^a-z0-9]","",p["title"].lower())
        if k not in uniq or len(p.get("url",""))>len(uniq[k].get("url","")):
            uniq[k]=p
    kept=sorted(uniq.values(),key=lambda p:(-p["year"],p["venue"],-max(0,int(p.get("citations") or 0))))

    # stable ids, then drop manually-excluded (off-topic) papers
    used=set()
    for p in kept: p["id"]=make_id(p,used)
    if EXCLUDE:
        kept=[p for p in kept if p["id"] not in EXCLUDE]
        for pid,why in EXCLUDE.items(): print(f"  EXCLUDE {pid}: {why}", file=sys.stderr)
    corpus=[{"id":p["id"],"title":html.unescape(p["title"]),"venue":p["venue"],"year":p["year"],
             "abstract":(p.get("abstract") or "")} for p in kept]
    json.dump(corpus,open("data/corpus.json","w"),ensure_ascii=False,indent=1)

    # merge abstract-based tags (+ manual override) over a rule fallback
    tags,manual=load_tags()
    for p in kept:
        base=rule_axes(p)
        t=dict(base)
        if p["id"] in tags: t.update(tags[p["id"]]); t["source"]=t.get("source","llm:title+abstract")
        if p["id"] in manual: t.update(manual[p["id"]]); t["needs_review"]=False; t["source"]="manual"
        if not (p.get("abstract")):                       # tagged from title alone
            t["needs_review"]=True; t["source"]=t.get("source","")+"|title-only"
        p["_tags"]=t

    # ---- assemble output records ----
    def axlist(p,axis): return [x for x in (p["_tags"].get(axis) or []) if x]
    papers=[]
    for p in kept:
        t=p["_tags"]; cit=max(0,int(p.get("citations") or 0)); mo=months_since(p["venue"],p["year"])
        papers.append({
            "id":p["id"],"title":html.unescape(p["title"]),"authors":p.get("authors",""),
            "venue":p["venue"],"year":p["year"],"url":p.get("url",""),"arxiv":p.get("arxiv",""),
            "review_url":p.get("review_url",""),"citations":cit,
            "months":mo,"cit_per_month":round(cit/mo,2),
            "task":axlist(p,"task"),"supervision":axlist(p,"supervision"),
            "model_family":axlist(p,"model_family"),"modality":axlist(p,"modality"),
            "domain":axlist(p,"domain"),"method":axlist(p,"method"),
            "contribution":t.get("contribution","method"),
            "confidence":round(float(t.get("confidence",0.3)),2),
            "needs_review":bool(t.get("needs_review",False)),
            "evidence":t.get("evidence",""),
        })

    # ---- trend matrix driven by the calendar ----
    # an edition we actually collected data for is "ok" regardless of its calendar default,
    # so a future DBLP run auto-upgrades a "pending"/"soon" cell to a real count.
    cnt=Counter((p["venue"],p["year"]) for p in papers)
    trend=[]
    for v,y,st in CALENDAR:
        eff="ok" if (v,y) in have else st
        trend.append({"venue":v,"year":y,"status":eff,
                      "count":(cnt.get((v,y),0) if eff=="ok" else None),
                      "total":totals.get((v,y))})

    # ---- axis distributions ----
    axes={}
    for key,_label in AXES:
        c=Counter(x for p in papers for x in p[key])
        axes[key]=[{"name":n,"count":k} for n,k in sorted(c.items(),key=lambda x:(-x[1],x[0]))]
    axes["contribution"]=[{"name":n,"count":k} for n,k in
                          sorted(Counter(p["contribution"] for p in papers).items(),key=lambda x:-x[1])]

    # ---- topic-by-year (for stacked charts / task evolution) ----
    years=sorted({y for _,y,_ in CALENDAR})
    by_year={}
    for key,_label in AXES:
        m={str(y):dict() for y in years}
        for p in papers:
            for x in p[key]: m[str(p["year"])][x]=m[str(p["year"])].get(x,0)+1
        by_year[key]=m

    # ---- venue × task matrix ----
    task_labels=[d["name"] for d in axes["task"]]
    vt_venues=[v for v in dict.fromkeys(v for v,_,_ in CALENDAR) if any(p["venue"]==v for p in papers)]
    venue_topic={"rows":vt_venues,"cols":task_labels,
                 "cells":[[sum(1 for p in papers if p["venue"]==v and t in p["task"]) for t in task_labels]
                          for v in vt_venues]}

    # ---- supervision × model-family co-occurrence ----
    sup_labels=[d["name"] for d in axes["supervision"]][:6]
    mdl_labels=[d["name"] for d in axes["model_family"]][:6]
    cooc={"rows":sup_labels,"cols":mdl_labels,
          "cells":[[sum(1 for p in papers if s in p["supervision"] and m in p["model_family"])
                    for m in mdl_labels] for s in sup_labels]}

    data={
        "field":FIELD["name"],"field_key":FIELD["key"],"tagline":FIELD["tagline"],
        "build_date":f"{BUILD_DATE[0]}-{BUILD_DATE[1]:02d}",
        "venues":[v for v in dict.fromkeys(v for v,_,_ in CALENDAR)],
        "years":years,"total":len(papers),
        "axis_order":[{"key":k,"label":l} for k,l in AXES],
        "trend":trend,"axes":axes,"by_year":by_year,
        "venue_topic":venue_topic,"cooc":cooc,
        "papers":papers,
        "criteria":CRITERIA,
        "sources":["CVF Open Access","Paper Copilot","DBLP","Semantic Scholar"],
        "tagged":sum(1 for p in papers if not p["needs_review"]),
    }
    json.dump(data,open("data.json","w"),ensure_ascii=False,indent=1)
    nrev=sum(1 for p in papers if p["needs_review"])
    print(f"\nwrote data.json — {len(papers)} papers, {len(CALENDAR)} calendar cells, "
          f"{nrev} need review; corpus.json has {len(corpus)} papers to tag",file=sys.stderr)

if __name__=="__main__":
    main()
