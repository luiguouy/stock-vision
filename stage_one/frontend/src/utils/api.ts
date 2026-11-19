// 股票技术分析平台 - 前端 HTTP API 客户端
import {
  calculateSRLevels,
  calculateRangeStats,
  type KLinePoint,
  type SRLevel,
  type RangeStatPoint,
  type RangeStats,
} from './mockEngine';

export * from './symbols';
export {
  calculateSRLevels,
  calculateRangeStats,
  type KLinePoint,
  type SRLevel,
  type RangeStatPoint,
  type RangeStats,
};

export const BASE_URL = '/api';

export const SUPPORTED_PERIODS = ['5m', '15m', '1h', '4h', '1d', '1w', '1M', '3M', '6M', '1Y'] as const;
export type Period = (typeof SUPPORTED_PERIODS)[number];

export const PERIOD_LABELS: Record<Period, string> = {
  '5m': '5分',
  '15m': '15分',
  '1h': '1小时',
  '4h': '4小时',
  '1d': '日K',
  '1w': '周K',
  '1M': '月K',
  '3M': '季K',
  '6M': '半年K',
  '1Y': '年K',
};

export interface StockInfo {
  symbol: string;
  name: string;
  pinyin?: string;
}

export interface WatchGroup {
  id: string;
  name: string;
  stocks: string[];
}

export interface AnalysisResponse {
  sr_levels: SRLevel[];
  statistics: RangeStats;
}

export interface LeveragePairInfo {
  underlying: string;
  leverage: number;
  label: string;
}

export const LEVERAGE_ETF_MAP: Record<string, LeveragePairInfo> = {
  usNVDL: { underlying: 'usNVDA', leverage: 2, label: 'NVDA 2x做多' },
  usAMDL: { underlying: 'usAMD', leverage: 2, label: 'AMD 2x做多' },
  usMUU: { underlying: 'usMU', leverage: 2, label: 'MU 2x做多' },
  usTQQQ: { underlying: 'usQQQ', leverage: 3, label: 'QQQ 3x做多' },
  usSQQQ: { underlying: 'usQQQ', leverage: -3, label: 'QQQ 3x做空' },
  usSOXL: { underlying: 'usSOXX', leverage: 3, label: 'SOXX 3x做多' },
  usSOXS: { underlying: 'usSOXX', leverage: -3, label: 'SOXX 3x做空' },
};

/** 模糊检索股票列表 */
export async function searchStocks(keyword: string): Promise<StockInfo[]> {
  try {
    const url = keyword
      ? `${BASE_URL}/search?keyword=${encodeURIComponent(keyword)}`
      : `${BASE_URL}/search`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('网络请求异常，搜不到股票');
    return await response.json();
  } catch (error) {
    console.warn('Error searching stocks:', error);
    throw new Error('网络连接异常，搜不到该股票');
  }
}

/** 获取股票多周期 K 线数据 */
export async function getKLines(
  symbol: string,
  period: Period = '1d',
  full: boolean = false,
  fresh: boolean = false,
  signal?: AbortSignal
): Promise<KLinePoint[]> {
  const params = new URLSearchParams({ symbol, period });
  if (full) params.set('full', 'true');
  if (fresh) params.set('fresh', 'true');
  const response = await fetch(`${BASE_URL}/klines?${params.toString()}`, { cache: 'no-store', signal });
  if (!response.ok) {
    let detail = '服务器返回异常';
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) detail = errJson.detail;
    } catch {}
    throw new Error(`无法加载 K 线数据：${detail}`);
  }
  return await response.json();
}

/** 获取股票技术分析（支撑位、阻力位、区间涨跌统计），后端不可用时降级使用前端计算引擎 */
export async function getStockAnalysis(
  symbol: string,
  startDate: string,
  endDate: string,
  klineCache?: KLinePoint[],
  period: Period = '1d'
): Promise<AnalysisResponse | null> {
  try {
    const response = await fetch(`${BASE_URL}/analysis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, start_date: startDate, end_date: endDate, period }),
    });
    if (!response.ok) throw new Error('服务器端技术分析接口错误');
    return await response.json();
  } catch (error) {
    console.warn('Backend analysis failed, running frontend calculation:', error);
    const klines = klineCache && klineCache.length > 0 ? klineCache : await getKLines(symbol, period);
    if (!klines || klines.length === 0) throw new Error('无法提取 K 线行情进行分析');

    const sr_levels = calculateSRLevels(klines, 5, period);
    const statistics = calculateRangeStats(klines, startDate, endDate);

    return {
      sr_levels,
      statistics: statistics || {
        bars_count: 0,
        total_return_pct: 0,
        period_amplitude_pct: 0,
        avg_daily_range_pct: 0,
        win_rate_pct: 0,
        max_rise: { pct: 0, start: startDate.slice(0, 10), end: startDate.slice(0, 10) },
        max_fall: { pct: 0, start: startDate.slice(0, 10), end: startDate.slice(0, 10) },
      },
    };
  }
}

/** 自选分组持久化接口 */
export async function getWatchlist(): Promise<WatchGroup[]> {
  try {
    const response = await fetch(`${BASE_URL}/watchlist`, { method: 'GET' });
    if (!response.ok) throw new Error('load failed');
    const json = await response.json();
    if (Array.isArray(json.groups)) return json.groups as WatchGroup[];
    return [];
  } catch {
    return [];
  }
}

export async function saveWatchlist(groups: WatchGroup[]): Promise<void> {
  try {
    await fetch(`${BASE_URL}/watchlist`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ groups }),
    });
  } catch {}
}

/** 执行价格行为交易策略 */
export async function runPAStrategy(
  symbol: string,
  period: string = '1d',
  mode: string = 'swing',
  klines?: KLinePoint[]
): Promise<any> {
  const body: any = { symbol, period, mode, draw_on_chart: true };
  if (klines && klines.length > 0) {
    body.klines = klines;
  }
  const response = await fetch(`${BASE_URL}/control/strategy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(`策略执行失败: ${err}`);
  }
  return await response.json();
}
