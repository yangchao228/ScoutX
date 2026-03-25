#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-./.venv312/bin/python}"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "[scoutx-canary][error] missing python interpreter: $PYTHON_BIN"
  echo "[scoutx-canary][hint] run: uv venv .venv312 --python 3.12 && uv pip install --python .venv312/bin/python -r requirements.txt"
  exit 1
fi

export SCOUTX_CONTENT_PROVIDER="${SCOUTX_CONTENT_PROVIDER:-service}"
export CONTENT_SERVICE_BASE_URL="${CONTENT_SERVICE_BASE_URL:-http://127.0.0.1:9100}"
export CONTENT_SERVICE_PULL_LIMIT="${CONTENT_SERVICE_PULL_LIMIT:-100}"
export CONTENT_SERVICE_PULL_MAX_PAGES="${CONTENT_SERVICE_PULL_MAX_PAGES:-10}"

echo "[scoutx-canary] provider=$SCOUTX_CONTENT_PROVIDER base_url=$CONTENT_SERVICE_BASE_URL limit=$CONTENT_SERVICE_PULL_LIMIT max_pages=$CONTENT_SERVICE_PULL_MAX_PAGES"

exec "$PYTHON_BIN" main.py --config config.yaml --once
