# CV Field Analysis

A 2024–2026 analysis of specific computer-vision research fields across the top venues — publication trend, a multi-axis taxonomy, task evolution, normalized citation impact and co-occurrence, drawn from the accepted proceedings.

**Live → https://cv-field-analysis.github.io/**

The first field is **Video Anomaly Detection / Understanding (VAD / VAU)** across **CVPR · ICCV · ECCV · BMVC · AAAI · NeurIPS · ICLR · ICML · TPAMI · TIP (2024–2026)** — 69 papers.

## What the page shows

1. **Publication trend** — a venue × year matrix. Cells show accepted-paper counts; `soon` marks a 2026 venue whose list isn't released yet; `n/c` marks an edition that is released but not yet collected in this environment (journals reachable only via DBLP). Blank = not held that year (ICCV runs odd years, ECCV is biennial).
2. **Task evolution & topic-by-year** — abstract-based tags split by year, switchable across axes. Shows the shift from anomaly *detection* toward *grounding*, *understanding* and *reasoning*.
3. **Multi-axis taxonomy** — every paper is tagged on six independent axes: **task · supervision · model family · modality · domain · method**. (This replaces the old single sub-topic bar, whose labels mixed different criteria.)
4. **Normalized impact** — citations ÷ months since the venue's typical publication date, so fast-rising recent work isn't buried under older papers' raw counts.
5. **Co-occurrence** — venue × task and supervision × model-family heatmaps.
6. **Papers** — cards with multi-axis tags, multi-axis filters, citations + citations/month, and OpenReview review links where available.

Everything exports to a clean PDF (print stylesheet).

## Staged, abstract-based analysis

Analysis is deliberately staged by how much text it needs, so automated labels are never presented as ground truth:

| Stage | Input | Produces | Status |
|---|---|---|---|
| 1 | title, venue, year, citations | publication trend, citations/month | done |
| 2 | **title + abstract** | multi-axis taxonomy, task/supervision/model tags | **done** |
| 3 | PDF excerpts | datasets, metrics, backbones, code availability | planned |

The **abstract-based tags** (stage 2) are kept separate from the raw metadata:

- `scripts/build.py` collects + filters the field and emits the raw corpus (`data/corpus.json`: id, title, abstract).
- Each paper is read and tagged on the six axes, with a **confidence** score and **evidence** snippet, in `data/tags.json`.
- `data/tags_manual.json` is a manual-override file (keyed by paper id) that wins over the automatic tags.
- Papers tagged from the title alone, or at low confidence, are flagged `needs_review` (the amber dot on the page).
- `build.py` merges `tags.json` (+ manual overrides) over a rule-based fallback and writes `data.json`.

So new labels carry confidence + evidence + a manual escape hatch, rather than being baked into the metadata as fact.

## Data sources

- **CVF Open Access** — complete CVPR/ICCV title lists (`data/*.html`).
- **Paper Copilot** ([open data](https://github.com/papercopilot/paperlists)) — complete accepted-paper lists **with abstracts** for the OpenReview venues (NeurIPS, ICLR, ICML) and the proceedings venues it indexes (CVPR, AAAI), which backfills the 2024 editions and provides **OpenReview review links**.
- **DBLP** — the remaining conferences/journals (ECCV, BMVC, TPAMI, TIP); no IEEE access needed, workshop tracks excluded by venue label.
- **Semantic Scholar** — abstracts + citations for CVF/DBLP papers (cached in `data/s2_cache.json`).
- **arXiv** — abstract backfill for papers the above miss, matched by a title-similarity guard (`scripts/fetch_arxiv_abs.py` → `data/arxiv_abs.json`).
- `data/exclude.json` — manual exclusions (paper id → reason), e.g. a paper that slips through the keyword filter but is out of scope.

### Inclusion / exclusion criteria
- **Include:** papers whose title/abstract explicitly target video anomaly detection, understanding, grounding or reasoning, video violence detection, traffic/road anomaly detection, or closely related abnormal-event analysis in video.
- **Exclude:** generic image anomaly detection, industrial defect detection, medical-image anomaly, graph/tabular/time-series anomaly, and deepfake/forgery — unless the paper explicitly addresses a video anomaly task.

## How it works

```
data/ (CVF listings) + Paper Copilot + DBLP
  → scripts/collect_papercopilot.py / collect_dblp.py   (refresh raw candidate lists)
  → scripts/build.py        (filter field → enrich via Semantic Scholar → emit corpus.json)
  → read abstracts → data/tags.json  (multi-axis tags + confidence + evidence)
  → scripts/build.py        (merge tags + manual overrides → derived analytics → data.json)
  → index.html              (field-agnostic dashboard; renders whatever data.json holds)
  → "Download PDF"          (print stylesheet → clean report)
```

- **Coverage:** accepted *main-conference & journal* papers only — workshop and findings tracks excluded.
- **Field definition** lives in `FIELD` at the top of `scripts/build.py`; the **edition calendar** (which venue×year cells exist and their release status) lives in `CALENDAR`. Swap them to analyse Re-ID, Crowd analysis, etc.
- **Citations/month** uses an estimated publication month per venue (`VENUE_MONTH`) anchored at `BUILD_DATE`.

## Rebuild

```bash
bash scripts/fetch_listings.sh        # CVF listings into data/  (network permitting)
python3 scripts/collect_papercopilot.py   # Paper Copilot candidate lists (+abstracts)
python3 scripts/collect_dblp.py           # DBLP candidate lists (rate-limited; rerun to fill TPAMI/TIP 2024, BMVC 2025)
python3 scripts/build.py                  # corpus.json + data.json
python3 scripts/fetch_arxiv_abs.py        # backfill missing abstracts from arXiv → data/arxiv_abs.json
# (read new abstracts in data/corpus.json → add entries to data/tags.json) → re-run build.py
python3 -m http.server                    # open http://localhost:8000
```

## Roadmap

- Stage 3: PDF-excerpt enrichment (datasets · metrics · backbones · code availability) as optional, confidence-scored `needs_review` fields.
- Fill the `n/c` journal cells (TPAMI/TIP 2024, BMVC 2025) once DBLP is reachable.
- More fields (Re-ID, Crowd) as drop-in `FIELD` configs.

## Credits & license

This is an **unofficial** research-field analysis — not affiliated with or endorsed by CVPR, ICCV, CVF, AAAI or IEEE. Bibliographic metadata only; every paper links to its official page.

Built by [Deokhyun Ahn](https://deo-ahn.github.io). Code [MIT](LICENSE).
