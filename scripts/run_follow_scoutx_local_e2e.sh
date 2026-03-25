#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SKIP_BOOTSTRAP="${SKIP_BOOTSTRAP:-0}"
SKIP_BUILD="${SKIP_BUILD:-0}"
SKIP_INGESTION="${SKIP_INGESTION:-0}"

echo "[follow-scoutx-e2e] root=$ROOT_DIR"

if [ "$SKIP_BOOTSTRAP" != "1" ]; then
  echo "[follow-scoutx-e2e] bootstrapping content-service"
  SKIP_BUILD="$SKIP_BUILD" SKIP_INGESTION="$SKIP_INGESTION" ./scripts/content_service_bootstrap.sh
else
  echo "[follow-scoutx-e2e] skipping bootstrap because SKIP_BOOTSTRAP=1"
fi

echo "[follow-scoutx-e2e] running local Follow ScoutX smoke"
./scripts/smoke_follow_scoutx_local.sh

echo "[follow-scoutx-e2e] OK"
