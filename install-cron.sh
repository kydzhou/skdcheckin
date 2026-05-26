#!/usr/bin/env bash
# 安装每天凌晨 1:30（服务器本地时区）的 cron 任务
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SH="$SCRIPT_DIR/run.sh"

chmod +x "$RUN_SH"

CRON_LINE="30 1 * * * $RUN_SH"
MARKER="# skland-checkin"

EXISTING="$(crontab -l 2>/dev/null || true)"
# 移除旧的 skland-checkin 任务（若存在）
FILTERED="$(echo "$EXISTING" | grep -vF "$MARKER" | sed '/^$/d' || true)"

{
  echo "$FILTERED"
  echo "$CRON_LINE $MARKER"
} | crontab -

echo "已设置 cron：每天 01:30 执行"
echo "  $CRON_LINE $MARKER"
echo ""
echo "当前 crontab："
crontab -l | grep -F "$MARKER" || true
echo ""
echo "提示：请确认服务器时区为 Asia/Shanghai（timedatectl）"
