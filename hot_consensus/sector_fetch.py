"""板块/题材盘面线索（领头羊≠仅涨停）。"""
from __future__ import annotations

import logging
import os
import time
from typing import List

import akshare as ak
import pandas as pd

log = logging.getLogger(__name__)


def fetch_concept_spot_summary(top_n: int = 8, max_tries: int = 3) -> str:
    """
    东财概念板块即时涨跌幅前列摘要，供 DeepSeek / 推送上下文。
    失败时返回空串。
    """
    top_n = max(3, min(30, top_n))
    delay = 0.5
    for attempt in range(max_tries):
        try:
            df = ak.stock_board_concept_spot_em()
            if df is None or df.empty:
                return ""
            # 常见列名：板块名称 / 涨跌幅 等
            name_col = None
            for c in ("板块名称", "名称", "板块"):
                if c in df.columns:
                    name_col = c
                    break
            pct_col = None
            for c in ("涨跌幅", "最新涨跌幅", "涨跌幅%"):
                if c in df.columns:
                    pct_col = c
                    break
            if not name_col:
                return ""
            work = df.copy()
            if pct_col:
                work["_p"] = pd.to_numeric(work[pct_col], errors="coerce")
                work = work.sort_values("_p", ascending=False)
            head = work.head(top_n)
            parts: List[str] = []
            for _, row in head.iterrows():
                nm = str(row.get(name_col, "") or "")[:16]
                if pct_col:
                    try:
                        p = float(row.get(pct_col, 0) or 0)
                        parts.append(f"{nm}({p:+.2f}%)")
                    except (TypeError, ValueError):
                        parts.append(nm)
                else:
                    parts.append(nm)
            return " | ".join(parts)
        except Exception:
            if attempt >= max_tries - 1:
                log.warning("stock_board_concept_spot_em 失败", exc_info=True)
            time.sleep(delay * (attempt + 1))
    return ""
