"""可选：对一批财联社标题做 DeepSeek 结构化摘要（OpenAI 兼容 API）。"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def analyze_titles(titles: List[str]) -> Optional[Dict[str, Any]]:
    if not titles:
        return None
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
    lines = "\n".join(f"- {t[:300]}" for t in titles[:40])
    user = (
        "以下为财联社电报标题列表。请输出**仅一个 JSON 对象**，不要 markdown 围栏，字段：\n"
        '{"themes":["主题1"], "mentioned_codes":["600000"], "sentiment":"中性|偏多|偏空", '
        '"one_line":"一句话摘要"}\n'
        "mentioned_codes 为可能涉及的 6 位 A 股代码，不确定则 []。\n\n"
        f"{lines}"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            max_tokens=600,
            messages=[
                {
                    "role": "system",
                    "content": "你是 A 股快讯分析助手，只输出合法 JSON，不编造行情数字。",
                },
                {"role": "user", "content": user},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        # 去掉可能的 ```json 围栏
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if "```" in text:
                text = text.rsplit("```", 1)[0]
        return json.loads(text)
    except Exception:
        log.exception("DeepSeek 调用失败")
        return None
