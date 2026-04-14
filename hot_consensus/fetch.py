"""AkShare 数据源封装：单源失败不影响其他源。"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import akshare as ak
import pandas as pd

log = logging.getLogger(__name__)


def normalize_code(raw: Any) -> Optional[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if not s:
        return None
    for prefix in ("SH", "SZ", "BJ", "sh", "sz", "bj"):
        if s.upper().startswith(prefix) and len(s) > 6:
            s = s[len(prefix) :]
            break
    s = "".join(c for c in s if c.isdigit())
    if len(s) != 6:
        return None
    return s


def fetch_zt_pool(date_yyyymmdd: str) -> pd.DataFrame:
    try:
        df = ak.stock_zt_pool_em(date=date_yyyymmdd)
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception:
        log.exception("stock_zt_pool_em 失败 date=%s", date_yyyymmdd)
        return pd.DataFrame()


def fetch_hot_up(max_tries: int = 3) -> pd.DataFrame:
    delay = 0.6
    for attempt in range(max_tries):
        try:
            df = ak.stock_hot_up_em()
            return df if df is not None and not df.empty else pd.DataFrame()
        except Exception:
            if attempt >= max_tries - 1:
                log.exception("stock_hot_up_em 失败（已重试 %s 次）", max_tries)
            else:
                log.warning("stock_hot_up_em 第 %s 次失败，将重试", attempt + 1)
            time.sleep(delay * (attempt + 1))
    return pd.DataFrame()


def fetch_cls_telegraph(key_only: bool = False) -> pd.DataFrame:
    """财联社电报。key_only=True 时 symbol=重点（文档中为 A/B 级）。"""
    try:
        sym = "重点" if key_only else "全部"
        df = ak.stock_info_global_cls(symbol=sym)
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception:
        log.exception("stock_info_global_cls 失败")
        return pd.DataFrame()


def row_fingerprint(title: str, content: str) -> str:
    raw = f"{title}\0{content}".encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()[:32]


def new_cls_rows(
    df: pd.DataFrame, seen: set[str], max_rows: int = 12
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """返回新电报行（字典列表）与新指纹列表。"""
    if df.empty:
        return [], []
    new_items: List[Dict[str, Any]] = []
    new_hashes: List[str] = []
    title_col = "标题" if "标题" in df.columns else None
    if not title_col:
        return [], []
    content_col = "内容" if "内容" in df.columns else title_col
    for _, row in df.iterrows():
        title = str(row.get(title_col, "") or "")
        content = str(row.get(content_col, "") or "")
        fp = row_fingerprint(title, content)
        if fp in seen:
            continue
        new_hashes.append(fp)
        item: Dict[str, Any] = {"title": title[:200], "fp": fp}
        if "发布时间" in df.columns:
            item["time"] = str(row.get("发布时间", ""))
        if "发布日期" in df.columns:
            item["date"] = str(row.get("发布日期", ""))
        new_items.append(item)
        if len(new_items) >= max_rows:
            break
    return new_items, new_hashes


def recent_cls_titles(df: pd.DataFrame, n: int = 18) -> List[str]:
    """取电报列表中最近 n 条标题（用于无新增时仍做脉络/AI 分析）。"""
    if df.empty or "标题" not in df.columns:
        return []
    titles = [str(x)[:400] for x in df["标题"].astype(str).tolist() if str(x).strip()]
    return titles[-n:] if len(titles) > n else titles


def fetch_lhb_detail(start_yyyymmdd: str, end_yyyymmdd: str) -> pd.DataFrame:
    try:
        df = ak.stock_lhb_detail_em(start_date=start_yyyymmdd, end_date=end_yyyymmdd)
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception:
        log.exception("stock_lhb_detail_em 失败")
        return pd.DataFrame()
