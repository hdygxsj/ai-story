#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env}"
ENV_EXAMPLE="${ENV_EXAMPLE:-.env.example}"
START_SERVICES=1

info() { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }

usage() {
  cat <<'EOF'
用法: ./install.sh [选项]

一键安装 Docker（如未安装）并启动 AI Story 前后端服务。

选项:
  --no-start    仅安装 Docker 并准备环境，不启动服务
  -h, --help    显示帮助

启动后访问:
  前端: http://localhost:5173
  后端: http://localhost:8000
EOF
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --no-start)
        START_SERVICES=0
        ;;
      -h | --help)
        usage
        exit 0
        ;;
      *)
        error "未知参数: $1"
        usage
        exit 1
        ;;
    esac
    shift
  done
}

detect_os() {
  case "$(uname -s)" in
    Darwin) echo "darwin" ;;
    Linux) echo "linux" ;;
    *)
      error "暂不支持的操作系统: $(uname -s)"
      error "请手动安装 Docker Desktop 后执行: docker compose --env-file .env up -d --build"
      exit 1
      ;;
  esac
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

docker_daemon_ready() {
  docker info >/dev/null 2>&1
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif command_exists docker-compose; then
    echo "docker-compose"
  else
    return 1
  fi
}

wait_for_docker() {
  local attempt=0
  local max_attempts=90

  info "等待 Docker 守护进程就绪..."
  while ! docker_daemon_ready; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$max_attempts" ]; then
      error "Docker 未在预期时间内启动。"
      if [ "$(detect_os)" = "darwin" ]; then
        error "请手动打开 Docker Desktop 应用后重新运行本脚本。"
      else
        error "请检查 Docker 服务状态: sudo systemctl status docker"
      fi
      exit 1
    fi
    sleep 2
  done
}

install_docker_macos() {
  if command_exists docker && docker_daemon_ready; then
    info "Docker 已安装且正在运行。"
    return
  fi

  if command_exists docker; then
    info "Docker 已安装，正在尝试启动 Docker Desktop..."
    open -a Docker >/dev/null 2>&1 || true
    wait_for_docker
    return
  fi

  info "未检测到 Docker，开始在 macOS 上安装..."

  if command_exists brew; then
    info "使用 Homebrew 安装 Docker Desktop..."
    brew install --cask docker
    info "正在启动 Docker Desktop..."
    open -a Docker >/dev/null 2>&1 || true
    wait_for_docker
    return
  fi

  error "未找到 Homebrew，无法自动安装 Docker。"
  cat <<'EOF'
请任选一种方式安装 Docker Desktop:
  1. 安装 Homebrew 后重新运行本脚本: https://brew.sh
  2. 从官网下载安装: https://www.docker.com/products/docker-desktop/
EOF
  exit 1
}

install_docker_linux() {
  if command_exists docker && docker_daemon_ready; then
    info "Docker 已安装且正在运行。"
    return
  fi

  if command_exists docker; then
    info "Docker 已安装，正在启动服务..."
    if command_exists systemctl; then
      sudo systemctl enable --now docker
    fi
    wait_for_docker
    return
  fi

  info "未检测到 Docker，开始在 Linux 上安装..."
  if ! command_exists curl; then
    error "需要 curl 来安装 Docker，请先安装 curl 后重试。"
    exit 1
  fi

  curl -fsSL https://get.docker.com | sh

  if command_exists systemctl; then
    sudo systemctl enable --now docker
  fi

  if ! groups "$USER" | tr ' ' '\n' | grep -qx docker; then
    sudo usermod -aG docker "$USER" || true
    warn "已将当前用户加入 docker 组。若后续无需 sudo 运行 docker，请重新登录终端后再试。"
  fi

  wait_for_docker
}

ensure_docker() {
  local os
  os="$(detect_os)"

  case "$os" in
    darwin) install_docker_macos ;;
    linux) install_docker_linux ;;
  esac

  if ! compose_cmd >/dev/null; then
    error "未找到 docker compose，请升级 Docker 到包含 Compose V2 的版本。"
    exit 1
  fi

  info "Docker 版本: $(docker --version)"
  info "Compose 版本: $(compose_cmd version | head -n 1)"
}

prepare_env() {
  if [ ! -f "$ENV_EXAMPLE" ]; then
    error "缺少环境模板文件: $ENV_EXAMPLE"
    exit 1
  fi

  if [ ! -f "$ENV_FILE" ]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    info "已根据 $ENV_EXAMPLE 创建 $ENV_FILE"
  else
    info "使用已有环境文件: $ENV_FILE"
  fi
}

start_stack() {
  local compose
  compose="$(compose_cmd)"

  info "正在构建并启动服务（首次启动可能需要几分钟）..."
  # shellcheck disable=SC2086
  $compose --env-file "$ENV_FILE" up -d --build

  info "服务已启动。"
  cat <<EOF

访问地址:
  前端: http://localhost:$(grep -E '^WEB_PORT=' "$ENV_FILE" | cut -d= -f2 || echo 5173)
  后端: http://localhost:$(grep -E '^API_PORT=' "$ENV_FILE" | cut -d= -f2 || echo 8000)

常用命令:
  查看日志: $compose --env-file $ENV_FILE logs -f
  停止服务: $compose --env-file $ENV_FILE down
  重启服务: $compose --env-file $ENV_FILE up -d --build
EOF
}

main() {
  parse_args "$@"

  info "AI Story 安装脚本"
  info "项目目录: $ROOT_DIR"

  ensure_docker
  prepare_env

  if [ "$START_SERVICES" -eq 1 ]; then
    start_stack
  else
    info "已跳过服务启动。手动启动请执行:"
    info "  $(compose_cmd) --env-file $ENV_FILE up -d --build"
  fi
}

main "$@"
