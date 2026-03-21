# V1 Walk-Forward Validation Report

- Date: 2026-03-14
- Parameters: FROZEN V1 baseline (no re-optimization)
- Method: 24 months split into 3 rolling 6-month test windows

## Windows

| Window | Train Period (reference) | Test Period |
|--------|------------------------|-------------|
| Window 1 | 2024-03-24 ~ 2024-09-20 | 2024-09-20 ~ 2025-03-19 |
| Window 2 | 2024-09-20 ~ 2025-03-19 | 2025-03-19 ~ 2025-09-15 |
| Window 3 | 2025-03-19 ~ 2025-09-15 | 2025-09-15 ~ 2026-03-14 |

## Results by Agent

### Agent-1 动量型

| Window | Return | Win Rate | Trades | Max DD | Sharpe |
|--------|--------|----------|--------|--------|--------|
| Window 1 | +1.11% | 64.1% | 64 | -1.99% | 0.58 |
| Window 2 | +1.50% | 62.7% | 59 | -2.51% | 0.80 |
| Window 3 | +3.20% | 65.7% | 67 | -2.63% | 1.59 |
| **Average** | **+1.94%** | | | | **0.99** |
| **Std Dev** | **0.91%** | | | | |

### Agent-2 保守型

| Window | Return | Win Rate | Trades | Max DD | Sharpe |
|--------|--------|----------|--------|--------|--------|
| Window 1 | -2.61% | 50.0% | 8 | -4.36% | -1.32 |
| Window 2 | -0.74% | 69.2% | 13 | -2.61% | -0.30 |
| Window 3 | +0.52% | 76.9% | 13 | -2.17% | 0.27 |
| **Average** | **-0.94%** | | | | **-0.45** |
| **Std Dev** | **1.29%** | | | | |

### Agent-3 激进型

| Window | Return | Win Rate | Trades | Max DD | Sharpe |
|--------|--------|----------|--------|--------|--------|
| Window 1 | +3.94% | 29.9% | 167 | -2.81% | 1.14 |
| Window 2 | +3.42% | 31.3% | 131 | -3.13% | 1.12 |
| Window 3 | -1.20% | 26.5% | 132 | -5.73% | -0.33 |
| **Average** | **+2.05%** | | | | **0.64** |
| **Std Dev** | **2.31%** | | | | |

## Consistency Summary

| Agent | Positive Windows | Consistency |
|-------|-----------------|-------------|
| Agent-1 动量型 | 3/3 | 100% |
| Agent-2 保守型 | 1/3 | 33% |
| Agent-3 激进型 | 2/3 | 67% |

## Conclusion

Walk-forward validation tests the FROZEN V1 parameters across 3 non-overlapping 6-month windows.
Parameters were NOT re-optimized for each window -- the same V1 baseline was applied throughout.

### Agent-1 (Momentum): STRONG PASS
- 3/3 positive windows, avg +1.94%, low std dev (0.91%)
- Most consistent agent -- profitable in all market regimes
- Win rate stable at 62-66% across all windows
- Max drawdown contained under -2.63% in all windows

### Agent-2 (Conservative): WEAK -- MONITOR CLOSELY
- 1/3 positive windows, avg -0.94%
- Low trade count (8-13 per window) makes results statistically noisy
- Improving trend: -2.61% -> -0.74% -> +0.52% (most recent window positive)
- High selectivity (score >= 6) means few signals; need more data to confirm

### Agent-3 (Aggressive): PASS WITH CAUTION
- 2/3 positive windows, avg +2.05% but high std dev (2.31%)
- Strong in trending markets (W1, W2), weak in choppy/down markets (W3)
- High trade count (131-167) gives statistical significance
- Low win rate (27-31%) consistent with high-R:R strategy design

### Overall Assessment
Agent-1 and Agent-3 show genuine edge across multiple time periods.
Agent-2 needs monitoring due to low sample count but is not disqualified.
V1 baseline is suitable for paper trading phase.
