#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT_DIR/desktop/src-tauri/resources/stack"

info() { printf '[prepare-stack] %s\n' "$*"; }

info "Preparing desktop stack bundle at $DEST"
rm -rf "$DEST"
mkdir -p "$DEST"

cp "$ROOT_DIR/docker-compose.yml" "$ROOT_DIR/.env.example" "$DEST/"
cp -r "$ROOT_DIR/scripts" "$DEST/"

if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude '*.pyc' \
    --exclude '.ruff_cache' \
    "$ROOT_DIR/backend/" "$DEST/backend/"
  rsync -a \
    --exclude 'node_modules' \
    --exclude 'dist' \
    "$ROOT_DIR/frontend/" "$DEST/frontend/"
else
  info "rsync not found, using cp (may include extra files)"
  cp -R "$ROOT_DIR/backend" "$ROOT_DIR/frontend" "$DEST/"
  rm -rf "$DEST/backend/.venv" "$DEST/frontend/node_modules" "$DEST/frontend/dist" 2>/dev/null || true
fi

info "Stack bundle ready"
