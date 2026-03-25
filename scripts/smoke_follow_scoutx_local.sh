#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-./.venv312/bin/python}"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:9100}"
FOLLOW_SCOUTX_HOME_DIR="${FOLLOW_SCOUTX_HOME_DIR:-/tmp/follow_scoutx_smoke}"
FOLLOW_SCOUTX_FEED_URL_OVERRIDE="${FOLLOW_SCOUTX_FEED_URL_OVERRIDE:-$API_BASE_URL/v1/public/feed}"
FOLLOW_SCOUTX_META_URL_OVERRIDE="${FOLLOW_SCOUTX_META_URL_OVERRIDE:-$API_BASE_URL/v1/public/meta}"
MAX_ITEMS="${MAX_ITEMS:-5}"
TOPICS="${TOPICS:-OpenAI,Anthropic,Cursor,Agent}"
KEYWORDS_EXCLUDE="${KEYWORDS_EXCLUDE:-融资}"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "[follow-scoutx-smoke][error] missing python interpreter: $PYTHON_BIN"
  echo "[follow-scoutx-smoke][hint] create it with: uv venv .venv312 --python 3.12"
  exit 1
fi

META_JSON="$(mktemp)"
FEED_JSON="$(mktemp)"
PREVIEW_JSON="$(mktemp)"
trap 'rm -f "$META_JSON" "$FEED_JSON" "$PREVIEW_JSON"' EXIT

echo "[follow-scoutx-smoke] checking public meta: $FOLLOW_SCOUTX_META_URL_OVERRIDE"
curl -fsS "$FOLLOW_SCOUTX_META_URL_OVERRIDE" -o "$META_JSON"

echo "[follow-scoutx-smoke] checking public feed: $FOLLOW_SCOUTX_FEED_URL_OVERRIDE"
curl -fsS "$FOLLOW_SCOUTX_FEED_URL_OVERRIDE" -o "$FEED_JSON"

echo "[follow-scoutx-smoke] configuring local skill profile in $FOLLOW_SCOUTX_HOME_DIR"
FOLLOW_SCOUTX_HOME="$FOLLOW_SCOUTX_HOME_DIR" \
"$PYTHON_BIN" skills/follow_scoutx/scripts/follow_scoutx.py configure \
  --frequency daily \
  --time 09:00 \
  --language zh-CN \
  --delivery-channel in_chat \
  --topics "$TOPICS" \
  --keywords-exclude "$KEYWORDS_EXCLUDE" \
  --max-items "$MAX_ITEMS" \
  --length short >/dev/null

echo "[follow-scoutx-smoke] running skill preview against local feed"
FOLLOW_SCOUTX_HOME="$FOLLOW_SCOUTX_HOME_DIR" \
FOLLOW_SCOUTX_FEED_URL="$FOLLOW_SCOUTX_FEED_URL_OVERRIDE" \
"$PYTHON_BIN" skills/follow_scoutx/scripts/follow_scoutx.py preview --json >"$PREVIEW_JSON"

echo "[follow-scoutx-smoke] summary"
"$PYTHON_BIN" -c '
import json, pathlib, sys
meta = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
feed = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
preview = json.loads(pathlib.Path(sys.argv[3]).read_text(encoding="utf-8"))
print(json.dumps({
    "meta": {
        "feed_url": meta.get("feed_url"),
        "default_limit": meta.get("default_limit"),
        "default_hours": meta.get("default_hours"),
        "cache_ttl_seconds": meta.get("cache_ttl_seconds"),
    },
    "feed": {
        "generated_at": feed.get("generated_at"),
        "item_count": len(feed.get("items") or []),
        "first_title": ((feed.get("items") or [{}])[0]).get("title"),
    },
    "preview": {
        "item_count": len(preview.get("items") or []),
        "first_title": ((preview.get("items") or [{}])[0]).get("title"),
        "topics": (((preview.get("profile") or {}).get("preferences") or {}).get("topics") or []),
    },
}, ensure_ascii=False, indent=2))
' "$META_JSON" "$FEED_JSON" "$PREVIEW_JSON"

echo "[follow-scoutx-smoke] OK"
