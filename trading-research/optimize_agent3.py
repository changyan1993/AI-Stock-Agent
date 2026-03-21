"""Agent-3 参数网格搜索优化器（含大盘评分）"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from backtest import *
from itertools import product

print("下载 Agent-3 股票数据...")
stock_data = download_data(AGENT_STOCKS[3], 6)
print("下载大盘数据...")
market_data = download_market_data(6)
print(f"数据就绪，开始网格搜索...\n")

param_grid = {
    'buy_threshold': [4, 5, 6, 7],
    'stop_loss': [-0.03, -0.04, -0.05, -0.06, -0.08],
    'take_profit': [0.03, 0.04, 0.05, 0.06, 0.08],
    'position_size': [0.06, 0.08, 0.10, 0.12],
    'max_positions': [1, 2, 3],
    'max_trades_day': [1, 2, 3],
}

keys = list(param_grid.keys())
values = list(param_grid.values())
combos = list(product(*values))
print(f"共 {len(combos)} 种参数组合，开始搜索...\n")

results = []
for i, combo in enumerate(combos):
    params = dict(zip(keys, combo))
    AGENT_CONFIGS[3] = {'name': 'Agent-3 激进型', 'score_fn': agent3_score, **params}
    try:
        result = run_backtest(3, stock_data, 6, market_data)
        stats = analyze_results(result)
        results.append({**params, **{k: stats[k] for k in ['total_profit','return_pct','win_rate','total_trades','max_drawdown','sharpe_ratio']}})
    except:
        pass
    if (i + 1) % 100 == 0:
        print(f"  进度: {i+1}/{len(combos)}")

results.sort(key=lambda x: x['total_profit'], reverse=True)

print(f"\n{'='*70}")
print(f"  Agent-3 参数优化结果 (Top 10)")
print(f"{'='*70}")
for i, r in enumerate(results[:10]):
    print(f"\n  #{i+1} 收益: ${r['total_profit']:+.2f} ({r['return_pct']:+.2f}%)")
    print(f"     胜率: {r['win_rate']}% | 交易: {r['total_trades']} | 回撤: {r['max_drawdown']:.2f}% | 夏普: {r['sharpe_ratio']:.2f}")
    print(f"     买入门槛: {r['buy_threshold']} | 止损: {r['stop_loss']*100:.0f}% | 止盈: {r['take_profit']*100:.0f}%")
    print(f"     仓位: {r['position_size']*100:.0f}% | 最大持仓: {r['max_positions']} | 日限: {r['max_trades_day']}")

best = results[0]
print(f"\n{'='*70}")
print(f"  最优参数")
print(f"{'='*70}")
print(f"  buy_threshold: {best['buy_threshold']}")
print(f"  stop_loss: {best['stop_loss']*100:.0f}%")
print(f"  take_profit: {best['take_profit']*100:.0f}%")
print(f"  position_size: {best['position_size']*100:.0f}%")
print(f"  max_positions: {best['max_positions']}")
print(f"  max_trades_day: {best['max_trades_day']}")
print(f"  预期收益: ${best['total_profit']:+.2f} ({best['return_pct']:+.2f}%)")
print(f"  预期胜率: {best['win_rate']}%")
