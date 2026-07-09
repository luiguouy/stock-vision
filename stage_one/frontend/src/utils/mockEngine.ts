// 前端技术分析纯计算引擎 (移植自后端 analysis.py)
// 用于当后端 API 发生 CORS 错误或不可用时，前端自包含降级运行计算分析
// 支持多周期: 支撑阻力位会随K线周期自适应调整半衰期

export interface KLinePoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SRLevel {
  price: number;
  count: number;
  type: 'support' | 'resistance';
  stars: number;
  level: 'Weak' | 'Medium' | 'Strong';
}

export interface RangeStatPoint {
  pct: number;
  start: string;
  end: string;
}

export interface RangeStats {
  max_rise: RangeStatPoint;
  max_fall: RangeStatPoint;
}

// 多周期算法参数表 (与后端 analysis.py PERIOD_PARAMS 保持一致)
const PERIOD_PARAMS: Record<string, { half_life: number; window: number }> = {
  '1d': { half_life: 60, window: 5 },
  '1w': { half_life: 26, window: 4 },
  '1M': { half_life: 12, window: 3 },
  '3M': { half_life: 8, window: 3 },
  '6M': { half_life: 5, window: 3 },
  '1Y': { half_life: 4, window: 3 },
};

/**
 * 局部极值寻找算法 (保留价格和K线位置索引)
 */
function findExtrema(data: KLinePoint[], windowSize: number = 5) {
  const extrema: { price: number; idx: number }[] = [];
  for (let i = windowSize; i < data.length - windowSize; i++) {
    let isMax = true;
    let isMin = true;
    for (let j = i - windowSize; j <= i + windowSize; j++) {
      if (data[j].high > data[i].high) isMax = false;
      if (data[j].low < data[i].low) isMin = false;
    }
    if (isMax) extrema.push({ price: data[i].high, idx: i });
    if (isMin) extrema.push({ price: data[i].low, idx: i });
  }
  return extrema;
}

/**
 * 前端自适应阻力支撑位计算逻辑 (与后端算法完全一致，支持多周期)
 * @param data K线数据
 * @param windowSize 局部极值窗口 (默认5)
 * @param period K线周期 '1d'/'1w'/'1M'，决定半衰期 (默认 '1d')
 */
export function calculateSRLevels(data: KLinePoint[], windowSize: number = 5, period: string = '1d'): SRLevel[] {
  const totalLen = data.length;
  
  // 根据周期获取参数
  const params = PERIOD_PARAMS[period] || PERIOD_PARAMS['1d'];
  const halfLife = params.half_life;
  // 若调用方未显式指定非默认 window，则使用周期对应的默认值
  const win = (windowSize === 5 && period !== '1d') ? params.window : windowSize;
  
  if (totalLen < win * 2 + 1) return [];

  const latestPrice = data[totalLen - 1].close;

  // 1. 自适应合并阈值：最近 20 根K线均波幅
  const lookback = Math.min(20, totalLen);
  let totalRange = 0;
  for (let i = totalLen - lookback; i < totalLen; i++) {
    totalRange += (data[i].high - data[i].low);
  }
  const atrApprox = totalRange / lookback;

  // 设置安全边界 [0.6%, 2.5%]
  const minDist = latestPrice * 0.006;
  const maxDist = latestPrice * 0.025;
  const absThreshold = Math.max(minDist, Math.min(atrApprox * 0.8, maxDist));

  // 2. 提取局部极值点
  const extrema = findExtrema(data, win);
  if (extrema.length === 0) return [];

  // 按价格从低到高排序
  extrema.sort((a, b) => a.price - b.price);

  // 3. 价格合并与时间衰减权重累加 (半衰期随周期变化)
  const clusters: { price: number; weight: number; count: number }[] = [];

  extrema.forEach(({ price, idx }) => {
    const barsAgo = totalLen - 1 - idx;
    const weight = Math.pow(0.5, barsAgo / halfLife);

    let merged = false;
    for (const c of clusters) {
      if (Math.abs(c.price - price) < absThreshold) {
        c.price = (c.price * c.weight + price * weight) / (c.weight + weight);
        c.weight += weight;
        c.count++;
        merged = true;
        break;
      }
    }
    if (!merged) {
      clusters.push({ price, weight, count: 1 });
    }
  });

  // 4. 重划支阻与接近度综合打分
  const supportCandidates: (SRLevel & { score: number })[] = [];
  const resistanceCandidates: (SRLevel & { score: number })[] = [];

  clusters.forEach(c => {
    const levelPrice = c.price;
    const distPct = Math.abs(levelPrice - latestPrice) / latestPrice;
    
    // 临近度因数
    const proximityFactor = 1.0 / (1.0 + 8.0 * distPct);
    const score = c.weight * proximityFactor;

    // 确定强弱和星级
    let stars = 2;
    let rank: 'Weak' | 'Medium' | 'Strong' = 'Weak';
    if (c.weight >= 3.5) {
      stars = 5;
      rank = 'Strong';
    } else if (c.weight >= 2.0) {
      stars = 3;
      rank = 'Medium';
    }

    const item = {
      price: Number(levelPrice.toFixed(2)),
      count: c.count,
      stars,
      level: rank,
      score
    };

    if (levelPrice < latestPrice) {
      supportCandidates.push({ ...item, type: 'support' });
    } else if (levelPrice > latestPrice) {
      resistanceCandidates.push({ ...item, type: 'resistance' });
    }
  });

  // 5. 按最终 Score 排序并各取前 3 个
  supportCandidates.sort((a, b) => b.score - a.score);
  resistanceCandidates.sort((a, b) => b.score - a.score);

  return [
    ...resistanceCandidates.slice(0, 3),
    ...supportCandidates.slice(0, 3)
  ];
}

/**
 * 前端区间最大涨跌统计
 *
 * 采用"运行峰值 / 运行谷值"的最大回撤 / 最大反弹算法：
 *   - 最大连贯上涨：扫描区间内每一个低点（运行中的最低点），记录从该谷值到其后
 *     最高点的累计涨幅峰值。不再只锁定"全局最低点之后"，因此对任何区间都会响应。
 *   - 最大连贯下跌：扫描区间内每一个高点（运行中的最高点），记录从该峰值到其后
 *     最低点的最大跌幅（最大回撤）。旧算法只取"全局最高点之后"的最低点，当区间
 *     最高点落在末尾时（近期上涨行情极常见）会退化为 0 且不随区间变化，故改为
 *     全程跟踪运行峰值，能正确捕获发生在最高点之前的大跌。
 *
 * 该实现与后端 analysis.calculate_range_stats 保持一致。
 */
export function calculateRangeStats(data: KLinePoint[], sDate: string, eDate: string): RangeStats | null {
  const rangeData = data.filter(d => d.time >= sDate && d.time <= eDate);
  if (rangeData.length === 0) return null;

  // 最大连贯上涨：从运行谷值到其后最高点的区间涨幅峰值
  let trough = rangeData[0];
  let maxRisePct = 0;
  let riseStart = trough.time;
  let riseEnd = trough.time;
  for (let i = 0; i < rangeData.length; i++) {
    const d = rangeData[i];
    if (d.low < trough.low) trough = d;
    if (trough.low > 0) {
      const rally = ((d.high - trough.low) / trough.low) * 100;
      if (rally > maxRisePct) {
        maxRisePct = rally;
        riseStart = trough.time;
        riseEnd = d.time;
      }
    }
  }

  // 最大连贯下跌（最大回撤）：从运行峰值到其后最低点的区间跌幅谷值
  let peak = rangeData[0];
  let maxFallPct = 0;
  let fallStart = peak.time;
  let fallEnd = peak.time;
  for (let i = 0; i < rangeData.length; i++) {
    const d = rangeData[i];
    if (d.high > peak.high) peak = d;
    if (peak.high > 0) {
      const drawdown = ((d.low - peak.high) / peak.high) * 100;
      if (drawdown < maxFallPct) {
        maxFallPct = drawdown;
        fallStart = peak.time;
        fallEnd = d.time;
      }
    }
  }

  return {
    max_rise: { pct: maxRisePct, start: riseStart, end: riseEnd },
    max_fall: { pct: maxFallPct, start: fallStart, end: fallEnd }
  };
}
