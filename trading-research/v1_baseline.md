# V1.1 Baseline (FROZEN)

- Version: V1.1
- Freeze date: 2026-03-14
- Status: **V1.1 FROZEN — NO MORE PARAMETER CHANGES**
- Holdout: ALL VALIDATED

## Trust Levels for Paper Trading

| Agent | Role | Trust |
|-------|------|-------|
| Agent-1 | Primary (主观察对象) | HIGH — stable across all windows |
| Agent-2 | 待验证补充 (Needs Verification) | LOW — +$7.80 baseline but low sample count, need more trades to confirm |
| Agent-3 | Experimental supplement (实验型补充) | LOW — kill-switch regime gate, low WR high payoff |

## Frozen Parameters

| Parameter | Agent-1 (Momentum) | Agent-2 (Conservative) | Agent-3 (Aggressive) |
|-----------|--------------------|-----------------------|---------------------|
| buy_threshold | 4 | 6 | 4 |
| stop_loss | -6% | -8% | -3% |
| take_profit | +4% | +3% | +8% |
| position_size | 8% | 18% | 8% |
| max_positions | 3 | 2 | 3 |
| max_trades_day | 3 | 2 | 2 |
| market_sentiment | score addition | none | regime kill switch (<=−2 only) |
| time_stop | N/A | **15 trading days (~21 calendar days)** | N/A |
| friction | 0.05% | 0.05% | 0.05% |

### Friction Model
- Slippage: 0.05% per trade (SLIPPAGE = 0.0005)
- Commission: $0 (zero-commission broker)
- Buy: actual_buy_price = price * (1 + 0.0005)
- Sell: actual_sell_price = exit_price * (1 - 0.0005)
- Round-trip cost: ~0.1%

### Agent-2 Time Stop
- Max holding period: 15 trading days (~21 calendar days)
- If exceeded, force close at current price (with slippage)
- Purpose: prevent tail losses (e.g., CLF -$29 from holding too long)

### Agent-3 Regime Gate (Kill-Switch Only)
- market_score = SPY trend + QQQ trend + VIX level (range: roughly -4 to +3)
- market_score <= -2: SKIP all buys (market panic) — **ONLY restriction**
- market_score > -2: normal trading (no -1 restriction)
- Not a score modifier — purely a gate/filter on execution

## 6-Month Results (V1.1 with Friction)

| Metric | Agent-1 | Agent-2 | Agent-3 |
|--------|---------|---------|---------|
| P&L | +$92.99 (+4.65%) | +$7.80 (+0.39%) | +$29.97 (+1.50%) |
| Win Rate | 69.1% | 75.0% | 29.1% |
| Max Drawdown | -2.95% | -2.09% | -3.42% |
| Sharpe Ratio | 2.27 | 0.22 | 0.55 |
| Expectancy | 0.186 | 0.025 | 0.085 |
| Monthly Consistency | 71.4% (5/7) | 57.1% (4/7) | 71.4% (5/7) |

## Holdout Status: ALL VALIDATED

## Known Differences (Backtest vs Live)

1. **News sentiment**: Live only, not in backtest
2. **Intraday filters** (dp>1%, c>o, day_position>0.6): Live only
3. **Market sentiment score**: Agent-1 only (score addition)
4. **Regime gate**: Agent-3 only (kill switch at <= -2)
5. **Time stop**: Agent-2 only (15 day max hold)
6. **Friction**: All agents (0.05% slippage per trade)

## Paper Trading Plan (2-4 weeks)

### 跟踪指标
Track per agent:
- Signal count (how many BUY signals per day)
- Fill rate (signals acted on / total signals)
- SL/TP hit ratio
- Average hold time
- Live vs backtest deviation (return, WR, drawdown)

All three agents trade simultaneously. Agent-1 is primary observation target.

### 熔断规则 (Circuit Breaker)

**预警线 (Warning)**:
- 单周回撤 <= -4%：触发预警，加强监控，不自动暂停

**熔断线 (Hard Stop)**:
- 前两周累计回撤 <= -5%：立即暂停开新仓
- 已有持仓按原策略正常出场（止损/止盈/time stop），不强制砍仓
- 进入人工复核流程

**复核流程**:
1. 检查是否为单笔异常（如某只股票闪崩）
2. 检查市场 regime 是否突变（如黑天鹅事件）
3. 检查 live vs backtest 执行偏差是否异常
4. 复核后决定：恢复 / 降权继续观察 / 转入 V1.2 research track

### Agent-2 样本量观察触发器

- 如果 paper tracking 4 周后 Agent-2 总交易 < 5 笔：触发研究分支
- 研究顺序（作为 V1.2 research track，不修改 V1.1 baseline）：
  1. 评估 buy_threshold 从 6 降到 5 的影响
  2. 如信号仍不足，考虑扩充股票池
- 任何参数变更需重新走回测 + holdout 验证流程
