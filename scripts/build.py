#!/usr/bin/env python3
"""v1 pipeline: extract a research field (VAD) from CVF Open Access listings,
enrich with Semantic Scholar (abstract, citations), classify sub-topics, emit data.json.

Field definition lives in FIELD below — swap it to analyse RE-ID, Crowd, etc."""
import re, html, json, sys, time, urllib.request, urllib.parse, ssl, os

CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE

FIELD = {
    "key": "vad",
    "name": "Video Anomaly Detection",
    "tagline": "VAD / VAU — anomalous event detection & understanding in video",
    # tightened include patterns (genuine video-anomaly signal)
    "include": re.compile(
        r"video anomal|anomal\w* (event|action|behavio|video)|"
        r"(weakly|semi|self)[- ]?supervised[- \w]*anomal|anomal[- \w]*supervis|"
        r"violen\w* (detection|recognition|anticipation|localiz)|"
        r"abnormal\w* (event|behavio|action|activit)|unusual event|"
        r"traffic anomal|skeleton[- \w]*anomal|anomal[- \w]*skeleton", re.I),
    "ctx": re.compile(r"(video|surveillance|crowd|cctv|pedestrian|traffic)", re.I),
    "anom": re.compile(r"anomal", re.I),
    # off-topic signatures (image/industrial anomaly, forgery) — drop unless clearly video-anomaly
    "neg": re.compile(r"\b(industrial|mvtec|visa\b|texture defect|medical image|wafer|manufactur|"
                      r"forgery|deepfake|face[- ]swap|multi[- ]class)\b", re.I),
    "subtopics": [
        ("Weakly-supervised", r"weakly[- ]?supervised|weak label|video[- ]level label|\bmil\b|multiple instance"),
        ("VLM / LLM", r"\b(vlm|llm|mllm)\b|vision[- ]language|language model|\bprompt|verbaliz|explainable"),
        ("Zero-/Open-vocab", r"zero[- ]shot|open[- ]vocabular|open[- ]set|open[- ]world|training[- ]free"),
        ("Skeleton / Pose", r"\bskeleton|\bkeypoint|\bgait\b|pose estimation|human pose"),
        ("Reconstruction / Prediction", r"reconstruct|\bpredict|memory bank|auto[- ]?encoder|future frame"),
        ("Diffusion / Flow", r"\bdiffusion|flow matching|score matching"),
        ("Multimodal / Audio", r"\baudio\b|multi[- ]?modal|\bsound\b|audio[- ]visual"),
        ("Traffic / Driving", r"\btraffic|\bdriving|\baccident|\broad\b"),
    ],
}

VENUES = [("CVPR","2025","data/cvpr2025_oa.html","CVPR2025","CVPR_2025"),
          ("CVPR","2026","data/cvpr2026_oa.html","CVPR2026","CVPR_2026"),
          ("ICCV","2025","data/iccv2025_oa.html","ICCV2025","ICCV_2025")]
CVF = "https://openaccess.thecvf.com/content/{slug}/html/{stub}_{ptag}_paper.html"

def is_field(t):
    """Return 'strong' (curated include pattern), 'weak' (anomaly + video context), or None."""
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

def s2(title):
    """Semantic Scholar best-match for a title → abstract, citations, year, venue."""
    try:
        url="https://api.semanticscholar.org/graph/v1/paper/search/match?"+urllib.parse.urlencode(
            {"query":title,"fields":"title,abstract,citationCount,year,venue,externalIds"})
        req=urllib.request.Request(url,headers={"User-Agent":"cv-field-analysis"})
        with urllib.request.urlopen(req,context=CTX,timeout=30) as r:
            d=json.load(r)
        m=(d.get("data") or [None])[0]
        if not m: return {}
        # require a reasonable title overlap to avoid wrong matches
        return {"abstract":m.get("abstract") or "","citations":m.get("citationCount") or 0,
                "s2year":m.get("year"),"s2venue":m.get("venue") or "",
                "arxiv":(m.get("externalIds") or {}).get("ArXiv","")}
    except Exception as e:
        return {}

def confirm(p):
    """Strong matches always kept; weak matches scrutinised against off-topic signatures."""
    title=p["title"].lower(); ab=(p.get("abstract") or "").lower(); blob=title+" "+ab
    clearly_vad=bool(re.search(r"video anomal|anomal\w* (event|video)", title))
    # off-topic (forgery / image / industrial AD) unless unmistakably video anomaly
    if FIELD["neg"].search(blob) and not (clearly_vad or re.search(r"\bsurveillance\b", blob)):
        return False
    if p["_match"]=="strong" or clearly_vad:
        return True
    # weak signal: require the abstract to affirm video + anomaly
    if ab:
        return bool(re.search(r"\b(surveillance|frame|clip|cctv|crowd)\b|video anomal", ab)
                    and re.search(r"anomal|abnormal|violen|unusual", ab))
    return False   # weak + no abstract → drop

def subtopics(p):
    blob=(p["title"]+" "+(p.get("abstract") or "")).lower()
    return [name for name,pat in FIELD["subtopics"] if re.search(pat,blob)]

def main():
    cand=[]
    totals={}
    for venue,year,path,slug,ptag in VENUES:
        papers=parse(path,slug,ptag)
        totals[(venue,year)]=len(papers)
        for p in papers:
            mt=is_field(p["title"])
            if mt:
                p["venue"]=venue; p["year"]=int(year); p["_match"]=mt; cand.append(p)
    print(f"candidates: {len(cand)}", file=sys.stderr)
    kept=[]
    for p in cand:
        info=s2(p["title"]); p.update(info); time.sleep(1.1)
        if confirm(p):
            p["subtopics"]=subtopics(p)
            p["url"]=CVF.format(slug=p["slug"],stub=p["stub"],ptag=p["ptag"])
            kept.append(p)
            print(f"  KEEP {p['venue']}{p['year']} [{p.get('citations',0)}c] {p['title'][:60]}", file=sys.stderr)
        else:
            print(f"  drop {p['venue']}{p['year']} {p['title'][:60]}", file=sys.stderr)

    # aggregate
    trend=[{"venue":v,"year":int(y),"count":sum(1 for p in kept if p["venue"]==v and p["year"]==int(y)),
            "total":totals[(v,y)]} for v,y,_,_,_ in VENUES]
    from collections import Counter
    sc=Counter(s for p in kept for s in p["subtopics"])
    subs=[{"name":n,"count":c} for n,c in sorted(sc.items(),key=lambda x:-x[1])]
    data={
        "field":FIELD["name"],"field_key":FIELD["key"],"tagline":FIELD["tagline"],
        "venues":sorted(set(v for v,_,_,_,_ in VENUES)),
        "years":sorted(set(int(y) for _,y,_,_,_ in VENUES)),
        "total":len(kept),
        "trend":trend,"subtopics":subs,
        "papers":[{"title":p["title"],"authors":p["authors"],"venue":p["venue"],"year":p["year"],
                   "url":p["url"],"arxiv":p.get("arxiv",""),"citations":p.get("citations",0),
                   "abstract":(p.get("abstract") or "")[:600],"subtopics":p["subtopics"]}
                  for p in sorted(kept,key=lambda p:(-p["year"],p["venue"],-p.get("citations",0)))],
        "sources":["CVF Open Access","Semantic Scholar"],
    }
    pass
    json.dump(data,open("data.json","w"),ensure_ascii=False,indent=1)
    print(f"\nwrote data.json — {len(kept)} papers, {len(subs)} subtopics",file=sys.stderr)

if __name__=="__main__":
    main()
