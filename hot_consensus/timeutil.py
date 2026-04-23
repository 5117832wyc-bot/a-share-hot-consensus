from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def shanghai_now() -> datetime.datetime:
    return datetime.datetime.now(tz=SHANGHAI_TZ)


def shanghai_today() -> datetime.date:
    return shanghai_now().date()


def is_trading_time() -> bool:
    """沪深 A 股常规交易时段（不含盘前盘后）；非法定交易日全天视为非交易时段。"""
    now = shanghai_now()
    if not is_cn_stock_trading_day(now.date()):
        return False
    t = now.time()
    return (datetime.time(9, 30) <= t <= datetime.time(11, 30)) or (
        datetime.time(13, 0) <= t <= datetime.time(15, 0)
    )


def date_str_yyyymmdd(d: datetime.date | None = None) -> str:
    d = d or shanghai_today()
    return d.strftime("%Y%m%d")


def previous_trade_date(ref: datetime.date | None = None) -> datetime.date:
    """向前找到最近一个沪深交易日（新浪日历；失败时退回仅跳过周末）。"""
    ref = ref or shanghai_today()
    x = ref - datetime.timedelta(days=1)
    for _ in range(400):
        if is_cn_stock_trading_day(x):
            return x
        x -= datetime.timedelta(days=1)
    x = ref - datetime.timedelta(days=1)
    while x.weekday() >= 5:
        x -= datetime.timedelta(days=1)
    return x


def is_call_auction_window() -> bool:
    """集合竞价时段 9:15–9:30（不含连续竞价）。"""
    now = shanghai_now()
    if not is_cn_stock_trading_day(now.date()):
        return False
    t = now.time()
    return datetime.time(9, 15) <= t < datetime.time(9, 30)


def is_early_open_window() -> bool:
    """开盘后短时分析窗 9:30–9:45（与 cron 对齐留余量）。"""
    now = shanghai_now()
    if not is_cn_stock_trading_day(now.date()):
        return False
    t = now.time()
    return datetime.time(9, 30) <= t <= datetime.time(9, 45)


def is_pre_afternoon_snapshot_window() -> bool:
    """午休中、下午开盘前参考窗 12:25–12:50（与 cron 12:30 对齐）。"""
    now = shanghai_now()
    if not is_cn_stock_trading_day(now.date()):
        return False
    t = now.time()
    return datetime.time(12, 25) <= t < datetime.time(12, 50)


from hot_consensus.trading_calendar import is_cn_stock_trading_day  # noqa: E402
