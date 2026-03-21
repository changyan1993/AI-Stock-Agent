# Improvement Log

## 2026-03-14: V1 -> V1.1 Updates

### 1. Friction Model (All Agents)
**What**: Added slippage of 0.05% per trade to all buy and sell operations.
**Why**: Real trading always has execution slippage (bid-ask spread, market impact). Zero-friction backtests overestimate returns. $0 commission matches modern brokers (Robinhood, Schwab, etc).
**Impact**:
- Agent-1: -$0.96 (negligible, 68 trades)
- Agent-2: -$3.34 (modest, 14 trades but larger position sizes)
- Agent-3: -$41.67 (significant, 86 trades + regime gate interaction)

### 2. Time Stop for Agent-2 (15 days max hold)
**What**: Force close any Agent-2 position held longer than 15 trading days.
**Why**: Agent-2's biggest problem was tail losses from holding too long (CLF -$29). The conservative "oversold bounce" strategy should bounce within 2 weeks or the thesis is wrong.
**Impact**:
- 2 time stops triggered in 6-month backtest
- Worst trade still CLF -$29.21 (that trade was stopped before 15 days by regular stop loss)
- Reduces average hold period and prevents long tail risk

### 3. Regime Gate for Agent-3
**What**: Market environment filter that blocks Agent-3 buys when SPY+QQQ down and VIX high. market_score <= -2 blocks all buys; market_score == -1 limits to 1 position.
**Why**: Agent-3 chases momentum in volatile stocks. During market-wide selloffs, momentum signals are unreliable -- stocks that look "strong" may be just temporarily bouncing. The gate prevents buying into falling markets.
**Impact**:
- Reduced total trades from ~94 to 86 (regime gate blocked some buys)
- Agent-3 IS return dropped from +$69.05 to +$27.38
- Holdout results also weakened significantly (-5.45% in Holdout-2)
- Note: The large drop is partially from friction and partially from regime gate. The gate may be too aggressive for Agent-3's strategy.

### 4. Expanded Metrics
**What**: Added expectancy, Calmar ratio, and monthly consistency to the analysis.
**Why**: These metrics provide a more complete picture of strategy quality:
- Expectancy: normalized expected value per trade (> 0 is good)
- Calmar ratio: return per unit of max drawdown (higher = better risk-adjusted return)
- Monthly consistency: percentage of profitable months (higher = more reliable)
**Impact**: No performance impact (reporting only).

### Summary Table

| Change | Agent-1 | Agent-2 | Agent-3 |
|--------|---------|---------|---------|
| Before (V1) | +$93.97 | +$38.61 | +$69.05 |
| After (V1.1) | +$93.01 | +$35.27 | +$27.38 |
| Net Impact | -$0.96 | -$3.34 | -$41.67 |
