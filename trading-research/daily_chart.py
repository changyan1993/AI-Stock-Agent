"""
三 Agent 每日收益图表
- 上图：账户价值曲线（equity curve）
- 中图：每日盈亏柱状图（绿赚红亏）
- 下图：累计收益对比

用法：
  python daily_chart.py           生成图表并保存
  python daily_chart.py --show    生成并弹出窗口
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
import os
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')  # 无窗口模式
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# 如果传了 --show 参数，切换到交互模式
if '--show' in sys.argv:
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
DESKTOP = os.path.dirname(BASE)

AGENTS = {
    'Agent-1 动量': os.path.join(DESKTOP, 'stock-agent-1'),
    'Agent-2 保守': os.path.join(DESKTOP, 'stock-agent-2'),
    'Agent-3 激进': os.path.join(DESKTOP, 'stock-agent-3'),
}

COLORS = {
    'Agent-1 动量': '#2196F3',
    'Agent-2 保守': '#4CAF50',
    'Agent-3 激进': '#FF5722',
}

INITIAL_CAPITAL = 2000

def load_agent_data(agent_dir):
    """从 trading_state.json 加载交易历史"""
    state_file = os.path.join(agent_dir, 'trading_state.json')
    if not os.path.exists(state_file):
        return None

    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)

    trades = state.get('trade_history', [])
    positions = state.get('positions', [])
    capital = state.get('capital', INITIAL_CAPITAL)

    return {
        'state': state,
        'trades': trades,
        'positions': positions,
        'capital': capital,
    }

def build_daily_pnl(agent_data):
    """从交易历史构建每日盈亏序列"""
    trades = agent_data['trades']
    if not trades:
        return {}, {}

    daily_pnl = {}  # date -> daily profit
    cumulative = {}  # date -> cumulative profit

    running_total = 0
    for trade in trades:
        exit_date = trade.get('exit_date', '')
        if not exit_date or exit_date == 'END':
            continue
        try:
            date = exit_date[:10]
            profit = trade.get('profit', 0)
            daily_pnl[date] = daily_pnl.get(date, 0) + profit
            running_total += profit
            cumulative[date] = running_total
        except:
            continue

    # 补充无交易日（用前一天的累计值填充）
    if cumulative:
        all_dates = sorted(cumulative.keys())
        start = datetime.strptime(all_dates[0], '%Y-%m-%d')
        end = datetime.strptime(all_dates[-1], '%Y-%m-%d')
        current = start
        last_cum = 0
        filled_cum = {}
        filled_pnl = {}
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            if current.weekday() < 5:  # 只保留交易日
                if date_str in cumulative:
                    last_cum = cumulative[date_str]
                    filled_pnl[date_str] = daily_pnl.get(date_str, 0)
                else:
                    filled_pnl[date_str] = 0
                filled_cum[date_str] = last_cum
            current += timedelta(days=1)
        return filled_pnl, filled_cum

    return daily_pnl, cumulative

def generate_chart():
    """生成三 Agent 收益图表"""
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), gridspec_kw={'height_ratios': [2, 1.5, 2]})

    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    matplotlib.rcParams['axes.unicode_minus'] = False

    has_data = False

    for agent_name, agent_dir in AGENTS.items():
        data = load_agent_data(agent_dir)
        if not data or not data['trades']:
            continue

        daily_pnl, cumulative = build_daily_pnl(data)
        if not daily_pnl:
            continue

        has_data = True
        dates = [datetime.strptime(d, '%Y-%m-%d') for d in sorted(daily_pnl.keys())]
        pnl_values = [daily_pnl[d.strftime('%Y-%m-%d')] for d in dates]
        cum_values = [cumulative[d.strftime('%Y-%m-%d')] for d in dates]
        equity_values = [INITIAL_CAPITAL + c for c in cum_values]
        color = COLORS[agent_name]

        # 上图：账户价值曲线
        axes[0].plot(dates, equity_values, color=color, label=agent_name, linewidth=1.8)

        # 中图：每日盈亏柱状图（只画最活跃的 Agent，避免重叠）
        bar_colors = ['#4CAF50' if v >= 0 else '#F44336' for v in pnl_values]
        width = 0.25
        offset = list(AGENTS.keys()).index(agent_name) - 1
        bar_dates = [d + timedelta(hours=offset * 8) for d in dates]
        axes[1].bar(bar_dates, pnl_values, width=width, color=bar_colors, alpha=0.7, label=agent_name)

        # 下图：累计收益对比
        axes[2].fill_between(dates, 0, cum_values, alpha=0.15, color=color)
        axes[2].plot(dates, cum_values, color=color, label=agent_name, linewidth=1.8)

    if not has_data:
        # 没有交易数据时显示提示
        for ax in axes:
            ax.text(0.5, 0.5, 'No trade data yet\nWaiting for first trades...',
                   transform=ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
        output_path = os.path.join(BASE, 'daily_performance.png')
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Chart saved (no data): {output_path}")
        if '--show' in sys.argv:
            plt.show()
        plt.close()
        return

    # 上图样式
    axes[0].axhline(y=INITIAL_CAPITAL, color='gray', linestyle='--', alpha=0.5, label=f'Initial ${INITIAL_CAPITAL:,}')
    axes[0].set_title('Account Value (Equity Curve)', fontsize=13, fontweight='bold')
    axes[0].set_ylabel('Portfolio Value ($)')
    axes[0].legend(loc='upper left', fontsize=9)
    axes[0].grid(True, alpha=0.3)
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    axes[0].xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))

    # 中图样式
    axes[1].axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    axes[1].set_title('Daily P&L', fontsize=13, fontweight='bold')
    axes[1].set_ylabel('Profit/Loss ($)')
    axes[1].legend(loc='upper left', fontsize=9)
    axes[1].grid(True, alpha=0.3)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    axes[1].xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))

    # 下图样式
    axes[2].axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    axes[2].set_title('Cumulative Profit', fontsize=13, fontweight='bold')
    axes[2].set_ylabel('Total Profit ($)')
    axes[2].legend(loc='upper left', fontsize=9)
    axes[2].grid(True, alpha=0.3)
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    axes[2].xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))

    # 添加生成时间
    fig.suptitle(f'Three-Agent Trading Performance\nGenerated: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                 fontsize=14, fontweight='bold', y=0.98)

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    output_path = os.path.join(BASE, 'daily_performance.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Chart saved: {output_path}")

    if '--show' in sys.argv:
        plt.show()
    plt.close()

    # 打印周报摘要
    print_weekly_summary()

def print_weekly_summary():
    """打印本周盈亏摘要"""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    monday_str = monday.strftime('%Y-%m-%d')

    print(f"\n{'='*50}")
    print(f"  Weekly Summary (week of {monday_str})")
    print(f"{'='*50}")

    for agent_name, agent_dir in AGENTS.items():
        data = load_agent_data(agent_dir)
        if not data or not data['trades']:
            print(f"\n  {agent_name}: No trades yet")
            continue

        week_trades = [t for t in data['trades']
                      if t.get('exit_date', '')[:10] >= monday_str
                      and t.get('exit_date') != 'END']
        week_profit = sum(t.get('profit', 0) for t in week_trades)
        wins = len([t for t in week_trades if t.get('profit', 0) > 0])
        losses = len([t for t in week_trades if t.get('profit', 0) <= 0])
        total_profit = sum(t.get('profit', 0) for t in data['trades'] if t.get('exit_date') != 'END')

        print(f"\n  {agent_name}:")
        print(f"    This week: ${week_profit:+.2f} ({wins}W / {losses}L)")
        print(f"    Total P&L: ${total_profit:+.2f}")
        print(f"    Capital:   ${data['capital']:,.2f}")
        if data['positions']:
            print(f"    Open positions: {len(data['positions'])}")
            for p in data['positions']:
                print(f"      - {p['ticker']} x{p['shares']} @ ${p['entry_price']:.2f}")

if __name__ == '__main__':
    generate_chart()
