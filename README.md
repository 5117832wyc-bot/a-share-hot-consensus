# a-share-hot-consensus

**版本**：`0.2.1`（见 `hot_consensus/__init__.py`、`CHANGELOG.md`，Git 打 tag **`v0.2.1`**）

独立于 [ab-stock-quant](../ab-stock-quant) 的 A 股「热门龙头 / 共识情报」：**龙头含板块领头羊（未必涨停）**；涨停池 + 飙升榜 + 概念板块强弱 + 财联社（仅作语料，**推送不逐条列新闻**）。

## 方案文档（随仓库发布）

完整合并方案见：**[docs/HOT_LEADER_SCHEME.md](docs/HOT_LEADER_SCHEME.md)**（盘中去重、电报门控、集合竞价早盘、与 AB 边界等）。

## 环境

```bash
cd /root/code/a-share-hot-consensus
cp .env.example .env
pip install -r requirements.txt
```

## 运行

```bash
# 单轮（交易时段内有效；测试加 --force）
python monitor.py --once --force

# 持续循环（默认 45s 与 AB 对齐）
python monitor.py --loop

# 午休中下午开盘前跑一次「热门龙头情报」（须在上海 12:25–12:50；与盘中同一套快照/电报/digest 触发逻辑）
python monitor.py --once --scheduled
```

**集合竞价 / 早盘预案**（独立冷却，与盘中分流）：

```bash
python auction_morning.py --force   # 测一次
# 生产：cron 在 9:25、9:31、9:35 等调用；或 HC_AUCTION_SLOT=any
```

**是否盘中实时**：与选股一样为 **HTTP 轮询**；默认 **`HC_POLL_INTERVAL_SEC=45`**；需常驻请 **`--loop`** 或 cron。若采用 **「9:25 `auction_morning.py` 预案 + 12:30 `monitor.py --scheduled` 情报」**：预案与情报**分流**；情报侧 **`--scheduled`** 仅在 **12:25–12:50（上海）** 生效，触发条件与盘中一致：**快照变化**、**重要电报**、或**当日尚未记过的下午盘前 digest**（见 `monitor.py`）。示例见 **`deploy/crontab.example`**。

**企业微信**：单条约 **4096 字节（UTF-8）**；超长 **自动分多段**（`HC_WECHAT_CHUNK_DELAY_SEC`）。

## 环境变量摘要

| 变量 | 说明 |
|------|------|
| `HC_TRADING_CAL_DISABLE` | 默认 **0**：用 AkShare 新浪历区分**法定节假日休市**；`1` 时退回仅周一至周五 |
| `HC_TRADING_CAL_CACHE` | 可选：交易日 JSON 缓存路径（默认项目根 `.cache/cn_sse_trade_dates.json`） |
| `HC_POLL_INTERVAL_SEC` | 默认 **45**（与 AB 一致） |
| `HC_CLS_IMPORTANT_ONLY` | 默认 **1**：仅「重要电报」可单独触发推送（关键词可配 `HC_CLS_KEYWORDS`） |
| `HC_CLS_GATE_DISABLE` | `1` 关闭门控（调试用） |
| `HC_SECTOR_ENABLE` | 默认 `1`：拉概念板块强弱摘要 |
| `HC_DEEPSEEK_ENABLE` / `DEEPSEEK_API_KEY` | 财联社整合 + 方向与标的 |
| `HC_AUCTION_MIN_INTERVAL_SEC` | 早盘推送最小间隔，默认 600 |

详见 `.env.example`。

## 其他脚本

```bash
python lhb_digest.py   # 盘后龙虎榜简报
```

## GitHub

远端：<https://github.com/5117832wyc-bot/a-share-hot-consensus>

```bash
git pull
git tag -l 'v*'
```

密钥勿提交；`.env` 仅本机。
