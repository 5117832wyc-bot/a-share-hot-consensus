"""DeepSeek：龙头逐只说明 + 财联社分析 + 新闻与榜单联动。"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def analyze_leaders_and_cls(
    leaders: List[Dict[str, Any]],
    cls_new_titles: List[str],
    cls_recent_titles: List[str],
) -> Optional[Dict[str, Any]]:
    """
    leaders: fusion_rows_to_dicts 输出（含 rule_hint）。
    cls_new_titles: 本批新增电报标题。
    cls_recent_titles: 近期电报标题（脉络，可与 new 重叠去重由调用方控制）。
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

    leaders_json = json.dumps(leaders, ensure_ascii=False)[:12000]
    new_block = "\n".join(f"- {t[:500]}" for t in cls_new_titles[:25]) or "（本批无新增电报）"
    recent_block = "\n".join(f"- {t[:400]}" for t in cls_recent_titles[:35]) or "（无）"

    user = f"""任务：结合「盘面龙头榜单」与「财联社电报」做联合分析。

【龙头榜单·结构化】（含代码与规则层提示 rule_hint，勿编造涨跌幅/成交额数字，可引用 rule_hint）
{leaders_json}

【财联社·本批新增标题】
{new_block}

【财联社·近期电报标题脉络】（用于判断叙事主线，可能与上表重叠）
{recent_block}

请输出**仅一个 JSON 对象**（不要 markdown 代码围栏），UTF-8，字段如下：
{{
  "market_tone": "偏多|中性|偏空",
  "cls_analysis": "对财联社电报的整体解读：市场在讨论什么主线、政策/行业情绪（3～6句）",
  "theme_bridge": "电报主线与上述龙头榜单的叠加关系：哪些票可能受益或被点名（2～5句）",
  "leader_notes": [
    {{"code":"6位代码","name":"简称","situation":"结合盘面+新闻的逐只判断（2～4句）","news_touch":"电报是否直接或间接相关：相关则写主题关键词；无则写「电报未直接点名」"}}
  ],
  "dragons_from_news": [
    {{"code":"6位或空","name":"若代码不确定可写简称","reason":"从新闻用语推断的龙头/核心标的线索（勿编造具体价位）"}}
  ],
  "risks": "一句风控提示（如追高风险、题材一日游等）"
}}

要求：
1. leader_notes **必须覆盖榜单中每一个 code**（顺序可与榜单一致）。
2. 不得捏造具体股价、涨跌幅数值；盘面事实以 rule_hint 为准。
3. mentioned_codes 从新闻与榜单推断，不确定的 code 置空或只写行业级判断。
"""

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.25,
            max_tokens=int(os.getenv("HC_DEEPSEEK_MAX_TOKENS", "3500")),
            messages=[
                {
                    "role": "system",
                    "content": "你是 A 股题材与快讯分析助手，只输出合法 JSON，不编造行情数字。",
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
        log.exception("DeepSeek 联合分析失败")
        return None


def format_joint_markdown(data: Dict[str, Any]) -> str:
    """将 JSON 转为企业微信 markdown 片段。"""
    lines: List[str] = ["", "**AI 联合分析（DeepSeek）**"]
    mt = data.get("market_tone")
    if mt:
        lines.append(f"- 市场情绪：**{mt}**")
    ca = data.get("cls_analysis")
    if ca:
        lines.extend(["", "**财联社解读**", str(ca)[:1500]])
    tb = data.get("theme_bridge")
    if tb:
        lines.extend(["", "**电报 × 榜单联动**", str(tb)[:1200]])

    lns = data.get("leader_notes")
    if isinstance(lns, list) and lns:
        lines.extend(["", "**逐只龙头（结合新闻）**"])
        for it in lns[:25]:
            if not isinstance(it, dict):
                continue
            code = it.get("code", "")
            name = it.get("name", "")
            sit = it.get("situation", "")
            nt = it.get("news_touch", "")
            lines.append(f"- `{code}` {name}")
            if sit:
                lines.append(f"  - 判断：{str(sit)[:500]}")
            if nt:
                lines.append(f"  - 电报关联：{str(nt)[:300]}")

    dr = data.get("dragons_from_news")
    if isinstance(dr, list) and dr:
        lines.extend(["", "**从新闻用语提取的龙头线索**"])
        for it in dr[:12]:
            if isinstance(it, dict):
                lines.append(
                    f"- `{it.get('code','')}` {it.get('name','')}：{str(it.get('reason',''))[:200]}"
                )

    rk = data.get("risks")
    if rk:
        lines.extend(["", f"> 风险提示：{str(rk)[:400]}"])
    return "\n".join(lines)
