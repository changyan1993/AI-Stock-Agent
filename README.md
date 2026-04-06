# AI-Stock-Agent

A multi-agent AI stock trading simulation system powered by Claude Code. Three autonomous agents run different trading strategies in parallel, competing against each other on paper trading with real-time market data.

## Overview

This project uses Claude Code's cron scheduling to run three independent trading agents, each with a distinct strategy. Agents fetch real-time quotes from Finnhub API every 10 minutes during US market hours (06:30-13:00 Pacific, Mon-Fri), execute trades based on technical analysis, and generate daily performance reports.

**Starting capital:** $2,000 per agent
**Market data:** Finnhub API (real-time quotes)
**Execution:** Paper trading (simulated orders with 0.05% slippage model)

## Architecture

```
AI-Stock-Agent/
├── stock-agent-1/     # Momentum + Technical Indicators
├── stock-agent-2/     # Conservative Mean-Reversion
├── stock-agent-3/     # Aggressive Momentum
└── trading-research/  # Backtesting, optimization & analytics
```

## The Three Agents

### Agent-1: Momentum (Technical Indicators)
- **Strategy:** Trend-following with RSI, MACD, and price action signals
- **Stock pool:** SOFI, WMT, INTC, NFLX, BABA, COIN, PLTR, SNAP, NIO, MARA, LCID, F, RIVN, PINS, T, OPEN
- **Risk profile:** Moderate — 8% position size, -6% stop-loss, +4% take-profit
- **Key features:** Market sentiment filter (green/red ratio), buy window 07:00-11:00, trailing stops

### Agent-2: Conservative (Oversold Bounce)
- **Strategy:** Buy deeply oversold stocks (RSI < 35, below SMA20) and wait for mean reversion
- **Stock pool:** PFE, VZ, CSCO, BAC, USB, KEY, KO, MO, GM, BMY, CMCSA, HPQ, DOW, NEM, CLF, AA
- **Risk profile:** Ultra-conservative — 18% position size (fewer but larger bets), -8% stop-loss, +3% take-profit, max 2 positions
- **Key features:** Strict entry (score >= 6), 15-day time stop, patience over frequency

### Agent-3: Aggressive (Chasing Momentum)
- **Strategy:** Chase strong intraday movers with quick entries and exits
- **Stock pool:** HOOD, SOUN, IONQ, DKNG, RBLX, AFRM, UPST, HIMS, JOBY, LUNR, CLSK, WULF, SKLZ, QUBT, RGTI, GRAB
- **Risk profile:** High risk/reward — 8% position size, -3% stop-loss (fast cut), +8% take-profit (let winners run)
- **Key features:** Regime gate (SPY/QQQ/VIX kill-switch), low win rate but high reward-to-risk ratio

## Technical Analysis (`analyze.js`)

Each agent has its own `analyze.js` script that scores stocks on a 0-10 scale using:
- **RSI** — Overbought/oversold levels
- **MACD** — Trend direction and crossovers
- **Price action** — Intraday position, range, momentum
- **News sentiment** — Bullish/bearish keyword analysis via Finnhub
- **Volume** — Unusual activity detection

## Backtesting & Optimization (`trading-research/`)

The research module validates strategies against 6 months of historical data before deployment:

- `backtest.py` — Full backtest engine for all three agent strategies with slippage modeling
- `optimize.py` — Parameter optimization (stop-loss, take-profit, position sizing)
- `holdout_validation.py` — Out-of-sample validation to prevent overfitting
- `walkforward_test.py` — Walk-forward analysis for robustness testing
- `daily_chart.py` — Multi-agent daily performance visualization

## How It Works

1. **Startup:** User says "start" in Claude Code — the agent reads `trading_state.json` and creates a cron job
2. **Every 10 min (market hours):** Cron triggers the full trading loop:
   - Fetch real-time quotes for all stocks in the pool
   - Assess market conditions (sentiment score / regime gate)
   - Check existing positions for stop-loss / take-profit / trailing stop
   - Run technical analysis and filter for buy signals
   - Execute trades and update state
3. **Market close:** Generate daily report and cross-agent performance summary
4. **Weekly (Friday):** Auto-run backtests with latest data

## State & Logging

Each agent maintains:
- `trading_state.json` — Current capital, positions, trade history, daily stats
- `trade_log.txt` — Full trade-by-trade log with entry/exit prices and reasons
- `daily_report.txt` — End-of-day P&L summaries
- `price_history.json` — Daily closing prices for trend analysis (Agent-1)

## Requirements

- [Claude Code](https://claude.com/claude-code) (CLI)
- Node.js (for `analyze.js`)
- Python 3 with `yfinance`, `pandas`, `numpy`, `matplotlib` (for backtesting)
- Finnhub API key (free tier)

## Disclaimer

This is a **paper trading simulation** for educational and research purposes only. No real money is involved. Past performance (backtested or simulated) does not guarantee future results. This is not financial advice.

## Live Paper Trading Results (as of 2026-04-05)

**Running since:** 2026-03-16 (3 weeks)

### Performance Summary

| Metric | Agent-1 Momentum | Agent-2 Conservative | Agent-3 Aggressive |
|--------|-------------------|----------------------|--------------------|
| **Capital** | $1,827.09 | $1,984.54 | $1,997.02 |
| **Total P/L** | -$48.91 (-2.45%) | -$15.46 (-0.77%) | -$2.98 (-0.15%) |
| **Trades** | 11 | 2 | 8 |
| **Win Rate** | 18.2% (2/11) | 50% (1/2) | 50% (4/8) |
| **Best Trade** | RIVN +$5.07 | CLF +$11.10 | HIMS +$11.12 |
| **Current Positions** | WMT 1 share | None | None |

**Combined:** $6,000 initial → $5,808.65 | **-$67.35 (-1.12%)**

### Latest Backtest (6-month, as of 2026-04-05)

| Metric | Agent-1 Momentum | Agent-2 Conservative | Agent-3 Aggressive |
|--------|-------------------|----------------------|--------------------|
| **Return** | -$4.59 (-0.23%) | +$62.28 (+3.11%) | -$40.28 (-2.01%) |
| **Win Rate** | 58.5% | 85.7% | 23.8% |
| **Sharpe Ratio** | -0.08 | 1.28 | -0.74 |
| **Max Drawdown** | -3.94% | -3.08% | -3.54% |
| **Profit Factor** | 0.98 | 2.09 | 0.83 |

**Best strategy by backtest:** Agent-2 Conservative (oversold bounce) — highest Sharpe, lowest drawdown, 85.7% win rate.

### Key Findings

1. **Agent-2's oversold bounce strategy dominates** in the current bearish environment — patient entries at RSI < 35 with wide stops produce the most consistent returns
2. **Agent-3's regime gate** (SPY/QQQ/VIX kill-switch) effectively prevents entries during market panic, preserving capital
3. **Market sentiment filters** across all agents successfully blocked trading on extreme red days (< 40% green stocks)
4. **Trailing stops** saved significant capital — multiple positions exited at breakeven instead of full stop-loss
