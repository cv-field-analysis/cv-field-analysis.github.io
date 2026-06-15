#!/usr/bin/env bash
# Download the CVF Open Access "all papers" listings the pipeline parses.
set -e; mkdir -p data
curl -sk "https://openaccess.thecvf.com/CVPR2025?day=all" -o data/cvpr2025_oa.html
curl -sk "https://openaccess.thecvf.com/CVPR2026?day=all" -o data/cvpr2026_oa.html
curl -sk "https://openaccess.thecvf.com/ICCV2025?day=all" -o data/iccv2025_oa.html
echo "downloaded $(ls data/*.html | wc -l) listings"
