# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 数据源抽象层

支持多数据源 + 主备故障转移 + 多周期K线:
  主源: 腾讯证券 (web.ifzq.gtimg.cn) — 日/周/月线优先
  备源: Yahoo Finance (yfinance)     — 4小时线优先(1h数据更丰富)

统一周期代码:
  '4h'  -> 4小时K线 (由1小时数据重采样)
  '1d'  -> 日K线
  '1w'  -> 周K线
  '1M'  -> 月K线
"""

import asyncio
import httpx
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException
from zoneinfo import ZoneInfo

# 美股以「美国东部时间」为交易日基准，避免服务器本地时区导致日期差一天
US_EAST = ZoneInfo('America/New_York')


def _normalize_date(raw: str) -> str:
    """将腾讯等源可能返回的日期统一规范为 'YYYY-MM-DD'（兼容 YYYYMMDD / 带时间格式）。"""
    s = str(raw).strip()
    for fmt in ('%Y-%m-%d', '%Y%m%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(s[:10], fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return s[:10]


def validate_klines(df: "pd.DataFrame", period: str) -> bool:
    """
    校验返回数据的「粒度」是否与请求周期一致。

    这是修复「每根 K 线跨 3 个月」问题的核心防线:

    某些网络环境 (如被代理拦截的 Yahoo 接口) 会把日/周/月线退化成
    「每季度一根」(相邻 90 天) 的稀疏数据, 直接渲染会让每根蜡烛在视觉上
    跨 3 个月; 另外缓存一旦被这类错位数据污染, 会在 TTL 内持续返回错误数据。

    通过对相邻日期间隔取中位数判断粒度是否匹配:
      1d -> 中位数间隔应 <= 5 天  (真实日线 1 天, 周末 <= 3 天)
      1w -> 中位数间隔应 <= 14 天 (真实周线 ~7 天, 假期略大)
      1M -> 中位数间隔应 <= 45 天 (真实月线 ~30 天)
      3M -> 中位数间隔应 <= 100 天 (真实季线 ~90 天)
      6M -> 中位数间隔应 <= 200 天 (真实半年线 ~180 天)
      1Y -> 中位数间隔应 <= 400 天 (真实年线 ~365 天)
      4h -> 含时分, 单独放行
    """
    # 聚合周期（季/半年/年）由日线重采样而来，天然 bar 数少:
    #   一只上市 1.4 年的股票(如退市股 SNDK) 只有约 2-3 根半年线 / 1-2 根年线。
    #   对这类周期放宽最小根数门槛，允许 ≥1 根通过粒度校验（粒度仍严格校验）。
    _MIN_BARS = {'4h': 1, '1d': 5, '1w': 3, '1M': 2, '3M': 1, '6M': 1, '1Y': 1}
    min_bars = _MIN_BARS.get(period, 5)
    if df is None or len(df) < min_bars:
        return False
    try:
        if period == '4h':
            return True
        dates = pd.to_datetime(df['date'], errors='coerce').dropna().sort_values()
        if len(dates) < min_bars:
            return False
        gaps = dates.diff().dropna()
        # 仅保留正向且合理的间隔 (<=400 天, 过滤极端异常)
        day_gaps = gaps[(gaps.dt.days > 0) & (gaps.dt.days <= 400)].dt.days
        if day_gaps.empty:
            return False
        median_gap = float(day_gaps.median())
        if period == '1d':
            return median_gap <= 5
        if period == '1w':
            return median_gap <= 14
        if period == '1M':
            return median_gap <= 45
        if period == '3M':
            return median_gap <= 100
        if period == '6M':
            return median_gap <= 200
        if period == '1Y':
            return median_gap <= 400
        return True
    except Exception:
        # 解析异常时保守放行, 避免误杀正常数据
        return True


# 常见拆股比例 (价格下折倍数, 即历史价需 ÷ 该值才与拆后价连续)
# 用于「前复权」时判定相邻 K 线间的巨大跳变是否为拆股事件, 而非普通波动
_SPLIT_RATIOS = [1.25, 1.333, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10, 15, 20, 25, 50, 100]


def _is_split_ratio(r: float) -> bool:
    """判断数值 r 是否接近某个常见拆股比例 (含正向拆股与反向拆股)。"""
    if r <= 0 or r == 1.0:
        return False
    # 正向拆股: r 落在 [1.25, 100] 且贴近常见比例
    for c in _SPLIT_RATIOS:
        if c < 1.2:
            continue
        if abs(r - c) / c <= 0.12:
            return True
    # 反向拆股: r 很小 (如 1:10 -> 0.1), 即 1/r 贴近常见比例
    for c in _SPLIT_RATIOS:
        if c < 1.2:
            continue
        inv = 1.0 / c
        if abs(r - inv) / inv <= 0.12:
            return True
    return False


def apply_forward_adjustment(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    前复权: 检测拆股事件, 把历史价格按拆股比例向下(或向上)调整, 使整张 K 线图连续无跳空。

    为什么需要: 腾讯 / Yahoo 返回的美股原始 K 线多为「不复权」数据, 遇到股票拆分
    (如 NVDA 2024-06 的 10 拆 1) 时, 拆前最后一根 ~$1200, 拆后第一根 ~$120, 中间出现
    一个巨大的向下跳空, 视觉上像「暴跌 90%」, 且会彻底破坏支撑/阻力、均线等技术指标。

    算法 (前复权 = 最新价格保持真实, 历史价格按比例折算):
      1. 从最新一根向前遍历, 在 bar[i] 收盘 与 bar[i+1] 开盘 之间检测拆股跳变;
      2. 若跳变倍率接近常见拆股比例 (如 10 倍), 则 bar[i] 及之前所有价格 ÷ 该倍率;
      3. 成交量同步反向调整 (历史 ÷倍率 的价格, 对应 ×倍率 的股数), 保持成交金额一致。

    数据要求: 必须按日期升序; 函数内部会自动排序防御。
    """
    if df is None or df.empty or len(df) < 2:
        return df

    df = df.copy()
    df['_dt'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['_dt']).sort_values('_dt').drop(columns=['_dt']).reset_index(drop=True)
    if len(df) < 2:
        return df

    n = len(df)
    closes = df['close'].to_numpy(dtype=float)
    opens = df['open'].to_numpy(dtype=float)
    factors = np.ones(n, dtype=float)
    cum = 1.0
    for i in range(n - 2, -1, -1):
        denom = opens[i + 1]
        if denom > 0:
            r = closes[i] / denom
            # 仅当跳变明显且贴近常见拆股比例时才视为拆股, 避免普通波动(如单日 -30%)误判
            if (r > 1.5 or r < 0.67) and _is_split_ratio(r):
                cum *= r
        factors[i] = cum

    for col in ('open', 'high', 'low', 'close'):
        df[col] = df[col] / factors
    # 成交量反向调整, 保持金额一致 (历史价 ÷倍率 => 同金额对应股数 ×倍率)
    df['volume'] = df['volume'] * factors

    return df.reset_index(drop=True)


# ============================================================
# 周期映射表
# ============================================================
# 统一周期 -> 各数据源的实际拉取周期 + 是否需要重采样
PERIOD_MAP = {
    '4h': {'tencent': 'm60',  'yahoo': '1h',  'need_resample': True,  'resample': '4h'},
    '1d': {'tencent': 'day',  'yahoo': '1d',  'need_resample': False, 'resample': None},
    '1w': {'tencent': 'week', 'yahoo': '1wk', 'need_resample': False, 'resample': None},
    '1M': {'tencent': 'month','yahoo': '1mo', 'need_resample': False, 'resample': None},
    # 季K / 半年K / 年K: 拉取日线后按日历时间聚合 (每根蜡烛=一个季度/半年/年)
    # 使用「起始日锚定」频率码 (QS/2QS/YS), 使每根蜡烛的日期标签=该周期起始日,
    # 避免旧码 Q/Y 产生的「前导空桶」与「季末标签」错位问题。
    '3M': {'tencent': 'day',  'yahoo': '1d',  'need_resample': True,  'resample': 'QS'},
    '6M': {'tencent': 'day',  'yahoo': '1d',  'need_resample': True,  'resample': '2QS'},
    '1Y': {'tencent': 'day',  'yahoo': '1d',  'need_resample': True,  'resample': 'YS'},
}

SUPPORTED_PERIODS: List[str] = list(PERIOD_MAP.keys())

# 美股交易所后缀 (腾讯代码格式: usAAPL.OQ)
US_SUFFIXES = ['.OQ', '.N', '.AM']


# ============================================================
# 数据源抽象基类
# ============================================================
class DataProvider:
    """所有数据源的统一接口"""

    def __init__(self, name: str):
        self.name = name

    async def fetch_klines(self, symbol: str, period: str, count: int = 320, full: bool = False) -> pd.DataFrame:
        """
        拉取指定周期的K线数据。

        参数:
            full: 为 True 时拉取该股票上市以来的全部历史数据 (忽略 count 截断)，
                  为 False 时按 count 上限截断 (向后兼容旧行为)。

        返回 DataFrame 列: date(str), open, high, low, close, volume
        - 日/周/月线: date 格式为 'YYYY-MM-DD'
        - 4小时线:    date 格式为 'YYYY-MM-DD HH:MM'
        """
        raise NotImplementedError

    def supports_period(self, period: str) -> bool:
        raise NotImplementedError


# ============================================================
# 腾讯证券数据源 (主源)
# ============================================================
class TencentProvider(DataProvider):
    """
    腾讯证券行情源。
    支持 day / week / month / m60(用于4h重采样)。
    """

    BASE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

    def __init__(self):
        super().__init__("tencent")

    def supports_period(self, period: str) -> bool:
        return period in PERIOD_MAP and PERIOD_MAP[period]['tencent'] is not None

    async def _fetch_raw(self, symbol: str, tencent_period: str, count: int, end: str = None) -> pd.DataFrame:
        """直接请求腾讯接口拉取原始K线。

        end: 分页回溯用的截止日期(不含), 格式 'YYYY-MM-DD'。
             腾讯接口的 start 参数会被忽略, 分页必须靠 end 驱动:
             不传 end 返回最近 count 根; 传 end 则返回 end 之前 count 根。
        """
        if end:
            param = f"{symbol},{tencent_period},,{end},{count},qfq"
        else:
            param = f"{symbol},{tencent_period},,,{count},qfq"
        url = f"{self.BASE_URL}?param={param}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, headers=headers, timeout=10.0, follow_redirects=True)
                if resp.status_code != 200:
                    return pd.DataFrame()

                json_data = resp.json()
                if json_data.get("code") != 0:
                    return pd.DataFrame()

                stock_data = json_data.get("data", {}).get(symbol, {})

                # 兼容前复权标识: qfqday / qfqweek / qfqmonth / m60
                if tencent_period == 'day':
                    kline_key = "qfqday" if "qfqday" in stock_data else "day"
                elif tencent_period == 'week':
                    kline_key = "qfqweek" if "qfqweek" in stock_data else "week"
                elif tencent_period == 'month':
                    kline_key = "qfqmonth" if "qfqmonth" in stock_data else "month"
                else:
                    # 分钟级数据 (m60 等) 直接用周期名
                    kline_key = tencent_period

                if kline_key not in stock_data or not stock_data[kline_key]:
                    return pd.DataFrame()

                raw = stock_data[kline_key]
                parsed = []
                for item in raw:
                    # 腾讯格式: ['日期或时间', '开', '收', '高', '低', '成交量']
                    if len(item) >= 6:
                        parsed.append({
                            "date": _normalize_date(item[0]),
                            "open": float(item[1]),
                            "close": float(item[2]),
                            "high": float(item[3]),
                            "low": float(item[4]),
                            "volume": float(item[5])
                        })

                if parsed and len(parsed) >= 5:
                    return pd.DataFrame(parsed)
                return pd.DataFrame()

            except Exception:
                return pd.DataFrame()

    async def _fetch_full_via_pagination(self, symbol: str, tencent_period: str,
                                        page_count: int = 2000, max_pages: int = 40) -> pd.DataFrame:
        """
        通过 end 参数分页回溯拉取腾讯全量历史, 突破单页 ~2000 根上限。

        为什么需要: 腾讯免费接口单次最多返回约 2000 根 K 线 (count>=3000 返回空),
        日线 2000 根仅覆盖最近约 8 年。通过 end 参数一路往前翻页, 可把历史回溯到
        数据源能提供的最早日期 (美股日线通常可到 ~2007 年)。

        分页流程:
          1. 第一页不传 end -> 最近 page_count 根 (最新一段历史);
          2. 之后每页以「上一页最早日期」作为 end -> 拿到更早期的历史;
          3. 当某页返回根数 < page_count, 说明已触达数据源最早数据, 停止。

        返回合并、去重、按日期升序的 DataFrame。
        """
        all_rows: dict = {}
        end = None
        for _ in range(max_pages):
            df = await self._fetch_raw(symbol, tencent_period, page_count, end=end)
            if df is None or df.empty:
                break
            for _, row in df.iterrows():
                d = row['date']
                if d not in all_rows:
                    all_rows[d] = row.to_dict()
            # 触达数据源最早数据 (本页不足一整页) -> 停止
            if len(df) < page_count:
                break
            earliest = df['date'].min()
            # 没有更早进展 (防止死循环)
            if end is not None and earliest >= end:
                break
            end = earliest

        if not all_rows:
            return pd.DataFrame()
        result = pd.DataFrame(list(all_rows.values()))
        result = result.sort_values('date').reset_index(drop=True)
        return result

    async def fetch_klines(self, symbol: str, period: str, count: int = 320, full: bool = False) -> pd.DataFrame:
        if not self.supports_period(period):
            return pd.DataFrame()

        tencent_period = PERIOD_MAP[period]['tencent']
        need_resample = PERIOD_MAP[period]['need_resample']

        # 全量历史模式: 通过 end 分页回溯拉取腾讯能给的全部历史 (突破单页 ~2000 根上限)。
        # 日线可回溯到数据源最早 (~2007), 周/月线单页即够覆盖。真正的「上市日全量」
        # 由 Yahoo range=max 在全量主源模式下提供 (见 DataProviderManager 主备顺序),
        # 腾讯分页在此作为 Yahoo 不可用时的兜底, 尽量往前逼近。
        if full:
            fetch_count = 2000
        else:
            fetch_count = count * 4 if need_resample else count

        # 美股自动匹配交易所后缀
        candidates = self._get_symbol_candidates(symbol)

        for cand in candidates:
            if full:
                df = await self._fetch_full_via_pagination(cand, tencent_period, page_count=fetch_count)
            else:
                df = await self._fetch_raw(cand, tencent_period, fetch_count)
            if not df.empty:
                if need_resample:
                    rule = PERIOD_MAP[period].get('resample')
                    if rule in ('QS', '2QS', 'YS'):
                        # 关键: 先校验原始数据确为日线 (防止代理返回已聚合数据),
                        # 再对日线做前复权 (消除拆股缺口), 最后按时间聚合,
                        # 否则季度/年蜡烛会混入拆股前后价格或退化数据导致巨大跳变。
                        if not validate_klines(df, '1d'):
                            print(f"[Tencent] {period} 原始数据非日线, 跳过候选 {cand}")
                            continue
                        df = apply_forward_adjustment(df)
                        df = self._resample_to_period(df, rule)
                    elif rule == '4h':
                        df = self._resample_to_4h(df)
                if not df.empty:
                    # 仅非全量模式下按 count 截断；全量模式保留上市以来全部数据
                    if not full and len(df) > count:
                        df = df.iloc[-count:].reset_index(drop=True)
                    return df
        return pd.DataFrame()

    def _get_symbol_candidates(self, symbol: str) -> List[str]:
        """根据输入代码生成候选腾讯代码列表"""
        if "." in symbol:
            return [symbol]
        if symbol.lower().startswith("us"):
            ticker = symbol[2:].upper()
            return [f"us{ticker}{s}" for s in US_SUFFIXES]
        return [symbol]

    @staticmethod
    def _resample_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
        """
        将1小时K线重采样为4小时K线。
        按交易日分组，每4根1h K线合并为1根4h K线，
        避免跨交易日(隔夜缺口)合并产生失真。
        """
        if df_1h.empty:
            return df_1h

        try:
            df = df_1h.copy()
            # 解析时间
            df['datetime'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.dropna(subset=['datetime']).sort_values('datetime').reset_index(drop=True)

            if df.empty:
                return pd.DataFrame()

            # 按日期分组
            df['day'] = df['datetime'].dt.date

            result = []
            for day, group in df.groupby('day'):
                group = group.sort_values('datetime').reset_index(drop=True)
                # 每4根合并为一根4h K线
                for i in range(0, len(group), 4):
                    chunk = group.iloc[i:i + 4]
                    if len(chunk) == 0:
                        continue
                    result.append({
                        'date': chunk.iloc[0]['date'],
                        'open': float(chunk.iloc[0]['open']),
                        'high': float(chunk['high'].max()),
                        'low': float(chunk['low'].min()),
                        'close': float(chunk.iloc[-1]['close']),
                        'volume': float(chunk['volume'].sum())
                    })

            if result:
                return pd.DataFrame(result)
            return pd.DataFrame()

        except Exception as e:
            print(f"[Tencent] 4h resample error: {e}")
            return pd.DataFrame()

    @staticmethod
    def _resample_to_period(df: pd.DataFrame, rule: str) -> pd.DataFrame:
        """
        将日线 K线按日历时间聚合为更大周期 (季/半年/年)。
        rule: 'QS'(季, 起始日锚定) / '2QS'(半年) / 'YS'(年)。每根蜡烛 = 一个时间单位。
        OHLC: 开=首, 高=最大, 低=最小, 收=末, 量=求和。
        日期标签用周期起始日 (如 2026-01-01 代表 Q1 / 上半年 / 全年)。
        """
        if df is None or df.empty:
            return pd.DataFrame()
        try:
            d = df.copy()
            d['datetime'] = pd.to_datetime(d['date'], errors='coerce')
            d = d.dropna(subset=['datetime']).sort_values('datetime').reset_index(drop=True)
            if d.empty:
                return pd.DataFrame()

            d = d.set_index('datetime')
            agg = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
            }
            # label='left' + closed='left' -> 周期起始日作为该组标签
            resampled = d.resample(rule, label='left', closed='left').agg(agg)
            resampled = resampled.dropna(subset=['close'])
            if resampled.empty:
                return pd.DataFrame()

            resampled = resampled.reset_index()
            out = pd.DataFrame({
                'date': resampled['datetime'].dt.strftime('%Y-%m-%d'),
                'open': resampled['open'].astype(float).round(4),
                'high': resampled['high'].astype(float).round(4),
                'low': resampled['low'].astype(float).round(4),
                'close': resampled['close'].astype(float).round(4),
                'volume': resampled['volume'].astype(float).round(2),
            })
            return out
        except Exception as e:
            print(f"[resample] {rule} resample error: {e}")
            return pd.DataFrame()
        except Exception as e:
            print(f"[resample] {rule} resample error: {e}")
            return pd.DataFrame()


# ============================================================
# Yahoo Finance 数据源 (备源)
# ============================================================
class YahooProvider(DataProvider):
    """
    Yahoo Finance 行情源 (基于 yfinance 库)。
    支持 1h(用于4h重采样) / 1d / 1wk / 1mo。
    无需 API Key，美股数据覆盖完整。
    """

    def __init__(self):
        super().__init__("yahoo")

    def supports_period(self, period: str) -> bool:
        return period in PERIOD_MAP and PERIOD_MAP[period]['yahoo'] is not None

    async def fetch_klines(self, symbol: str, period: str, count: int = 320, full: bool = False) -> pd.DataFrame:
        if not self.supports_period(period):
            return pd.DataFrame()

        yahoo_interval = PERIOD_MAP[period]['yahoo']
        need_resample = PERIOD_MAP[period]['need_resample']
        resample_rule = PERIOD_MAP[period].get('resample')

        ticker = self._to_yahoo_ticker(symbol)
        if not ticker:
            return pd.DataFrame()

        # 全量历史模式：优先用 Yahoo 直连 chart API (range=max)。
        # 比 yfinance 更稳定（不受 cookie / 限流影响），能稳定返回上市以来全部数据。
        if full:
            df = await self._fetch_yahoo_direct(ticker, yahoo_interval, need_resample, resample_rule)
            if not df.empty:
                return df

        # 回退到 yfinance（同步库，在线程池中执行避免阻塞事件循环）
        try:
            import yfinance as yf
        except ImportError:
            print("[Yahoo] yfinance 未安装，跳过备源")
            return pd.DataFrame()

        try:
            df = await asyncio.to_thread(
                self._fetch_yfinance_sync, yf, ticker, yahoo_interval, count, need_resample, full, resample_rule
            )
            return df
        except Exception as e:
            print(f"[Yahoo] fetch error: {e}")
            return pd.DataFrame()

    @staticmethod
    def _fetch_yfinance_sync(yf, ticker: str, interval: str, count: int, need_resample: bool, full: bool = False, resample_rule: str = None) -> pd.DataFrame:
        """同步拉取 yfinance 数据 (在线程池中调用)"""
        # 全量历史模式: 直接请求 period='max' 拿到上市以来全部数据
        period_str = 'max' if full else YahooProvider._calc_yahoo_period(interval, count)
        tk = yf.Ticker(ticker)
        hist = tk.history(period=period_str, interval=interval)

        if hist.empty:
            return pd.DataFrame()

        # yfinance 返回的索引为 UTC 时区, 统一转换到美东时间 (美股交易日基准),
        # 避免出现日期整体差一天的问题 (与 Yahoo 直连行为保持一致)
        idx = hist.index
        if getattr(idx, 'tz', None) is None:
            idx = idx.tz_localize('UTC')
        idx = idx.tz_convert(US_EAST)

        # 格式化时间列
        if need_resample and resample_rule == '4h':
            # 1h数据: 保留时分
            time_col = idx.strftime('%Y-%m-%d %H:%M').tolist()
        else:
            # 日/周/月/季/半年/年: 只保留日期
            time_col = idx.strftime('%Y-%m-%d').tolist()

        df = pd.DataFrame({
            'date': time_col,
            'open': hist['Open'].values,
            'close': hist['Close'].values,
            'high': hist['High'].values,
            'low': hist['Low'].values,
            'volume': hist['Volume'].values
        })

        # 过滤无效行 (成交量为0或价格为NaN的行)
        df = df.dropna(subset=['open', 'high', 'low', 'close'])
        df = df[df['volume'] > 0].reset_index(drop=True)

        if need_resample and resample_rule:
            df = YahooProvider._dispatch_resample(df, resample_rule)

        if len(df) >= 5:
            return df.reset_index(drop=True)
        return pd.DataFrame()

    @staticmethod
    def _dispatch_resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
        """根据重采样规则分发到对应的重采样函数。
        对时间聚合类周期 (季/半年/年)，先校验原始数据确为日线粒度、再做前复权、最后聚合，
        避免某些网络代理把 interval=1d 退化成已聚合数据导致重采样失效。"""
        if rule in ('QS', '2QS', 'YS'):
            if not validate_klines(df, '1d'):
                print(f"[resample] 原始数据非日线粒度 (无法重采样为{rule})，拒绝")
                return pd.DataFrame()
            df = apply_forward_adjustment(df)
            return TencentProvider._resample_to_period(df, rule)
        if rule == '4h':
            return TencentProvider._resample_to_4h(df)
        return df

    async def _fetch_yahoo_direct(self, ticker: str, interval: str, need_resample: bool, resample_rule: str = None) -> pd.DataFrame:
        """
        直连 Yahoo Finance chart API 拉取全量历史 (range=max)。
        返回结构: chart.result[0].timestamp + indicators.quote[0]
        该方式比 yfinance 更稳定，能稳定返回上市以来全部数据。
        """
        hosts = [
            "https://query1.finance.yahoo.com/v8/finance/chart",
            "https://query2.finance.yahoo.com/v8/finance/chart",
        ]
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        data = None
        for host in hosts:
            url = f"{host}/{ticker}?range=max&interval={interval}"
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, headers=headers, timeout=20.0, follow_redirects=True)
                    if resp.status_code == 200:
                        data = resp.json()
                        break
                    print(f"[YahooDirect] {host} HTTP {resp.status_code}")
            except Exception as e:
                print(f"[YahooDirect] {host} request error: {e}")
        if data is None:
            return pd.DataFrame()

        try:
            result = data.get("chart", {}).get("result")
            if not result:
                return pd.DataFrame()
            res = result[0]
            ts = res.get("timestamp")
            quote = res.get("indicators", {}).get("quote", [{}])[0]
            if not ts or not quote.get("close"):
                return pd.DataFrame()

            opens = quote.get("open", [])
            highs = quote.get("high", [])
            lows = quote.get("low", [])
            closes = quote.get("close", [])
            vols = quote.get("volume", [])

            rows = []
            for i, t in enumerate(ts):
                if i >= len(closes) or closes[i] is None:
                    continue
                dt = datetime.fromtimestamp(t, tz=US_EAST)
                date_str = dt.strftime('%Y-%m-%d %H:%M') if need_resample else dt.strftime('%Y-%m-%d')
                o = opens[i] if i < len(opens) and opens[i] is not None else closes[i]
                h = highs[i] if i < len(highs) and highs[i] is not None else closes[i]
                l = lows[i] if i < len(lows) and lows[i] is not None else closes[i]
                v = vols[i] if i < len(vols) and vols[i] is not None else 0
                rows.append({
                    "date": date_str,
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(closes[i]),
                    "volume": float(v),
                })

            df = pd.DataFrame(rows)
            if df.empty:
                return pd.DataFrame()
            # 过滤无效行 (价格为 NaN 的行)
            df = df.dropna(subset=['open', 'high', 'low', 'close'])
            df = df[df['volume'] >= 0].reset_index(drop=True)

            if need_resample and resample_rule:
                df = YahooProvider._dispatch_resample(df, resample_rule)

            if len(df) >= 5:
                return df.reset_index(drop=True)
            return pd.DataFrame()
        except Exception as e:
            print(f"[YahooDirect] parse error: {e}")
            return pd.DataFrame()

    @staticmethod
    def _to_yahoo_ticker(symbol: str) -> str:
        """将平台代码转换为 Yahoo Finance ticker"""
        if "." in symbol:
            # usAAPL.OQ -> AAPL
            base = symbol.split(".")[0]
            if base.lower().startswith("us"):
                return base[2:].upper()
            return base.upper()
        if symbol.lower().startswith("us"):
            return symbol[2:].upper()
        return symbol.upper()

    @staticmethod
    def _calc_yahoo_period(interval: str, count: int) -> str:
        """根据 interval 和需要的数量，计算 yfinance period 参数"""
        # yfinance period 选项: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
        if interval == '1h':
            # 1h 数据 Yahoo 最多保留 730 天，每天约 7 根
            # 取 2y 拿尽量多数据
            return '2y'
        elif interval == '1d':
            if count > 365:
                return '2y'
            elif count > 180:
                return '1y'
            else:
                return '6mo'
        elif interval == '1wk':
            if count > 104:
                return '5y'
            elif count > 52:
                return '2y'
            else:
                return '1y'
        elif interval == '1mo':
            if count > 36:
                return '10y'
            elif count > 12:
                return '5y'
            else:
                return '2y'
        return '2y'


# ============================================================
# 数据源管理器 — 主备故障转移
# ============================================================
class DataProviderManager:
    """
    管理多个数据源，提供统一的 K线拉取入口。

    故障转移策略:
      - 4h 周期: Yahoo 优先 (1h 历史数据更丰富)，腾讯备选
      - 日/周/月:  腾讯优先 (主源)，Yahoo 备选
    """

    def __init__(self):
        self.tencent = TencentProvider()
        self.yahoo = YahooProvider()
        # 记录最近成功的数据源 (供调试/日志)
        self._last_source: Optional[str] = None

    @property
    def last_source(self) -> Optional[str]:
        return self._last_source

    async def fetch_klines(
        self, symbol: str, period: str = '1d', count: int = 320, full: bool = False
    ) -> pd.DataFrame:
        """
        拉取指定周期的K线数据，自动故障转移。

        参数:
            symbol: 股票代码 (如 usAAPL)
            period: K线周期 ('4h'/'1d'/'1w'/'1M')
            count:  K线数量上限 (仅非全量模式生效)
            full:   为 True 时拉取上市以来全部历史数据

        返回: 包含 [date, open, high, low, close, volume] 的 DataFrame
        """
        if period not in SUPPORTED_PERIODS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的K线周期: '{period}'，支持: {', '.join(SUPPORTED_PERIODS)}"
            )

        # 确定主备源顺序
        if full:
            # 全量历史模式：优先 Yahoo (period='max' 可返回上市以来全部数据)。
            # 腾讯接口对单次返回的 K 线根数有上限，难以拿到完整历史，故作为备源。
            primary, backup = self.yahoo, self.tencent
        elif period == '4h':
            # 4h: Yahoo 1h 数据更丰富，优先使用
            primary, backup = self.yahoo, self.tencent
        else:
            # 日/周/月: 腾讯为主源
            primary, backup = self.tencent, self.yahoo

        # 两个数据源都拉取并做「粒度校验」，再择优返回：
        #   - 拒绝粒度错位的数据 (如 Yahoo 代理把日线退化成每 3 个月一根的季度桩)
        #   - 在都有效的前提下，优先选择「根数更多」的结果 (更接近全量历史)
        # 这样既能在本机走 Yahoo 拿完整历史，也能在受限网络下退回腾讯的真实日/周/月线。
        candidates = [primary, backup]
        best_df = None
        best_source = None
        for src in candidates:
            try:
                df = await src.fetch_klines(symbol, period, count, full)
            except Exception as e:
                print(f"[{src.name}] fetch error: {e}")
                df = pd.DataFrame()
            if df.empty or not validate_klines(df, period):
                continue
            if best_df is None or len(df) > len(best_df):
                best_df = df
                best_source = src.name

        if best_df is not None and not best_df.empty:
            self._last_source = best_source
            # 前复权: 消除拆股造成的跳空, 使 K 线连续、技术指标可用。
            # 3M/6M/1Y 已在 provider 内对「日线」前复权后再重采样(避免拆股缺口混入聚合),
            # 此处跳过以免重复调整; 其余周期(含 4h)在此统一调整。
            if period not in ('3M', '6M', '1Y'):
                best_df = apply_forward_adjustment(best_df)
            return best_df

        # 全部失败 / 全部粒度错位
        self._last_source = None
        raise HTTPException(
            status_code=404,
            detail=f"所有数据源均无法获取 {symbol} 的 {period} K线数据，"
                   f"或返回的数据粒度与周期不匹配(如被退化成季度数据)已拒绝，"
                   f"请检查网络连接或确认代码是否正确"
        )


# 全局单例
provider_manager = DataProviderManager()
