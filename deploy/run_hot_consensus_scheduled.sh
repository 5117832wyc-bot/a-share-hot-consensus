#!/usr/bin/env bash
# 交易日 12:30：「热门龙头情报」——须落在 12:25–12:50 上海窗内，与盘中同一套触发逻辑（见 monitor.py --scheduled）
set -euo pipefail

ROOT_DIR="/root/code/a-share-hot-consensus"
PYTHON_BIN="${PYTHON_BIN:-/root/miniconda3/bin/python3}"

cd "$ROOT_DIR"

if ! "$PYTHON_BIN" -c "from hot_consensus.timeutil import is_cn_stock_trading_day; import sys; sys.exit(0 if is_cn_stock_trading_day() else 1)"; then
  echo "$(date -Is) 非沪深交易日（休市），跳过"
  exit 0
fi

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.env"
  set +a
fi

exec "$PYTHON_BIN" "$ROOT_DIR/monitor.py" --once --scheduled
