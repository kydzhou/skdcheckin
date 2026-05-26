#!/usr/bin/env bash
# 安装每天凌晨 3:00（服务器本地时区）的 cron 任务
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SH="$SCRIPT_DIR/run.sh"

chmod +x "$RUN_SH"

CRON_LINE="0 3 * * * $RUN_SH"
MARKER="# skland-checkin"

EXISTING="$(crontab -l 2>/dev/null || true)"
if echo "$EXISTING" | grep -qF "$MARKER"; then
  echo "已存在定时任务，跳过安装。"
  echo "$EXISTING" | grep -F "$MARKER" || true
  exit 0
fi

{
  echo "$EXISTING" | sed '/^$/d'
  echo "$CRON_LINE $MARKER"
} | crontab -

echo "已添加 cron：每天 03:00 执行"
echo "  $CRON_LINE $MARKER"
echo ""
echo "当前 crontab："
crontab -l | grep -F "$MARKER" || true
echo ""
echo "提示：请确认服务器时区为 Asia/Shanghai（timedatectl）"
