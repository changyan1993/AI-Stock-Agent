/**
 * AI Stock Trading - Technical Analysis Script
 *
 * Usage:
 *   node analyze.js all          - 分析全部16只股票
 *   node analyze.js SOFI WMT     - 分析指定股票
 *   node analyze.js scan         - 只显示有买入信号的股票
 *   node analyze.js detail SOFI  - 显示单只股票详细分析
 *   node analyze.js --json       - 输出JSON格式（供cron调用）
 */

const https = require('https');

// ============== 配置 ==============
const WATCHLIST = ['SOFI', 'WMT', 'INTC', 'NFLX', 'BABA', 'COIN', 'PLTR', 'SNAP', 'NIO', 'MARA', 'LCID', 'F', 'RIVN', 'PINS', 'T', 'OPEN'];
const MAX_PRICE = 50;  // 只看 $50 以下的股票
const SCREENER_IDS = ['most_actives', 'day_gainers', 'undervalued_growth_stocks'];
const FINNHUB_KEY = 'd6ogpt1r01qnu98i0r10d6ogpt1r01qnu98i0r1g';

// 新闻情绪关键词
const BULLISH_WORDS = ['upgrade','beat','surpass','record','growth','profit','surge','rally','breakout','buy','outperform','raise','boost','strong','exceed','bullish','positive','gain','recover','rebound','acquisition','partnership','approve','launch','expand'];
const BEARISH_WORDS = ['downgrade','miss','cut','loss','decline','crash','sell','underperform','weak','disappoint','layoff','lawsuit','recall','bankruptcy','debt','bearish','negative','drop','warning','investigate','fraud','default','slash','delay','concern'];

// ============== 股票发现 ==============

/**
 * 从 Yahoo Finance 筛选器获取股票池
 * 自动发现：最活跃、今日涨幅榜、低估成长股
 * 过滤条件：价格 <= MAX_PRICE，排除已在关注列表的
 */
function fetchScreener(scrId) {
  return new Promise((resolve, reject) => {
    const url = `https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds=${scrId}&count=100`;
    const options = {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
    };
    https.get(url, options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (json.finance && json.finance.result && json.finance.result[0]) {
            const quotes = json.finance.result[0].quotes || [];
            const filtered = quotes
              .filter(q => q.regularMarketPrice && q.regularMarketPrice <= MAX_PRICE)
              .filter(q => q.regularMarketPrice >= 2) // 排除仙股
              .filter(q => q.averageDailyVolume3Month > 1000000) // 日均成交量 > 100万
              .map(q => ({
                symbol: q.symbol,
                price: q.regularMarketPrice,
                change: q.regularMarketChangePercent ? round(q.regularMarketChangePercent, 2) : 0,
                name: q.shortName || q.symbol,
                volume: q.regularMarketVolume || 0,
                source: scrId
              }));
            resolve(filtered);
          } else {
            resolve([]);
          }
        } catch (e) {
          resolve([]);
        }
      });
    }).on('error', () => resolve([]));
  });
}

/**
 * 发现新股票：从多个 Yahoo 筛选器获取候选
 * 合并去重，排除已有关注列表的
 * 返回按交易量排序的股票列表
 */
async function discoverStocks() {
  console.log('\n🔍 扫描全市场...');

  const promises = SCREENER_IDS.map(id => fetchScreener(id));
  const results = await Promise.all(promises);

  // 合并去重
  const seen = new Set(WATCHLIST);
  const discovered = [];

  results.forEach(stocks => {
    stocks.forEach(s => {
      if (!seen.has(s.symbol)) {
        seen.add(s.symbol);
        discovered.push(s);
      }
    });
  });

  // 按成交量排序（流动性好的优先）
  discovered.sort((a, b) => b.volume - a.volume);

  console.log(`   从 ${SCREENER_IDS.length} 个筛选器发现 ${discovered.length} 只新股票（<=$${MAX_PRICE}）\n`);

  return discovered;
}

// ============== 数据获取 ==============
function fetchChart(symbol) {
  return new Promise((resolve, reject) => {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?range=3mo&interval=1d`;
    const options = {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
    };
    https.get(url, options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (json.chart && json.chart.result && json.chart.result[0]) {
            const result = json.chart.result[0];
            const quotes = result.indicators.quote[0];
            const timestamps = result.timestamp || [];
            const closes = quotes.close || [];
            const highs = quotes.high || [];
            const lows = quotes.low || [];
            const opens = quotes.open || [];
            const volumes = quotes.volume || [];

            // 过滤掉 null 值的天数
            const days = [];
            for (let i = 0; i < timestamps.length; i++) {
              if (closes[i] != null && highs[i] != null && lows[i] != null) {
                days.push({
                  date: new Date(timestamps[i] * 1000).toISOString().split('T')[0],
                  open: opens[i],
                  high: highs[i],
                  low: lows[i],
                  close: closes[i],
                  volume: volumes[i] || 0
                });
              }
            }
            resolve({ symbol, days, meta: result.meta });
          } else {
            reject(new Error(`No data for ${symbol}`));
          }
        } catch (e) {
          reject(new Error(`Parse error for ${symbol}: ${e.message}`));
        }
      });
    }).on('error', reject);
  });
}

// ============== 技术指标计算 ==============

/**
 * RSI (Relative Strength Index) - 相对强弱指标
 * 衡量股票是超买还是超卖
 * period: 通常用14天
 */
function calcRSI(closes, period = 14) {
  if (closes.length < period + 1) return null;

  let gains = [];
  let losses = [];

  for (let i = 1; i < closes.length; i++) {
    const change = closes[i] - closes[i - 1];
    gains.push(change > 0 ? change : 0);
    losses.push(change < 0 ? Math.abs(change) : 0);
  }

  // 用 Wilder's smoothing method（和 TradingView 一致）
  let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
  let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;

  for (let i = period; i < gains.length; i++) {
    avgGain = (avgGain * (period - 1) + gains[i]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i]) / period;
  }

  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return 100 - (100 / (1 + rs));
}

/**
 * SMA (Simple Moving Average) - 简单移动平均线
 * period天收盘价的平均值
 */
function calcSMA(closes, period) {
  if (closes.length < period) return null;
  const slice = closes.slice(-period);
  return slice.reduce((a, b) => a + b, 0) / period;
}

/**
 * EMA (Exponential Moving Average) - 指数移动平均线
 * 对近期价格赋予更高权重
 */
function calcEMA(closes, period) {
  if (closes.length < period) return null;
  const multiplier = 2 / (period + 1);

  // 用前 period 个数据的 SMA 作为起始 EMA
  let ema = closes.slice(0, period).reduce((a, b) => a + b, 0) / period;

  for (let i = period; i < closes.length; i++) {
    ema = (closes[i] - ema) * multiplier + ema;
  }
  return ema;
}

/**
 * MACD (Moving Average Convergence Divergence) - 指数平滑异同移动平均线
 * 判断趋势方向和转折点
 * 返回: { macd, signal, histogram }
 */
function calcMACD(closes, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
  if (closes.length < slowPeriod + signalPeriod) return null;

  // 计算完整的 EMA 序列
  function emaSequence(data, period) {
    const multiplier = 2 / (period + 1);
    const result = [];
    let ema = data.slice(0, period).reduce((a, b) => a + b, 0) / period;

    for (let i = 0; i < period; i++) result.push(null);
    result[period - 1] = ema;

    for (let i = period; i < data.length; i++) {
      ema = (data[i] - ema) * multiplier + ema;
      result.push(ema);
    }
    return result;
  }

  const fastEMA = emaSequence(closes, fastPeriod);
  const slowEMA = emaSequence(closes, slowPeriod);

  // MACD 线 = 快线 - 慢线
  const macdLine = [];
  for (let i = 0; i < closes.length; i++) {
    if (fastEMA[i] != null && slowEMA[i] != null) {
      macdLine.push(fastEMA[i] - slowEMA[i]);
    }
  }

  if (macdLine.length < signalPeriod) return null;

  // Signal 线 = MACD 线的 9日 EMA
  const multiplier = 2 / (signalPeriod + 1);
  let signal = macdLine.slice(0, signalPeriod).reduce((a, b) => a + b, 0) / signalPeriod;

  for (let i = signalPeriod; i < macdLine.length; i++) {
    signal = (macdLine[i] - signal) * multiplier + signal;
  }

  const macd = macdLine[macdLine.length - 1];
  const histogram = macd - signal;

  // 判断前一天的 MACD 和 signal 来检测交叉
  let prevMacd = macdLine[macdLine.length - 2];
  const multiplierPrev = 2 / (signalPeriod + 1);
  let prevSignal = macdLine.slice(0, signalPeriod).reduce((a, b) => a + b, 0) / signalPeriod;
  for (let i = signalPeriod; i < macdLine.length - 1; i++) {
    prevSignal = (macdLine[i] - prevSignal) * multiplierPrev + prevSignal;
  }
  const prevHistogram = prevMacd - prevSignal;

  let crossover = 'none';
  if (prevHistogram <= 0 && histogram > 0) crossover = 'golden'; // 金叉
  if (prevHistogram >= 0 && histogram < 0) crossover = 'death';  // 死叉

  return { macd: round(macd, 4), signal: round(signal, 4), histogram: round(histogram, 4), crossover };
}

/**
 * ATR (Average True Range) - 平均真实波幅
 * 衡量股票的波动性，用于动态设置止损
 */
function calcATR(highs, lows, closes, period = 14) {
  if (closes.length < period + 1) return null;

  const trueRanges = [];
  for (let i = 1; i < closes.length; i++) {
    const tr = Math.max(
      highs[i] - lows[i],                    // 当日最高-最低
      Math.abs(highs[i] - closes[i - 1]),     // 当日最高-昨收
      Math.abs(lows[i] - closes[i - 1])       // 当日最低-昨收
    );
    trueRanges.push(tr);
  }

  // Wilder's smoothing
  let atr = trueRanges.slice(0, period).reduce((a, b) => a + b, 0) / period;
  for (let i = period; i < trueRanges.length; i++) {
    atr = (atr * (period - 1) + trueRanges[i]) / period;
  }

  return atr;
}

/**
 * 成交量分析
 * 比较今天成交量和20日平均成交量
 */
function calcVolumeRatio(volumes) {
  if (volumes.length < 20) return null;
  const avg20 = volumes.slice(-21, -1).reduce((a, b) => a + b, 0) / 20;
  const current = volumes[volumes.length - 1];
  return avg20 > 0 ? current / avg20 : null;
}

// ============== 市场情绪 & 新闻分析 ==============

/**
 * 获取大盘趋势 (SPY, QQQ) 和 VIX 恐慌指数
 * 返回: { spy: {price, change%}, qqq: {price, change%}, vix: {price, level}, score: -2 ~ +2 }
 */
function fetchMarketSentiment() {
  return new Promise((resolve) => {
    const symbols = ['SPY', 'QQQ', '^VIX'];
    const promises = symbols.map(sym => {
      return new Promise((res) => {
        const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?range=5d&interval=1d`;
        const options = {
          headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
        };
        https.get(url, options, (response) => {
          let data = '';
          response.on('data', chunk => data += chunk);
          response.on('end', () => {
            try {
              const json = JSON.parse(data);
              const result = json.chart.result[0];
              const closes = result.indicators.quote[0].close.filter(c => c !== null);
              const current = closes[closes.length - 1];
              const prev = closes.length >= 2 ? closes[closes.length - 2] : current;
              const change = ((current - prev) / prev) * 100;
              res({ symbol: sym, price: current, change: round(change, 2) });
            } catch (e) { res(null); }
          });
        }).on('error', () => res(null));
      });
    });

    Promise.all(promises).then(results => {
      const spy = results[0];
      const qqq = results[1];
      const vix = results[2];

      let score = 0;
      let signals = [];

      // SPY 趋势
      if (spy) {
        if (spy.change > 0.5) { score += 1; signals.push(`SPY ${spy.change > 0 ? '+' : ''}${spy.change}% 大盘上涨 ✓`); }
        else if (spy.change < -0.5) { score -= 1; signals.push(`SPY ${spy.change}% 大盘下跌 ✗`); }
        else { signals.push(`SPY ${spy.change > 0 ? '+' : ''}${spy.change}% 大盘平稳`); }
      }

      // QQQ 趋势
      if (qqq) {
        if (qqq.change > 0.5) { score += 1; signals.push(`QQQ ${qqq.change > 0 ? '+' : ''}${qqq.change}% 科技股上涨 ✓`); }
        else if (qqq.change < -0.5) { score -= 1; signals.push(`QQQ ${qqq.change}% 科技股下跌 ✗`); }
        else { signals.push(`QQQ ${qqq.change > 0 ? '+' : ''}${qqq.change}% 科技股平稳`); }
      }

      // VIX 恐慌指数
      if (vix) {
        let vixLevel;
        if (vix.price > 30) { score -= 2; vixLevel = '极度恐慌'; signals.push(`VIX ${round(vix.price,1)} 极度恐慌，不宜买入 ✗✗`); }
        else if (vix.price > 25) { score -= 1; vixLevel = '恐慌'; signals.push(`VIX ${round(vix.price,1)} 恐慌偏高 ✗`); }
        else if (vix.price > 20) { vixLevel = '偏高'; signals.push(`VIX ${round(vix.price,1)} 波动偏高 ⚠`); }
        else if (vix.price < 15) { score += 1; vixLevel = '平静'; signals.push(`VIX ${round(vix.price,1)} 市场平静 ✓`); }
        else { vixLevel = '正常'; signals.push(`VIX ${round(vix.price,1)} 正常水平`); }
        vix.level = vixLevel;
      }

      resolve({ spy, qqq, vix, score, signals });
    });
  });
}

/**
 * 获取个股新闻并分析情绪
 * Finnhub API: /company-news
 * 返回: { headlines: [], sentiment: 'bullish'/'bearish'/'neutral', score: -2 ~ +2 }
 */
function fetchNews(symbol) {
  return new Promise((resolve) => {
    const today = new Date();
    const weekAgo = new Date(today - 7 * 24 * 60 * 60 * 1000);
    const from = weekAgo.toISOString().split('T')[0];
    const to = today.toISOString().split('T')[0];
    const url = `https://finnhub.io/api/v1/company-news?symbol=${symbol}&from=${from}&to=${to}&token=${FINNHUB_KEY}`;

    https.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const articles = JSON.parse(data);
          if (!Array.isArray(articles) || articles.length === 0) {
            resolve({ headlines: [], sentiment: 'neutral', score: 0, bullish: 0, bearish: 0, total: 0, signals: [] });
            return;
          }

          // 取最近20条新闻
          const recent = articles.slice(0, 20);
          let bullishCount = 0;
          let bearishCount = 0;

          recent.forEach(article => {
            const text = (article.headline || '').toLowerCase();
            const hasBull = BULLISH_WORDS.some(w => text.includes(w));
            const hasBear = BEARISH_WORDS.some(w => text.includes(w));
            if (hasBull && !hasBear) bullishCount++;
            else if (hasBear && !hasBull) bearishCount++;
          });

          let score = 0;
          let sentiment = 'neutral';
          const signals = [];

          const total = bullishCount + bearishCount;
          if (total >= 3) {
            const bullRatio = bullishCount / total;
            if (bullRatio >= 0.7) {
              score = 2;
              sentiment = 'bullish';
              signals.push(`新闻情绪强烈看多 (${bullishCount}正/${bearishCount}负/${recent.length}篇) ✓✓`);
            } else if (bullRatio >= 0.55) {
              score = 1;
              sentiment = 'bullish';
              signals.push(`新闻情绪偏多 (${bullishCount}正/${bearishCount}负/${recent.length}篇) ✓`);
            } else if (bullRatio <= 0.3) {
              score = -2;
              sentiment = 'bearish';
              signals.push(`新闻情绪强烈看空 (${bullishCount}正/${bearishCount}负/${recent.length}篇) ✗✗`);
            } else if (bullRatio <= 0.45) {
              score = -1;
              sentiment = 'bearish';
              signals.push(`新闻情绪偏空 (${bullishCount}正/${bearishCount}负/${recent.length}篇) ✗`);
            } else {
              signals.push(`新闻情绪中性 (${bullishCount}正/${bearishCount}负/${recent.length}篇)`);
            }
          } else {
            signals.push(`新闻较少，情绪无法判断 (${recent.length}篇)`);
          }

          // 最新3条标题
          const headlines = recent.slice(0, 3).map(a => a.headline);

          resolve({ headlines, sentiment, score, bullish: bullishCount, bearish: bearishCount, total: recent.length, signals });
        } catch (e) {
          resolve({ headlines: [], sentiment: 'neutral', score: 0, bullish: 0, bearish: 0, total: 0, signals: [] });
        }
      });
    }).on('error', () => {
      resolve({ headlines: [], sentiment: 'neutral', score: 0, bullish: 0, bearish: 0, total: 0, signals: [] });
    });
  });
}

/**
 * 获取财报日历 - 财报前后3天标记高风险
 * Finnhub API: /calendar/earnings
 */
function checkEarnings(symbol) {
  return new Promise((resolve) => {
    const today = new Date();
    const from = today.toISOString().split('T')[0];
    const nextWeek = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);
    const to = nextWeek.toISOString().split('T')[0];
    const url = `https://finnhub.io/api/v1/calendar/earnings?from=${from}&to=${to}&symbol=${symbol}&token=${FINNHUB_KEY}`;

    https.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          const earnings = json.earningsCalendar || [];
          if (earnings.length > 0) {
            const nextDate = earnings[0].date;
            resolve({ hasEarnings: true, date: nextDate, signal: `⚠ 财报日 ${nextDate}，波动风险高` });
          } else {
            resolve({ hasEarnings: false, date: null, signal: null });
          }
        } catch (e) {
          resolve({ hasEarnings: false, date: null, signal: null });
        }
      });
    }).on('error', () => {
      resolve({ hasEarnings: false, date: null, signal: null });
    });
  });
}

// ============== 评分系统 ==============

function analyzeStock(data, newsData = null, marketData = null) {
  const { symbol, days, meta } = data;
  const closes = days.map(d => d.close);
  const highs = days.map(d => d.high);
  const lows = days.map(d => d.low);
  const volumes = days.map(d => d.volume);

  const currentPrice = closes[closes.length - 1];
  const prevClose = closes.length >= 2 ? closes[closes.length - 2] : currentPrice;
  const todayChange = ((currentPrice - prevClose) / prevClose) * 100;

  // 计算所有指标
  const rsi = calcRSI(closes, 14);
  const sma5 = calcSMA(closes, 5);
  const sma20 = calcSMA(closes, 20);
  const macd = calcMACD(closes);
  const atr = calcATR(highs, lows, closes, 14);
  const volumeRatio = calcVolumeRatio(volumes);

  // 评分
  let score = 0;
  const signals = [];

  // 1. RSI 信号
  if (rsi !== null) {
    if (rsi >= 30 && rsi <= 50) {
      score += 1;
      signals.push(`RSI ${round(rsi, 1)} 中低区域，有反弹空间 ✓`);
    } else if (rsi < 30) {
      score += 1;
      signals.push(`RSI ${round(rsi, 1)} 超卖区，反弹概率高 ✓`);
    } else if (rsi > 70) {
      score -= 1;
      signals.push(`RSI ${round(rsi, 1)} 超买区，风险高 ✗`);
    } else {
      signals.push(`RSI ${round(rsi, 1)} 中性`);
    }
  }

  // 2. 均线信号 - 价格在5日均线上方
  if (sma5 !== null && currentPrice > sma5) {
    score += 1;
    signals.push(`价格 $${round(currentPrice, 2)} > SMA5 $${round(sma5, 2)} 短期上升 ✓`);
  } else if (sma5 !== null) {
    signals.push(`价格 $${round(currentPrice, 2)} < SMA5 $${round(sma5, 2)} 短期下降 ✗`);
  }

  // 3. 均线排列 - 5日均线在20日均线上方
  if (sma5 !== null && sma20 !== null && sma5 > sma20) {
    score += 1;
    signals.push(`SMA5 $${round(sma5, 2)} > SMA20 $${round(sma20, 2)} 多头排列 ✓`);
  } else if (sma5 !== null && sma20 !== null) {
    signals.push(`SMA5 $${round(sma5, 2)} < SMA20 $${round(sma20, 2)} 空头排列 ✗`);
  }

  // 4. MACD 信号
  if (macd !== null) {
    if (macd.crossover === 'golden') {
      score += 2; // 金叉给2分，很强的信号
      signals.push(`MACD 金叉 (${macd.histogram > 0 ? '+' : ''}${macd.histogram}) ✓✓`);
    } else if (macd.histogram > 0) {
      score += 1;
      signals.push(`MACD 柱状图为正 (+${macd.histogram}) ✓`);
    } else if (macd.crossover === 'death') {
      score -= 1;
      signals.push(`MACD 死叉 (${macd.histogram}) ✗`);
    } else {
      signals.push(`MACD 柱状图为负 (${macd.histogram}) ✗`);
    }
  }

  // 5. 当日涨幅
  if (todayChange >= 0.5 && todayChange <= 2.0) {
    score += 1;
    signals.push(`日涨幅 ${round(todayChange, 2)}% 在理想区间 ✓`);
  } else if (todayChange > 3.0) {
    score -= 1;
    signals.push(`日涨幅 ${round(todayChange, 2)}% 过热 ✗`);
  } else if (todayChange < -2.0) {
    signals.push(`日跌幅 ${round(todayChange, 2)}% 弱势 ✗`);
  } else {
    signals.push(`日涨跌 ${round(todayChange, 2)}%`);
  }

  // 6. 成交量确认
  if (volumeRatio !== null && volumeRatio > 1.2 && todayChange > 0) {
    score += 1;
    signals.push(`成交量 ${round(volumeRatio, 1)}x 放量上涨 ✓`);
  } else if (volumeRatio !== null) {
    signals.push(`成交量 ${round(volumeRatio, 1)}x 平均水平`);
  }

  // 7. 新闻情绪（如果有数据）
  if (newsData && newsData.score !== 0) {
    score += newsData.score;
    signals.push(...newsData.signals);
  } else if (newsData) {
    signals.push(...newsData.signals);
  }

  // 8. 市场大盘环境（如果有数据）
  if (marketData && marketData.score !== 0) {
    score += marketData.score;
  }

  // 9. 财报预警（如果有数据）
  let earningsWarning = null;
  if (newsData && newsData.earnings && newsData.earnings.hasEarnings) {
    earningsWarning = newsData.earnings.signal;
    signals.push(newsData.earnings.signal);
  }

  // 决策（评分满分从6分扩展到10分）
  let action = 'SKIP';
  if (score >= 5) action = 'BUY';
  else if (score >= 3) action = 'WATCH';
  else if (score <= -1) action = 'AVOID';

  // 固定比例止损止盈（V1.1 基线：-6% / +4%，与回测对齐）
  const suggestedStop = round(currentPrice * 0.94, 2);
  const suggestedTP = round(currentPrice * 1.04, 2);

  return {
    symbol,
    price: round(currentPrice, 2),
    change: round(todayChange, 2),
    rsi: rsi ? round(rsi, 1) : null,
    sma5: sma5 ? round(sma5, 2) : null,
    sma20: sma20 ? round(sma20, 2) : null,
    macd: macd,
    atr: atr ? round(atr, 4) : null,
    volumeRatio: volumeRatio ? round(volumeRatio, 1) : null,
    newsScore: newsData ? newsData.score : null,
    newsSentiment: newsData ? newsData.sentiment : null,
    earningsWarning,
    suggestedStop,
    suggestedTP,
    score,
    action,
    signals
  };
}

// ============== 输出格式 ==============

function round(num, decimals) {
  return Math.round(num * Math.pow(10, decimals)) / Math.pow(10, decimals);
}

function printAnalysis(result, detailed = false) {
  const actionColors = {
    'BUY': '🟢 BUY',
    'WATCH': '🟡 WATCH',
    'SKIP': '⚪ SKIP',
    'AVOID': '🔴 AVOID'
  };

  console.log(`\n${'='.repeat(50)}`);
  console.log(`  ${result.symbol}  |  $${result.price}  |  ${result.change > 0 ? '+' : ''}${result.change}%  |  评分: ${result.score}/10  |  ${actionColors[result.action]}`);
  console.log('='.repeat(50));

  if (detailed || result.action === 'BUY') {
    console.log(`  RSI(14):    ${result.rsi || 'N/A'}`);
    console.log(`  SMA5:       $${result.sma5 || 'N/A'}`);
    console.log(`  SMA20:      $${result.sma20 || 'N/A'}`);
    if (result.macd) {
      console.log(`  MACD:       ${result.macd.macd} | Signal: ${result.macd.signal} | Hist: ${result.macd.histogram} | ${result.macd.crossover}`);
    }
    console.log(`  ATR(14):    $${result.atr || 'N/A'}`);
    console.log(`  Vol Ratio:  ${result.volumeRatio || 'N/A'}x`);
    console.log(`  建议止损:   $${result.suggestedStop}`);
    console.log(`  建议止盈:   $${result.suggestedTP}`);
    console.log('');
    result.signals.forEach(s => console.log(`  ${s}`));
  }
}

function printSummaryTable(results) {
  console.log('\n' + '='.repeat(70));
  console.log('  AI Stock Trading - 技术分析报告');
  console.log('  ' + new Date().toLocaleString('en-US', { timeZone: 'America/Los_Angeles', timeZoneName: 'short' }));
  console.log('='.repeat(70));

  // 按评分排序
  results.sort((a, b) => b.score - a.score);

  console.log(`\n  ${'股票'.padEnd(8)} ${'价格'.padEnd(10)} ${'涨跌'.padEnd(8)} ${'RSI'.padEnd(7)} ${'SMA趋势'.padEnd(8)} ${'MACD'.padEnd(10)} ${'评分'.padEnd(6)} 信号`);
  console.log('  ' + '-'.repeat(65));

  results.forEach(r => {
    const smaStatus = (r.sma5 && r.sma20) ? (r.sma5 > r.sma20 ? '多头' : '空头') : 'N/A';
    const macdStatus = r.macd ? (r.macd.crossover === 'golden' ? '金叉' : r.macd.histogram > 0 ? '正' : '负') : 'N/A';
    const changeStr = (r.change > 0 ? '+' : '') + r.change + '%';

    const actionIcon = { 'BUY': '🟢', 'WATCH': '🟡', 'SKIP': '⚪', 'AVOID': '🔴' };

    console.log(`  ${r.symbol.padEnd(8)} $${String(r.price).padEnd(9)} ${changeStr.padEnd(8)} ${String(r.rsi || '-').padEnd(7)} ${smaStatus.padEnd(8)} ${macdStatus.padEnd(10)} ${String(r.score).padEnd(6)} ${actionIcon[r.action]} ${r.action}`);
  });

  // 买入推荐
  const buySignals = results.filter(r => r.action === 'BUY');
  const watchSignals = results.filter(r => r.action === 'WATCH');

  console.log('\n' + '='.repeat(70));
  if (buySignals.length > 0) {
    console.log(`  🟢 买入信号 (${buySignals.length}):`);
    buySignals.forEach(r => {
      console.log(`     ${r.symbol} @ $${r.price} | 止损: $${r.suggestedStop} | 止盈: $${r.suggestedTP}`);
      r.signals.filter(s => s.includes('✓')).forEach(s => console.log(`       ${s}`));
    });
  } else {
    console.log('  🟢 暂无买入信号');
  }

  if (watchSignals.length > 0) {
    console.log(`\n  🟡 关注 (${watchSignals.length}): ${watchSignals.map(r => r.symbol).join(', ')}`);
  }
  console.log('='.repeat(70));
}

// ============== 主程序 ==============

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log('用法:');
    console.log('  node analyze.js all           - 分析关注列表16只股票');
    console.log('  node analyze.js scan          - 只显示买入/关注信号');
    console.log('  node analyze.js discover      - 扫描全市场，发现新机会');
    console.log('  node analyze.js detail SOFI   - 单只股票详细分析');
    console.log('  node analyze.js SOFI WMT      - 分析指定股票');
    console.log('  node analyze.js all --json    - JSON格式输出（供程序调用）');
    return;
  }

  const jsonMode = args.includes('--json');
  const quietMode = jsonMode;  // suppress all non-JSON output when --json is active
  const filteredArgs = args.filter(a => a !== '--json');

  let tickers = [];
  let mode = 'normal';

  if (filteredArgs[0] === 'discover') {
    // 全市场扫描模式
    const discovered = await discoverStocks();

    // 先分析关注列表
    console.log('📋 分析关注列表...');
    const watchlistResults = [];
    for (let i = 0; i < WATCHLIST.length; i += 4) {
      const batch = WATCHLIST.slice(i, i + 4);
      const promises = batch.map(async t => {
        try { return analyzeStock(await fetchChart(t)); } catch(e) { return null; }
      });
      watchlistResults.push(...(await Promise.all(promises)).filter(r => r));
      if (i + 4 < WATCHLIST.length) await new Promise(r => setTimeout(r, 500));
    }

    // 再分析发现的新股票（取前30只最活跃的）
    const topDiscovered = discovered.slice(0, 30);
    console.log(`\n🌐 分析 ${topDiscovered.length} 只新发现股票...`);
    const discoveredResults = [];
    for (let i = 0; i < topDiscovered.length; i += 4) {
      const batch = topDiscovered.slice(i, i + 4);
      const promises = batch.map(async s => {
        try { return analyzeStock(await fetchChart(s.symbol)); } catch(e) { return null; }
      });
      discoveredResults.push(...(await Promise.all(promises)).filter(r => r));
      if (i + 4 < topDiscovered.length) await new Promise(r => setTimeout(r, 500));
    }

    // 合并所有结果，按评分排序
    const allResults = [...watchlistResults, ...discoveredResults].sort((a, b) => b.score - a.score);

    console.log('\n' + '='.repeat(70));
    console.log('  🔍 全市场扫描结果 - 关注列表 + 新发现');
    console.log('  ' + new Date().toLocaleString('en-US', { timeZone: 'America/Los_Angeles', timeZoneName: 'short' }));
    console.log('='.repeat(70));

    const buySignals = allResults.filter(r => r.action === 'BUY');
    const watchSignals = allResults.filter(r => r.action === 'WATCH');

    if (buySignals.length > 0) {
      console.log(`\n  🟢 买入信号 (${buySignals.length}):`);
      buySignals.forEach(r => {
        const isNew = !WATCHLIST.includes(r.symbol);
        const tag = isNew ? ' [新发现]' : '';
        console.log(`\n     ${r.symbol}${tag} @ $${r.price} | 评分: ${r.score}/6`);
        console.log(`     止损: $${r.suggestedStop} | 止盈: $${r.suggestedTP}`);
        r.signals.filter(s => s.includes('✓')).forEach(s => console.log(`       ${s}`));
      });
    } else {
      console.log('\n  🟢 暂无买入信号');
    }

    if (watchSignals.length > 0) {
      console.log(`\n  🟡 关注 (${watchSignals.length}):`);
      watchSignals.forEach(r => {
        const isNew = !WATCHLIST.includes(r.symbol);
        const tag = isNew ? ' [新]' : '';
        console.log(`     ${r.symbol}${tag} $${r.price} (${r.change > 0 ? '+' : ''}${r.change}%) 评分:${r.score}`);
      });
    }

    console.log('\n' + '='.repeat(70));
    console.log(`  共扫描 ${allResults.length} 只股票 | 关注列表 ${watchlistResults.length} + 新发现 ${discoveredResults.length}`);
    console.log('='.repeat(70));

    if (jsonMode) {
      const output = {};
      allResults.forEach(r => { output[r.symbol] = r; });
      console.log(JSON.stringify(output, null, 2));
    }
    return;
  }

  if (filteredArgs[0] === 'all') {
    tickers = WATCHLIST;
  } else if (filteredArgs[0] === 'scan') {
    tickers = WATCHLIST;
    mode = 'scan';
  } else if (filteredArgs[0] === 'detail') {
    tickers = filteredArgs.slice(1).map(t => t.toUpperCase());
    mode = 'detail';
  } else {
    tickers = filteredArgs.map(t => t.toUpperCase());
  }

  if (tickers.length === 0) {
    console.log('请指定股票代码');
    return;
  }

  // 获取大盘情绪
  if (!quietMode) console.log('📡 获取大盘情绪...');
  const marketData = await fetchMarketSentiment();
  if (!quietMode) {
    console.log('');
    marketData.signals.forEach(s => console.log(`  ${s}`));
    console.log(`  大盘综合评分: ${marketData.score > 0 ? '+' : ''}${marketData.score}`);
    console.log('');
  }

  // 获取数据 + 新闻（并行请求，但限制并发避免被封）
  const results = [];
  const batchSize = 3;

  for (let i = 0; i < tickers.length; i += batchSize) {
    const batch = tickers.slice(i, i + batchSize);
    const promises = batch.map(async (ticker) => {
      try {
        const [chartData, newsData, earningsData] = await Promise.all([
          fetchChart(ticker),
          fetchNews(ticker),
          checkEarnings(ticker)
        ]);
        newsData.earnings = earningsData;
        return analyzeStock(chartData, newsData, marketData);
      } catch (e) {
        if (!quietMode) console.error(`  ⚠ ${ticker}: ${e.message}`);
        return null;
      }
    });

    const batchResults = await Promise.all(promises);
    results.push(...batchResults.filter(r => r !== null));

    // 批次之间等待一下避免限流
    if (i + batchSize < tickers.length) {
      await new Promise(resolve => setTimeout(resolve, 800));
    }
  }

  // 输出
  if (jsonMode) {
    const output = {};
    results.forEach(r => { output[r.symbol] = r; });
    console.log(JSON.stringify(output, null, 2));
  } else if (mode === 'scan') {
    const actionable = results.filter(r => r.action === 'BUY' || r.action === 'WATCH');
    if (actionable.length === 0) {
      console.log('\n暂无买入或关注信号。市场可能整体偏弱。');
    } else {
      actionable.forEach(r => printAnalysis(r, true));
    }
  } else if (mode === 'detail') {
    results.forEach(r => printAnalysis(r, true));
  } else if (tickers.length > 3) {
    printSummaryTable(results);
  } else {
    results.forEach(r => printAnalysis(r, true));
  }
}

main().catch(console.error);
