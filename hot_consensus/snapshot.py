"""榜单快照指纹：无实质变化则不触发推送（防刷屏）。"""
from __future__ import annotations

import hashlib
import json
from typing import Any, List

import pandas as pd


def _hot_rank_bucket(v: Any) -> float:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return -1.0
        return round(float(v), 0)
    except (TypeError, ValueError):
        return -1.0


def fusion_snapshot_hash(fusion: pd.DataFrame) -> str:
    """对 Top 融合榜做稳定哈希（排序、量化字段）。"""
    if fusion is None or fusion.empty:
        return "empty"
    rows: List[dict] = []
    for _, row in fusion.iterrows():
        code = str(row.get("code", "") or "")
        if not code:
            continue
        rows.append(
            {
                "c": code,
                "lb": round(float(row.get("zt_lb") or 0), 2),
                "hr": _hot_rank_bucket(row.get("hot_rank")),
                "se": round(float(row.get("seal_amt") or 0) / 1.0e7, 1),
                "zb": int(row.get("zhaban") or 0),
                "iz": bool(row.get("in_zt")),
                "ih": bool(row.get("in_hot")),
            }
        )
    rows.sort(key=lambda x: x["c"])
    raw = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]
