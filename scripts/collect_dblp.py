#!/usr/bin/env python3
"""Collect field-candidate papers from DBLP for venues not on CVF Open Access.
Polite pacing + retries (DBLP rate-limits hard) + caches to data/dblp_raw.json."""
import urllib.request, urllib.parse, json, ssl, time, os, sys
CTX=ssl.create_default_context();CTX.check_hostname=False;CTX.verify_mode=ssl.CERT_NONE

# (display venue, dblp stream, [years])
SOURCES=[("ECCV","conf/eccv",[2024,2026]),("BMVC","conf/bmvc",[2024,2025]),
         ("AAAI","conf/aaai",[2025,2026]),("NeurIPS","conf/nips",[2024,2025]),
         ("ICLR","conf/iclr",[2025,2026]),("ICML","conf/icml",[2025,2026]),
         ("TPAMI","journals/pami",[2025,2026]),("TIP","journals/tip",[2025,2026])]
QUERIES=["anomaly","violence","abnormal event"]   # union catches most VAD titles
PAUSE=5.0

def dblp(q, retries=5):
    url="https://dblp.org/search/publ/api?"+urllib.parse.urlencode({"q":q,"format":"json","h":100})
    for a in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"cv-field-analysis"}),context=CTX,timeout=40) as r:
                d=json.load(r)
            return d["result"]["hits"].get("hit",[])
        except Exception:
            time.sleep(6+a*6)
    return None

def authors(info):
    a=info.get("authors",{}).get("author",[])
    if isinstance(a,dict): a=[a]
    return ", ".join(x.get("text","") if isinstance(x,dict) else str(x) for x in a)

def main():
    out={}; fails=[]
    for venue,stream,years in SOURCES:
        for y in years:
            seen={}
            for kq in QUERIES:
                hits=dblp(f"{kq} stream:streams/{stream}: year:{y}:")
                if hits is None: fails.append((venue,y,kq)); time.sleep(PAUSE); continue
                for x in hits:
                    info=x["info"]; t=info.get("title","").rstrip(".").strip()
                    key=t.lower()
                    if key and key not in seen:
                        seen[key]={"title":t,"authors":authors(info),
                                   "url":info.get("ee") or info.get("url",""),
                                   "venue":venue,"year":int(y)}
                time.sleep(PAUSE)
            out[f"{venue}{y}"]=list(seen.values())
            print(f"  {venue} {y}: {len(seen)} candidates", flush=True)
    os.makedirs("data",exist_ok=True)
    json.dump(out,open("data/dblp_raw.json","w"),ensure_ascii=False,indent=1)
    print(f"\nwrote data/dblp_raw.json ({sum(len(v) for v in out.values())} rows)",flush=True)
    if fails: print("RATE-LIMIT FAILS (rerun to fill):",fails,flush=True)

if __name__=="__main__": main()
