"""财联社标题重要性门控：避免「有新增就推」导致信息爆炸。"""
from __future__ import annotations

import os
from typing import List

# 默认关键词（可环境变量覆盖 HC_CLS_KEYWORDS 逗号分隔）
_DEFAULT_KW = (
    "央行,证监会,国务院,金融监管,降准,降息,加息,汇率,地缘政治,中美,俄乌,北约,台海,"
    "财政部,国资委,发改委,工信部,商务部,住建部,重大,突发,紧急,禁止,立案,调查,问询,"
    "减持,增持,回购,停牌,复牌,业绩,预告,亏损,盈利,ST,退市,并购,重组,借壳,IPO"
)


def _keyword_list() -> List[str]:
    raw = os.getenv("HC_CLS_KEYWORDS", "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return [x.strip() for x in _DEFAULT_KW.split(",") if x.strip()]


def is_important_title(title: str) -> bool:
    """
    规则层重要性：命中关键词或标题足够短快讯中的强信号（可自行调 HC_CLS_KEYWORDS）。
    HC_CLS_GATE_DISABLE=1 时恒为 True（等同不门控，仅用于调试）。
    """
    if os.getenv("HC_CLS_GATE_DISABLE", "0").strip() == "1":
        return True
    t = (title or "").strip()
    if not t:
        return False
    if os.getenv("HC_CLS_IMPORTANT_LEN_ONLY", "0").strip() == "1":
        return len(t) >= int(os.getenv("HC_CLS_MIN_TITLE_LEN", "18"))
    for kw in _keyword_list():
        if kw and kw in t:
            return True
    return False


def filter_important_new_items(new_items: List[dict]) -> List[dict]:
    """new_cls 行列表，仅保留标题重要的条目。"""
    out: List[dict] = []
    for it in new_items:
        title = str(it.get("title", "") or "")
        if is_important_title(title):
            out.append(it)
    return out
