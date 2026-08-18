#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/start.sh" "$@"
status=$?

if [[ "$status" -ne 0 && "$status" -ne 130 ]]; then
  printf '\n启动失败，按 Enter 关闭此窗口。'
  read -r
fi

exit "$status"
