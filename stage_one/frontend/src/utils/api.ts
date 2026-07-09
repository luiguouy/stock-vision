// 股票技术分析平台 - 前端 API 封装
// 采用 Fetch API 构建，避免不必要的依赖
import { calculateSRLevels, calculateRangeStats } from './mockEngine';

// 使用相对路径，配合 Vite 代理或生产环境反向代理
const BASE_URL = '/api';

// 支持的K线周期（日K/周K/月K/季K/半年K/年K）
export const SUPPORTED_PERIODS = ['1d', '1w', '1M', '3M', '6M', '1Y'] as const;
export type Period = typeof SUPPORTED_PERIODS[number];

export const PERIOD_LABELS: Record<Period, string> = {
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

export interface AnalysisResponse {
  sr_levels: SRLevel[];
  statistics: RangeStats;
}

/**
 * 模糊检索股票列表
 */
export async function searchStocks(keyword: string): Promise<StockInfo[]> {
  try {
    const url = keyword ? `${BASE_URL}/search?keyword=${encodeURIComponent(keyword)}` : `${BASE_URL}/search`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('网络请求异常，搜不到股票');
    return await response.json();
  } catch (error) {
    console.warn('Error searching stocks:', error);
    throw new Error('网络连接异常，搜不到该股票');
  }
}

/**
 * 获取股票多周期K线数据
 * @param symbol 股票代码
 * @param period K线周期 '1d'/'1w'/'1M'，默认 '1d'
 * @param full   是否拉取上市以来全部历史 (默认 true)
 *
 * 说明: 仅向后端请求，不再静默降级到直连腾讯 (那只会返回约 320 根残缺数据，
 *        会误导用户以为已是完整历史)。后端失败则抛出明确错误。
 */
export async function getKLines(symbol: string, period: Period = '1d', full: boolean = true): Promise<KLinePoint[]> {
  const params = new URLSearchParams({ symbol, period });
  if (full) params.set('full', 'true');
  const response = await fetch(`${BASE_URL}/klines?${params.toString()}`);
  if (!response.ok) {
    let detail = '服务器返回异常';
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) detail = errJson.detail;
    } catch { /* ignore */ }
    throw new Error(`无法加载 K 线数据：${detail}`);
  }
  return await response.json();
}

/**
 * 获取股票技术分析（支撑位、阻力位、区间涨跌统计）
 * @param symbol 股票代码
 * @param startDate 区间开始日期
 * @param endDate 区间结束日期
 * @param klineCache 已缓存的K线数据（避免重复请求）
 * @param period K线周期 '1d'/'1w'/'1M'，默认 '1d'
 */
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
    // 降级使用前端内置计算引擎 (这是纯数学计算，不是 Mock 假 K 线数据)
    const klines = klineCache && klineCache.length > 0 ? klineCache : await getKLines(symbol, period);
    if (!klines || klines.length === 0) throw new Error('无法提取 K 线行情进行分析');
    
    const sr_levels = calculateSRLevels(klines, 5, period);
    const statistics = calculateRangeStats(klines, startDate, endDate);
    
    return {
      sr_levels,
      statistics: statistics || {
        max_rise: { pct: 0, start: '', end: '' },
        max_fall: { pct: 0, start: '', end: '' }
      }
    };
  }
}

/**
 * 生成测试用的模拟K线数据（用于前端独立调试）
 * @param symbol 股票代码
 * @param days 天数，默认320天
 * @param basePrice 基准价格，默认150
 */
export function generateMockKLines(symbol: string, days: number = 320, basePrice: number = 150): KLinePoint[] {
  const data: KLinePoint[] = [];
  let price = basePrice;
  const now = new Date();
  
  // 根据股票代码调整波动特性
  const volatilityMap: Record<string, number> = {
    'AAPL': 0.02,
    'NVDA': 0.035,
    'TSLA': 0.04,
    'MSFT': 0.018,
    'GOOGL': 0.022,
    'AMZN': 0.025,
    'META': 0.03,
    'AMD': 0.038,
    'MU': 0.045,
    'SNDK': 0.032,
  };
  
  const volatility = volatilityMap[symbol.toUpperCase()] || 0.025;
  
  for (let i = days; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    
    // 跳过周末
    if (date.getDay() === 0 || date.getDay() === 6) continue;
    
    // 随机游走算法生成价格
    const change = (Math.random() - 0.5) * 2 * volatility;
    const open = price;
    const close = price * (1 + change);
    
    // 高低点在开盘收盘价基础上增加随机波动
    const high = Math.max(open, close) * (1 + Math.random() * volatility * 0.5);
    const low = Math.min(open, close) * (1 - Math.random() * volatility * 0.5);
    
    // 成交量随机生成（百万股）
    const volume = Math.floor(Math.random() * 50_000_000) + 5_000_000;
    
    data.push({
      time: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`,
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
      volume,
    });
    
    price = close;
  }
  
  return data;
}

/**
 * 自选股持久化接口 (后端 JSON 文件存储，跨浏览器/origin 生效)
 */
export async function getWatchlist(): Promise<string[]> {
  try {
    const response = await fetch(`${BASE_URL}/watchlist`, { method: 'GET' });
    if (!response.ok) throw new Error('load failed');
    const json = await response.json();
    if (Array.isArray(json.symbols)) return json.symbols;
    return [];
  } catch {
    return [];
  }
}

export async function saveWatchlist(symbols: string[]): Promise<void> {
  try {
    await fetch(`${BASE_URL}/watchlist`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols }),
    });
  } catch {
    /* 后端不可用时静默失败，前端已同步写入 localStorage 兜底 */
  }
}

