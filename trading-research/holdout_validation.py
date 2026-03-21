"""
V1 基线 Final Holdout 验证
用完全未参与调参的历史窗口验证策略稳定性

数据切分：
  - 训练窗口 (IS): 最近 6 个月 (2024-09 ~ 2025-03) — 参数优化用过
  - 污染窗口: 7-12 个月前 (2024-03 ~ 2024-09) — 守护任务迭代时看过
  - Holdout 窗口: 13-18 个月前 (2023-09 ~ 2024-03) — 完全未参与任何决策
  - 更远 Holdout: 19-24 个月前 (2023-03 ~ 2023-09) — 更早期验证

如果 holdout 窗口的收益方向和 IS 一致（正收益或接近盈亏平衡），
且回撤没有显著恶化，则认为策略有一定稳定性。
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backtest import (
    AGENT_STOCKS, AGENT_CONFIGS, INITIAL_CAPITAL, SLIPPAGE,
    prepare_indicators, analyze_results, print_report,
    download_market_data, calc_market_score,
    agent1_score, agent2_score, agent3_score
)

def download_data_range(tickers, start_date, end_date):
    """下载指定日期范围的数据"""
    print(f"  下载 {len(tickers)} 只股票 ({start_date} ~ {end_date})...")
    # 多拉60天用于指标预热
    actual_start = start_date - timedelta(days=60)
    data = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=actual_start, end=end_date, progress=False, auto_adjust=True)
            if df is not None and len(df) > 40:
                data[ticker] = df
        except:
            pass
    print(f"  成功下载 {len(data)}/{len(tickers)} 只")
    return data

def download_market_range(start_date, end_date):
    """下载指定范围的大盘数据"""
    actual_start = start_date - timedelta(days=60)
    market = {}
    for sym in ['SPY', 'QQQ', '^VIX']:
        try:
            df = yf.download(sym, start=actual_start, end=end_date, progress=False, auto_adjust=True)
            if df is not None and len(df) > 0:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                market[sym] = df
        except:
            pass
    return market

def run_backtest_range(agent_id, stock_data, start_date, end_date, market_data=None):
    """在指定日期范围内运行回测"""
    config = AGENT_CONFIGS[agent_id]
    score_fn = config['score_fn']

    capital = INITIAL_CAPITAL
    positions = []
    trade_history = []
    daily_values = []
    trades_today = 0
    current_date = None

    prepared_data = {}
    all_dates = set()
    for ticker, df in stock_data.items():
        df_prep = prepare_indicators(df)
        prepared_data[ticker] = df_prep
        all_dates.update(df_prep.index)

    all_dates = sorted(all_dates)
    # 只在指定范围内回测
    backtest_dates = [d for d in all_dates if hasattr(d, 'date') and start_date.date() <= d.date() <= end_date.date()]

    for date in backtest_dates:
        d = date.date() if hasattr(date, 'date') else date
        if current_date != d:
            trades_today = 0
            current_date = d

        # 止损止盈
        positions_to_remove = []
        for i, pos in enumerate(positions):
            ticker = pos['ticker']
            if ticker in prepared_data and date in prepared_data[ticker].index:
                row = prepared_data[ticker].loc[date]
                current_price = float(row['Close']) if not isinstance(row['Close'], (int, float)) else row['Close']
                low_price = float(row['Low']) if not isinstance(row['Low'], (int, float)) else row['Low']
                high_price = float(row['High']) if not isinstance(row['High'], (int, float)) else row['High']

                # Agent-2 时间止损：15 trading days (~21 calendar days) 强制平仓
                if agent_id == 2:
                    hold_days = (date - pos['entry_date']).days if hasattr(date, 'date') else 0
                    if hold_days > 21:  # 15 trading days ≈ 21 calendar days
                        exit_price = current_price * (1 - SLIPPAGE)
                        profit = (exit_price - pos['entry_price']) * pos['shares']
                        capital += exit_price * pos['shares']
                        trade_history.append({
                            'ticker': ticker, 'entry_price': pos['entry_price'],
                            'exit_price': round(exit_price, 2), 'shares': pos['shares'],
                            'profit': round(profit, 2), 'reason': 'time_stop',
                            'entry_date': pos['entry_date'], 'exit_date': str(date)[:10],
                            'hold_days': hold_days
                        })
                        positions_to_remove.append(i)
                        trades_today += 1
                        continue

                stop_price = pos['entry_price'] * (1 + config['stop_loss'])
                tp_price = pos['entry_price'] * (1 + config['take_profit'])

                if low_price <= stop_price:
                    exit_price = stop_price * (1 - SLIPPAGE)
                    profit = (exit_price - pos['entry_price']) * pos['shares']
                    capital += exit_price * pos['shares']
                    trade_history.append({
                        'ticker': ticker, 'entry_price': pos['entry_price'],
                        'exit_price': round(exit_price, 2), 'shares': pos['shares'],
                        'profit': round(profit, 2), 'reason': 'stop_loss',
                        'entry_date': pos['entry_date'], 'exit_date': str(date)[:10],
                        'hold_days': (date - pos['entry_date']).days if hasattr(date, 'date') else 0
                    })
                    positions_to_remove.append(i)
                    trades_today += 1
                elif high_price >= tp_price:
                    exit_price = tp_price * (1 - SLIPPAGE)
                    profit = (exit_price - pos['entry_price']) * pos['shares']
                    capital += exit_price * pos['shares']
                    trade_history.append({
                        'ticker': ticker, 'entry_price': pos['entry_price'],
                        'exit_price': round(exit_price, 2), 'shares': pos['shares'],
                        'profit': round(profit, 2), 'reason': 'take_profit',
                        'entry_date': pos['entry_date'], 'exit_date': str(date)[:10],
                        'hold_days': (date - pos['entry_date']).days if hasattr(date, 'date') else 0
                    })
                    positions_to_remove.append(i)
                    trades_today += 1

        for i in sorted(positions_to_remove, reverse=True):
            positions.pop(i)

        # Agent-3 regime kill switch（折中版：仅 <= -2 禁买）
        effective_max_positions = config['max_positions']
        if agent_id == 3 and market_data is not None:
            day_market_score = calc_market_score(market_data, date)
            if day_market_score <= -2:
                effective_max_positions = 0

        # 买入
        if len(positions) < effective_max_positions and trades_today < config['max_trades_day']:
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
                # 大盘评分仅 Agent-1
                if market_data is not None and agent_id == 1:
                    s += calc_market_score(market_data, date)
                if s >= config['buy_threshold']:
                    candidates.append((ticker, s, row))

            candidates.sort(key=lambda x: x[1], reverse=True)
            for ticker, s, row in candidates:
                if len(positions) >= effective_max_positions or trades_today >= config['max_trades_day']:
                    break
                price = float(row['Close']) if not isinstance(row['Close'], (int, float)) else row['Close']
                actual_buy_price = price * (1 + SLIPPAGE)
                trade_amount = capital * config['position_size']
                shares = int(trade_amount // actual_buy_price)
                if shares < 1 or capital < actual_buy_price:
                    continue
                capital -= shares * actual_buy_price
                positions.append({'ticker': ticker, 'entry_price': actual_buy_price, 'shares': shares, 'entry_date': date})
                trades_today += 1

        # 每日价值
        portfolio_value = capital
        for pos in positions:
            ticker = pos['ticker']
            if ticker in prepared_data and date in prepared_data[ticker].index:
                row = prepared_data[ticker].loc[date]
                current_price = float(row['Close']) if not isinstance(row['Close'], (int, float)) else row['Close']
                portfolio_value += current_price * pos['shares']
        daily_values.append({'date': date, 'value': portfolio_value})

    # 平仓（滑点适用）
    for pos in positions:
        ticker = pos['ticker']
        if ticker in prepared_data and len(prepared_data[ticker]) > 0:
            last_row = prepared_data[ticker].iloc[-1]
            raw_price = float(last_row['Close']) if not isinstance(last_row['Close'], (int, float)) else last_row['Close']
            exit_price = raw_price * (1 - SLIPPAGE)
            profit = (exit_price - pos['entry_price']) * pos['shares']
            capital += exit_price * pos['shares']
            trade_history.append({
                'ticker': ticker, 'entry_price': pos['entry_price'],
                'exit_price': round(exit_price, 2), 'shares': pos['shares'],
                'profit': round(profit, 2), 'reason': 'end_of_backtest',
                'entry_date': pos['entry_date'], 'exit_date': 'END', 'hold_days': 0
            })

    return {
        'agent_id': agent_id,
        'name': config['name'],
        'trade_history': trade_history,
        'daily_values': pd.DataFrame(daily_values),
        'final_capital': capital,
    }


def main():
    now = datetime.now()

    windows = {
        'IS (最近6个月)': (now - timedelta(days=180), now),
        'Holdout-1 (13-18个月前)': (now - timedelta(days=540), now - timedelta(days=360)),
        'Holdout-2 (19-24个月前)': (now - timedelta(days=720), now - timedelta(days=540)),
    }

    print(f"\n{'='*70}")
    print(f"  V1 基线 Final Holdout 验证")
    print(f"  策略参数已冻结，以下结果用于判断是否过拟合")
    print(f"{'='*70}")

    all_window_results = {}

    for window_name, (start, end) in windows.items():
        print(f"\n{'='*70}")
        print(f"  窗口: {window_name}")
        print(f"  区间: {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")
        print(f"{'='*70}")

        window_stats = {}

        for agent_id in [1, 2, 3]:
            config = AGENT_CONFIGS[agent_id]
            tickers = AGENT_STOCKS[agent_id]
            print(f"\n  📊 {config['name']}...")

            stock_data = download_data_range(tickers, start, end)
            market_data = download_market_range(start, end) if agent_id in [1, 3] else None

            if not stock_data:
                print(f"  ⚠ 无数据，跳过")
                continue

            result = run_backtest_range(agent_id, stock_data, start, end, market_data)
            stats = analyze_results(result)
            window_stats[agent_id] = stats

            print(f"    收益: ${stats['total_profit']:+.2f} ({stats['return_pct']:+.2f}%)")
            print(f"    胜率: {stats['win_rate']}% | 交易: {stats['total_trades']} | 回撤: {stats['max_drawdown']:.2f}% | 夏普: {stats['sharpe_ratio']:.2f}")

        all_window_results[window_name] = window_stats

    # === 汇总对比 ===
    print(f"\n\n{'='*70}")
    print(f"  跨窗口稳定性对比")
    print(f"{'='*70}")

    for agent_id in [1, 2, 3]:
        name = AGENT_CONFIGS[agent_id]['name']
        print(f"\n  {name}:")
        print(f"  {'窗口':<24} | {'收益':>10} | {'胜率':>8} | {'交易':>6} | {'回撤':>8} | {'夏普':>6}")
        print(f"  {'-'*24}-+-{'-'*10}-+-{'-'*8}-+-{'-'*6}-+-{'-'*8}-+-{'-'*6}")
        for window_name, stats_dict in all_window_results.items():
            if agent_id in stats_dict:
                s = stats_dict[agent_id]
                print(f"  {window_name:<24} | {s['return_pct']:>+9.2f}% | {s['win_rate']:>7.1f}% | {s['total_trades']:>6} | {s['max_drawdown']:>7.2f}% | {s['sharpe_ratio']:>6.2f}")
            else:
                print(f"  {window_name:<24} | {'N/A':>10} | {'N/A':>8} | {'N/A':>6} | {'N/A':>8} | {'N/A':>6}")

    # === 验证判定 ===
    print(f"\n\n{'='*70}")
    print(f"  验证判定")
    print(f"{'='*70}")

    passed = True
    for agent_id in [1, 2, 3]:
        name = AGENT_CONFIGS[agent_id]['name']
        issues = []

        for window_name, stats_dict in all_window_results.items():
            if 'Holdout' not in window_name:
                continue
            if agent_id not in stats_dict:
                issues.append(f"{window_name}: 无数据")
                continue
            s = stats_dict[agent_id]
            if s['total_trades'] < 5:
                issues.append(f"{window_name}: 交易次数过少 ({s['total_trades']})")
            if s['max_drawdown'] < -10:
                issues.append(f"{window_name}: 回撤过大 ({s['max_drawdown']:.2f}%)")
            if s['return_pct'] < -5:
                issues.append(f"{window_name}: 收益严重偏离 ({s['return_pct']:+.2f}%)")

        if issues:
            print(f"\n  {name}: ⚠ NEEDS REVIEW")
            for issue in issues:
                print(f"    - {issue}")
            passed = False
        else:
            print(f"\n  {name}: ✓ PASS")

    overall = "VALIDATED" if passed else "NEEDS_REVIEW"
    print(f"\n  总体判定: {overall}")

    # === 保存报告 ===
    import os
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'holdout_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# V1 基线 Final Holdout 验证报告\n\n")
        f.write(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"- 总体判定: **{overall}**\n\n")

        f.write(f"## 数据切分\n\n")
        f.write(f"| 窗口 | 区间 | 用途 |\n")
        f.write(f"|------|------|------|\n")
        for wn, (s, e) in windows.items():
            usage = "参数优化" if "IS" in wn else "未参与任何调参"
            f.write(f"| {wn} | {s.strftime('%Y-%m-%d')} ~ {e.strftime('%Y-%m-%d')} | {usage} |\n")

        f.write(f"\n## 跨窗口对比\n\n")
        for agent_id in [1, 2, 3]:
            name = AGENT_CONFIGS[agent_id]['name']
            f.write(f"\n### {name}\n\n")
            f.write(f"| 窗口 | 收益 | 胜率 | 交易 | 回撤 | 夏普 |\n")
            f.write(f"|------|------|------|------|------|------|\n")
            for wn, sd in all_window_results.items():
                if agent_id in sd:
                    s = sd[agent_id]
                    f.write(f"| {wn} | {s['return_pct']:+.2f}% | {s['win_rate']:.1f}% | {s['total_trades']} | {s['max_drawdown']:.2f}% | {s['sharpe_ratio']:.2f} |\n")

        f.write(f"\n## 结论\n\n")
        f.write(f"判定: **{overall}**\n\n")
        if passed:
            f.write(f"所有 Agent 在 holdout 窗口中均未出现严重失效（回撤 < -10%, 收益 > -5%）。\n")
            f.write(f"V1 基线参数可进入 paper trading 阶段。\n")
        else:
            f.write(f"部分 Agent 在 holdout 窗口中存在异常，需人工审核后决定是否进入 paper trading。\n")

    print(f"\n  📄 报告已保存: {report_path}")


if __name__ == '__main__':
    main()
