#!/usr/bin/env python3
"""盘中轮询：涨停池 + 飙升榜 + 财联社（仅作 AI 语料）→ 融合 → 企业微信。"""
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
    fetch_zt_pool,
    new_cls_rows,
)
from hot_consensus.fusion import build_fusion, fusion_rows_to_dicts, rule_based_hint, signature
from hot_consensus.state import cls_seen_set, load_state, save_state, trim_seen
from hot_consensus.timeutil import (
    date_str_yyyymmdd,
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
    if not force and not is_trading_time():
        logging.info("非交易时段，跳过（--force 可强制执行）")
        return

    today = date_str_yyyymmdd()
    key_only = os.getenv("HC_CLS_KEY_ONLY", "0").strip() == "1"
    top_n = max(5, min(50, int(os.getenv("HC_TOP_N", "15"))))
    min_push = max(30, int(os.getenv("HC_MIN_PUSH_INTERVAL_SEC", "300")))
    min_push_cls = max(30, int(os.getenv("HC_MIN_PUSH_ON_CLS_SEC", "120")))
    corp_items = max(15, min(80, int(os.getenv("HC_CLS_CORPUS_ITEMS", "45"))))
    title_max = max(80, min(400, int(os.getenv("HC_CLS_TITLE_MAX", "220"))))
    content_max = max(60, min(400, int(os.getenv("HC_CLS_CONTENT_MAX", "160"))))

    zt = fetch_zt_pool(today)
    hot = fetch_hot_up()
    cls_df = fetch_cls_telegraph(key_only=key_only)

    fusion, _ = build_fusion(zt, hot, top_n=top_n)
    sig = signature(zt, hot, fusion)

    state = load_state()
    seen = cls_seen_set(state)
    new_cls, new_fps = new_cls_rows(cls_df, seen)

    now_ts = time.time()
    last_sig = str(state.get("last_signature", "") or "")
    last_push = float(state.get("last_push_ts", 0.0) or 0.0)

    changed = (sig != last_sig) or bool(new_cls)
    if not changed:
        save_state(state)
        logging.info("榜单与电报无新内容，不推送")
        return

    elapsed = now_ts - last_push if last_push > 0 else min_push
    need_push = last_push <= 0
    if new_cls:
        need_push = need_push or (elapsed >= min_push_cls)
    else:
        need_push = need_push or (elapsed >= min_push)

    if not need_push:
        logging.info(
            "有变化但处于推送冷却: elapsed=%.0fs min=%ss(cls=%ss)",
            elapsed,
            min_push,
            min_push_cls,
        )
        save_state(state)
        return

    def _commit_cls_seen() -> None:
        for fp in new_fps:
            seen.add(fp)
        state["cls_seen"] = list(seen)
        trim_seen(state)

    leaders_payload = fusion_rows_to_dicts(fusion)
    cls_corpus = cls_corpus_for_llm(
        cls_df, max_items=corp_items, title_max=title_max, content_max=content_max
    )

    lines = [
        "### 热门龙头情报",
        f"> 日期 {shanghai_today()} 上海 {shanghai_now().strftime('%H:%M:%S')} | 涨停池约 {len(zt)} 只 | 飙升榜约 {len(hot)} 只",
        "",
        f"**融合 Top {top_n}（盘面）**",
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

    joint_md = ""
    if os.getenv("HC_DEEPSEEK_ENABLE", "0").strip() == "1":
        joint = analyze_integrated_cls_and_leaders(leaders_payload, cls_corpus)
        if joint:
            joint_md = format_integrated_markdown(joint)
        else:
            joint_md = (
                "\n### 财联社整合\n"
                "（DeepSeek 调用失败或未返回 JSON，请查日志；**本推送不含新闻列表**。）\n"
            )
    else:
        joint_md = (
            "\n### 财联社整合\n"
            "已拉取财联社语料用于下次分析；请设置 **`HC_DEEPSEEK_ENABLE=1`** 以生成「整合观点 + 方向与标的」。\n"
        )

    body = "\n".join(lines) + "\n" + joint_md
    body += "\n> 数据来源：AkShare / 东财 / 财联社；正文不列举电报原文；非投资建议。"

    ok = push_markdown(body)
    if ok:
        state["last_push_ts"] = now_ts
        state["last_signature"] = sig
        _commit_cls_seen()
        logging.info("推送成功")
    else:
        logging.warning("推送失败，不写入电报已读")

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

    poll = max(30, int(os.getenv("HC_POLL_INTERVAL_SEC", "90")))

    if args.loop:
        logging.info("进入循环 poll=%ss", poll)
        while True:
            try:
                if is_trading_time() or args.force:
                    run_cycle(force=args.force)
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
