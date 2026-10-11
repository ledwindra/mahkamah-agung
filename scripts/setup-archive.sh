#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-archive.txt
.venv/bin/python -m unittest discover -s tests -v
printf '\nSetup finished. Example:\n'
printf '.venv/bin/python -m rulings.archive crawl --url https://putusan3.mahkamahagung.go.id/direktori/putusan/11f1acd8ace2d8248c03313233303033.html --download --text\n'
