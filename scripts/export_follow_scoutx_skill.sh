#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/skills/follow_scoutx"
DEST_DIR="${DEST_DIR:-$ROOT_DIR/dist/follow_scoutx-skill}"
OVERWRITE="${OVERWRITE:-0}"
CREATE_ARCHIVES="${CREATE_ARCHIVES:-1}"
ARCHIVE_BASENAME="${ARCHIVE_BASENAME:-follow_scoutx-skill}"

if [ ! -d "$SOURCE_DIR" ]; then
  echo "[export-follow-scoutx][error] missing source skill directory: $SOURCE_DIR"
  exit 1
fi

if [ -e "$DEST_DIR" ]; then
  if [ "$OVERWRITE" != "1" ]; then
    echo "[export-follow-scoutx][error] destination already exists: $DEST_DIR"
    echo "[export-follow-scoutx][hint] rerun with OVERWRITE=1 or set DEST_DIR"
    exit 1
  fi
  rm -rf "$DEST_DIR"
fi

mkdir -p "$DEST_DIR/scripts" "$DEST_DIR/prompts"

cp "$SOURCE_DIR/SKILL.md" "$DEST_DIR/SKILL.md"
cp "$SOURCE_DIR/service.json" "$DEST_DIR/service.json"
cp "$SOURCE_DIR/scripts/follow_scoutx.py" "$DEST_DIR/scripts/follow_scoutx.py"
cp "$SOURCE_DIR/prompts/"*.md "$DEST_DIR/prompts/"
cp "$SOURCE_DIR/repo_README.md" "$DEST_DIR/README.md"

cat >"$DEST_DIR/.gitignore" <<'EOF'
__pycache__/
*.py[cod]
.DS_Store
EOF

chmod +x "$DEST_DIR/scripts/follow_scoutx.py"

echo "[export-follow-scoutx] exported standalone skill repo to: $DEST_DIR"
echo "[export-follow-scoutx] files:"
find "$DEST_DIR" -maxdepth 3 -type f | sort

if [ "$CREATE_ARCHIVES" = "1" ]; then
  ARCHIVE_DIR="$(dirname "$DEST_DIR")"
  ZIP_PATH="$ARCHIVE_DIR/$ARCHIVE_BASENAME.zip"
  TAR_PATH="$ARCHIVE_DIR/$ARCHIVE_BASENAME.tar.gz"

  rm -f "$ZIP_PATH" "$TAR_PATH"

  (
    cd "$ARCHIVE_DIR"
    zip -qr "$ZIP_PATH" "$(basename "$DEST_DIR")"
    tar -czf "$TAR_PATH" "$(basename "$DEST_DIR")"
  )

  echo "[export-follow-scoutx] archives:"
  printf '%s\n' "$ZIP_PATH" "$TAR_PATH"
fi
