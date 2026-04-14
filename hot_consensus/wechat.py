from __future__ import annotations

import logging
import os
import time
from typing import List

import requests

log = logging.getLogger(__name__)

# 企业微信 errcode 40058：markdown.content 总长度上限约 4096 **字节**（UTF-8）
MAX_MD_BYTES = int(os.getenv("HC_WECHAT_MD_MAX_BYTES", "4000"))
# 多段发送时两段之间的间隔（秒），降低频率限制风险
CHUNK_DELAY_SEC = float(os.getenv("HC_WECHAT_CHUNK_DELAY_SEC", "0.55"))


def _truncate_utf8_bytes(text: str, max_bytes: int) -> str:
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    cut = raw[: max_bytes - 40]
    while cut:
        try:
            return cut.decode("utf-8") + "\n\n…(截断)"
        except UnicodeDecodeError:
            cut = cut[:-1]
    return "…"


def _split_utf8_chunks(text: str, max_bytes: int) -> List[str]:
    """将长文按 UTF-8 字节切分为多段，不在多字节字符中间截断。"""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return [text]
    out: List[str] = []
    i = 0
    n = len(raw)
    while i < n:
        j = min(i + max_bytes, n)
        while j > i:
            try:
                out.append(raw[i:j].decode("utf-8"))
                break
            except UnicodeDecodeError:
                j -= 1
        else:
            j = i + 1
            out.append(raw[i:j].decode("utf-8"))
        i = j
    return out if out else [""]


def _post_markdown_once(body: str, timeout: int = 45) -> bool:
    url = webhook_url()
    if not url:
        return False
    safe = body
    if len(safe.encode("utf-8")) > MAX_MD_BYTES:
        safe = _truncate_utf8_bytes(safe, MAX_MD_BYTES)
    try:
        r = requests.post(
            url,
            json={"msgtype": "markdown", "markdown": {"content": safe}},
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


def webhook_url() -> str:
    return (
        os.getenv("HC_WECHAT_WEBHOOK", "").strip()
        or os.getenv("WECHAT_WEBHOOK", "").strip()
    )


def push_markdown(content: str, timeout: int = 45) -> bool:
    """
    推送 markdown；超长时按 UTF-8 字节拆成多段依次发送（每段带 第 i/n 段 标记），不丢正文。
    """
    if not webhook_url():
        log.error("未配置 HC_WECHAT_WEBHOOK 或 WECHAT_WEBHOOK")
        return False

    raw_len = len(content.encode("utf-8"))
    if raw_len <= MAX_MD_BYTES:
        return _post_markdown_once(content, timeout=timeout)

    # 为「第 i/n 段」头预留字节（中文环境多留一些）
    header_reserve = 72
    chunk_body_bytes = max(512, MAX_MD_BYTES - header_reserve)
    chunks = _split_utf8_chunks(content, chunk_body_bytes)
    total = len(chunks)
    ok_all = True
    for i, chunk in enumerate(chunks, 1):
        header = f"> **第 {i}/{total} 段**\n\n"
        part = header + chunk
        if len(part.encode("utf-8")) > MAX_MD_BYTES:
            part = _truncate_utf8_bytes(part, MAX_MD_BYTES)
        if not _post_markdown_once(part, timeout=timeout):
            ok_all = False
        if i < total:
            time.sleep(CHUNK_DELAY_SEC)
    if ok_all:
        log.info("markdown 已分 %s 段发送，总字节约 %s", total, raw_len)
    return ok_all


def push_text(text: str, timeout: int = 30) -> bool:
    """text 类型亦分段，避免超长。"""
    url = webhook_url()
    if not url:
        return False
    max_t = 3900
    raw = text.encode("utf-8")
    if len(raw) <= max_t:
        chunks = [text]
    else:
        chunks = _split_utf8_chunks(text, max_t)
    total = len(chunks)
    ok_all = True
    for i, chunk in enumerate(chunks, 1):
        t = chunk if total == 1 else f"({i}/{total}) {chunk}"
        if len(t.encode("utf-8")) > 4000:
            t = _truncate_utf8_bytes(t, 4000)
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
                ok_all = False
            elif i < total:
                time.sleep(CHUNK_DELAY_SEC)
        except Exception:
            log.exception("企业微信 text 失败")
            ok_all = False
    return ok_all
