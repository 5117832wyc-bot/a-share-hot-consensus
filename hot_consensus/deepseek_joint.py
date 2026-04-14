"""DeepSeek：财联社整合（不列新闻）+ 方向与候选票 + 与榜单联动。"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def analyze_integrated_cls_and_leaders(
    leaders: List[Dict[str, Any]],
    cls_corpus: str,
) -> Optional[Dict[str, Any]]:
    """
    cls_corpus：仅供模型阅读的标题+正文截断拼接，**不得**出现在最终推送正文中。
    """
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        log.warning("未安装 openai 包，跳过 DeepSeek")
        return None

    base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    client = OpenAI(api_key=key, base_url=base)

    leaders_json = json.dumps(leaders, ensure_ascii=False)[:14000]
    corp = (cls_corpus or "").strip()
    if not corp:
        corp = "（当前未拉到财联社正文，仅依据榜单做保守归纳）"

    user = f"""你是 A 股快讯与盘面联动分析师。下列【财联社语料】仅为你内部阅读，用于整合判断，**禁止**在输出中逐条复述或枚举新闻标题。

【龙头榜单·结构化】（含 rule_hint，勿编造数值）
{leaders_json}

【财联社语料·内部材料】
{corp[:28000]}

请输出**仅一个 JSON**（不要 markdown 围栏），字段严格如下：
{{
  "market_tone": "偏多|中性|偏空",
  "cls_synthesis": "对财联社快讯的整合判断，4～8 句话；写主线、政策/行业情绪、与盘面的关系；**禁止**出现「第一条、第二条」或逐条新闻列举",
  "directions": [
    {{
      "theme": "方向或主题名（简短）",
      "outlook": "可能走强|结构性机会|震荡观察|谨慎",
      "bias_reason": "为何当前叙事可能指向该方向（1～3 句，综合语料与榜单，不抄新闻原文）",
      "watchlist": [
        {{
          "code": "6位或空字符串",
          "name": "简称或空",
          "evidence": "盘面共振|新闻叙事|榜单交集|纯叙事推断",
          "hint": "一句说明（若与榜单 code 重合请标明）"
        }}
      ]
    }}
  ],
  "index_alignment": "当前叙事与 Top 榜单标的的共振或背离（1～3 句）",
  "risks": "一句风险提示"
}}

硬性要求：
1. directions 数组 **2～4 个**主题；每个 watchlist **最多 5 条**，优先填 6 位代码；拿不准 code 可只写 name 并标「待核实」。
2. evidence 必须四选一；「纯叙事推断」表示未在榜单共振、波动大。
3. 输出中 **不得**包含财联社单条新闻的原文照抄或编号列表。
"""

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.22,
            max_tokens=int(os.getenv("HC_DEEPSEEK_MAX_TOKENS", "3200")),
            messages=[
                {
                    "role": "system",
                    "content": "只输出合法 JSON。不编造股价、涨跌幅、成交额。不逐条列举新闻。",
                },
                {"role": "user", "content": user},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if "```" in text:
                text = text.rsplit("```", 1)[0]
        return json.loads(text)
    except Exception:
        log.exception("DeepSeek 整合分析失败")
        return None


def format_integrated_markdown(data: Dict[str, Any]) -> str:
    """推送正文：整合观点 + 方向与标的，不含新闻列表。"""
    lines: List[str] = ["", "### 财联社整合 · 方向与标的（无新闻逐条列举）"]
    mt = data.get("market_tone")
    if mt:
        lines.append(f"市场情绪：**{mt}**")

    syn = data.get("cls_synthesis")
    if syn:
        lines.extend(["", "**整合观点**", str(syn)[:2000]])

    dirs = data.get("directions")
    if isinstance(dirs, list) and dirs:
        lines.extend(["", "**可能走强 / 值得跟踪的方向**"])
        for i, d in enumerate(dirs[:6], 1):
            if not isinstance(d, dict):
                continue
            theme = str(d.get("theme", "") or "")[:80]
            out = str(d.get("outlook", "") or "")[:40]
            br = str(d.get("bias_reason", "") or "")[:400]
            lines.append(f"{i}. **{theme}** · *{out}*")
            if br:
                lines.append(f"   {br}")
            wl = d.get("watchlist")
            if isinstance(wl, list):
                for w in wl[:6]:
                    if not isinstance(w, dict):
                        continue
                    code = str(w.get("code", "") or "").strip()
                    name = str(w.get("name", "") or "").strip()
                    ev = str(w.get("evidence", "") or "").strip()
                    hint = str(w.get("hint", "") or "").strip()[:120]
                    cpart = f"`{code}`" if len(code) == 6 else "（代码待核实）"
                    lines.append(f"   - {cpart} {name} 〔{ev}〕 {hint}".strip())

    ia = data.get("index_alignment")
    if ia:
        lines.extend(["", "**与榜单共振**", str(ia)[:800]])

    rk = data.get("risks")
    if rk:
        lines.extend(["", f"> 风险提示：{str(rk)[:500]}"])
    return "\n".join(lines)


# 兼容旧名
def analyze_leaders_and_cls(
    leaders: List[Dict[str, Any]],
    cls_new_titles: List[str],
    cls_recent_titles: List[str],
) -> Optional[Dict[str, Any]]:
    """已弃用：请使用 analyze_integrated_cls_and_leaders + cls_corpus_for_llm。"""
    corp = "\n".join(cls_new_titles[:30] + cls_recent_titles[:40])
    return analyze_integrated_cls_and_leaders(leaders, corp)
