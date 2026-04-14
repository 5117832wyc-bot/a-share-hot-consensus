"""涨停池 + 飙升榜 融合得分与表格。"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

from hot_consensus.fetch import normalize_code


def build_fusion(
    zt: pd.DataFrame, hot: pd.DataFrame, top_n: int = 15
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    返回按 score 降序的 DataFrame，列：code, name, score, zt_lb, hot_rank, industry
    """
    scores: Dict[str, Dict[str, Any]] = {}

    if not zt.empty and "代码" in zt.columns:
        for _, row in zt.iterrows():
            code = normalize_code(row.get("代码"))
            if not code:
                continue
            name = str(row.get("名称", "") or "")
            lb = float(row.get("连板数", 0) or 0)
            fb = float(row.get("封板资金", 0) or 0)
            ind = str(row.get("所属行业", "") or "")
            # 情绪权重：连板 + 封板资金（亿元量级缩放）
            part = 100.0 + lb * 25.0 + min(fb / 1e8, 50.0)
            scores[code] = {
                "code": code,
                "name": name,
                "score": part,
                "zt_lb": lb,
                "hot_rank": None,
                "industry": ind,
            }

    if not hot.empty and "代码" in hot.columns:
        for _, row in hot.iterrows():
            code = normalize_code(row.get("代码"))
            if not code:
                continue
            rank = row.get("当前排名")
            try:
                rk = float(rank) if rank is not None and not pd.isna(rank) else 999.0
            except (TypeError, ValueError):
                rk = 999.0
            name = str(row.get("股票名称", "") or "")
            bonus = max(0.0, 80.0 - rk * 0.5)
            if code in scores:
                scores[code]["score"] = float(scores[code]["score"]) + bonus
                scores[code]["hot_rank"] = rk
                if name and not scores[code].get("name"):
                    scores[code]["name"] = name
            else:
                scores[code] = {
                    "code": code,
                    "name": name,
                    "score": bonus,
                    "zt_lb": 0.0,
                    "hot_rank": rk,
                    "industry": "",
                }

    rows = sorted(scores.values(), key=lambda x: float(x["score"]), reverse=True)[:top_n]
    out = pd.DataFrame(rows)
    if out.empty:
        return out, {}
    sig_map = {r["code"]: float(r["score"]) for r in rows}
    return out, sig_map


def signature(zt: pd.DataFrame, hot: pd.DataFrame, fusion: pd.DataFrame) -> str:
    """用于判断榜单是否显著变化。"""
    import hashlib

    parts: List[str] = []
    if fusion is not None and not fusion.empty and "code" in fusion.columns:
        parts.append(",".join(fusion["code"].astype(str).tolist()))
    else:
        parts.append("")
    if not zt.empty and "连板数" in zt.columns:
        try:
            mx = float(zt["连板数"].max())
        except Exception:
            mx = 0.0
        parts.append(f"ztmax={mx}")
    parts.append(f"zt_n={len(zt)}")
    parts.append(f"hot_n={len(hot)}")
    raw = "|".join(parts).encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()[:40]
