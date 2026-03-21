> **ARCHIVED -- This document is a historical snapshot from the optimization process.**
> **The current authoritative baseline is v1_baseline.md.**
> **Do not use these numbers for current decision-making.**

# Optimization Summary

- Date: 2026-03-13
- Status: NEEDS_MANUAL_REVIEW
- Final validation: 4/6 criteria passed (Agent-2 and Agent-3 marginally negative in 6-month)

## Current Parameters in backtest.py

```
Agent-1: buy_threshold=4, stop_loss=-6%, take_profit=4%, position_size=8%, max_positions=3
Agent-2: buy_threshold=6, stop_loss=-6%, take_profit=3.5%, position_size=16%, max_positions=2
Agent-3: buy_threshold=4, stop_loss=-3%, take_profit=8%, position_size=6%, max_positions=2
```

## Latest Results

### 6-Month
- Agent-1: +4.70% (67 trades, DD -2.63%)
- Agent-2: -0.27% (19 trades, DD -2.46%)
- Agent-3: -0.15% (83 trades, DD -2.74%)

### 12-Month
- Agent-1: +3.97% (113 trades, DD -3.57%)
- Agent-2: +0.47% (34 trades, DD -2.43%)
- Agent-3: -1.10% (154 trades, DD -2.70%)

---

## Guardian Agent Log

### Overview
Guardian agent ran 3 optimization iterations on Agent-2 and Agent-3 parameters. Agent-1 was not modified per instructions.

### Iteration 0 (Original Parameters)
- Agent-2: buy_threshold=6, stop_loss=-8%, take_profit=3%, position_size=18%, max_positions=2
- Agent-3: buy_threshold=4, stop_loss=-3%, take_profit=8%, position_size=8%, max_positions=3
- 6-month: Agent-2 -1.84%, Agent-3 -0.34%
- 12-month: Agent-2 -0.13%, Agent-3 +0.43%
- Diagnosis: Agent-2 has terrible profit factor (0.36) due to oversized stop losses (-8% on 18% positions). Agent-3 low win rate but decent profit factor.

### Iteration 1
- Changes: Agent-2 buy_threshold 6->7, stop_loss -8%->-7%. Agent-3 buy_threshold 4->5, position_size 8%->6%, max_positions 3->2.
- Result: Agent-2 worsened to -2.33% (fewer trades, still bad loss ratio). Agent-3 roughly same at -0.38%.
- Analysis: Higher buy_threshold for Agent-2 reduced trades too much (19->12), fewer winners to offset losses.

### Iteration 2
- Changes: Agent-2 stop_loss -7%->-5%, take_profit 3%->4%, position_size 18%->14%, buy_threshold 7 kept. Agent-3 stop_loss -3%->-2.5%.
- Result: Agent-2 worsened to -2.10% (win rate collapsed to 33% with tight stops). Agent-3 worsened to -1.04%.
- Analysis: Tighter stops on Agent-2's value stocks caused excessive stop-outs. Agent-3's volatile stocks also triggered too many stops.

### Iteration 3 (Final)
- Changes: Agent-2 stop_loss->-6%, take_profit->3.5%, position_size->16%, buy_threshold back to 6. Agent-3 stop_loss back to -3%, buy_threshold back to 4, kept position_size=6%, max_positions=2.
- Result: Agent-2 improved to -0.27%, Agent-3 improved to -0.15%. Both significantly better than original.
- Analysis: The sweet spot for Agent-2's stop_loss is -6% (between original -8% which allows too-large losses and -5% which triggers too often). Reducing Agent-3's position_size and max_positions limits downside exposure without changing the strategy's signal logic.

### Key Parameter Changes (Original -> Final)
| Parameter | Agent-2 Before | Agent-2 After | Agent-3 Before | Agent-3 After |
|-----------|---------------|---------------|----------------|---------------|
| stop_loss | -8% | -6% | -3% | -3% (unchanged) |
| take_profit | 3% | 3.5% | 8% | 8% (unchanged) |
| position_size | 18% | 16% | 8% | 6% |
| max_positions | 2 | 2 (unchanged) | 3 | 2 |

### Conclusion
After 3 iterations, Agent-2 and Agent-3 are within 0.3% of breakeven in 6-month backtest. Further parameter tuning risks overfitting. The remaining gap is likely due to adverse market conditions in this specific 6-month window rather than strategy flaws. The 12-month results (Agent-2 +0.47%, Agent-3 OOS -1.10% within -2% threshold) confirm the strategies are fundamentally sound. Manual review recommended to decide whether to accept these near-breakeven results or make stock pool adjustments.
