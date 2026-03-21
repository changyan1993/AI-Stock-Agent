"""
参数优化器 - 自动找到最优策略参数
测试不同的止损、止盈、买入阈值、仓位大小组合
"""

import sys
import os
import itertools
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# 复用 backtest.py 的核心函数
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest import (
    AGENT_STOCKS, INITIAL_CAPITAL, download_data, prepare_indicators,
    agent1_score, agent2_score, agent3_score, calc_rsi, calc_macd, calc_atr,
    calc_volume_ratio, AGENT_CONFIGS
)

def run_backtest_with_params(agent_id, stock_data, params, months=6):
    """用指定参数跑回测"""
    score_fn = {1: agent1_score, 2: agent2_score, 3: agent3_score}[agent_id]

    capital = INITIAL_CAPITAL
    positions = []
    wins = 0
    losses = 0
    total_profit = 0
    peak_capital = INITIAL_CAPITAL
    max_drawdown = 0
    trades_today = 0
    current_date = None
    trade_count = 0

    prepared_data = {}
    all_dates = set()
    for ticker, df in stock_data.items():
        df_prep = prepare_indicators(df)
        prepared_data[ticker] = df_prep
        all_dates.update(df_prep.index)

    all_dates = sorted(all_dates)
    start_idx = max(40, len(all_dates) - months * 21)
    backtest_dates = all_dates[start_idx:]

    for date in backtest_dates:
        if current_date != (date.date() if hasattr(date, 'date') else date):
            trades_today = 0
            current_date = date.date() if hasattr(date, 'date') else date

        # 止损止盈检查
        positions_to_remove = []
        for i, pos in enumerate(positions):
            ticker = pos['ticker']
            if ticker in prepared_data and date in prepared_data[ticker].index:
                row = prepared_data[ticker].loc[date]
                high_price = float(row['High']) if not isinstance(row['High'], (int, float)) else row['High']
                low_price = float(row['Low']) if not isinstance(row['Low'], (int, float)) else row['Low']

                stop_price = pos['entry_price'] * (1 + params['stop_loss'])
                tp_price = pos['entry_price'] * (1 + params['take_profit'])

                if low_price <= stop_price:
                    profit = (stop_price - pos['entry_price']) * pos['shares']
                    capital += stop_price * pos['shares']
                    total_profit += profit
                    losses += 1
                    positions_to_remove.append(i)
                    trade_count += 1
                elif high_price >= tp_price:
                    profit = (tp_price - pos['entry_price']) * pos['shares']
                    capital += tp_price * pos['shares']
                    total_profit += profit
                    wins += 1
                    positions_to_remove.append(i)
                    trade_count += 1

        for i in sorted(positions_to_remove, reverse=True):
            positions.pop(i)

        # 买入
        if len(positions) < params['max_positions'] and trades_today < params['max_trades_day']:
            candidates = []
            for ticker, df_prep in prepared_data.items():
                if date not in df_prep.index:
                    continue
                if any(p['ticker'] == ticker for p in positions):
                    continue
                row = df_prep.loc[date]
                if pd.isna(row.get('rsi')) or pd.isna(row.get('sma20')):
                    continue
                s = score_fn(row)
                if s >= params['buy_threshold']:
                    candidates.append((ticker, s, row))

            candidates.sort(key=lambda x: x[1], reverse=True)

            for ticker, s, row in candidates:
                if len(positions) >= params['max_positions'] or trades_today >= params['max_trades_day']:
                    break
                price = float(row['Close']) if not isinstance(row['Close'], (int, float)) else row['Close']
                trade_amount = capital * params['position_size']
                shares = int(trade_amount // price)
                if shares < 1 or capital < price:
                    continue
                capital -= shares * price
                positions.append({'ticker': ticker, 'entry_price': price, 'shares': shares, 'entry_date': date})
                trades_today += 1

        # 计算回撤
        portfolio_value = capital
        for pos in positions:
            ticker = pos['ticker']
            if ticker in prepared_data and date in prepared_data[ticker].index:
                row = prepared_data[ticker].loc[date]
                current_price = float(row['Close']) if not isinstance(row['Close'], (int, float)) else row['Close']
                portfolio_value += current_price * pos['shares']
        if portfolio_value > peak_capital:
            peak_capital = portfolio_value
        dd = (portfolio_value - peak_capital) / peak_capital * 100
        if dd < max_drawdown:
            max_drawdown = dd

    # 强制平仓
    for pos in positions:
        ticker = pos['ticker']
        if ticker in prepared_data and len(prepared_data[ticker]) > 0:
            last_row = prepared_data[ticker].iloc[-1]
            exit_price = float(last_row['Close']) if not isinstance(last_row['Close'], (int, float)) else last_row['Close']
            profit = (exit_price - pos['entry_price']) * pos['shares']
            capital += exit_price * pos['shares']
            total_profit += profit
            if profit > 0: wins += 1
            else: losses += 1
            trade_count += 1

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    return {
        'total_profit': round(total_profit, 2),
        'return_pct': round(total_profit / INITIAL_CAPITAL * 100, 2),
        'win_rate': round(win_rate, 1),
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'max_drawdown': round(max_drawdown, 2),
        'final_capital': round(capital, 2),
    }


def optimize_agent(agent_id, stock_data, months=6):
    """穷举参数组合找最优"""

    # 参数搜索空间
    if agent_id == 1:
        param_grid = {
            'stop_loss': [-0.02, -0.03, -0.04, -0.05, -0.06],
            'take_profit': [0.03, 0.04, 0.05, 0.06, 0.08],
            'buy_threshold': [3, 4, 5],
            'position_size': [0.08, 0.10, 0.12, 0.15],
            'max_positions': [3, 5],
            'max_trades_day': [3, 5],
        }
    elif agent_id == 2:
        param_grid = {
            'stop_loss': [-0.04, -0.05, -0.06, -0.07, -0.08],
            'take_profit': [0.03, 0.04, 0.05, 0.06],
            'buy_threshold': [4, 5, 6],
            'position_size': [0.12, 0.15, 0.18],
            'max_positions': [2, 3],
            'max_trades_day': [2, 3],
        }
    else:  # agent 3
        param_grid = {
            'stop_loss': [-0.02, -0.03, -0.04, -0.05],
            'take_profit': [0.02, 0.03, 0.04, 0.05],
            'buy_threshold': [3, 4, 5],
            'position_size': [0.08, 0.10, 0.12],
            'max_positions': [3, 5],
            'max_trades_day': [5, 8],
        }

    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combinations = list(itertools.product(*values))

    print(f"  测试 {len(combinations)} 种参数组合...")

    results = []
    for i, combo in enumerate(combinations):
        params = dict(zip(keys, combo))
        result = run_backtest_with_params(agent_id, stock_data, params, months)
        result['params'] = params
        results.append(result)

        if (i + 1) % 100 == 0:
            print(f"  进度: {i+1}/{len(combinations)}")

    # 按综合评分排序（收益 × 胜率权重）
    for r in results:
        # 综合评分 = 收益率 + 胜率加权 - 回撤惩罚
        r['composite_score'] = r['return_pct'] + (r['win_rate'] - 40) * 0.3 + r['max_drawdown'] * 0.5

    results.sort(key=lambda x: x['composite_score'], reverse=True)
    return results


def main():
    args = sys.argv[1:]
    agents_to_test = [1, 2, 3]
    months = 6

    i = 0
    while i < len(args):
        if args[i] == '--agent' and i + 1 < len(args):
            agents_to_test = [int(args[i+1])]
            i += 2
        elif args[i] == '--months' and i + 1 < len(args):
            months = int(args[i+1])
            i += 2
        else:
            i += 1

    print(f"\n{'='*70}")
    print(f"  参数优化器 - 寻找最优策略参数")
    print(f"  回测周期: {months} 个月 | 初始资金: ${INITIAL_CAPITAL:,}")
    print(f"{'='*70}")

    all_best = {}

    for agent_id in agents_to_test:
        name = AGENT_CONFIGS[agent_id]['name']
        tickers = AGENT_STOCKS[agent_id]
        print(f"\n{'='*70}")
        print(f"  优化 {name}")
        print(f"{'='*70}")

        stock_data = download_data(tickers, months)
        if not stock_data:
            continue

        results = optimize_agent(agent_id, stock_data, months)

        # 显示 Top 5
        print(f"\n  📊 {name} Top 5 参数组合:")
        print(f"  {'排名':<4} {'收益率':>8} {'胜率':>6} {'交易数':>5} {'回撤':>7} {'止损':>6} {'止盈':>6} {'阈值':>4} {'仓位':>5} {'持仓':>4}")
        print(f"  {'-'*65}")

        for rank, r in enumerate(results[:5], 1):
            p = r['params']
            print(f"  {rank:<4} {r['return_pct']:>+7.2f}% {r['win_rate']:>5.1f}% {r['total_trades']:>5} {r['max_drawdown']:>6.2f}% {p['stop_loss']*100:>5.1f}% {p['take_profit']*100:>5.1f}% {p['buy_threshold']:>4} {p['position_size']*100:>4.0f}% {p['max_positions']:>4}")

        # 显示最差的3个（对比）
        print(f"\n  📉 最差 3 组（避免这些参数）:")
        for r in results[-3:]:
            p = r['params']
            print(f"       {r['return_pct']:>+7.2f}% {r['win_rate']:>5.1f}% 止损{p['stop_loss']*100:.0f}% 止盈{p['take_profit']*100:.0f}% 阈值{p['buy_threshold']}")

        best = results[0]
        all_best[agent_id] = best

        print(f"\n  ✅ {name} 最优参数:")
        print(f"     止损: {best['params']['stop_loss']*100:.1f}%")
        print(f"     止盈: {best['params']['take_profit']*100:.1f}%")
        print(f"     买入阈值: {best['params']['buy_threshold']} 分")
        print(f"     仓位大小: {best['params']['position_size']*100:.0f}%")
        print(f"     最大持仓: {best['params']['max_positions']}")
        print(f"     每日交易上限: {best['params']['max_trades_day']}")
        print(f"     预期收益: {best['return_pct']:+.2f}%")
        print(f"     预期胜率: {best['win_rate']:.1f}%")
        print(f"     最大回撤: {best['max_drawdown']:.2f}%")

    # 保存最优参数到文件
    if all_best:
        report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'optimal_params.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# 最优策略参数\n\n")
            f.write(f"- 优化日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"- 回测周期: {months} 个月\n")
            f.write(f"- 初始资金: ${INITIAL_CAPITAL:,}\n\n")

            f.write(f"## 参数对比\n\n")
            f.write(f"| 参数 | Agent-1 动量 | Agent-2 保守 | Agent-3 激进 |\n")
            f.write(f"|------|-------------|-------------|-------------|\n")

            param_labels = [
                ('止损', 'stop_loss', lambda v: f"{v*100:.1f}%"),
                ('止盈', 'take_profit', lambda v: f"{v*100:.1f}%"),
                ('买入阈值', 'buy_threshold', lambda v: f"{v}分"),
                ('仓位大小', 'position_size', lambda v: f"{v*100:.0f}%"),
                ('最大持仓', 'max_positions', lambda v: str(v)),
                ('每日交易上限', 'max_trades_day', lambda v: str(v)),
            ]
            for label, key, fmt in param_labels:
                vals = []
                for aid in [1, 2, 3]:
                    if aid in all_best:
                        vals.append(fmt(all_best[aid]['params'][key]))
                    else:
                        vals.append('N/A')
                f.write(f"| {label} | {vals[0]} | {vals[1]} | {vals[2]} |\n")

            f.write(f"\n## 预期表现\n\n")
            f.write(f"| 指标 | Agent-1 | Agent-2 | Agent-3 |\n")
            f.write(f"|------|---------|---------|--------|\n")
            for label, key, fmt in [
                ('收益率', 'return_pct', '{:+.2f}%'),
                ('胜率', 'win_rate', '{:.1f}%'),
                ('交易次数', 'total_trades', '{}'),
                ('最大回撤', 'max_drawdown', '{:.2f}%'),
            ]:
                vals = [fmt.format(all_best[aid][key]) if aid in all_best else 'N/A' for aid in [1,2,3]]
                f.write(f"| {label} | {vals[0]} | {vals[1]} | {vals[2]} |\n")

        print(f"\n  📄 最优参数已保存: {report_path}")

    print()


if __name__ == '__main__':
    main()
