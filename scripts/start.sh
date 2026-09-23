#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/check-save.py
bash scripts/docker.sh compose up -d
