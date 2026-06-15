# CV Field Analysis

A 2-year analysis of specific computer-vision research fields across the top venues — counts, sub-topics and trends drawn from the accepted proceedings.

**Live → https://cv-field-analysis.github.io/**

The first field is **Video Anomaly Detection (VAD / VAU)** across **CVPR · ICCV · ECCV · BMVC · AAAI · NeurIPS · ICLR · ICML · TPAMI · TIP (2024–2026)**. The page shows the publication trend as a venue × year matrix, the sub-topic distribution (weakly-supervised, VLM/LLM-based, reconstruction, …), and the full paper list with citation counts — and exports the whole thing as a PDF report.

Data sources are hybrid: CVF Open Access for the complete CVPR/ICCV title lists, DBLP for the other conferences and journals (no IEEE access needed; workshop tracks are labelled separately and excluded), and Semantic Scholar for abstracts + citations.

## How it works

```
data/ (CVF Open Access listings)
  → scripts/build.py  (filter the field, enrich via Semantic Scholar, classify sub-topics)
  → data.json
  → index.html        (field-agnostic dashboard; renders whatever data.json holds)
  → "Download PDF"    (print stylesheet → clean report)
```

- **Coverage:** accepted *main-conference* papers only — workshop and findings tracks are excluded. ICCV runs in odd years; ECCV is biennial.
- **Sources:** [CVF Open Access](https://openaccess.thecvf.com) (paper lists) + [Semantic Scholar](https://www.semanticscholar.org) (abstracts, citations).
- **Field definition** lives in `FIELD` at the top of `scripts/build.py` — swap the keywords/sub-topics to analyse **Re-ID**, **Crowd analysis**, or any other field with the same logic.

## Rebuild

```bash
bash scripts/fetch_listings.sh      # download the CVF listings into data/
python3 scripts/build.py            # → data.json
python3 -m http.server              # open http://localhost:8000
```

## Roadmap

- More venues: ECCV · WACV · BMVC · AAAI · NeurIPS · ICLR · ICML, plus journals (TIP, TPAMI) via DBLP/Semantic Scholar metadata.
- Common-benchmark performance comparison (UCF-Crime · ShanghaiTech · XD-Violence …).
- More fields (Re-ID, Crowd) as drop-in configs.

## Credits & license

This is an **unofficial** research-field analysis — not affiliated with or endorsed by CVPR, ICCV, CVF or IEEE. Bibliographic metadata only; every paper links to its official CVF Open Access page.

Built by [Deokhyun Ahn](https://deo-ahn.github.io). Code [MIT](LICENSE).
