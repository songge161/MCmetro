#!/usr/bin/env bash
set -euo pipefail

python3 -m compileall -q src tests
python3 -m ruff check src tests
python3 -m ruff format --check src tests
python3 -m pytest -q
python3 -m minijapan validate --config data/samples/tokyo_demo.yaml
python3 -m minijapan plan --config data/samples/tokyo_demo.yaml --out out/demo
xmllint --noout out/demo/preview.svg
