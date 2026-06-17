#!/usr/bin/env python3
"""Classify CVPR accepted papers into research themes by title keyword and emit
per-year theme shares for the stacked theme-trend chart.

Reads every data/cvpr<YYYY>_oa.html (CVF Open Access "all papers" listing) present,
so adding more years = drop the listing in and re-run. Title-only, approximate:
each paper is assigned to ONE theme = the first matching keyword group (priority
order below). Writes data/cvpr_themes.json."""
import re, html, json, glob, os
from collections import Counter

# priority-ordered (first match wins → single assignment, shares sum to 100%)
THEMES = [
 ("Multimodal · LLM/VLM",   r"multimodal|vision[- ]language|\bvlm\b|\bmllm\b|\bllm\b|language model|\bvqa\b|question answer|grounding|caption|\bagent|instruction|\bchat|gpt|reasoning|embodied|retrieval"),
 ("3D · Geometry · Avatars",r"\b3d\b|gaussian splatt|\bnerf\b|neural field|point cloud|\bmesh\b|geometry|multi[- ]view|\bdepth\b|stereo|pose estimat|\bslam\b|reconstruct|avatar|render|novel view|\bsurface\b|\bshape\b"),
 ("Generative · Diffusion", r"diffusion|generat|text[- ]to[- ]image|synthesis|\bediting\b|\bgan\b|flow matching|autoregress|restoration|super[- ]resolution|inpaint|deblur|coloriz|styliz"),
 ("Video · Motion",         r"video|motion|tracking|\baction\b|temporal|trajectory|world model|optical flow|event camera|\bframe"),
 ("Detection · Segmentation",r"detect|segment|recogni|classif|re[- ]identif|\bocr\b|open[- ]vocab|anomaly|counting|localiz"),
 ("Efficiency · Learning · Robust",r"efficient|transformer|distill|quantiz|prun|continual|test[- ]time|domain adapt|federat|self[- ]supervis|semi[- ]supervis|weakly|adversari|robust|uncertain|contrastive|few[- ]shot|zero[- ]shot"),
]
THEME_NAMES = [n for n, _ in THEMES] + ["Other"]
_C = [(n, re.compile(p, re.I)) for n, p in THEMES]

def classify(t):
    for n, p in _C:
        if p.search(t):
            return n
    return "Other"

def titles(path):
    doc = open(path, encoding="utf-8", errors="ignore").read()
    out = []
    for b in re.split(r'<dt class="ptitle">', doc)[1:]:
        m = re.search(r'<a href="[^"]*">(.*?)</a>', b, re.S)
        if m:
            out.append(html.unescape(re.sub(r'\s+', ' ', m.group(1)).strip()))
    return out

def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    years = []
    for path in sorted(glob.glob(os.path.join(base, "data", "cvpr*_oa.html"))):
        m = re.search(r'cvpr(\d{4})_oa\.html', os.path.basename(path))
        if not m:
            continue
        yr = int(m.group(1))
        ts = titles(path)
        c = Counter(classify(t) for t in ts)
        years.append({"year": yr, "total": len(ts),
                      "count": {n: c.get(n, 0) for n in THEME_NAMES}})
        print(f"  CVPR {yr}: {len(ts)} papers classified")
    years.sort(key=lambda y: y["year"])
    out = {
        "method": ("Each accepted paper assigned to one theme = first-matching keyword group "
                   "in its TITLE (priority order). Title-only, approximate. "
                   "Source: CVF Open Access listings."),
        "themes": THEME_NAMES,
        "years": years,
    }
    dst = os.path.join(base, "data", "cvpr_themes.json")
    json.dump(out, open(dst, "w"), ensure_ascii=False, indent=1)
    print(f"wrote {dst} — {len(years)} years: {[y['year'] for y in years]}")

if __name__ == "__main__":
    main()
