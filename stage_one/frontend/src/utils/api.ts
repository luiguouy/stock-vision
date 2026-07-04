// 股票技术分析平台 - 前端 API 封装
// 采用 Fetch API 构建，避免不必要的依赖
import { calculateSRLevels, calculateRangeStats } from './mockEngine';

// 使用相对路径，配合 Vite 代理或生产环境反向代理
const BASE_URL = '/api';

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
 * 获取股票日K线数据
 */
export async function getKLines(symbol: string): Promise<KLinePoint[]> {
  try {
    const response = await fetch(`${BASE_URL}/klines?symbol=${encodeURIComponent(symbol)}`);
    if (!response.ok) throw new Error('服务器端日K线接口返回异常');
    return await response.json();
  } catch (error) {
    console.warn('Error fetching KLines, trying direct Tencent API:', error);
    try {
      // 尝试直接拉取腾讯证券接口（纯美股 us 前缀）
      const ticker = symbol.toUpperCase();
      const tencentUrl = `https://web.ifzq.gtimg.cn/appzone/newstrend/new_chart/query?code=${ticker.toLowerCase()}&type=qfqk`;
      const res = await fetch(tencentUrl);
      if (!res.ok) throw new Error('腾讯源行情接口连接失败');
      const json = await res.json();
      const rawLines = json.data[ticker.toLowerCase()].qfqk;
      if (rawLines && rawLines.length >= 5) {
        return rawLines.map((item: any) => ({
          time: item[0],
          open: parseFloat(item[1]),
          close: parseFloat(item[2]),
          high: parseFloat(item[3]),
          low: parseFloat(item[4]),
          volume: parseFloat(item[5])
        }));
      }
      throw new Error('腾讯源行情数据为空');
    } catch (directErr) {
      console.error('Tencent direct fetch failed:', directErr);
      throw new Error('网络原因，无法加载 K 线行情图');
    }
  }
}

/**
 * 获取股票技术分析（支撑位、阻力位、区间涨跌统计）
 */
export async function getStockAnalysis(
  symbol: string,
  startDate: string,
  endDate: string,
  klineCache?: KLinePoint[]
): Promise<AnalysisResponse | null> {
  try {
    const response = await fetch(`${BASE_URL}/analysis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, start_date: startDate, end_date: endDate }),
    });
    if (!response.ok) throw new Error('服务器端技术分析接口错误');
    return await response.json();
  } catch (error) {
    console.warn('Backend analysis failed, running frontend calculation:', error);
    // 降级使用前端内置计算引擎 (这是纯数学计算，不是 Mock 假 K 线数据)
    const klines = klineCache && klineCache.length > 0 ? klineCache : await getKLines(symbol);
    if (!klines || klines.length === 0) throw new Error('无法提取 K 线行情进行分析');
    
    const sr_levels = calculateSRLevels(klines);
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

