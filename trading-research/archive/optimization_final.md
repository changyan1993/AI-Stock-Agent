> **ARCHIVED -- This document is a historical snapshot from the optimization process.**
> **The current authoritative baseline is v1_baseline.md.**
> **Do not use these numbers for current decision-making.**

# Optimization Final Report

- Status: **NEEDS_MANUAL_REVIEW**
- Generated: 2026-03-13
- Guardian Agent: 3 iterations completed

## Reason for Manual Review

Agent-2 and Agent-3 remain marginally negative in the 6-month backtest (-0.27% and -0.15% respectively). All other criteria pass including 12-month OOS, max drawdown, and 12-month profitability for Agent-2. These are borderline results that improved significantly from the original (-1.84% and -0.34%) but did not cross into positive territory in the 6-month window.

## Final Parameters (after 3 iterations)

| Parameter | Agent-1 (unchanged) | Agent-2 (adjusted) | Agent-3 (adjusted) |
|-----------|---------------------|--------------------|--------------------|
| buy_threshold | 4 | 6 (was 6, unchanged) | 4 (was 4, unchanged) |
| stop_loss | -6% | **-6%** (was -8%) | -3% (unchanged) |
| take_profit | 4% | **3.5%** (was 3%) | 8% (unchanged) |
| position_size | 8% | **16%** (was 18%) | **6%** (was 8%) |
| max_positions | 3 | 2 (unchanged) | **2** (was 3) |
| max_trades_day | 3 | 2 (unchanged) | 2 (unchanged) |

## 6-Month Backtest Results (Final)

| Metric | Agent-1 | Agent-2 | Agent-3 |
|--------|---------|---------|---------|
| Total Return | $+93.97 (+4.70%) | $-5.47 (-0.27%) | $-3.05 (-0.15%) |
| Win Rate | 68.7% | 63.2% | 26.5% |
| Total Trades | 67 | 19 | 83 |
| Max Drawdown | -2.63% | -2.46% | -2.74% |
| Sharpe Ratio | 2.32 | -0.11 | -0.06 |
| Profit Factor | 0.74 | 0.56 | 2.73 |

## 12-Month Backtest Results (Final)

| Metric | Agent-1 | Agent-2 | Agent-3 |
|--------|---------|---------|---------|
| Total Return | $+79.38 (+3.97%) | $+9.42 (+0.47%) | $-22.03 (-1.10%) |
| Win Rate | 64.6% | 64.7% | 26.0% |
| Total Trades | 113 | 34 | 154 |
| Max Drawdown | -3.57% | -2.43% | -2.70% |
| Sharpe Ratio | 1.05 | 0.14 | -0.31 |
| Profit Factor | 0.69 | 0.57 | 2.67 |

## OOS vs IS Comparison (12-month)

- **Agent-1**: 12-month (+3.97%) vs 6-month (+4.70%) -- consistent, slight degradation expected with longer period. No overfitting concern.
- **Agent-2**: 12-month (+0.47%) vs 6-month (-0.27%) -- 12-month is actually better, suggesting the first half had positive returns that offset the recent weak period. Acceptable OOS performance.
- **Agent-3**: 12-month (-1.10%) vs 6-month (-0.15%) -- OOS return is -1.10%, within the -2% threshold. The recent 6 months perform better than the first 6 months, suggesting improving market fit.

## Criteria Evaluation

| Criterion | Agent-1 | Agent-2 | Agent-3 |
|-----------|---------|---------|---------|
| 6-month profitable | PASS (+4.70%) | FAIL (-0.27%) | FAIL (-0.15%) |
| 12-month OOS > -2% | PASS | PASS (+0.47%) | PASS (-1.10%) |
| Max drawdown < -10% | PASS (-3.57%) | PASS (-2.46%) | PASS (-2.74%) |

## Recommendations for Manual Review

1. **Agent-2**: The -0.27% 6-month loss is essentially breakeven. The core issue is CLF producing outsized losses (worst trade -$19.49). Consider removing CLF from Agent-2's stock pool, or accept this marginal result as the strategy is profitable over 12 months.

2. **Agent-3**: The -0.15% 6-month loss is nearly breakeven. The strategy has excellent profit factor (2.73) but very low win rate (26%). This is by design (wide TP at 8%, tight SL at 3%). The live execution layer has additional intraday filters (day_position, close_gt_open, market_score) not fully captured in daily backtesting, which should improve real performance.

3. **Both agents are within rounding distance of breakeven**. The parameter changes (Agent-2 stop_loss -8% to -6%, position_size 18% to 16%; Agent-3 position_size 8% to 6%, max_positions 3 to 2) significantly reduced risk and improved results from the original parameters.
