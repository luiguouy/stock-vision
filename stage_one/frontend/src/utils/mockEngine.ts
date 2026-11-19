// 前端技术分析与降级计算引擎 (与后端 analysis.py 算法保持双向同步)

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
  bars_count?: number;
  total_return_pct?: number;
  period_amplitude_pct?: number;
  avg_daily_range_pct?: number;
  win_rate_pct?: number;
  max_rise: RangeStatPoint;
  max_fall: RangeStatPoint;
}

// 多周期算法参数表 (与后端 analysis.py PERIOD_PARAMS 保持一致)
const PERIOD_PARAMS: Record<string, { half_life: number; window: number }> = {
  '5m': { half_life: 30, window: 5 },
  '15m': { half_life: 30, window: 5 },
  '1h': { half_life: 30, window: 5 },
  '4h': { half_life: 30, window: 5 },
  '1d': { half_life: 60, window: 5 },
  '1w': { half_life: 26, window: 4 },
  '1M': { half_life: 12, window: 3 },
  '3M': { half_life: 8, window: 3 },
  '6M': { half_life: 5, window: 3 },
  '1Y': { half_life: 4, window: 3 },
};

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

// 与后端 analysis.py PERIOD_CLAMP_BOUNDS 保持一致
const PERIOD_CLAMP_BOUNDS: Record<string, [number, number]> = {
  '5m': [0.0015, 0.008],
  '15m': [0.002, 0.010],
  '1h': [0.003, 0.015],
  '4h': [0.004, 0.020],
  '1d': [0.006, 0.025],
  '1w': [0.012, 0.050],
  '1M': [0.020, 0.080],
  '3M': [0.030, 0.120],
  '6M': [0.040, 0.150],
  '1Y': [0.050, 0.200],
};

function median(values: number[]): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

/**
 * 自适应支撑阻力位计算（与重构后后端 analysis.calculate_sr_levels 严格一致）：
 * True Range 中位数相对波动率阈值 + 分周期钳制 + 簇首锚点防漂移单趟聚类
 */
export function calculateSRLevels(data: KLinePoint[], windowSize: number = 5, period: string = '1d'): SRLevel[] {
  const totalLen = data.length;
  const params = PERIOD_PARAMS[period] || PERIOD_PARAMS['1d'];
  const halfLife = params.half_life;
  const win = windowSize === 5 && period !== '1d' ? params.window : windowSize;

  if (totalLen < win * 2 + 1) return [];

  const latestPrice = data[totalLen - 1].close;
  if (latestPrice <= 0) return [];

  // 1. 相对波动率自适应阈值（含隔夜跳空的 True Range 中位数）
  const lookback = Math.min(20, totalLen - 1);
  const relTrList: number[] = [];
  for (let i = totalLen - lookback; i < totalLen; i++) {
    const prevClose = Math.max(data[i - 1].close, 1e-6);
    const tr = Math.max(
      data[i].high - data[i].low,
      Math.abs(data[i].high - prevClose),
      Math.abs(data[i].low - prevClose)
    );
    relTrList.push(tr / prevClose);
  }
  const relTrMed = median(relTrList);
  const [loBound, hiBound] = PERIOD_CLAMP_BOUNDS[period] || [0.006, 0.025];
  const relThreshold = Math.max(loBound, Math.min(relTrMed * 0.8, hiBound));

  // 2. 局部极值提取并升序排列
  const extrema = findExtrema(data, win);
  if (extrema.length === 0) return [];
  extrema.sort((a, b) => a.price - b.price);

  // 3. O(M) 簇首锚点防漂移单趟聚类
  const clusters: { anchor: number; price: number; weight: number; count: number }[] = [];
  for (const { price, idx } of extrema) {
    const barsAgo = totalLen - 1 - idx;
    const weight = Math.pow(0.5, barsAgo / halfLife);
    const last = clusters[clusters.length - 1];

    if (last && (price - last.anchor) / Math.max(last.anchor, 1e-6) <= relThreshold) {
      const totalW = last.weight + weight;
      last.price = (last.price * last.weight + price * weight) / totalW;
      last.weight = totalW;
      last.count++;
    } else {
      clusters.push({ anchor: price, price, weight, count: 1 });
    }
  }

  // 4. 划分支撑/阻力并按临近度综合打分
  const maxW = clusters.reduce((m, c) => Math.max(m, c.weight), 1.0);
  const supportCandidates: (SRLevel & { score: number })[] = [];
  const resistanceCandidates: (SRLevel & { score: number })[] = [];

  clusters.forEach((c) => {
    const levelPrice = c.price;
    const distPct = Math.abs(levelPrice - latestPrice) / Math.max(latestPrice, 1e-6);
    const proximityFactor = 1.0 / (1.0 + 8.0 * distPct);
    const score = c.weight * proximityFactor;
    const relW = c.weight / Math.max(maxW, 1e-6);

    let stars = 2;
    let rank: 'Weak' | 'Medium' | 'Strong' = 'Weak';
    if (c.weight >= 3.5 || (maxW >= 1.5 && relW >= 0.85)) {
      stars = 5;
      rank = 'Strong';
    } else if (c.weight >= 2.0 || (maxW >= 1.0 && relW >= 0.50)) {
      stars = 3;
      rank = 'Medium';
    }

    const item = {
      price: Number(levelPrice.toFixed(2)),
      count: c.count,
      stars,
      level: rank,
      score,
    };

    if (levelPrice < latestPrice) {
      supportCandidates.push({ ...item, type: 'support' });
    } else if (levelPrice > latestPrice) {
      resistanceCandidates.push({ ...item, type: 'resistance' });
    }
  });

  supportCandidates.sort((a, b) => b.score - a.score);
  resistanceCandidates.sort((a, b) => b.score - a.score);

  return [...resistanceCandidates.slice(0, 3), ...supportCandidates.slice(0, 3)].map(
    ({ score: _score, ...item }) => item
  );
}

/**
 * 区间量化统计（与后端 analysis.calculate_range_stats 算法及输出结构一致）
 */
export function calculateRangeStats(data: KLinePoint[], sDate: string, eDate: string): RangeStats | null {
  const s = sDate.slice(0, 10);
  const e = eDate.slice(0, 10);
  const rangeData = data.filter((d) => d.time.slice(0, 10) >= s && d.time.slice(0, 10) <= e);
  if (rangeData.length === 0) return null;

  let trough = rangeData[0];
  let maxRisePct = 0;
  let riseStart = trough.time.slice(0, 10);
  let riseEnd = trough.time.slice(0, 10);
  for (let i = 0; i < rangeData.length; i++) {
    const d = rangeData[i];
    if (d.low < trough.low) trough = d;
    if (trough.low > 0) {
      const rally = ((d.high - trough.low) / trough.low) * 100;
      if (rally > maxRisePct) {
        maxRisePct = rally;
        riseStart = trough.time.slice(0, 10);
        riseEnd = d.time.slice(0, 10);
      }
    }
  }

  let peak = rangeData[0];
  let maxFallPct = 0;
  let fallStart = peak.time.slice(0, 10);
  let fallEnd = peak.time.slice(0, 10);
  for (let i = 0; i < rangeData.length; i++) {
    const d = rangeData[i];
    if (d.high > peak.high) peak = d;
    if (peak.high > 0) {
      const drawdown = ((d.low - peak.high) / peak.high) * 100;
      if (drawdown < maxFallPct) {
        maxFallPct = drawdown;
        fallStart = peak.time.slice(0, 10);
        fallEnd = d.time.slice(0, 10);
      }
    }
  }

  const firstOpen = rangeData[0].open > 0 ? rangeData[0].open : rangeData[0].close;
  const lastClose = rangeData[rangeData.length - 1].close;
  const totalReturnPct = firstOpen > 0 ? ((lastClose - firstOpen) / firstOpen) * 100 : 0;

  const periodMin = Math.min(...rangeData.map((d) => d.low));
  const periodMax = Math.max(...rangeData.map((d) => d.high));
  const periodAmplitudePct = periodMin > 0 ? ((periodMax - periodMin) / periodMin) * 100 : 0;

  const dailyRanges = rangeData.map((d) => (d.low > 0 ? ((d.high - d.low) / d.low) * 100 : 0));
  const avgDailyRangePct = dailyRanges.reduce((acc, v) => acc + v, 0) / rangeData.length;

  const upBars = rangeData.filter((d) => d.close >= d.open).length;
  const winRatePct = (upBars / rangeData.length) * 100;

  return {
    bars_count: rangeData.length,
    total_return_pct: Number(totalReturnPct.toFixed(2)),
    period_amplitude_pct: Number(periodAmplitudePct.toFixed(2)),
    avg_daily_range_pct: Number(avgDailyRangePct.toFixed(2)),
    win_rate_pct: Number(winRatePct.toFixed(2)),
    max_rise: { pct: Number(maxRisePct.toFixed(2)), start: riseStart, end: riseEnd },
    max_fall: { pct: Number(maxFallPct.toFixed(2)), start: fallStart, end: fallEnd },
  };
}
