#!/usr/bin/env bash
# 仅沪深交易日兜底拉起 monitor --loop（与 crontab 15:10 配合）
set -euo pipefail

ROOT_DIR="/root/code/a-share-hot-consensus"
PYTHON_BIN="${PYTHON_BIN:-/root/miniconda3/bin/python3}"

cd "$ROOT_DIR"

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.env"
  set +a
fi

if ! "$PYTHON_BIN" -c "from hot_consensus.timeutil import is_cn_stock_trading_day; import sys; sys.exit(0 if is_cn_stock_trading_day() else 1)"; then
  exit 0
fi

if pgrep -f "$ROOT_DIR/monitor.py --loop" >/dev/null 2>&1; then
  exit 0
fi

nohup "$PYTHON_BIN" "$ROOT_DIR/monitor.py" --loop >>"$ROOT_DIR/monitor_nohup.log" 2>&1 &
echo "$(date -Is) ensure_monitor_loop: started monitor.py --loop pid=$!"
