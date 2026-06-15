#!/usr/bin/env python3
"""Backfill abstracts for corpus papers that have none (CVF/DBLP rows where Semantic Scholar
missed them) by querying the arXiv API, validated against a title-similarity guard so we never
attach the wrong preprint. Caches to data/arxiv_abs.json keyed by the paper's normalised title."""
import json, re, time, sys, urllib.request, urllib.parse, ssl
import xml.etree.ElementTree as ET
CTX=ssl.create_default_context();CTX.check_hostname=False;CTX.verify_mode=ssl.CERT_NONE
API="https://export.arxiv.org/api/query?"
ATOM="{http://www.w3.org/2005/Atom}"

def norm(s): return re.sub(r"[^a-z0-9]+"," ",s.lower()).strip()
def toks(s): return set(norm(s).split())
def sim(a,b):
    A,B=toks(a),toks(b)
    return len(A&B)/len(A|B) if A|B else 0.0

def query(title):
    q=urllib.parse.urlencode({"search_query":f'ti:"{title}"',"max_results":5,"start":0})
    try:
        with urllib.request.urlopen(urllib.request.Request(API+q,headers={"User-Agent":"cv-field-analysis"}),context=CTX,timeout=40) as r:
            return ET.fromstring(r.read())
    except Exception as e:
        print(f"  ! query failed: {e}",file=sys.stderr); return None

def best(feed,title):
    cand=[]
    for e in feed.findall(ATOM+"entry"):
        t=(e.findtext(ATOM+"title") or "").strip()
        s=(e.findtext(ATOM+"summary") or "").strip()
        aid=(e.findtext(ATOM+"id") or "")
        m=re.search(r"arxiv\.org/abs/([^v]+)",aid)
        cand.append((sim(title,t),t,re.sub(r"\s+"," ",s),m.group(1) if m else ""))
    cand.sort(reverse=True)
    return cand[0] if cand else None

def main():
    corpus=json.load(open("data/corpus.json"))
    targets=[p for p in corpus if not (p.get("abstract") or "").strip()]
    try: cache=json.load(open("data/arxiv_abs.json"))
    except Exception: cache={}
    print(f"{len(targets)} abstract-less papers to look up",file=sys.stderr)
    for p in targets:
        key=norm(p["title"])
        if key in cache: continue
        feed=query(p["title"]); time.sleep(3.2)        # arXiv API: be polite
        if feed is None: continue
        b=best(feed,p["title"])
        if b and b[0]>=0.72 and len(b[2])>120:
            cache[key]={"arxiv":b[3],"abstract":b[2],"matched_title":b[1],"sim":round(b[0],2)}
            print(f"  MATCH {b[0]:.2f} [{p['venue']}{p['year']}] {p['title'][:48]} -> {b[3]}",file=sys.stderr)
        else:
            cache[key]={"arxiv":"","abstract":"","sim":round(b[0],2) if b else 0.0,"miss":True}
            print(f"  miss  {b[0] if b else 0:.2f} [{p['venue']}{p['year']}] {p['title'][:48]}",file=sys.stderr)
        json.dump(cache,open("data/arxiv_abs.json","w"),ensure_ascii=False,indent=1)
    got=sum(1 for v in cache.values() if v.get("abstract"))
    print(f"\nwrote data/arxiv_abs.json — {got} abstracts matched of {len(cache)} looked up",file=sys.stderr)

if __name__=="__main__": main()
