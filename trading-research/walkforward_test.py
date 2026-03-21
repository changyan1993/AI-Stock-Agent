"""
V1 Walk-Forward Validation
Uses FROZEN V1 parameters (no re-optimization).
Splits 24 months into 3 rolling windows, tests on each.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import (
    AGENT_STOCKS, AGENT_CONFIGS, INITIAL_CAPITAL,
    prepare_indicators, analyze_results,
    download_market_data, calc_market_score,
    agent1_score, agent2_score, agent3_score
)
from holdout_validation import download_data_range, download_market_range, run_backtest_range

def main():
    now = datetime.now()

    # 3 rolling windows (train period listed for reference, we only TEST)
    windows = [
        {
            'name': 'Window 1',
            'train': f'{(now - timedelta(days=720)).strftime("%Y-%m-%d")} ~ {(now - timedelta(days=540)).strftime("%Y-%m-%d")}',
            'test_start': now - timedelta(days=540),
            'test_end': now - timedelta(days=360),
            'test_label': f'{(now - timedelta(days=540)).strftime("%Y-%m-%d")} ~ {(now - timedelta(days=360)).strftime("%Y-%m-%d")}',
        },
        {
            'name': 'Window 2',
            'train': f'{(now - timedelta(days=540)).strftime("%Y-%m-%d")} ~ {(now - timedelta(days=360)).strftime("%Y-%m-%d")}',
            'test_start': now - timedelta(days=360),
            'test_end': now - timedelta(days=180),
            'test_label': f'{(now - timedelta(days=360)).strftime("%Y-%m-%d")} ~ {(now - timedelta(days=180)).strftime("%Y-%m-%d")}',
        },
        {
            'name': 'Window 3',
            'train': f'{(now - timedelta(days=360)).strftime("%Y-%m-%d")} ~ {(now - timedelta(days=180)).strftime("%Y-%m-%d")}',
            'test_start': now - timedelta(days=180),
            'test_end': now,
            'test_label': f'{(now - timedelta(days=180)).strftime("%Y-%m-%d")} ~ {now.strftime("%Y-%m-%d")}',
        },
    ]

    print(f"\n{'='*70}")
    print(f"  V1 Walk-Forward Validation (FROZEN parameters)")
    print(f"  Date: {now.strftime('%Y-%m-%d')}")
    print(f"{'='*70}")

    all_results = {}

    for w in windows:
        print(f"\n{'='*70}")
        print(f"  {w['name']}")
        print(f"  Train (reference): {w['train']}")
        print(f"  Test: {w['test_label']}")
        print(f"{'='*70}")

        window_stats = {}
        for agent_id in [1, 2, 3]:
            config = AGENT_CONFIGS[agent_id]
            tickers = AGENT_STOCKS[agent_id]
            print(f"\n  {config['name']}...")

            stock_data = download_data_range(tickers, w['test_start'], w['test_end'])
            market_data = download_market_range(w['test_start'], w['test_end']) if agent_id == 1 else None

            if not stock_data:
                print(f"  No data, skipping")
                continue

            result = run_backtest_range(agent_id, stock_data, w['test_start'], w['test_end'], market_data)
            stats = analyze_results(result)
            window_stats[agent_id] = stats

            print(f"    P&L: ${stats['total_profit']:+.2f} ({stats['return_pct']:+.2f}%)")
            print(f"    Win: {stats['win_rate']}% | Trades: {stats['total_trades']} | DD: {stats['max_drawdown']:.2f}% | Sharpe: {stats['sharpe_ratio']:.2f}")

        all_results[w['name']] = {'meta': w, 'stats': window_stats}

    # Summary
    print(f"\n\n{'='*70}")
    print(f"  Walk-Forward Summary")
    print(f"{'='*70}")

    for agent_id in [1, 2, 3]:
        name = AGENT_CONFIGS[agent_id]['name']
        print(f"\n  {name}:")
        print(f"  {'Window':<12} | {'Return':>10} | {'Win%':>8} | {'Trades':>6} | {'MaxDD':>8} | {'Sharpe':>6}")
        print(f"  {'-'*12}-+-{'-'*10}-+-{'-'*8}-+-{'-'*6}-+-{'-'*8}-+-{'-'*6}")

        returns = []
        for wname, wdata in all_results.items():
            if agent_id in wdata['stats']:
                s = wdata['stats'][agent_id]
                print(f"  {wname:<12} | {s['return_pct']:>+9.2f}% | {s['win_rate']:>7.1f}% | {s['total_trades']:>6} | {s['max_drawdown']:>7.2f}% | {s['sharpe_ratio']:>6.2f}")
                returns.append(s['return_pct'])

        if returns:
            avg_ret = np.mean(returns)
            std_ret = np.std(returns) if len(returns) > 1 else 0
            print(f"  {'Avg':.<12} | {avg_ret:>+9.2f}% | {'':>8} | {'':>6} | {'':>8} | {'':>6}")
            print(f"  {'Std':.<12} | {std_ret:>9.2f}% | {'':>8} | {'':>6} | {'':>8} | {'':>6}")

    # Consistency check
    print(f"\n  Consistency Check:")
    for agent_id in [1, 2, 3]:
        name = AGENT_CONFIGS[agent_id]['name']
        returns = []
        for wdata in all_results.values():
            if agent_id in wdata['stats']:
                returns.append(wdata['stats'][agent_id]['return_pct'])
        positive = sum(1 for r in returns if r > 0)
        total = len(returns)
        consistency = positive / total * 100 if total > 0 else 0
        print(f"    {name}: {positive}/{total} positive windows ({consistency:.0f}%)")

    # Write report
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'walkforward_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# V1 Walk-Forward Validation Report\n\n")
        f.write(f"- Date: {now.strftime('%Y-%m-%d')}\n")
        f.write(f"- Parameters: FROZEN V1 baseline (no re-optimization)\n")
        f.write(f"- Method: 24 months split into 3 rolling 6-month test windows\n\n")

        f.write(f"## Windows\n\n")
        f.write(f"| Window | Train Period (reference) | Test Period |\n")
        f.write(f"|--------|------------------------|-------------|\n")
        for w in windows:
            f.write(f"| {w['name']} | {w['train']} | {w['test_label']} |\n")

        f.write(f"\n## Results by Agent\n\n")
        for agent_id in [1, 2, 3]:
            name = AGENT_CONFIGS[agent_id]['name']
            f.write(f"### {name}\n\n")
            f.write(f"| Window | Return | Win Rate | Trades | Max DD | Sharpe |\n")
            f.write(f"|--------|--------|----------|--------|--------|--------|\n")

            returns = []
            sharpes = []
            for wname, wdata in all_results.items():
                if agent_id in wdata['stats']:
                    s = wdata['stats'][agent_id]
                    f.write(f"| {wname} | {s['return_pct']:+.2f}% | {s['win_rate']:.1f}% | {s['total_trades']} | {s['max_drawdown']:.2f}% | {s['sharpe_ratio']:.2f} |\n")
                    returns.append(s['return_pct'])
                    sharpes.append(s['sharpe_ratio'])

            if returns:
                avg_ret = np.mean(returns)
                std_ret = np.std(returns) if len(returns) > 1 else 0
                avg_sharpe = np.mean(sharpes)
                f.write(f"| **Average** | **{avg_ret:+.2f}%** | | | | **{avg_sharpe:.2f}** |\n")
                f.write(f"| **Std Dev** | **{std_ret:.2f}%** | | | | |\n")
            f.write(f"\n")

        f.write(f"## Consistency Summary\n\n")
        f.write(f"| Agent | Positive Windows | Consistency |\n")
        f.write(f"|-------|-----------------|-------------|\n")
        for agent_id in [1, 2, 3]:
            name = AGENT_CONFIGS[agent_id]['name']
            returns = []
            for wdata in all_results.values():
                if agent_id in wdata['stats']:
                    returns.append(wdata['stats'][agent_id]['return_pct'])
            positive = sum(1 for r in returns if r > 0)
            total = len(returns)
            consistency = positive / total * 100 if total > 0 else 0
            f.write(f"| {name} | {positive}/{total} | {consistency:.0f}% |\n")

        f.write(f"\n## Conclusion\n\n")
        f.write(f"Walk-forward validation tests the FROZEN V1 parameters across 3 non-overlapping 6-month windows.\n")
        f.write(f"Parameters were NOT re-optimized for each window -- the same V1 baseline was applied throughout.\n")
        f.write(f"This tests whether the strategy generalizes beyond the original in-sample period.\n")

    print(f"\n  Report saved: {report_path}")


if __name__ == '__main__':
    main()
