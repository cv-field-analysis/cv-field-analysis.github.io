#!/usr/bin/env python3
"""Collect field candidates from Paper Copilot's open data dumps (github.com/papercopilot/paperlists).
Gives complete accepted-paper lists for OpenReview venues (fills DBLP gaps) + OpenReview review links."""
import urllib.request, json, ssl, os, re, sys
CTX=ssl.create_default_context();CTX.check_hostname=False;CTX.verify_mode=ssl.CERT_NONE
RAW="https://raw.githubusercontent.com/papercopilot/paperlists/main/{v}/{v}{y}.json"

# (display venue, papercopilot dir, [years])
SOURCES=[("NeurIPS","nips",[2024,2025]),("ICLR","iclr",[2025,2026]),("ICML","icml",[2025])]
ACCEPT=re.compile(r"poster|spotlight|oral|accept|notable|highlight",re.I)
REJECT=re.compile(r"reject|withdraw|desk",re.I)
# broad anomaly/video pre-filter (build.py applies the real is_field/confirm afterwards)
PRE=re.compile(r"anomal|abnormal|violen",re.I)
VID=re.compile(r"video|surveillance|crowd|pedestrian|traffic|cctv",re.I)

def fetch(v,y):
    url=RAW.format(v=v,y=y)
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"cvfa"}),context=CTX,timeout=120) as r:
            return json.load(r)
    except Exception as e:
        print(f"  ! {v}{y} fetch failed: {e}",file=sys.stderr); return None

def main():
    out={}; verify={}
    for venue,vd,years in SOURCES:
        for y in years:
            rows=fetch(vd,y)
            if rows is None: continue
            accepted=[x for x in rows if (x.get("status") and ACCEPT.search(x["status"]) and not REJECT.search(x["status"]))]
            verify[f"{venue}{y}"]={"total_rows":len(rows),"accepted":len(accepted)}
            cands=[]
            for x in accepted:
                t=x.get("title","") or ""
                blob=t+" "+(x.get("abstract","") or "")
                if not (PRE.search(t) or (PRE.search(blob) and VID.search(blob))): continue
                cands.append({
                    "title":t.strip(),
                    "authors":(x.get("author") or "").replace(";",", ").strip(", "),
                    "venue":venue,"year":int(y),
                    "url":x.get("site") or "",
                    "review_url":x.get("site") or "",          # OpenReview forum
                    "abstract":(x.get("abstract") or "")[:600],
                    "citations":x.get("gs_citation") or 0,
                    "status":x.get("status",""),
                })
            out[f"{venue}{y}"]=cands
            print(f"  {venue} {y}: {len(accepted)} accepted, {len(cands)} anomaly-candidates",flush=True)
    os.makedirs("data",exist_ok=True)
    json.dump(out,open("data/papercopilot_raw.json","w"),ensure_ascii=False,indent=1)
    json.dump(verify,open("data/papercopilot_verify.json","w"),ensure_ascii=False,indent=1)
    print(f"\nwrote data/papercopilot_raw.json + verify ({sum(len(v) for v in out.values())} candidates)",flush=True)
    print("VERIFY (accepted counts):",flush=True)
    for k,v in verify.items(): print(f"  {k}: {v['accepted']} accepted / {v['total_rows']} rows",flush=True)

if __name__=="__main__": main()
