#!/usr/bin/env python3
"""盘中轮询：涨停池 + 飙升榜 + 财联社（语料）+ 板块强弱 → 融合 → 企业微信。"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from hot_consensus.cls_gate import filter_important_new_items
from hot_consensus.deepseek_joint import analyze_integrated_cls_and_leaders, format_integrated_markdown
from hot_consensus.env import load_repo_dotenv, repo_root
from hot_consensus.fetch import (
    cls_corpus_for_llm,
    fetch_cls_telegraph,
    fetch_hot_up,
    fetch_zt_pool,
    new_cls_rows,
)
from hot_consensus.fusion import build_fusion, fusion_rows_to_dicts, rule_based_hint, signature
from hot_consensus.sector_fetch import fetch_concept_spot_summary
from hot_consensus.snapshot import fusion_snapshot_hash
from hot_consensus.state import cls_seen_set, load_state, save_state, trim_seen
from hot_consensus.timeutil import (
    date_str_yyyymmdd,
    is_cn_stock_trading_day,
    is_trading_time,
    shanghai_now,
    shanghai_today,
)
from hot_consensus.wechat import push_markdown

load_repo_dotenv()

LOG_PATH = repo_root() / "hot_consensus.log"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def run_cycle(*, force: bool) -> None:
    if not force and not is_cn_stock_trading_day(shanghai_today()):
        logging.info("非沪深交易日（休市），跳过（--force 可强制执行）")
        return
    if not force and not is_trading_time():
        logging.info("非连续竞价时段，跳过（--force 可强制执行）")
        return

    today = date_str_yyyymmdd()
    key_only = os.getenv("HC_CLS_KEY_ONLY", "0").strip() == "1"
    top_n = max(5, min(50, int(os.getenv("HC_TOP_N", "15"))))
    min_push = max(30, int(os.getenv("HC_MIN_PUSH_INTERVAL_SEC", "300")))
    min_push_cls = max(30, int(os.getenv("HC_MIN_PUSH_ON_CLS_SEC", "120")))
    corp_items = max(15, min(80, int(os.getenv("HC_CLS_CORPUS_ITEMS", "45"))))
    title_max = max(80, min(400, int(os.getenv("HC_CLS_TITLE_MAX", "220"))))
    content_max = max(60, min(400, int(os.getenv("HC_CLS_CONTENT_MAX", "160"))))
    important_only = os.getenv("HC_CLS_IMPORTANT_ONLY", "1").strip() == "1"
    sector_on = os.getenv("HC_SECTOR_ENABLE", "1").strip() == "1"

    zt = fetch_zt_pool(today)
    hot = fetch_hot_up()
    cls_df = fetch_cls_telegraph(key_only=key_only)

    fusion, _ = build_fusion(zt, hot, top_n=top_n)
    sig = signature(zt, hot, fusion)
    snap_hash = fusion_snapshot_hash(fusion)

    state = load_state()
    seen = cls_seen_set(state)
    new_cls, new_fps = new_cls_rows(cls_df, seen)

    triggered_news = (
        filter_important_new_items(new_cls) if important_only else list(new_cls)
    )
    last_snap = str(state.get("last_snap_hash") or "")
    snap_changed = snap_hash != last_snap
    need_push = snap_changed or (len(triggered_news) > 0)

    if not need_push:
        for fp in new_fps:
            seen.add(fp)
        state["cls_seen"] = list(seen)
        trim_seen(state)
        save_state(state)
        logging.info(
            "快照未变且无非重要电报，跳过推送；已静默消化 %s 条电报指纹",
            len(new_fps),
        )
        return

    now_ts = time.time()
    last_push = float(state.get("last_push_ts", 0.0) or 0.0)
    elapsed = now_ts - last_push if last_push > 0 else min_push
    need_push2 = last_push <= 0
    if triggered_news:
        need_push2 = need_push2 or (elapsed >= min_push_cls)
    else:
        need_push2 = need_push2 or (elapsed >= min_push)

    if not need_push2:
        logging.info(
            "满足推送条件但处于冷却: elapsed=%.0fs",
            elapsed,
        )
        save_state(state)
        return

    sector_line = ""
    if sector_on:
        sector_line = fetch_concept_spot_summary(
            top_n=int(os.getenv("HC_SECTOR_TOP_N", "8"))
        )

    leaders_payload = fusion_rows_to_dicts(fusion)
    cls_corpus = cls_corpus_for_llm(
        cls_df, max_items=corp_items, title_max=title_max, content_max=content_max
    )

    lines = [
        "### 热门龙头情报（含板块线索）",
        f"> 日期 {shanghai_today()} 上海 {shanghai_now().strftime('%H:%M:%S')} | 涨停池约 {len(zt)} | 飙升榜约 {len(hot)}",
        "",
        f"**融合 Top {top_n}**（情绪高标 + 人气；**龙头含板块领头羊，见下栏整合**）",
    ]
    if fusion is None or fusion.empty:
        lines.append("（无数据或接口失败）")
    else:
        for rank, (_, row) in enumerate(fusion.iterrows(), 1):
            code = row.get("code", "")
            name = row.get("name", "")
            sc = float(row.get("score", 0) or 0)
            hint = rule_based_hint(row)
            zf = row.get("zf")
            zf_s = ""
            try:
                if zf is not None and float(zf) == float(zf):
                    zf_s = f" 涨跌幅≈{float(zf):.2f}%"
            except (TypeError, ValueError):
                pass
            lines.append(
                f"{rank}. **`{code}` {name}**  score≈{sc:.1f}{zf_s}\n"
                f"> 快照：{hint}"
            )

    if sector_line:
        lines.extend(["", "**概念板块·即时强弱（摘要）**", f"> {sector_line[:1200]}"])

    joint_md = ""
    if os.getenv("HC_DEEPSEEK_ENABLE", "0").strip() == "1":
        joint = analyze_integrated_cls_and_leaders(
            leaders_payload, cls_corpus, sector_summary=sector_line
        )
        if joint:
            joint_md = format_integrated_markdown(joint)
        else:
            joint_md = "\n### 财联社整合\n（DeepSeek 未返回有效 JSON，见日志。）\n"
    else:
        joint_md = (
            "\n### 财联社整合\n"
            "已拉取语料；请设 **`HC_DEEPSEEK_ENABLE=1`** 生成整合与方向。\n"
        )

    body = "\n".join(lines) + "\n" + joint_md
    body += "\n> 数据来源：AkShare；**非投资建议**。电报正文不在此展示。"

    ok = push_markdown(body)
    if ok:
        state["last_push_ts"] = now_ts
        state["last_signature"] = sig
        state["last_snap_hash"] = snap_hash
        for fp in new_fps:
            seen.add(fp)
        state["cls_seen"] = list(seen)
        trim_seen(state)
        logging.info("推送成功 snap=%s…", snap_hash[:12])
    else:
        logging.warning("推送失败，不更新快照与电报已读")

    save_state(state)


def main() -> None:
    setup_logging()
    p = argparse.ArgumentParser(description="A 股热门龙头情报监控")
    p.add_argument("--once", action="store_true", help="只跑一轮")
    p.add_argument("--force", action="store_true", help="忽略交易时段")
    p.add_argument(
        "--loop",
        action="store_true",
        help="循环运行（需配合 systemd/cron 或自行 nohup）",
    )
    args = p.parse_args()

    poll = max(30, int(os.getenv("HC_POLL_INTERVAL_SEC", "45")))

    if args.loop:
        logging.info("进入循环 poll=%ss（默认与 AB 对齐 45s）", poll)
        while True:
            try:
                if is_trading_time() or args.force:
                    run_cycle(force=args.force)
                else:
                    if not is_cn_stock_trading_day(shanghai_today()):
                        logging.info("非沪深交易日（休市）休眠")
                    else:
                        logging.info("非交易时段休眠")
            except Exception:
                logging.exception("本轮异常")
            time.sleep(poll)
        return

    run_cycle(force=args.force)
    if not args.once:
        logging.info("单次运行结束（使用 --loop 持续运行）")


if __name__ == "__main__":
    main()
