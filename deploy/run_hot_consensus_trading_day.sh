#!/usr/bin/env bash
# 交易日早盘：集合竞价后推一次「龙头预案」，并确保盘中 monitor --loop 常驻。
# 由 crontab 工作日 9:25 调用；与 ab-stock-quant 的 run_ab_trading_day.sh 类似。
set -euo pipefail

ROOT_DIR="/root/code/a-share-hot-consensus"
PYTHON_BIN="${PYTHON_BIN:-/root/miniconda3/bin/python3}"

cd "$ROOT_DIR"

# 非法定交易日（周末/节假日）不跑早盘与拉起监控
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

# 1) 早盘/竞价预案（日志见项目根 auction_morning.log）；失败仍继续拉起盘中监控
set +e
"$PYTHON_BIN" "$ROOT_DIR/auction_morning.py"
auc=$?
set -e
if [ "$auc" -ne 0 ]; then
  echo "$(date -Is) auction_morning.py exit=$auc (continuing)" >&2
fi

# 2) 盘中轮询：未运行时拉起（单实例）
if pgrep -f "$ROOT_DIR/monitor.py --loop" >/dev/null 2>&1; then
  exit 0
fi

nohup "$PYTHON_BIN" "$ROOT_DIR/monitor.py" --loop >>"$ROOT_DIR/monitor_nohup.log" 2>&1 &
echo "$(date -Is) started monitor.py --loop pid=$!"
