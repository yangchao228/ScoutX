#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SKIP_BUILD="${SKIP_BUILD:-0}"
SKIP_PROVIDER_RUN="${SKIP_PROVIDER_RUN:-0}"
SKIP_CONSUMER_RUN="${SKIP_CONSUMER_RUN:-0}"
PYTHON_BIN="${PYTHON_BIN:-./.venv312/bin/python}"
NO_PROXY_VALUE="${NO_PROXY_VALUE:-127.0.0.1,localhost}"

if [ ! -x "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "[verify-local][error] missing python interpreter: $PYTHON_BIN"
    exit 1
  fi
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

HEALTH_JSON="$TMP_DIR/health.json"
META_JSON="$TMP_DIR/meta.json"
FEED_JSON="$TMP_DIR/feed.json"
STATUS_JSON="$TMP_DIR/status.json"
SOURCES_JSON="$TMP_DIR/sources.json"
RUNTIME_JSON="$TMP_DIR/runtime.json"
HEALTHCHECK_JSON="$TMP_DIR/healthcheck.json"
PREVIEW_JSON="$TMP_DIR/preview.json"

COMPOSE_SERVICES=(
  postgres
  rsshub
  content-service-api
  content-service-scheduler
  scoutx-web
  scoutx-scheduler
  scoutx-healthcheck
)

BUILD_SERVICES=(
  content-service-api
  content-service-scheduler
  scoutx-web
  scoutx-scheduler
  scoutx-healthcheck
)

wait_for_running() {
  local container_name="$1"
  local retries="${2:-60}"
  local attempt=1
  while [ "$attempt" -le "$retries" ]; do
    local status
    status="$(docker inspect -f '{{.State.Status}}' "$container_name" 2>/dev/null || true)"
    if [ "$status" = "running" ]; then
      return 0
    fi
    sleep 2
    attempt=$((attempt + 1))
  done
  echo "[verify-local][error] container not running: $container_name"
  return 1
}

wait_for_healthy() {
  local container_name="$1"
  local retries="${2:-60}"
  local attempt=1
  while [ "$attempt" -le "$retries" ]; do
    local status
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_name" 2>/dev/null || true)"
    if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
      return 0
    fi
    sleep 2
    attempt=$((attempt + 1))
  done
  echo "[verify-local][error] container not healthy: $container_name"
  return 1
}

wait_for_http() {
  local container_name="$1"
  local url="$2"
  local retries="${3:-60}"
  local attempt=1
  while [ "$attempt" -le "$retries" ]; do
    if docker exec -i "$container_name" /bin/sh -lc "curl -fsS '$url' >/dev/null"; then
      return 0
    fi
    sleep 2
    attempt=$((attempt + 1))
  done
  echo "[verify-local][error] endpoint not ready: $container_name $url"
  return 1
}

echo "[verify-local] root=$ROOT_DIR"
echo "[verify-local] python=$PYTHON_BIN"

if [ "$SKIP_BUILD" != "1" ]; then
  echo "[verify-local] building images"
  docker compose build "${BUILD_SERVICES[@]}"
else
  echo "[verify-local] skipping image build because SKIP_BUILD=1"
fi

echo "[verify-local] starting compose services"
docker compose up -d "${COMPOSE_SERVICES[@]}"

wait_for_healthy scoutx-postgres
wait_for_running scoutx-rsshub
wait_for_running scoutx-content-service-api
wait_for_running scoutx-content-service-scheduler
wait_for_running scoutx-web
wait_for_running scoutx-scheduler
wait_for_running scoutx-healthcheck

wait_for_http scoutx-content-service-api "http://127.0.0.1:9100/health"
wait_for_http scoutx-content-service-api "http://127.0.0.1:9100/v1/public/meta"
wait_for_http scoutx-healthcheck "http://scoutx-web:9000/api/runtime-status"

if [ "$SKIP_PROVIDER_RUN" != "1" ]; then
  echo "[verify-local] running provider one-shot"
  docker exec -i scoutx-content-service-scheduler python -m apps.content_service.scheduler.runner --once
else
  echo "[verify-local] skipping provider one-shot because SKIP_PROVIDER_RUN=1"
fi

if [ "$SKIP_CONSUMER_RUN" != "1" ]; then
  echo "[verify-local] running consumer one-shot"
  docker exec -i scoutx-scheduler python main.py --config config.yaml --once
else
  echo "[verify-local] skipping consumer one-shot because SKIP_CONSUMER_RUN=1"
fi

echo "[verify-local] collecting validation payloads"
docker exec -i scoutx-content-service-api curl -fsS http://127.0.0.1:9100/health > "$HEALTH_JSON"
docker exec -i scoutx-content-service-api curl -fsS http://127.0.0.1:9100/v1/public/meta > "$META_JSON"
docker exec -i scoutx-content-service-api curl -fsS http://127.0.0.1:9100/v1/public/feed > "$FEED_JSON"
docker exec -i scoutx-content-service-api curl -fsS http://127.0.0.1:9100/v1/status > "$STATUS_JSON"
docker exec -i scoutx-content-service-api curl -fsS "http://127.0.0.1:9100/v1/sources?type=json_feed" > "$SOURCES_JSON"
docker exec -i scoutx-healthcheck curl -fsS http://scoutx-web:9000/api/runtime-status > "$RUNTIME_JSON"

set +e
docker exec -i scoutx-healthcheck python check_runtime_health.py \
  --content-service-url http://content-service-api:9100/v1/status \
  --scoutx-url http://scoutx-web:9000/api/runtime-status \
  --notify-on none > "$HEALTHCHECK_JSON"
HEALTHCHECK_EXIT="$?"
set -e

echo "[verify-local] running follow_scoutx preview"
docker exec -i scoutx-content-service-api /bin/sh -lc \
  "FOLLOW_SCOUTX_HOME=/tmp/follow_scoutx_acceptance \
  FOLLOW_SCOUTX_FEED_URL=http://127.0.0.1:9100/v1/public/feed \
  NO_PROXY='$NO_PROXY_VALUE' no_proxy='$NO_PROXY_VALUE' \
  HTTP_PROXY= HTTPS_PROXY= ALL_PROXY= http_proxy= https_proxy= all_proxy= \
  python skills/follow_scoutx/scripts/follow_scoutx.py configure \
    --frequency daily \
    --time 09:00 \
    --language zh-CN \
    --delivery-channel in_chat \
    --topics 'OpenAI,Anthropic,Cursor,Agent' \
    --keywords-exclude '融资' \
    --max-items 5 \
    --length short >/dev/null && \
  FOLLOW_SCOUTX_HOME=/tmp/follow_scoutx_acceptance \
  FOLLOW_SCOUTX_FEED_URL=http://127.0.0.1:9100/v1/public/feed \
  NO_PROXY='$NO_PROXY_VALUE' no_proxy='$NO_PROXY_VALUE' \
  HTTP_PROXY= HTTPS_PROXY= ALL_PROXY= http_proxy= https_proxy= all_proxy= \
  python skills/follow_scoutx/scripts/follow_scoutx.py preview --json" > "$PREVIEW_JSON"

echo "[verify-local] validating results"
"$PYTHON_BIN" - <<'PY' "$HEALTH_JSON" "$META_JSON" "$FEED_JSON" "$STATUS_JSON" "$SOURCES_JSON" "$RUNTIME_JSON" "$HEALTHCHECK_JSON" "$PREVIEW_JSON" "$HEALTHCHECK_EXIT"
import json
import sys
from pathlib import Path

health_path, meta_path, feed_path, status_path, sources_path, runtime_path, healthcheck_path, preview_path, healthcheck_exit = sys.argv[1:]

def load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))

health = load(health_path)
meta = load(meta_path)
feed = load(feed_path)
status_envelope = load(status_path)
sources_envelope = load(sources_path)
runtime_status = load(runtime_path)
healthcheck = load(healthcheck_path)
preview = load(preview_path)

errors: list[str] = []

if not (health.get("data") or {}).get("ok"):
    errors.append("content-service /health returned ok=false")
if not meta.get("feed_url"):
    errors.append("public meta missing feed_url")
feed_items = list(feed.get("items") or [])
if not feed_items:
    errors.append("public feed returned 0 items")

status = status_envelope.get("data") or {}
source_stats = status.get("sources") or {}
if not status.get("latest_scheduler_run"):
    errors.append("provider status missing latest_scheduler_run")
if int(source_stats.get("failed") or 0) != 0:
    errors.append(f"provider has failed sources: {source_stats.get('failed')}")

health_status = str(healthcheck.get("status") or "").lower()
if healthcheck_exit != "0" or health_status != "ok":
    errors.append(f"runtime healthcheck is not ok: exit={healthcheck_exit} status={health_status}")

sync_states = list(runtime_status.get("sync_states") or [])
content_sync_states = [item for item in sync_states if str(item.get("provider") or "") == "content_service"]
if not content_sync_states:
    errors.append("runtime status missing content_service sync_state")

preview_items = list(preview.get("items") or [])
if not preview_items:
    errors.append("follow_scoutx preview returned 0 items")

json_feed_items = list(((sources_envelope.get("data") or {}).get("items") or []))
empty_json_feeds = [
    {
        "name": item.get("name"),
        "snapshot_fetched_from_url": ((item.get("snapshot") or {}).get("snapshot_fetched_from_url")),
    }
    for item in json_feed_items
    if ((item.get("snapshot") or {}).get("has_snapshot")) and int(((item.get("snapshot") or {}).get("snapshot_item_count") or 0)) == 0
]

summary = {
    "status": "ok" if not errors else "fail",
    "provider": {
        "latest_scheduler_run": status.get("latest_scheduler_run"),
        "sources": {
            "total": source_stats.get("total"),
            "success": source_stats.get("success"),
            "failed": source_stats.get("failed"),
            "slow": source_stats.get("slow"),
            "stale": source_stats.get("stale"),
            "empty": source_stats.get("empty"),
        },
    },
    "public_feed": {
        "generated_at": feed.get("generated_at"),
        "item_count": len(feed_items),
        "first_title": (feed_items[0] if feed_items else {}).get("title"),
    },
    "runtime_status": {
        "latest_report_date": ((runtime_status.get("reports") or {}).get("latest_report_date")),
        "latest_report_count": ((runtime_status.get("reports") or {}).get("latest_report_count")),
        "content_service_sync_state_count": len(content_sync_states),
    },
    "follow_scoutx_preview": {
        "item_count": len(preview_items),
        "first_title": (preview_items[0] if preview_items else {}).get("title"),
    },
    "json_feed_empty_sources": empty_json_feeds,
    "healthcheck": healthcheck,
    "errors": errors,
}

print(json.dumps(summary, ensure_ascii=False, indent=2))
if errors:
    raise SystemExit(1)
PY

echo "[verify-local] OK"
