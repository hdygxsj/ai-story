#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env}"
if [ ! -f "$ENV_FILE" ]; then
  ENV_FILE=".env.example"
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "未找到 docker compose，请先安装 Docker。" >&2
  exit 1
fi

echo "使用环境文件: $ENV_FILE"
echo "启动 Postgres..."
# shellcheck disable=SC2086
$COMPOSE --env-file "$ENV_FILE" up -d postgres

echo "执行数据库迁移..."
# shellcheck disable=SC2086
$COMPOSE --env-file "$ENV_FILE" run --rm api alembic upgrade head

echo "数据库迁移完成。"
