#!/usr/bin/env python3
"""集合竞价 / 早盘：定时「龙头预案」推送（与 monitor 分流，独立冷却）。"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from hot_consensus.deepseek_joint import analyze_integrated_cls_and_leaders, format_integrated_markdown
from hot_consensus.env import load_repo_dotenv, repo_root
from hot_consensus.fetch import (
    cls_corpus_for_llm,
    fetch_cls_telegraph,
    fetch_hot_up,
    fetch_lhb_detail,
    fetch_zt_pool,
)
from hot_consensus.fusion import build_fusion, fusion_rows_to_dicts
from hot_consensus.sector_fetch import fetch_concept_spot_summary
from hot_consensus.state import load_state, save_state
from hot_consensus.timeutil import (
    date_str_yyyymmdd,
    is_call_auction_window,
    is_cn_stock_trading_day,
    is_early_open_window,
    previous_trade_date,
    shanghai_now,
    shanghai_today,
)
from hot_consensus.wechat import push_markdown

load_repo_dotenv()

LOG_PATH = repo_root() / "auction_morning.log"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def run_auction(*, force: bool) -> None:
    today = shanghai_today()
    if not force and not is_cn_stock_trading_day(today):
        logging.info("非沪深交易日（周末或法定休市），跳过（--force 可执行）")
        return

    now = shanghai_now()
    slot = os.getenv("HC_AUCTION_SLOT", "auto").strip().lower()
    if slot not in ("any", "always") and not force:
        if slot == "auto" and not (
            is_call_auction_window() or is_early_open_window()
        ):
            logging.info(
                "当前不在集合竞价/开盘初窗（约 9:15–9:45），跳过；"
                "或设 HC_AUCTION_SLOT=any / --force"
            )
            return

    min_gap = max(120, int(os.getenv("HC_AUCTION_MIN_INTERVAL_SEC", "600")))
    state = load_state()
    last = float(state.get("last_auction_push_ts", 0.0) or 0.0)
    if not force and last > 0 and (time.time() - last) < min_gap:
        logging.info("距上次早盘推送不足 %ss，跳过", min_gap)
        return

    today_s = date_str_yyyymmdd(today)
    yday = previous_trade_date(today)
    yday_s = date_str_yyyymmdd(yday)

    zt_t = fetch_zt_pool(today_s)
    zt_y = fetch_zt_pool(yday_s)
    hot = fetch_hot_up()
    fusion, _ = build_fusion(zt_t, hot, top_n=int(os.getenv("HC_AUCTION_TOP_N", "12")))
    leaders = fusion_rows_to_dicts(fusion)

    key_only = os.getenv("HC_AUCTION_CLS_KEY_ONLY", "1").strip() == "1"
    cls_df = fetch_cls_telegraph(key_only=key_only)
    corp = cls_corpus_for_llm(
        cls_df,
        max_items=int(os.getenv("HC_AUCTION_CLS_ITEMS", "35")),
        title_max=220,
        content_max=180,
    )

    sector = fetch_concept_spot_summary(top_n=int(os.getenv("HC_AUCTION_SECTOR_TOP", "10")))

    lhb_note = ""
    lhb = fetch_lhb_detail(yday_s, yday_s)
    if lhb is not None and not lhb.empty and "代码" in lhb.columns:
        rows = []
        for _, row in lhb.head(8).iterrows():
            c = row.get("代码", "")
            n = row.get("名称", "")
            j = row.get("龙虎榜净买额", row.get("龙虎榜净买额(万)", ""))
            rows.append(f"`{c}`{n} 净买≈{j}")
        lhb_note = "\n".join(rows)

    lines = [
        "### 早盘龙头预案（集合竞价/开盘）",
        f"> {today} {now.strftime('%H:%M:%S')} 上海 | 方案见 `docs/HOT_LEADER_SCHEME.md`",
        "",
        f"- 昨日涨停池约 **{len(zt_y)}** 只；今日当前涨停池快照 **{len(zt_t)}** 只（随时间变化）。",
    ]
    if lhb_note:
        lines.extend(["", "**昨日龙虎榜摘录**", lhb_note[:2000]])
    if sector:
        lines.extend(["", "**概念板块即时强弱**", sector[:1500]])

    joint = ""
    if os.getenv("HC_DEEPSEEK_ENABLE", "0").strip() == "1":
        extra = f"【昨日涨停池数量】{len(zt_y)} 【今日涨停池数量】{len(zt_t)}"
        j = analyze_integrated_cls_and_leaders(
            leaders,
            corp + "\n" + extra,
            sector_summary=sector,
        )
        if j:
            joint = format_integrated_markdown(j)
        else:
            joint = "\n（DeepSeek 早盘整合未返回 JSON）\n"
    else:
        joint = "\n（未启用 DeepSeek，仅数据摘要）\n"

    body = "\n".join(lines) + "\n" + joint
    body += "\n> 早盘预案，非投资建议；与盘中 `monitor.py` 推送独立计数。"

    if push_markdown(body):
        state["last_auction_push_ts"] = time.time()
        save_state(state)
        logging.info("早盘推送成功")
    else:
        logging.warning("早盘推送失败")


def main() -> None:
    setup_logging()
    p = argparse.ArgumentParser(description="集合竞价/早盘龙头预案")
    p.add_argument("--force", action="store_true", help="忽略时段与周末")
    p.add_argument("--loop", action="store_true", help="常驻每 60s 检查（一般改用 cron）")
    args = p.parse_args()
    if args.loop:
        while True:
            try:
                run_auction(force=args.force)
            except Exception:
                logging.exception("早盘任务异常")
            time.sleep(60)
        return
    run_auction(force=args.force)


if __name__ == "__main__":
    main()
