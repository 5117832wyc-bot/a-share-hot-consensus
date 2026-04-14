"""涨停池 + 飙升榜 融合得分与表格（含盘面辅助字段）。"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

from hot_consensus.fetch import normalize_code


def _num(row: Any, key: str, default: float = 0.0) -> float:
    try:
        v = row.get(key)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _str(row: Any, key: str) -> str:
    v = row.get(key)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def build_fusion(
    zt: pd.DataFrame, hot: pd.DataFrame, top_n: int = 15
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    返回按 score 降序的 DataFrame，含列：
    code, name, score, zt_lb, hot_rank, industry,
    seal_amt, zhaban, zf, zt_stat, first_seal,
    hot_zf, rank_delta, in_zt, in_hot
    """
    scores: Dict[str, Dict[str, Any]] = {}

    if not zt.empty and "代码" in zt.columns:
        for _, row in zt.iterrows():
            code = normalize_code(row.get("代码"))
            if not code:
                continue
            name = _str(row, "名称")
            lb = _num(row, "连板数")
            fb = _num(row, "封板资金")
            ind = _str(row, "所属行业")
            zb = int(_num(row, "炸板次数"))
            zf = _num(row, "涨跌幅")
            zt_stat = _str(row, "涨停统计")
            fs = _str(row, "首次封板时间")
            if len(fs) == 6 and fs.isdigit():
                fs = f"{fs[:2]}:{fs[2:4]}:{fs[4:6]}"

            part = 100.0 + lb * 25.0 + min(fb / 1e8, 50.0)
            scores[code] = {
                "code": code,
                "name": name,
                "score": part,
                "zt_lb": lb,
                "hot_rank": None,
                "industry": ind,
                "seal_amt": fb,
                "zhaban": zb,
                "zf": zf,
                "zt_stat": zt_stat,
                "first_seal": fs,
                "hot_zf": None,
                "rank_delta": None,
                "in_zt": True,
                "in_hot": False,
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
            name = _str(row, "股票名称")
            hot_zf = _num(row, "涨跌幅")
            rd = _num(row, "排名较昨日变动")
            bonus = max(0.0, 80.0 - rk * 0.5)
            if code in scores:
                scores[code]["score"] = float(scores[code]["score"]) + bonus
                scores[code]["hot_rank"] = rk
                scores[code]["hot_zf"] = hot_zf
                scores[code]["rank_delta"] = rd
                scores[code]["in_hot"] = True
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
                    "seal_amt": 0.0,
                    "zhaban": 0,
                    "zf": hot_zf,
                    "zt_stat": "",
                    "first_seal": "",
                    "hot_zf": hot_zf,
                    "rank_delta": rd,
                    "in_zt": False,
                    "in_hot": True,
                }

    rows = sorted(scores.values(), key=lambda x: float(x["score"]), reverse=True)[:top_n]
    out = pd.DataFrame(rows)
    if out.empty:
        return out, {}
    sig_map = {r["code"]: float(r["score"]) for r in rows}
    return out, sig_map


def rule_based_hint(row: Any) -> str:
    """非 AI 的盘面辅助一句话（可核对字段）。"""
    parts: List[str] = []
    code = row.get("code", "")
    in_zt = bool(row.get("in_zt"))
    in_hot = bool(row.get("in_hot"))
    lb = float(row.get("zt_lb") or 0)
    seal = float(row.get("seal_amt") or 0)
    zb = int(row.get("zhaban") or 0)
    ind = str(row.get("industry") or "").strip()

    if in_zt:
        parts.append("当前涨停池内")
        if lb >= 2:
            parts.append(f"连板高度约{lb:.0f}（情绪标杆）")
        else:
            parts.append("首板/高度1")
        if seal > 0:
            parts.append(f"封板资金约{seal / 1e8:.2f}亿元")
        if zb > 0:
            parts.append(f"炸板{zb}次（封板分歧）")
        elif zb == 0:
            parts.append("未炸板（封板较稳）")
        if ind:
            parts.append(f"行业:{ind}")
    if in_hot:
        hr = row.get("hot_rank")
        try:
            if hr is not None and float(hr) == float(hr):
                parts.append(f"东财飙升榜名次约{float(hr):.0f}")
        except (TypeError, ValueError):
            pass
        rd = row.get("rank_delta")
        try:
            if rd is not None and float(rd) == float(rd) and float(rd) != 0:
                parts.append(f"人气排名较昨变动{float(rd):+.0f}")
        except (TypeError, ValueError):
            pass
    if not in_zt and in_hot:
        parts.insert(0, "未在当前涨停池快照中（仅人气飙升）")
    if not parts:
        parts.append("数据不足")
    return "；".join(parts)[:220]


def fusion_rows_to_dicts(fusion: pd.DataFrame) -> List[Dict[str, Any]]:
    if fusion is None or fusion.empty:
        return []
    out: List[Dict[str, Any]] = []
    for _, row in fusion.iterrows():
        out.append(
            {
                "code": str(row.get("code", "")),
                "name": str(row.get("name", "")),
                "zt_lb": float(row.get("zt_lb") or 0),
                "hot_rank": row.get("hot_rank"),
                "industry": str(row.get("industry") or ""),
                "seal_amt": float(row.get("seal_amt") or 0),
                "zhaban": int(row.get("zhaban") or 0),
                "in_zt": bool(row.get("in_zt")),
                "in_hot": bool(row.get("in_hot")),
                "rule_hint": rule_based_hint(row),
            }
        )
    return out


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
