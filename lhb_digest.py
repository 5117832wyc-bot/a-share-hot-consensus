#!/usr/bin/env python3
"""盘后：东财龙虎榜当日摘要 → 企业微信（适合 cron 17:00 后）。"""
from __future__ import annotations

import argparse
import logging
import sys

from hot_consensus.env import load_repo_dotenv, repo_root
from hot_consensus.fetch import fetch_lhb_detail
from hot_consensus.timeutil import date_str_yyyymmdd
from hot_consensus.wechat import push_markdown

load_repo_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(repo_root() / "lhb_digest.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--date", default="", help="YYYYMMDD，默认今日（上海）")
    args = p.parse_args()
    d = args.date.strip() or date_str_yyyymmdd()
    df = fetch_lhb_detail(d, d)
    if df is None or df.empty:
        logging.warning("无龙虎榜数据（可能尚未披露或非交易日）")
        return
    # 列名以 AkShare 为准
    net_col = "龙虎榜净买额" if "龙虎榜净买额" in df.columns else None
    lines = [f"### 龙虎榜摘要 {d}", ""]
    sort_df = df
    if net_col:
        sort_df = df.reindex(df[net_col].abs().sort_values(ascending=False).index)
    for i, (_, row) in enumerate(sort_df.head(20).iterrows(), 1):
        code = row.get("代码", "")
        name = row.get("名称", "")
        reason = str(row.get("上榜原因", "") or "")[:40]
        net = row.get(net_col, "") if net_col else ""
        lines.append(f"{i}. `{code}` {name} 净买≈{net}  {reason}")
    lines.append("\n> 数据来源 AkShare stock_lhb_detail_em；非投资建议。")
    push_markdown("\n".join(lines))


if __name__ == "__main__":
    main()
