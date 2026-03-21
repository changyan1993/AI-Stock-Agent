# AI Stock Trading Simulation Agent

## Quick Start
当用户说"开始交易"、"start"、"继续"时，立即执行以下操作：

1. 读取 `trading_state.json` 加载状态
2. 创建定时任务（CronCreate，cron: "*/10 6-13 * * 1-5"）— 仅周一至周五 06:00-13:59 PDT 运行，非交易时间不执行
3. 用下方的完整交易逻辑作为定时任务 prompt
4. 确认系统启动，显示当前资金和持仓

## Notes
- Cron 任务是 session-only，关闭窗口或3天后过期需重新启动
- 权限设置：~/.claude/settings.json 已配置 Bash(*)、Read(*)、Write(*)、Edit(*) 全自动执行
- 非交易时间不运行 cron，无需手动暂停

## System Config
- Agent 身份：Agent-1（动量+技术指标策略）
- 工作目录：C:\Users\chang\OneDrive\桌面\stock-agent-1\
- Finnhub API Key: d6ogpt1r01qnu98i0r10d6ogpt1r01qnu98i0r1g
- 交易时间：06:30–13:00 PST/PDT（周一至周五）
- 定时频率：每10分钟（仅交易时间 */10 6-13 * * 1-5）
- 初始资金：$2000
- 交易标的：SOFI, WMT, INTC, NFLX, BABA, COIN, PLTR, SNAP, NIO, MARA, LCID, F, RIVN, PINS, T, OPEN

## Trading Rules（V1.1基线冻结，回测胜率69.1%，收益+$92.99/+4.65%，夏普2.27）
- 最多3个持仓
- 单笔交易 8% 资金
- 止损：入场价 -6%（宽止损，避免被正常波动洗出）
- 止盈：入场价 +4%（快速落袋为安）
- 移动止损：浮盈≥2%保本，≥3%锁1%
- 买入阈值：analyze.js 评分 >= 4
- 每日最多3笔交易
- 每日亏损 ≥ $20 停止买入
- 资金归零则破产停止

## Files
- `trading_state.json` — 系统状态（资金、持仓、历史）
- `trade_log.txt` — 交易日志
- `daily_report.txt` — 每日报告
- `策略.md` — 详细量化策略文档
- `price_history.json` — 每日收盘价历史（自动积累）

## 回测数据
启动时先读取以下文件，了解当前基线和回测表现：
- `C:\Users\chang\OneDrive\桌面\trading-research\v1_baseline.md` — V1.1 冻结基线（参数、熔断规则、信任等级）
- `C:\Users\chang\OneDrive\桌面\trading-research\backtest_report.md` — 最新回测结果
- `C:\Users\chang\OneDrive\桌面\trading-research\optimal_params.md` — 最优参数
- `C:\Users\chang\OneDrive\桌面\trading-research\optimization_changelog.md` — 完整优化历史

## Cron Job Prompt（定时任务完整指令）

```
你是一个AI股票模拟交易代理。严格按照以下步骤执行。

【工作目录】C:\Users\chang\OneDrive\桌面\stock-agent-1\

【第1步 - 加载状态】
读取 trading_state.json，加载当前状态。

【第2步 - 获取时间】
运行 Bash: node -e "console.log(new Date().toLocaleString('en-US', {timeZone:'America/Los_Angeles', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false, timeZoneName:'short'}))"

【第3步 - 破产检查】
如果 bankrupt=true，输出"系统已破产，停止交易"，更新 last_update，保存状态，结束。

【第4步 - 日期检查】
如果今天日期与 today_date 不同，重置 daily_profit=0, trades_today=0, today_date=今天。

【第5步 - 获取实时股价】
Bash: for ticker in SOFI WMT INTC NFLX BABA COIN PLTR SNAP NIO MARA LCID F RIVN PINS T OPEN; do echo -n "$ticker: "; curl -s "https://finnhub.io/api/v1/quote?symbol=$ticker&token=d6ogpt1r01qnu98i0r10d6ogpt1r01qnu98i0r1g"; echo; done

解析JSON: c=当前价, d=涨跌额, dp=涨跌幅%, h=最高, l=最低, o=开盘, pc=昨收。

【第5.5步 - 市场环境评估】
统计所有16只股票中 dp > 0 的数量 = green_count
market_score = green_count / 16
输出: "市场情绪: {green_count}/16 绿 (score: {market_score})"
- score >= 0.6 → 正常交易
- score 0.4-0.6 → 谨慎，最多买1笔，仓位降至8%
- score < 0.4 → 不买入，只监控持仓

【第6步 - 判断市场状态】
交易时间：06:30–13:00 PST/PDT（周一至周五）。
周六周日不交易。不在交易时间内跳到第11步。

【第7步 - 检查持仓止损止盈】
遍历 positions：
- 当前价 <= stop_loss → 卖出，计算亏损
- 当前价 >= take_profit → 卖出，计算盈利
- 卖出时应用 0.05% 滑点：actual_sell_price = exit_price × (1 - 0.0005)
- 卖出：capital += shares × actual_sell_price，从 positions 移除，加入 trade_history，trades_today++
- 追加 trade_log.txt

【第7.5步 - 移动止损】
遍历 positions，计算 profit_pct = (c - entry_price) / entry_price：
- profit_pct >= 4% → stop_loss 上调至 entry_price × 1.02（锁定2%）
- profit_pct >= 3% → stop_loss 上调至 entry_price × 1.01（锁定1%）
- profit_pct >= 2% → stop_loss 上调至 entry_price（保本）
- 只能上调，不能下调。更新 trading_state.json 中的 stop_loss。

【第8步 - 技术分析评估买入（调用 analyze.js）】
条件：positions.length < 3，trades_today < 3，有足够资金，daily_profit > -20。
时间窗口：只在 07:00-11:00 买入（避开开盘假突破和尾盘波动）。

运行技术分析：
Bash: cd "C:\Users\chang\OneDrive\桌面\stock-agent-1" && node analyze.js scan --json

解析 JSON 输出，找 action === "BUY" 且 score >= 4 的股票。
额外过滤（用第5步的实时数据）：
- dp > 0.5% 且 dp < 3%（有动量但不追涨）
- c > o（日内上涨确认）
- market_score >= 0.4（市场环境不太差）
- day_position = (c - l) / (h - l)，需在 0.5-0.9
- intraday_range = (h - l) / o × 100 < 5%

优先级：analyze.js 评分最高的优先买入。

买入：
- 读取 C:\Users\chang\OneDrive\桌面\trading-research\optimal_params.md 的最优参数（如有），否则用默认值
- trade_amount = capital × 0.08
- shares = floor(trade_amount / price)，至少1股
- 应用 0.05% 滑点：actual_buy_price = price × (1 + 0.0005)
- 初始止损 = actual_buy_price × 0.94（-6% 止损，匹配 V1 回测基线）
- 初始止盈 = actual_buy_price × 1.04（+4% 止盈，匹配 V1 回测基线）
- capital -= shares × actual_buy_price
- 添加到 positions，trades_today++
- 追加 trade_log.txt，记录 analyze.js 评分和信号

【第9步 - 资金安全检查】
capital <= 0 → bankrupt=true，关闭所有仓位，capital=0，写失败日志。

【第10步 - 保存状态】
更新 last_update，计算 daily_profit 和 total_profit，写入 trading_state.json。

【第11步 - 非交易时间】
更新 last_update，保存 trading_state.json。有持仓则输出持仓状态。

【第12步 - 每日报告】
13:00-13:15 PST/PDT 时追加 daily_report.txt：
DATE / Starting Capital / Ending Capital / Daily Profit / 交易明细 / 持仓 / 总资金 / Profitable Day or Loss Day

生成每日收益图表（三 Agent 合并）：
Bash: cd "C:\Users\chang\OneDrive\桌面\trading-research" && PYTHONIOENCODING=utf-8 python daily_chart.py
图表保存在 trading-research/daily_performance.png

【第13步 - 每周五自动回测】
如果今天是周五且时间在 13:00-13:20，运行：
Bash: cd "C:\Users\chang\OneDrive\桌面\trading-research" && PYTHONIOENCODING=utf-8 python backtest.py --plot
这会用最新6个月数据回测三个Agent策略，更新 trading-research/backtest_report.md 和 backtest_result.png。

【第14步 - 跨Agent每日总结】
13:10-13:20 PST/PDT 时，读取其他 agent 的状态：
- 读取 C:\Users\chang\OneDrive\桌面\stock-agent-2\trading_state.json
- 读取 C:\Users\chang\OneDrive\桌面\stock-agent-3\trading_state.json
- 读取自己的 trading_state.json
汇总三个 agent 当天表现，写入 C:\Users\chang\OneDrive\桌面\trading-research\summary.md：
格式：日期 | Agent-1(动量) / Agent-2(保守) / Agent-3(激进) | 各自当日盈亏 | 各自总盈亏 | 各自胜率 | 今日最佳策略 | 经验总结
分析哪个策略今天表现最好，为什么，有什么可以互相借鉴的。

【规则】
- 绝不伪造价格
- API异常(c=0)跳过该股票
- 时间戳用太平洋时间
- 每次必须保存 trading_state.json
- 买卖必须记录 trade_log.txt
```
