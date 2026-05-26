#!/usr/bin/env bash
# ECS 一键初始化：Python 虚拟环境 + 依赖 + 提示后续步骤
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 python3，请先安装："
  echo "  Ubuntu/Debian: sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
  echo "  CentOS/Alibaba Cloud Linux: sudo yum install -y python3"
  exit 1
fi

python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

chmod +x run.sh install-cron.sh

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo ""
  echo "已创建 .env，请编辑并填入 SKYLAND_TOKEN："
  echo "  nano $SCRIPT_DIR/.env"
fi

echo ""
echo "初始化完成。接下来："
echo "  1. 编辑 .env 填入 Token"
echo "  2. 测试： ./run.sh && tail logs/checkin-\$(date +%Y%m%d).log"
echo "  3. 定时： ./install-cron.sh"
