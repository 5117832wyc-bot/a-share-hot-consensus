# a-share-hot-consensus

独立于 [ab-stock-quant](../ab-stock-quant) 的 A 股「热门龙头 / 共识情报」监控：涨停池 + 东财飙升榜 + 财联社电报，融合打分后推送企业微信。

每条龙头带 **盘面快照**（连板、封板资金、炸板、行业、人气名次等）。财联社 **不在推送里逐条列举**，只把近期电报 **标题+正文截断** 作为模型语料；若 `HC_DEEPSEEK_ENABLE=1`，输出 **整合观点 + 可能走强方向 + 关注标的（含依据：盘面共振/新闻叙事/榜单交集等）**，并与 Top 榜单做 **共振说明**。

## 环境

```bash
cd /root/code/a-share-hot-consensus
cp .env.example .env
# 编辑 .env：WECHAT_WEBHOOK 或 HC_WECHAT_WEBHOOK
pip install -r requirements.txt
```

## 运行

```bash
# 单轮（交易时段内有效；测试加 --force）
python monitor.py --once --force

# 持续循环（建议 systemd / nohup）
python monitor.py --loop
```

**是否「像选股一样盘中实时」**：本程序与 ab-stock-quant 的盘中监控 **一样属于 HTTP 轮询、定时拉数**，不是交易所逐笔级「实时」。默认 `HC_POLL_INTERVAL_SEC=90` 一轮（可改）；需 **长期跑** 请用 `--loop` 或 crontab，否则只执行你手动/cron 的那一次。选股侧是 `intraday_monitor_ab_shape.py` 等 **另一进程**，二者互不影响。

**企业微信**：单条 markdown 有 **约 4096 字节**上限；正文超长时会 **自动拆成多段**依次发送（每段带「第 i/n 段」），无需手剪。可调 `HC_WECHAT_CHUNK_DELAY_SEC` 控制段间间隔。

环境变量要点：

| 变量 | 说明 |
|------|------|
| `HC_WECHAT_WEBHOOK` | 优先于 `WECHAT_WEBHOOK` |
| `HC_POLL_INTERVAL_SEC` | 循环间隔，默认 90 |
| `HC_MIN_PUSH_INTERVAL_SEC` | 榜单变化推送最小间隔，默认 300 |
| `HC_MIN_PUSH_ON_CLS_SEC` | 有新电报时最小间隔，默认 120 |
| `HC_TOP_N` | 融合榜条数，默认 15 |
| `HC_CLS_CORPUS_ITEMS` | 财联社喂给模型的最近条数，默认 45 |
| `HC_DEEPSEEK_ENABLE` | 1：财联社整合 + 方向与标的（推送不列新闻） |
| `DEEPSEEK_API_KEY` | 与 ab-stock-quant 可共用 |

盘后龙虎榜简报：

```bash
python lhb_digest.py
```

## GitHub

远端仓库：<https://github.com/5117832wyc-bot/a-share-hot-consensus>

```bash
git clone https://github.com/5117832wyc-bot/a-share-hot-consensus.git
# 或 SSH：git@github.com:5117832wyc-bot/a-share-hot-consensus.git
```

本地已配置 `origin` 时，更新代码后：

```bash
git push -u origin main
```

密钥勿入库；`.env` 仅放本机。
