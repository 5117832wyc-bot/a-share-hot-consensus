# a-share-hot-consensus

独立于 [ab-stock-quant](../ab-stock-quant) 的 A 股「热门龙头 / 共识情报」监控：涨停池 + 东财飙升榜 + 财联社电报，融合打分后推送企业微信。

每条龙头带 **盘面快照**（连板、封板资金、炸板、行业、人气名次等规则层说明）；财联社除 **本批新增** 外附 **近期标题脉络**；若开启 `HC_DEEPSEEK_ENABLE=1`，由 DeepSeek 做 **电报解读、与榜单联动、逐只龙头结合新闻的判断**（不编造行情数字）。

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

环境变量要点：

| 变量 | 说明 |
|------|------|
| `HC_WECHAT_WEBHOOK` | 优先于 `WECHAT_WEBHOOK` |
| `HC_POLL_INTERVAL_SEC` | 循环间隔，默认 90 |
| `HC_MIN_PUSH_INTERVAL_SEC` | 榜单变化推送最小间隔，默认 300 |
| `HC_MIN_PUSH_ON_CLS_SEC` | 有新电报时最小间隔，默认 120 |
| `HC_TOP_N` | 融合榜条数，默认 15 |
| `HC_DEEPSEEK_ENABLE` | 1 则对新电报标题调 DeepSeek |
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
