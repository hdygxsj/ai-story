#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env}"
if [ ! -f "$ENV_FILE" ]; then
  ENV_FILE=".env.example"
fi

API_PORT="$(grep -E '^API_PORT=' "$ENV_FILE" | cut -d= -f2- || echo 8000)"
API_URL="${API_URL:-http://localhost:${API_PORT}}"

DEMO_EMAIL="${DEMO_EMAIL:-demo@example.com}"
DEMO_USERNAME="${DEMO_USERNAME:-demo}"
DEMO_PASSWORD="${DEMO_PASSWORD:-secret123}"

payload=$(cat <<EOF
{"email":"${DEMO_EMAIL}","username":"${DEMO_USERNAME}","password":"${DEMO_PASSWORD}"}
EOF
)

echo "创建演示账号: ${DEMO_EMAIL} / ${DEMO_USERNAME}"
response="$(curl -sS -w "\n%{http_code}" -X POST "${API_URL}/auth/register" \
  -H "Content-Type: application/json" \
  -d "$payload")"

body="${response%$'\n'*}"
status="${response##*$'\n'}"

case "$status" in
  201)
    echo "演示账号已创建，可使用以下信息登录："
    echo "  邮箱: ${DEMO_EMAIL}"
    echo "  用户名: ${DEMO_USERNAME}"
    echo "  密码: ${DEMO_PASSWORD}"
    ;;
  409)
    echo "演示账号已存在，可直接登录。"
    ;;
  *)
    echo "创建演示账号失败 (HTTP ${status})。" >&2
    echo "$body" >&2
    echo "请确认后端已启动: ${API_URL}/health" >&2
    exit 1
    ;;
esac
