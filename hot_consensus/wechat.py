from __future__ import annotations

import logging
import os
from typing import Optional

import requests

log = logging.getLogger(__name__)

# 企业微信 markdown 单条建议控制在 3800 字以内
MAX_MD_LEN = 3800


def webhook_url() -> str:
    return (
        os.getenv("HC_WECHAT_WEBHOOK", "").strip()
        or os.getenv("WECHAT_WEBHOOK", "").strip()
    )


def push_markdown(content: str, timeout: int = 45) -> bool:
    url = webhook_url()
    if not url:
        log.error("未配置 HC_WECHAT_WEBHOOK 或 WECHAT_WEBHOOK")
        return False
    body = content if len(content) <= MAX_MD_LEN else content[: MAX_MD_LEN - 20] + "\n\n…(截断)"
    try:
        r = requests.post(
            url,
            json={"msgtype": "markdown", "markdown": {"content": body}},
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("errcode") != 0:
            log.error("企业微信返回错误: %s", data)
            return False
        return True
    except Exception:
        log.exception("企业微信推送失败")
        return False


def push_text(text: str, timeout: int = 30) -> bool:
    url = webhook_url()
    if not url:
        return False
    t = text if len(text) <= 4000 else text[:3980] + "…"
    try:
        r = requests.post(
            url,
            json={"msgtype": "text", "text": {"content": t}},
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("errcode") != 0:
            log.error("企业微信 text 错误: %s", data)
            return False
        return True
    except Exception:
        log.exception("企业微信 text 失败")
        return False
