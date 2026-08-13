#!/usr/bin/env bash

set -Eeuo pipefail
set -m

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
BACKEND_PID=""
FRONTEND_PID=""

log() {
  printf '[start] %s\n' "$*"
}

fail() {
  printf '[start] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少命令 '$1'，请先安装后重试。"
}

check_port() {
  local port="$1"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >&2
    fail "端口 $port 已被占用。"
  fi
}

stop_process_group() {
  local pid="$1"
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    kill -TERM -- "-$pid" >/dev/null 2>&1 || kill -TERM "$pid" >/dev/null 2>&1 || true
  fi
}

cleanup() {
  local status=$?
  trap - EXIT INT TERM

  if [[ -n "$BACKEND_PID" || -n "$FRONTEND_PID" ]]; then
    log "正在停止服务..."
  fi
  stop_process_group "$FRONTEND_PID"
  stop_process_group "$BACKEND_PID"

  [[ -z "$FRONTEND_PID" ]] || wait "$FRONTEND_PID" >/dev/null 2>&1 || true
  [[ -z "$BACKEND_PID" ]] || wait "$BACKEND_PID" >/dev/null 2>&1 || true
  log "服务已停止。"
  exit "$status"
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local pid="$3"
  local attempts=30

  while (( attempts > 0 )); do
    if curl -fsS --max-time 1 "$url" >/dev/null 2>&1; then
      log "$name 已就绪。"
      return 0
    fi
    kill -0 "$pid" >/dev/null 2>&1 || fail "$name 启动失败，请查看上方日志。"
    attempts=$((attempts - 1))
    sleep 1
  done

  fail "$name 在 30 秒内未就绪。"
}

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--no-open" ) ]]; then
  fail "用法：./start.sh [--no-open]"
fi

require_command python3
require_command node
require_command npm
require_command curl
require_command lsof

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
  || fail "需要 Python 3.11 或更高版本。"

check_port 8000
check_port 5173

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  log "创建 Python 虚拟环境..."
  python3 -m venv "$VENV_DIR"
fi

if ! "$VENV_DIR/bin/python" -c 'import aiosqlite, fastapi, sqlalchemy, uvicorn' >/dev/null 2>&1; then
  log "安装后端依赖..."
  (
    cd "$BACKEND_DIR"
    "$VENV_DIR/bin/python" -m pip install -r requirements-dev.txt
  )
fi

if [[ ! -x "$FRONTEND_DIR/node_modules/.bin/vite" ]]; then
  log "安装前端依赖..."
  npm ci --prefix "$FRONTEND_DIR"
fi

trap cleanup EXIT
trap 'exit 130' INT TERM

log "启动后端：http://localhost:8000"
(
  cd "$BACKEND_DIR"
  exec "$VENV_DIR/bin/python" run_dev.py
) &
BACKEND_PID=$!

log "启动前端：http://localhost:5173"
(
  cd "$FRONTEND_DIR"
  exec npm run dev -- --host 127.0.0.1
) &
FRONTEND_PID=$!

wait_for_url "后端" "http://localhost:8000/api/health" "$BACKEND_PID"
wait_for_url "前端" "http://localhost:5173" "$FRONTEND_PID"

printf '\nAI Tool Site 已启动：http://localhost:5173\n'
printf '按 Ctrl+C 同时停止前后端。\n\n'

if [[ "${1:-}" != "--no-open" ]] && command -v open >/dev/null 2>&1; then
  open "http://localhost:5173"
fi

while kill -0 "$BACKEND_PID" >/dev/null 2>&1 \
  && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; do
  sleep 1
done

fail "有服务意外退出，请查看上方日志。"
