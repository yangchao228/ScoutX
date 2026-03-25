#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SKIP_BUILD="${SKIP_BUILD:-0}"
SKIP_INGESTION="${SKIP_INGESTION:-0}"

echo "[content-service] bootstrapping via docker compose"

echo "[content-service] starting postgres and rsshub"
docker compose up -d postgres rsshub

if [ "$SKIP_BUILD" != "1" ]; then
  echo "[content-service] building service images"
  docker compose build content-service-api content-service-scheduler scoutx-healthcheck
else
  echo "[content-service] skipping image build because SKIP_BUILD=1"
fi

echo "[content-service] starting api, scheduler, and runtime healthcheck"
docker compose up -d content-service-api content-service-scheduler scoutx-healthcheck

echo "[content-service] waiting for API health endpoint"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:9100/health >/dev/null 2>&1; then
    echo "[content-service] API is healthy"
    break
  fi
  sleep 2
done

if ! curl -fsS http://127.0.0.1:9100/health >/dev/null 2>&1; then
  echo "[content-service][error] API did not become healthy in time"
  exit 1
fi

echo "[content-service] waiting for public meta endpoint"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:9100/v1/public/meta >/dev/null 2>&1; then
    echo "[content-service] public meta is available"
    break
  fi
  sleep 2
done

if ! curl -fsS http://127.0.0.1:9100/v1/public/meta >/dev/null 2>&1; then
  echo "[content-service][error] public meta endpoint did not become ready in time"
  exit 1
fi

if [ "$SKIP_INGESTION" != "1" ]; then
  echo "[content-service] running one-shot ingestion"
  docker compose exec -T content-service-scheduler python -m apps.content_service.scheduler.runner --once
else
  echo "[content-service] skipping one-shot ingestion because SKIP_INGESTION=1"
fi

echo "[content-service] bootstrap completed"
echo "[content-service] API: http://127.0.0.1:9100/health"
echo "[content-service] Public meta: http://127.0.0.1:9100/v1/public/meta"
echo "[content-service] Public feed: http://127.0.0.1:9100/v1/public/feed"
echo "[content-service] logs:"
echo "  docker logs -f scoutx-content-service-api"
echo "  docker logs -f scoutx-content-service-scheduler"
echo "  docker logs -f scoutx-healthcheck"
