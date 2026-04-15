"""沪深交易日历：AkShare 新浪历史交易日 + 本地日缓存，失败时退回周一至周五。"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import FrozenSet, Optional

from hot_consensus.env import repo_root


def _cache_file() -> Path:
    root = os.getenv("HC_TRADING_CAL_CACHE", "").strip()
    if root:
        return Path(root).expanduser()
    d = repo_root() / ".cache"
    d.mkdir(parents=True, exist_ok=True)
    return d / "cn_sse_trade_dates.json"


def _parse_cal_df(cal) -> FrozenSet[date]:
    import pandas as pd

    if cal is None or getattr(cal, "empty", True):
        return frozenset()
    col = "trade_date" if "trade_date" in cal.columns else cal.columns[0]
    s = pd.to_datetime(cal[col].astype(str), errors="coerce")
    days = {x.date() for x in s.dropna().tolist()}
    return frozenset(days)


def _load_trading_days_from_network() -> FrozenSet[date]:
    import akshare as ak

    cal = ak.tool_trade_date_hist_sina()
    return _parse_cal_df(cal)


def load_cn_trading_days_set() -> FrozenSet[date]:
    """
    返回沪深交易日集合（尽量用缓存，按上海日历日刷新网络数据）。
    网络失败时返回空集，由调用方退回「仅工作日」逻辑。
    """
    from hot_consensus.timeutil import shanghai_today

    if os.getenv("HC_TRADING_CAL_DISABLE", "0").strip() == "1":
        return frozenset()

    today_s = shanghai_today().isoformat()
    path = _cache_file()
    try:
        if path.is_file() and path.stat().st_size > 0:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if (
                isinstance(data, dict)
                and data.get("fetched_at") == today_s
                and isinstance(data.get("dates"), list)
            ):
                out = set()
                for x in data["dates"]:
                    try:
                        out.add(date.fromisoformat(str(x)))
                    except ValueError:
                        continue
                if out:
                    return frozenset(out)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass

    try:
        days = _load_trading_days_from_network()
    except Exception:
        return frozenset()

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "fetched_at": today_s,
                    "source": "akshare.tool_trade_date_hist_sina",
                    "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "dates": sorted(d.isoformat() for d in days),
                },
                f,
                ensure_ascii=False,
            )
    except OSError:
        pass

    return days


def is_cn_stock_trading_day(d: Optional[date] = None) -> bool:
    """
    是否为沪深交易日（含节假日休市）。
    关闭日历：HC_TRADING_CAL_DISABLE=1 → 仅周一至周五为「交易日」。
    数据源失败时：周一至周五视为交易日（与旧版行为一致，节假日可能误判）。
    """
    from hot_consensus.timeutil import shanghai_today

    d = d or shanghai_today()
    if os.getenv("HC_TRADING_CAL_DISABLE", "0").strip() == "1":
        return d.weekday() < 5

    days = load_cn_trading_days_set()
    if not days:
        return d.weekday() < 5
    return d in days
