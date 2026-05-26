#!/usr/bin/env bash
# 单次执行签到（cron 会调用此脚本）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PYTHON="${PYTHON:-python3}"
if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  PYTHON="$SCRIPT_DIR/.venv/bin/python"
fi

mkdir -p "$SCRIPT_DIR/logs"
LOG_FILE="$SCRIPT_DIR/logs/checkin-$(date +%Y%m%d).log"

{
  echo "======== $(date '+%Y-%m-%d %H:%M:%S') ========"
  "$PYTHON" "$SCRIPT_DIR/main.py"
  echo ""
} >>"$LOG_FILE" 2>&1
