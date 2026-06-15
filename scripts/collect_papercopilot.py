#!/usr/bin/env python3
"""Collect field candidates from Paper Copilot's open data dumps (github.com/papercopilot/paperlists).
Gives complete accepted-paper lists + abstracts for OpenReview venues (NeurIPS/ICLR/ICML) AND the
proceedings venues it indexes (CVPR/AAAI), which lets us backfill 2024 editions DBLP can't reach here."""
import urllib.request, json, ssl, os, re, sys
CTX=ssl.create_default_context();CTX.check_hostname=False;CTX.verify_mode=ssl.CERT_NONE
RAW="https://raw.githubusercontent.com/papercopilot/paperlists/main/{v}/{v}{y}.json"

# (display venue, papercopilot dir, [years]). Only editions NOT covered by CVF Open Access (CVPR/ICCV
# title lists are parsed from data/*.html) or already cached from DBLP for other years.
SOURCES=[("NeurIPS","nips",[2024,2025]),
         ("ICLR","iclr",[2024,2025,2026]),
         ("ICML","icml",[2024,2025]),
         ("CVPR","cvpr",[2024]),          # 2025/2026 come from CVF Open Access
         ("AAAI","aaai",[2024])]          # 2025/2026 come from DBLP cache
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

def is_accepted(x):
    """Accepted = a finalised status that is not a reject/withdrawal. Proceedings venues
    (CVPR 'Poster', AAAI 'Technical') have no reject rows; OpenReview venues filter Withdraw/Reject."""
    s=(x.get("status") or "").strip()
    return bool(s) and not REJECT.search(s)

def main():
    out={}; verify={}
    for venue,vd,years in SOURCES:
        for y in years:
            rows=fetch(vd,y)
            if rows is None: continue
            accepted=[x for x in rows if is_accepted(x)]
            verify[f"{venue}{y}"]={"total_rows":len(rows),"accepted":len(accepted)}
            cands=[]
            for x in accepted:
                t=(x.get("title","") or "").strip()
                blob=t+" "+(x.get("abstract","") or "")
                if not (PRE.search(t) or (PRE.search(blob) and VID.search(blob))): continue
                site=x.get("site") or ""
                cands.append({
                    "title":t,
                    "authors":(x.get("author") or "").replace(";",", ").strip(", "),
                    "venue":venue,"year":int(y),
                    "url":x.get("oa") or site or "",
                    "review_url":site if "openreview" in site else "",
                    "abstract":(x.get("abstract") or "").strip(),
                    "arxiv":(x.get("arxiv") or "").strip(),
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
