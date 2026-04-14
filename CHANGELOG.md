# Changelog

## [0.2.0] - 2026-04-14

### Added

- 合并方案文档：[`docs/HOT_LEADER_SCHEME.md`](docs/HOT_LEADER_SCHEME.md)（仓库内可长期查阅）。
- **榜单快照指纹**（`snapshot.py`）：`last_snap_hash` 不变且无非重要电报时不推送；静默消化电报指纹。
- **财联社重要性门控**（`cls_gate.py`）：`HC_CLS_IMPORTANT_ONLY`（默认 1）+ 可配 `HC_CLS_KEYWORDS`；`HC_CLS_GATE_DISABLE=1` 关闭门控。
- **概念板块强弱摘要**（`sector_fetch.py`）：`stock_board_concept_spot_em` 供 DeepSeek 与推送「领头羊≠仅涨停」。
- **早盘/集合竞价**脚本：`auction_morning.py`（独立冷却 `last_auction_push_ts`），`timeutil` 增加集合竞价/开盘窗。
- **企业微信**：超长 markdown 按 UTF-8 字节自动分多段（沿用 `wechat.py`）。

### Changed

- 默认轮询 **`HC_POLL_INTERVAL_SEC=45`**（与 AB 对齐）。
- `state.json` 升级 **version 2**：`last_snap_hash`、`last_auction_push_ts`。
- DeepSeek 提示词增加 **概念板块摘要** 与龙头定义说明。

## [0.1.0] - 2026-04-14

- 首期：涨停池 + 飙升榜 + 财联社语料 + 分段微信 + GitHub 远端。
