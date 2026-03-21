"""
三Agent策略回测系统
用过去6个月历史数据验证三种策略的表现

用法:
  python backtest.py              回测全部3种策略并对比
  python backtest.py --agent 1    只回测Agent-1策略
  python backtest.py --months 12  回测12个月
  python backtest.py --plot       生成收益曲线图
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# ============== 三个Agent的股票池 ==============
AGENT_STOCKS = {
    1: ['SOFI', 'WMT', 'INTC', 'NFLX', 'BABA', 'COIN', 'PLTR', 'SNAP', 'NIO', 'MARA', 'LCID', 'F', 'RIVN', 'PINS', 'T', 'OPEN'],
    2: ['PFE', 'VZ', 'CSCO', 'BAC', 'USB', 'KEY', 'KO', 'MO', 'GM', 'BMY', 'CMCSA', 'HPQ', 'DOW', 'NEM', 'CLF', 'AA'],
    3: ['HOOD', 'SOUN', 'IONQ', 'DKNG', 'RBLX', 'AFRM', 'UPST', 'HIMS', 'JOBY', 'LUNR', 'CLSK', 'WULF', 'SKLZ', 'QUBT', 'RGTI', 'GRAB'],
}

INITIAL_CAPITAL = 2000

# ============== 摩擦模型（滑点 + 佣金） ==============
# 滑点 0.05% per trade（买高卖低），佣金 $0（零佣金券商）
# 每次往返约 0.1% 摩擦成本，模拟真实市场执行偏差
SLIPPAGE = 0.0005

# ============== 技术指标计算 ==============
def calc_rsi(closes, period=14):
    deltas = closes.diff()
    gain = deltas.where(deltas > 0, 0.0)
    loss = (-deltas).where(deltas < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_macd(closes, fast=12, slow=26, signal=9):
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calc_atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calc_volume_ratio(volume, period=20):
    avg_vol = volume.rolling(window=period).mean()
    return volume / avg_vol

# ============== 策略逻辑 ==============
def agent1_score(row):
    """Agent-1 动量+技术指标策略"""
    score = 0
    rsi, sma5, sma20, macd_hist, macd_hist_prev, daily_change, vol_ratio = (
        row['rsi'], row['sma5'], row['sma20'], row['macd_hist'], row['macd_hist_prev'], row['daily_change'], row['vol_ratio']
    )
    price = row['Close']

    # RSI
    if pd.notna(rsi):
        if 30 <= rsi <= 50: score += 1
        elif rsi < 30: score += 1
        elif rsi > 70: score -= 1

    # 价格 > SMA5
    if pd.notna(sma5) and price > sma5: score += 1

    # SMA5 > SMA20
    if pd.notna(sma5) and pd.notna(sma20) and sma5 > sma20: score += 1

    # MACD
    if pd.notna(macd_hist) and pd.notna(macd_hist_prev):
        if macd_hist > 0 and macd_hist_prev <= 0: score += 2  # 金叉
        elif macd_hist > 0: score += 1

    # 日涨幅 0.5-2%
    if 0.5 <= daily_change <= 2.0: score += 1
    elif daily_change > 3.0: score -= 1

    # 放量上涨
    if pd.notna(vol_ratio) and vol_ratio > 1.2 and daily_change > 0: score += 1

    return score

def agent2_score(row):
    """Agent-2 保守型超卖反弹策略"""
    score = 0
    rsi, sma5, sma20, macd_hist, macd_hist_prev, daily_change, vol_ratio = (
        row['rsi'], row['sma5'], row['sma20'], row['macd_hist'], row['macd_hist_prev'], row['daily_change'], row['vol_ratio']
    )
    price = row['Close']

    # RSI（越低越好）
    if pd.notna(rsi):
        if rsi < 25: score += 3
        elif rsi < 30: score += 2
        elif rsi < 35: score += 1
        elif rsi > 60: score -= 1

    # 价格低于SMA20
    if pd.notna(sma20) and price < sma20:
        deviation = (sma20 - price) / sma20 * 100
        if deviation > 5: score += 2
        else: score += 1

    # 价格低于SMA5
    if pd.notna(sma5) and price < sma5: score += 1

    # MACD 底部反转
    if pd.notna(macd_hist) and pd.notna(macd_hist_prev):
        if macd_hist > 0 and macd_hist_prev <= 0: score += 2  # 金叉
        elif macd_hist < 0 and macd_hist > -0.1: score += 1  # 接近零轴

    # 日跌幅（跌了才是机会）
    if -5.0 <= daily_change <= -2.0: score += 1
    elif daily_change > 2.0: score -= 1

    # 放量下跌
    if pd.notna(vol_ratio) and vol_ratio > 1.5 and daily_change < -1: score += 1

    return score

def agent3_score(row):
    """Agent-3 激进型追强势股策略（原始版本）"""
    score = 0
    rsi, sma5, sma20, macd_hist, macd_hist_prev, daily_change, vol_ratio = (
        row['rsi'], row['sma5'], row['sma20'], row['macd_hist'], row['macd_hist_prev'], row['daily_change'], row['vol_ratio']
    )
    price = row['Close']

    # RSI 强势区间
    if pd.notna(rsi):
        if 55 <= rsi <= 75: score += 2
        elif 45 <= rsi < 55: score += 1
        elif rsi > 80: score -= 1
        elif rsi < 35: score -= 1

    # 价格 > SMA5
    if pd.notna(sma5):
        if price > sma5: score += 1
        else: score -= 1

    # 多头排列
    if pd.notna(sma5) and pd.notna(sma20) and sma5 > sma20: score += 1

    # MACD
    if pd.notna(macd_hist) and pd.notna(macd_hist_prev):
        if macd_hist > 0 and macd_hist_prev <= 0: score += 2
        elif macd_hist > 0: score += 1
        elif macd_hist < 0 and macd_hist_prev >= 0: score -= 2  # 死叉

    # 涨幅（涨得多才好）
    if 1.0 <= daily_change <= 5.0: score += 1
    elif 5.0 < daily_change <= 10.0: score += 1
    elif daily_change < -1.0: score -= 1

    # 放量（关键信号）
    if pd.notna(vol_ratio) and daily_change > 0:
        if vol_ratio > 2.0: score += 2
        elif vol_ratio > 1.2: score += 1

    return score

# ============== 回测引擎 ==============
AGENT_CONFIGS = {
    1: {'name': 'Agent-1 动量型', 'score_fn': agent1_score, 'buy_threshold': 4,
        'stop_loss': -0.06, 'take_profit': 0.04, 'position_size': 0.08, 'max_positions': 3, 'max_trades_day': 3},
    2: {'name': 'Agent-2 保守型', 'score_fn': agent2_score, 'buy_threshold': 6,
        'stop_loss': -0.08, 'take_profit': 0.03, 'position_size': 0.18, 'max_positions': 2, 'max_trades_day': 2},
    3: {'name': 'Agent-3 激进型', 'score_fn': agent3_score, 'buy_threshold': 4,
        'stop_loss': -0.03, 'take_profit': 0.08, 'position_size': 0.08, 'max_positions': 3, 'max_trades_day': 2},
}

def download_data(tickers, months=6):
    """下载历史数据"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=months * 30 + 60)  # 多拉60天算指标
    print(f"  下载 {len(tickers)} 只股票 {months} 个月数据...")
    data = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
            if df is not None and len(df) > 40:
                data[ticker] = df
        except Exception as e:
            print(f"  ⚠ {ticker} 下载失败: {e}")
    print(f"  成功下载 {len(data)}/{len(tickers)} 只")
    return data

def prepare_indicators(df):
    """计算技术指标"""
    df = df.copy()
    # Handle MultiIndex columns from yfinance
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df['rsi'] = calc_rsi(df['Close'])
    df['sma5'] = df['Close'].rolling(5).mean()
    df['sma20'] = df['Close'].rolling(20).mean()
    macd_line, signal_line, histogram = calc_macd(df['Close'])
    df['macd_hist'] = histogram
    df['macd_hist_prev'] = histogram.shift(1)
    df['atr'] = calc_atr(df['High'], df['Low'], df['Close'])
    df['vol_ratio'] = calc_volume_ratio(df['Volume'])
    df['daily_change'] = df['Close'].pct_change() * 100
    # 日内过滤字段（Agent-3 live 执行使用）
    df['day_position'] = (df['Close'] - df['Low']) / (df['High'] - df['Low'])
    df['close_gt_open'] = df['Close'] > df['Open']
    return df

def download_market_data(months=6):
    """下载大盘数据（SPY/QQQ/VIX）用于市场环境评分"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=months * 30 + 60)
    market = {}
    for sym in ['SPY', 'QQQ', '^VIX']:
        try:
            df = yf.download(sym, start=start_date, end=end_date, progress=False, auto_adjust=True)
            if df is not None and len(df) > 0:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                market[sym] = df
        except:
            pass
    return market

def calc_market_score(market_data, date):
    """计算某天的大盘环境评分（与 analyze.js fetchMarketSentiment 一致）"""
    score = 0
    # SPY
    if 'SPY' in market_data and date in market_data['SPY'].index:
        spy_change = market_data['SPY'].loc[date]['Close'] / market_data['SPY'].loc[date].get('Open', market_data['SPY'].loc[date]['Close']) - 1
        spy_daily = market_data['SPY']['Close'].pct_change()
        if date in spy_daily.index and pd.notna(spy_daily[date]):
            spy_chg = spy_daily[date] * 100
            if spy_chg > 0.5: score += 1
            elif spy_chg < -0.5: score -= 1
    # QQQ
    if 'QQQ' in market_data and date in market_data['QQQ'].index:
        qqq_daily = market_data['QQQ']['Close'].pct_change()
        if date in qqq_daily.index and pd.notna(qqq_daily[date]):
            qqq_chg = qqq_daily[date] * 100
            if qqq_chg > 0.5: score += 1
            elif qqq_chg < -0.5: score -= 1
    # VIX
    if '^VIX' in market_data and date in market_data['^VIX'].index:
        vix_price = market_data['^VIX'].loc[date]['Close']
        if pd.notna(vix_price):
            vix_val = float(vix_price)
            if vix_val > 30: score -= 2
            elif vix_val > 25: score -= 1
            elif vix_val < 15: score += 1
    return score

def run_backtest(agent_id, stock_data, months=6, market_data=None):
    """运行单个Agent的回测"""
    config = AGENT_CONFIGS[agent_id]
    score_fn = config['score_fn']

    capital = INITIAL_CAPITAL
    positions = []  # {ticker, entry_price, shares, entry_date}
    trade_history = []
    daily_values = []
    trades_today = 0
    current_date = None

    # 确定回测开始日期（跳过指标预热期）
    all_dates = set()
    prepared_data = {}
    for ticker, df in stock_data.items():
        df_prep = prepare_indicators(df)
        prepared_data[ticker] = df_prep
        all_dates.update(df_prep.index)

    all_dates = sorted(all_dates)
    start_idx = max(40, len(all_dates) - months * 21)  # 约21个交易日/月
    backtest_dates = all_dates[start_idx:]

    for date in backtest_dates:
        if current_date != date.date() if hasattr(date, 'date') else date:
            trades_today = 0
            current_date = date.date() if hasattr(date, 'date') else date

        # 检查止损止盈
        positions_to_remove = []
        for i, pos in enumerate(positions):
            ticker = pos['ticker']
            if ticker in prepared_data and date in prepared_data[ticker].index:
                row = prepared_data[ticker].loc[date]
                current_price = float(row['Close']) if not isinstance(row['Close'], (int, float)) else row['Close']
                high_price = float(row['High']) if not isinstance(row['High'], (int, float)) else row['High']
                low_price = float(row['Low']) if not isinstance(row['Low'], (int, float)) else row['Low']

                # Agent-2 时间止损：15 trading days (~21 calendar days) 强制平仓
                # 防止尾部亏损（如CLF -$29长期持仓问题）
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
                        continue  # 已平仓，跳过后续止损止盈检查

                # 用日内最低价检查止损
                stop_price = pos['entry_price'] * (1 + config['stop_loss'])
                tp_price = pos['entry_price'] * (1 + config['take_profit'])

                if low_price <= stop_price:
                    # 止损 — 滑点：卖出时实际成交价略低
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
                    # 止盈 — 滑点：卖出时实际成交价略低
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

        # 评估买入
        # Agent-3 regime kill switch（折中版）：仅在极端恶劣市场禁止开新仓
        # market_score <= -2 (SPY跌+QQQ跌+VIX高) → 禁止开新仓
        # 其他情况 → 正常交易（不限制 -1 场景，避免过度削减高波动机会）
        effective_max_positions = config['max_positions']
        if agent_id == 3 and market_data is not None:
            day_market_score = calc_market_score(market_data, date)
            if day_market_score <= -2:
                effective_max_positions = 0  # 极端市场禁买

        if (len(positions) < effective_max_positions and
            trades_today < config['max_trades_day']):

            # NOTE: Agent-3 日内过滤（dp>1%, c>o, day_position>0.6）
            # 仅保留在 live 执行层（CLAUDE.md），不纳入日线回测主口径。
            # 原因：日线收盘数据无法准确模拟 10 分钟级盘中强势判断，
            # 硬映射会导致入场偏晚、负贡献。待升级 10 分钟级回测后再验证。

            candidates = []
            for ticker, df_prep in prepared_data.items():
                if date not in df_prep.index:
                    continue
                # 跳过已持仓的股票
                if any(p['ticker'] == ticker for p in positions):
                    continue

                row = df_prep.loc[date]
                if pd.isna(row.get('rsi')) or pd.isna(row.get('sma20')):
                    continue

                s = score_fn(row)
                # 大盘环境评分 — 仅 Agent-1 使用（回测验证：对动量策略正贡献，对保守/激进策略负贡献）
                # Agent-2/3 后续如需引入市场因子，应改为 regime gate / 过滤条件，不做统一加分
                if market_data is not None and agent_id == 1:
                    s += calc_market_score(market_data, date)
                if s >= config['buy_threshold']:
                    candidates.append((ticker, s, row))

            # 按分数排序，买最高分的
            candidates.sort(key=lambda x: x[1], reverse=True)

            for ticker, s, row in candidates:
                if (len(positions) >= effective_max_positions or
                    trades_today >= config['max_trades_day']):
                    break

                price = float(row['Close']) if not isinstance(row['Close'], (int, float)) else row['Close']
                # 滑点：买入时实际成交价略高于收盘价
                actual_buy_price = price * (1 + SLIPPAGE)
                trade_amount = capital * config['position_size']
                shares = int(trade_amount // actual_buy_price)
                if shares < 1 or capital < actual_buy_price:
                    continue

                cost = shares * actual_buy_price
                capital -= cost
                positions.append({
                    'ticker': ticker, 'entry_price': actual_buy_price,
                    'shares': shares, 'entry_date': date
                })
                trades_today += 1

        # 记录每日账户价值
        portfolio_value = capital
        for pos in positions:
            ticker = pos['ticker']
            if ticker in prepared_data and date in prepared_data[ticker].index:
                row = prepared_data[ticker].loc[date]
                current_price = float(row['Close']) if not isinstance(row['Close'], (int, float)) else row['Close']
                portfolio_value += current_price * pos['shares']
        daily_values.append({'date': date, 'value': portfolio_value})

    # 强制平仓剩余持仓（滑点适用）
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
                'entry_date': pos['entry_date'], 'exit_date': 'END',
                'hold_days': 0
            })

    return {
        'agent_id': agent_id,
        'name': config['name'],
        'trade_history': trade_history,
        'daily_values': pd.DataFrame(daily_values),
        'final_capital': capital,
    }

# ============== 统计分析 ==============
def analyze_results(result):
    """分析回测结果"""
    trades = result['trade_history']
    daily_values = result['daily_values']

    if not trades:
        return {'total_trades': 0, 'win_rate': 0, 'total_profit': 0, 'return_pct': 0,
                'wins': 0, 'losses': 0, 'avg_win': 0, 'avg_loss': 0, 'profit_factor': 0,
                'payoff_ratio': 0,
                'max_drawdown': 0, 'sharpe_ratio': 0, 'stop_losses': 0, 'take_profits': 0,
                'time_stops': 0, 'avg_hold_days': 0, 'final_capital': INITIAL_CAPITAL,
                'expectancy': 0, 'calmar_ratio': 0, 'monthly_consistency': 0,
                'profitable_months': 0, 'total_months': 0,
                'best_trade': None, 'worst_trade': None}

    wins = [t for t in trades if t['profit'] > 0]
    losses = [t for t in trades if t['profit'] <= 0]
    stop_losses = [t for t in trades if t['reason'] == 'stop_loss']
    take_profits = [t for t in trades if t['reason'] == 'take_profit']

    total_profit = sum(t['profit'] for t in trades)
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    # 最大回撤
    if len(daily_values) > 0:
        values = daily_values['value']
        peak = values.expanding(min_periods=1).max()
        drawdown = (values - peak) / peak * 100
        max_drawdown = drawdown.min()
    else:
        max_drawdown = 0

    # 夏普比率（简化版，假设无风险利率=0）
    if len(daily_values) > 1:
        daily_returns = daily_values['value'].pct_change().dropna()
        if daily_returns.std() > 0:
            sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe = 0
    else:
        sharpe = 0

    avg_win = np.mean([t['profit'] for t in wins]) if wins else 0
    avg_loss = np.mean([t['profit'] for t in losses]) if losses else 0
    avg_hold = np.mean([t['hold_days'] for t in trades if t['hold_days'] > 0]) if trades else 0

    # 盈亏比 (payoff ratio = avg_win / |avg_loss|)
    payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    # 利润因子 (profit factor = gross_profit / |gross_loss|)
    gross_profit = sum(t['profit'] for t in wins) if wins else 0
    gross_loss = sum(t['profit'] for t in losses) if losses else 0
    profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else float('inf')

    # 期望值 (expectancy) = (win_rate * avg_win + (1-win_rate) * avg_loss) / |avg_loss|
    wr = len(wins) / len(trades) if trades else 0
    if avg_loss != 0:
        expectancy = (wr * avg_win + (1 - wr) * avg_loss) / abs(avg_loss)
    else:
        expectancy = float('inf') if avg_win > 0 else 0

    # Calmar比率 = 年化收益率 / |最大回撤|
    if len(daily_values) > 1:
        total_days = (daily_values['date'].iloc[-1] - daily_values['date'].iloc[0]).days
        if total_days > 0 and max_drawdown != 0:
            annualized_return = (total_profit / INITIAL_CAPITAL) * (365 / total_days) * 100
            calmar = annualized_return / abs(max_drawdown)
        else:
            calmar = 0
    else:
        calmar = 0

    # 月度一致性 = 盈利月数 / 总月数
    if len(daily_values) > 1:
        dv_copy = daily_values.copy()
        dv_copy['month'] = pd.to_datetime(dv_copy['date']).dt.to_period('M')
        monthly = dv_copy.groupby('month')['value'].agg(['first', 'last'])
        monthly['return'] = monthly['last'] - monthly['first']
        profitable_months = (monthly['return'] > 0).sum()
        total_months = len(monthly)
        monthly_consistency = profitable_months / total_months if total_months > 0 else 0
    else:
        profitable_months = 0
        total_months = 0
        monthly_consistency = 0

    time_stops = [t for t in trades if t['reason'] == 'time_stop']

    return {
        'total_trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': round(win_rate, 1),
        'total_profit': round(total_profit, 2),
        'return_pct': round(total_profit / INITIAL_CAPITAL * 100, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'profit_factor': round(profit_factor, 2),
        'payoff_ratio': round(payoff_ratio, 2),
        'max_drawdown': round(max_drawdown, 2),
        'sharpe_ratio': round(sharpe, 2),
        'stop_losses': len(stop_losses),
        'take_profits': len(take_profits),
        'time_stops': len(time_stops),
        'avg_hold_days': round(avg_hold, 1),
        'final_capital': round(result['final_capital'], 2),
        'expectancy': round(expectancy, 3),
        'calmar_ratio': round(calmar, 2),
        'monthly_consistency': round(monthly_consistency * 100, 1),
        'profitable_months': profitable_months,
        'total_months': total_months,
        'best_trade': max(trades, key=lambda t: t['profit']) if trades else None,
        'worst_trade': min(trades, key=lambda t: t['profit']) if trades else None,
    }

def print_report(result, stats):
    """打印回测报告"""
    print(f"\n{'='*60}")
    print(f"  {result['name']} 回测报告")
    print(f"{'='*60}")
    print(f"  初始资金:     ${INITIAL_CAPITAL:,.2f}")
    print(f"  最终资金:     ${stats['final_capital']:,.2f}")
    print(f"  总收益:       ${stats['total_profit']:+,.2f} ({stats['return_pct']:+.2f}%)")
    print(f"  最大回撤:     {stats['max_drawdown']:.2f}%")
    print(f"  夏普比率:     {stats['sharpe_ratio']:.2f}")
    print()
    print(f"  总交易次数:   {stats['total_trades']}")
    print(f"  胜率:         {stats['win_rate']}% ({stats['wins']}胜 / {stats['losses']}负)")
    print(f"  止盈次数:     {stats['take_profits']}")
    print(f"  止损次数:     {stats['stop_losses']}")
    print(f"  平均盈利:     ${stats['avg_win']:+.2f}")
    print(f"  平均亏损:     ${stats['avg_loss']:+.2f}")
    print(f"  利润因子:     {stats['profit_factor']:.2f}")
    print(f"  盈亏比:       {stats['payoff_ratio']:.2f}")
    print(f"  期望值:       {stats['expectancy']:.3f}")
    print(f"  Calmar比率:   {stats['calmar_ratio']:.2f}")
    print(f"  月度一致性:   {stats['monthly_consistency']:.1f}% ({stats['profitable_months']}/{stats['total_months']}月)")
    print(f"  平均持仓天数: {stats['avg_hold_days']} 天")
    if stats.get('time_stops', 0) > 0:
        print(f"  时间止损次数: {stats['time_stops']}")

    if stats['best_trade']:
        t = stats['best_trade']
        print(f"\n  最佳交易:     {t['ticker']} +${t['profit']:.2f}")
    if stats['worst_trade']:
        t = stats['worst_trade']
        print(f"  最差交易:     {t['ticker']} ${t['profit']:.2f}")

def print_comparison(all_stats):
    """打印三个Agent对比"""
    print(f"\n{'='*70}")
    print(f"  三Agent策略对比")
    print(f"{'='*70}")
    print(f"  {'指标':<16} | {'Agent-1 动量':>14} | {'Agent-2 保守':>14} | {'Agent-3 激进':>14}")
    print(f"  {'-'*16}-+-{'-'*14}-+-{'-'*14}-+-{'-'*14}")

    metrics = [
        ('总收益', 'total_profit', '${:+,.2f}'),
        ('收益率', 'return_pct', '{:+.2f}%'),
        ('胜率', 'win_rate', '{:.1f}%'),
        ('总交易', 'total_trades', '{}'),
        ('最大回撤', 'max_drawdown', '{:.2f}%'),
        ('夏普比率', 'sharpe_ratio', '{:.2f}'),
        ('利润因子', 'profit_factor', '{:.2f}'),
        ('盈亏比', 'payoff_ratio', '{:.2f}'),
        ('平均持仓天', 'avg_hold_days', '{:.1f}'),
        ('期望值', 'expectancy', '{:.3f}'),
        ('Calmar比率', 'calmar_ratio', '{:.2f}'),
        ('月度一致性', 'monthly_consistency', '{:.1f}%'),
        ('止盈次数', 'take_profits', '{}'),
        ('止损次数', 'stop_losses', '{}'),
        ('时间止损', 'time_stops', '{}'),
    ]

    for label, key, fmt in metrics:
        vals = []
        for i in [1, 2, 3]:
            if i in all_stats:
                vals.append(fmt.format(all_stats[i][key]))
            else:
                vals.append('N/A')
        print(f"  {label:<16} | {vals[0]:>14} | {vals[1]:>14} | {vals[2]:>14}")

    # 判断最佳
    best_profit = max(all_stats.items(), key=lambda x: x[1]['total_profit'])
    best_winrate = max(all_stats.items(), key=lambda x: x[1]['win_rate'])
    best_sharpe = max(all_stats.items(), key=lambda x: x[1]['sharpe_ratio'])

    print(f"\n  🏆 最高收益: {AGENT_CONFIGS[best_profit[0]]['name']}")
    print(f"  🏆 最高胜率: {AGENT_CONFIGS[best_winrate[0]]['name']}")
    print(f"  🏆 最佳夏普: {AGENT_CONFIGS[best_sharpe[0]]['name']}")

def plot_results(all_results):
    """生成收益曲线对比图"""
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    matplotlib.rcParams['axes.unicode_minus'] = False

    fig, axes = plt.subplots(2, 1, figsize=(14, 10))

    # 上图：账户价值曲线
    ax1 = axes[0]
    colors = {1: '#2196F3', 2: '#4CAF50', 3: '#FF5722'}
    for agent_id, result in all_results.items():
        dv = result['daily_values']
        if len(dv) > 0:
            ax1.plot(dv['date'], dv['value'], color=colors[agent_id],
                    label=result['name'], linewidth=1.5)
    ax1.axhline(y=INITIAL_CAPITAL, color='gray', linestyle='--', alpha=0.5, label='Initial $2,000')
    ax1.set_title('Account Value Over Time')
    ax1.set_ylabel('Portfolio Value ($)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 下图：每日收益率
    ax2 = axes[1]
    for agent_id, result in all_results.items():
        dv = result['daily_values']
        if len(dv) > 1:
            returns = dv['value'].pct_change() * 100
            ax2.plot(dv['date'], returns, color=colors[agent_id],
                    label=result['name'], alpha=0.6, linewidth=0.8)
    ax2.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    ax2.set_title('Daily Returns (%)')
    ax2.set_ylabel('Return (%)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backtest_result.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n  📊 收益曲线已保存: {output_path}")
    plt.close()

# ============== 保存报告 ==============
def save_report(all_results, all_stats, months):
    """保存回测报告到文件"""
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backtest_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# 三Agent策略回测报告\n\n")
        f.write(f"- 回测周期: {months} 个月\n")
        f.write(f"- 初始资金: ${INITIAL_CAPITAL:,}\n")
        f.write(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

        f.write(f"## 策略对比\n\n")
        f.write(f"| 指标 | Agent-1 动量 | Agent-2 保守 | Agent-3 激进 |\n")
        f.write(f"|------|-------------|-------------|-------------|\n")
        for label, key, fmt in [
            ('总收益', 'total_profit', '${:+,.2f}'),
            ('收益率', 'return_pct', '{:+.2f}%'),
            ('胜率', 'win_rate', '{:.1f}%'),
            ('总交易', 'total_trades', '{}'),
            ('最大回撤', 'max_drawdown', '{:.2f}%'),
            ('夏普比率', 'sharpe_ratio', '{:.2f}'),
            ('利润因子', 'profit_factor', '{:.2f}'),
            ('盈亏比', 'payoff_ratio', '{:.2f}'),
            ('期望值', 'expectancy', '{:.3f}'),
            ('Calmar比率', 'calmar_ratio', '{:.2f}'),
            ('月度一致性', 'monthly_consistency', '{:.1f}%'),
        ]:
            vals = [fmt.format(all_stats[i][key]) if i in all_stats else 'N/A' for i in [1,2,3]]
            f.write(f"| {label} | {vals[0]} | {vals[1]} | {vals[2]} |\n")

        for agent_id in [1, 2, 3]:
            if agent_id not in all_stats:
                continue
            stats = all_stats[agent_id]
            result = all_results[agent_id]
            f.write(f"\n## {result['name']} 详细\n\n")
            f.write(f"- 最终资金: ${stats['final_capital']:,.2f}\n")
            f.write(f"- 交易次数: {stats['total_trades']} ({stats['wins']}胜/{stats['losses']}负)\n")
            f.write(f"- 止盈/止损: {stats['take_profits']}/{stats['stop_losses']}\n")
            if stats['best_trade']:
                t = stats['best_trade']
                f.write(f"- 最佳交易: {t['ticker']} +${t['profit']:.2f}\n")
            if stats['worst_trade']:
                t = stats['worst_trade']
                f.write(f"- 最差交易: {t['ticker']} ${t['profit']:.2f}\n")

    print(f"  📄 报告已保存: {report_path}")

# ============== 主程序 ==============
def main():
    args = sys.argv[1:]
    agents_to_test = [1, 2, 3]
    months = 6
    do_plot = False

    i = 0
    while i < len(args):
        if args[i] == '--agent' and i + 1 < len(args):
            agents_to_test = [int(args[i+1])]
            i += 2
        elif args[i] == '--months' and i + 1 < len(args):
            months = int(args[i+1])
            i += 2
        elif args[i] == '--plot':
            do_plot = True
            i += 1
        else:
            i += 1

    print(f"\n{'='*60}")
    print(f"  三Agent策略回测系统")
    print(f"  回测周期: {months} 个月 | 初始资金: ${INITIAL_CAPITAL:,}")
    print(f"{'='*60}")

    # 下载大盘数据（SPY/QQQ/VIX）用于市场环境评分
    print(f"\n📡 下载大盘数据 (SPY/QQQ/VIX)...")
    market_data = download_market_data(months)
    print(f"  大盘数据就绪: {', '.join(market_data.keys())}")

    all_results = {}
    all_stats = {}

    for agent_id in agents_to_test:
        config = AGENT_CONFIGS[agent_id]
        tickers = AGENT_STOCKS[agent_id]
        print(f"\n📊 {config['name']} 回测中...")
        print(f"  股票池: {', '.join(tickers[:8])}...")

        stock_data = download_data(tickers, months)
        if not stock_data:
            print(f"  ⚠ 无数据，跳过")
            continue

        result = run_backtest(agent_id, stock_data, months, market_data)
        stats = analyze_results(result)

        all_results[agent_id] = result
        all_stats[agent_id] = stats

        print_report(result, stats)

    if len(all_stats) > 1:
        print_comparison(all_stats)

    save_report(all_results, all_stats, months)

    if do_plot:
        plot_results(all_results)

    print()

if __name__ == '__main__':
    main()
