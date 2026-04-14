from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def shanghai_now() -> datetime.datetime:
    return datetime.datetime.now(tz=SHANGHAI_TZ)


def shanghai_today() -> datetime.date:
    return shanghai_now().date()


def is_trading_time() -> bool:
    """沪深 A 股常规交易时段（不含盘前盘后）。"""
    now = shanghai_now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return (datetime.time(9, 30) <= t <= datetime.time(11, 30)) or (
        datetime.time(13, 0) <= t <= datetime.time(15, 0)
    )


def date_str_yyyymmdd(d: datetime.date | None = None) -> str:
    d = d or shanghai_today()
    return d.strftime("%Y%m%d")
