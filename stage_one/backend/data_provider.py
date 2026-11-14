# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 数据源抽象层（VPN 双通道智能分流 + 美股高可靠版）
路径: stage_one/backend/data_provider.py
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import httpx
import numpy as np
import pandas as pd
from fastapi import HTTPException

from symbols import market_of, normalize_symbol

US_EAST = ZoneInfo('America/New_York')

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# 双通道全局连接池（按事件循环隔离，避免跨 loop 复用报错）：
# use_proxy=False 强制绕过 VPN 直连腾讯/新浪；use_proxy=True 走系统代理访问 Yahoo Finance
_clients: Dict[bool, Optional[httpx.AsyncClient]] = {False: None, True: None}
_client_loops: Dict[bool, Any] = {False: None, True: None}


async def _get_http_client(use_proxy: bool, timeout: float) -> httpx.AsyncClient:
    cur_loop = None
    try:
        cur_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass

    client = _clients[use_proxy]
    prev_loop = _client_loops[use_proxy]
    if (
        client is None
        or client.is_closed
        or prev_loop != cur_loop
        or (cur_loop and cur_loop.is_closed())
    ):
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
        client = httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            timeout=timeout,
            limits=limits,
            follow_redirects=True,
            verify=False,
            trust_env=use_proxy,
        )
        _clients[use_proxy] = client
        _client_loops[use_proxy] = cur_loop
    return client


async def get_direct_client() -> httpx.AsyncClient:
    """直连连接池（trust_env=False，绕过代理访问腾讯/新浪）。"""
    return await _get_http_client(use_proxy=False, timeout=8.0)


async def get_proxy_client() -> httpx.AsyncClient:
    """代理连接池（trust_env=True，走系统代理访问 Yahoo Finance）。"""
    return await _get_http_client(use_proxy=True, timeout=15.0)

def _normalize_date(raw: str) -> str:
    s = str(raw).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y%m%d%H%M', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d %H:%M')
        except ValueError:
            continue
    for fmt in ('%Y-%m-%d', '%Y%m%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(s[:10], fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return s

def validate_klines(df: "pd.DataFrame", period: str) -> bool:
    _MIN_BARS = {'5m': 1, '15m': 1, '1h': 1, '4h': 1, '1d': 5, '1w': 3, '1M': 2, '3M': 1, '6M': 1, '1Y': 1}
    min_bars = _MIN_BARS.get(period, 1)
    if df is None or len(df) < min_bars:
        return False
    try:
        if period in ('5m', '15m', '1h', '4h'):
            return True
        dates = pd.to_datetime(df['date'], errors='coerce').dropna().sort_values()
        if len(dates) < min_bars:
            return False
        gaps = dates.diff().dropna()
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
            return 45 < median_gap <= 130
        if period == '6M':
            return 100 < median_gap <= 260
        if period == '1Y':
            return 260 < median_gap <= 400
        return True
    except Exception:
        return True

_SPLIT_RATIOS = [2, 2.5, 3, 4, 5, 10, 15, 20, 25, 50, 100]

def _is_split_ratio(r: float) -> bool:
    if r <= 0 or r == 1.0:
        return False
    for c in _SPLIT_RATIOS:
        if abs(r - c) / c <= 0.08:
            return True
        inv = 1.0 / c
        if abs(r - inv) / inv <= 0.08:
            return True
    return False

def apply_forward_adjustment(df: "pd.DataFrame") -> "pd.DataFrame":
    """启发式拆股前复权（仅用于未复权的腾讯日线兜底，收紧容差防止误伤杠杆 ETF）。"""
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
            if (r >= 1.85 or r <= 0.54) and _is_split_ratio(r):
                cum *= r
        factors[i] = cum

    for col in ('open', 'high', 'low', 'close'):
        df[col] = df[col] / factors
    df['volume'] = df['volume'] * factors

    return df.reset_index(drop=True)


def resample_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
    """将 1 小时 K 线按交易日内每 4 根聚合为 4 小时 K 线。"""
    if df_1h is None or df_1h.empty:
        return pd.DataFrame()
    try:
        df = df_1h.copy()
        df['datetime'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['datetime']).sort_values('datetime').reset_index(drop=True)
        if df.empty:
            return pd.DataFrame()
        df['day'] = df['datetime'].dt.date
        result = []
        for _, group in df.groupby('day'):
            group = group.sort_values('datetime').reset_index(drop=True)
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
                    'volume': float(chunk['volume'].sum()),
                })
        return pd.DataFrame(result) if result else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def resample_to_period(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """将日 K 线按周期规则（W/MS/QS/2QS/YS）重采样为周/月/季/半年/年 K 线。"""
    if df is None or df.empty:
        return pd.DataFrame()
    try:
        d = df.copy()
        d['datetime'] = pd.to_datetime(d['date'], errors='coerce')
        d = d.dropna(subset=['datetime']).sort_values('datetime').reset_index(drop=True)
        if d.empty:
            return pd.DataFrame()
        d = d.set_index('datetime')
        agg = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
        resampled = d.resample(rule, label='left', closed='left').agg(agg).dropna(subset=['close'])
        if resampled.empty:
            return pd.DataFrame()
        resampled = resampled.reset_index()
        return pd.DataFrame({
            'date': resampled['datetime'].dt.strftime('%Y-%m-%d'),
            'open': resampled['open'].astype(float).round(4),
            'high': resampled['high'].astype(float).round(4),
            'low': resampled['low'].astype(float).round(4),
            'close': resampled['close'].astype(float).round(4),
            'volume': resampled['volume'].astype(float).round(2),
        })
    except Exception:
        return pd.DataFrame()


PERIOD_MAP = {
    '5m':  {'tencent': 'm5',   'yahoo': '5m',  'need_resample': False, 'resample': None},
    '15m': {'tencent': 'm15',  'yahoo': '15m', 'need_resample': False, 'resample': None},
    '1h':  {'tencent': 'm60',  'yahoo': '1h',  'need_resample': False, 'resample': None},
    '4h':  {'tencent': 'm60',  'yahoo': '1h',  'need_resample': True,  'resample': '4h'},
    '1d':  {'tencent': 'day',  'yahoo': '1d',  'need_resample': False, 'resample': None},
    '1w':  {'tencent': 'week', 'yahoo': '1wk', 'need_resample': False, 'resample': None},
    '1M':  {'tencent': 'month','yahoo': '1mo', 'need_resample': False, 'resample': None},
    '3M':  {'tencent': 'day',  'yahoo': '1d',  'need_resample': True,  'resample': 'QS'},
    '6M':  {'tencent': 'day',  'yahoo': '1d',  'need_resample': True,  'resample': '2QS'},
    '1Y':  {'tencent': 'day',  'yahoo': '1d',  'need_resample': True,  'resample': 'YS'},
}

SUPPORTED_PERIODS: List[str] = list(PERIOD_MAP.keys())

_FUTURES_RESAMPLE_RULE = {
    '1w': 'W',
    '1M': 'MS',
    '3M': 'QS',
    '6M': '2QS',
    '1Y': 'YS',
}

# 补齐 .P (NYSE Arca ETF 如 SPY, SOXL, NVDL, AMDL) 与无后缀兜底
US_SUFFIXES = ['.OQ', '.N', '.P', '.AM', '']

FUTURES_YAHOO_MAP = {
    "nqmain": "NQ=F",
    "esmain": "ES=F",
    "ymmain": "YM=F",
    "vxmain": "^VIX",
}

class DataProvider:
    def __init__(self, name: str):
        self.name = name

    async def fetch_klines(self, symbol: str, period: str, count: int = 320, full: bool = False) -> pd.DataFrame:
        raise NotImplementedError

    def supports_period(self, period: str) -> bool:
        raise NotImplementedError

class TencentProvider(DataProvider):
    """腾讯证券行情源（强制走本地直连，修复分时 mkline 接口与分页耗时）。"""

    BASE_FQ_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    BASE_MK_URL = "https://ifzq.gtimg.cn/appstock/app/kline/mkline"

    def __init__(self):
        super().__init__("tencent")

    def supports_period(self, period: str) -> bool:
        return period in PERIOD_MAP and PERIOD_MAP[period]['tencent'] is not None

    async def _fetch_raw(self, symbol: str, tencent_period: str, count: int, end: str = None) -> pd.DataFrame:
        is_min = tencent_period in ('m5', 'm15', 'm30', 'm60')
        if is_min:
            url = f"{self.BASE_MK_URL}?param={symbol},{tencent_period},,{count}"
        else:
            param = f"{symbol},{tencent_period},,{end or ''},{count},qfq"
            url = f"{self.BASE_FQ_URL}?param={param}"

        client = await get_direct_client()
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return pd.DataFrame()

            json_data = resp.json()
            if json_data.get("code") != 0:
                return pd.DataFrame()

            data_map = json_data.get("data", {})
            stock_data = data_map.get(symbol)
            if not stock_data and data_map:
                stock_data = next(iter(data_map.values()), {})
            if not isinstance(stock_data, dict):
                return pd.DataFrame()

            if tencent_period == 'day':
                kline_key = "qfqday" if "qfqday" in stock_data else "day"
            elif tencent_period == 'week':
                kline_key = "qfqweek" if "qfqweek" in stock_data else "week"
            elif tencent_period == 'month':
                kline_key = "qfqmonth" if "qfqmonth" in stock_data else "month"
            else:
                kline_key = tencent_period

            raw = stock_data.get(kline_key)
            if not raw:
                return pd.DataFrame()

            parsed = []
            for item in raw:
                if len(item) >= 6:
                    parsed.append({
                        "date": _normalize_date(item[0]),
                        "open": float(item[1]),
                        "close": float(item[2]),
                        "high": float(item[3]),
                        "low": float(item[4]),
                        "volume": float(item[5]),
                    })

            if parsed:
                return pd.DataFrame(parsed)
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    async def _fetch_full_via_pagination(
        self, symbol: str, tencent_period: str, page_count: int = 1000, max_pages: int = 8
    ) -> pd.DataFrame:
        """限制最大分页数为 8 页（约 8000 根 K 线 ≈ 32 年日线），防止 40 页串行请求卡死。"""
        if tencent_period in ('m5', 'm15', 'm30', 'm60'):
            return await self._fetch_raw(symbol, tencent_period, 500)

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
            if len(df) < page_count * 0.8:
                break
            earliest = df['date'].min()
            if end is not None and earliest >= end:
                break
            end = earliest

        if not all_rows:
            return pd.DataFrame()
        result = pd.DataFrame(list(all_rows.values()))
        return result.sort_values('date').reset_index(drop=True)

    async def fetch_klines(self, symbol: str, period: str, count: int = 320, full: bool = False) -> pd.DataFrame:
        if not self.supports_period(period):
            return pd.DataFrame()

        tencent_period = PERIOD_MAP[period]['tencent']
        need_resample = PERIOD_MAP[period]['need_resample']
        fetch_count = 1000 if full else (count * 4 if need_resample else count)

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
                        if not validate_klines(df, '1d'):
                            continue
                        df = apply_forward_adjustment(df)
                        df = resample_to_period(df, rule)
                    elif rule == '4h':
                        df = resample_to_4h(df)
                if not df.empty:
                    if not full and len(df) > count:
                        df = df.iloc[-count:].reset_index(drop=True)
                    return df
        return pd.DataFrame()

    def _get_symbol_candidates(self, symbol: str) -> List[str]:
        if "." in symbol:
            if symbol[:2].upper() in ("US", "SH", "SZ", "HK"):
                return [symbol[:2].lower() + symbol[2:]]
            return [symbol]
        s = symbol.lower()
        if s.startswith("us"):
            ticker = symbol[2:].upper()
            return [f"us{ticker}{suf}" for suf in US_SUFFIXES]
        return [symbol.lower()]


class YahooProvider(DataProvider):
    """Yahoo Finance 行情源（走 VPN 代理连接池，开启盘前盘后分时与官方复权）。"""

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

        df = await self._fetch_yahoo_direct(ticker, yahoo_interval, need_resample, resample_rule)
        if not df.empty:
            if not full and len(df) > count:
                df = df.iloc[-count:].reset_index(drop=True)
            return df
        return pd.DataFrame()

    @staticmethod
    def _dispatch_resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
        if rule in ('QS', '2QS', 'YS'):
            if not validate_klines(df, '1d'):
                return pd.DataFrame()
            return resample_to_period(df, rule)
        if rule == '4h':
            return resample_to_4h(df)
        return df

    async def _fetch_yahoo_direct(
        self, ticker: str, interval: str, need_resample: bool, resample_rule: str = None
    ) -> pd.DataFrame:
        hosts = [
            "https://query1.finance.yahoo.com/v8/finance/chart",
            "https://query2.finance.yahoo.com/v8/finance/chart",
        ]
        safe_ticker = ticker.replace('^', '%5E')
        is_intraday_req = interval in ('1m', '2m', '5m', '15m', '30m', '60m', '1h')
        is_crypto = market_of(ticker) == 'crypto'
        if interval in ('1m', '2m', '5m', '15m', '30m'):
            r_range = '15d'
        elif interval in ('60m', '1h'):
            r_range = '90d'
        elif is_crypto and interval in ('1d', '1wk'):
            r_range = '10y'
        else:
            r_range = 'max'
        # 开启美股盘前盘后分时数据
        prepost_param = "&includePrePost=true" if is_intraday_req else ""

        async def _query_data(query_range: str):
            client = await get_proxy_client()
            for host in hosts:
                url = f"{host}/{safe_ticker}?range={query_range}&interval={interval}&events=splits{prepost_param}"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        return resp.json()
                except Exception as e:
                    print(f"[YahooDirect] {host} error: {e}")
            return None

        def _parse_chart_json(data_json) -> pd.DataFrame:
            if data_json is None:
                return pd.DataFrame()
            try:
                result = data_json.get("chart", {}).get("result")
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

                is_intraday = is_intraday_req or (need_resample and resample_rule == '4h')
                rows = []
                for i, t in enumerate(ts):
                    if i >= len(closes) or closes[i] is None:
                        continue
                    dt = datetime.fromtimestamp(t, tz=US_EAST)
                    date_str = dt.strftime('%Y-%m-%d %H:%M') if is_intraday else dt.strftime('%Y-%m-%d')
                    c_val = float(closes[i])
                    o_val = float(opens[i]) if i < len(opens) and opens[i] is not None else c_val
                    h_val = float(highs[i]) if i < len(highs) and highs[i] is not None else max(o_val, c_val)
                    l_val = float(lows[i]) if i < len(lows) and lows[i] is not None else min(o_val, c_val)
                    v_val = float(vols[i]) if i < len(vols) and vols[i] is not None else 0.0
                    rows.append({
                        "date": date_str,
                        "open": o_val,
                        "high": h_val,
                        "low": l_val,
                        "close": c_val,
                        "volume": v_val,
                    })

                df = pd.DataFrame(rows)
                if df.empty:
                    return pd.DataFrame()
                df = df.dropna(subset=['open', 'high', 'low', 'close'])
                df = df.drop_duplicates(subset=['date'], keep='last').sort_values('date').reset_index(drop=True)
                return df
            except Exception as e:
                print(f"[YahooDirect] parse error: {e}")
                return pd.DataFrame()

        data = await _query_data(r_range)
        df = _parse_chart_json(data)

        # 针对加密货币或 Yahoo 异常将 range=max 降采样为月线的标的，使用 10y 兜底重试
        if interval in ('1d', '1wk') and r_range == 'max':
            chk_period = '1d' if interval == '1d' else '1w'
            if df.empty or not validate_klines(df, chk_period):
                data_10y = await _query_data('10y')
                df_10y = _parse_chart_json(data_10y)
                if not df_10y.empty and validate_klines(df_10y, chk_period):
                    df = df_10y

        if df.empty:
            return pd.DataFrame()

        if need_resample and resample_rule:
            df = YahooProvider._dispatch_resample(df, resample_rule)

        return df.reset_index(drop=True) if len(df) >= 1 else pd.DataFrame()

    @staticmethod
    def _to_yahoo_ticker(symbol: str) -> str:
        """将平台代码转换为 Yahoo Finance ticker（复用 symbols.py 的归一与市场识别）。"""
        s = symbol.strip().lower()
        if s in FUTURES_YAHOO_MAP:
            return FUTURES_YAHOO_MAP[s]

        # 加密货币：BTC/USDT、BTCUSDT、BTC/USD、USBTC 等统一由 normalize_symbol 收敛为 XXX-USD
        if market_of(symbol) == 'crypto':
            return normalize_symbol(symbol) or symbol.upper()

        if s.startswith("sh"):
            return symbol[2:].upper() + ".SS"
        if s.startswith("sz"):
            return symbol[2:].upper() + ".SZ"
        if s.startswith("hk"):
            return symbol[2:].upper().zfill(5) + ".HK"
        if "." in symbol:
            base = symbol.split(".")[0]
            if base.lower().startswith("us"):
                return base[2:].upper()
            return base.upper()
        if s.startswith("us"):
            return symbol[2:].upper()
        return symbol.upper()

class SinaFuturesProvider(DataProvider):
    """新浪财经国际期货数据源（走本地直连连接池）。"""

    SINA_FUTURES_CODE = {
        "nqmain": "NQ",
        "esmain": "ES",
        "ymmain": "YM",
        "vxmain": "VX",
    }
    _KLINE_URL = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php"

    def __init__(self):
        super().__init__("sina")

    def supports_period(self, period: str) -> bool:
        return period in PERIOD_MAP

    def _to_code(self, symbol: str) -> Optional[str]:
        return self.SINA_FUTURES_CODE.get(symbol.lower())

    async def fetch_klines(self, symbol: str, period: str, count: int = 320, full: bool = False) -> pd.DataFrame:
        code = self._to_code(symbol)
        if not code or period in ('5m', '15m', '1h', '4h'):
            return pd.DataFrame()
        df = await self._fetch_daily(code)
        if df.empty:
            return pd.DataFrame()
        if period == '1d':
            return df
        rule = _FUTURES_RESAMPLE_RULE.get(period)
        return resample_to_period(df, rule) if rule else pd.DataFrame()

    async def _fetch_daily(self, code: str) -> pd.DataFrame:
        now = datetime.now()
        cb = f"_S{now.year}_{now.month}_{now.day}"
        url = (
            f"{self._KLINE_URL}/var%20{cb}=/GlobalFuturesService.getGlobalFuturesDailyKLine"
            f"?symbol={code}&_={now.year}_{now.month}_{now.day}&source=web"
        )
        try:
            client = await get_direct_client()
            resp = await client.get(url, headers={"Referer": "https://finance.sina.com.cn/"})
            if resp.status_code != 200:
                return pd.DataFrame()
            return self._parse_klines(resp.text)
        except Exception as e:
            print(f"[Sina] {code} kline error: {e}")
            return pd.DataFrame()

    @staticmethod
    def _parse_klines(text: str) -> "pd.DataFrame":
        if not text:
            return pd.DataFrame()
        m = re.search(r"=\s*\(?\s*(\[.*\])\s*\)?\s*;?\s*$", text, re.DOTALL)
        if not m:
            return pd.DataFrame()
        try:
            rows = json.loads(m.group(1))
        except Exception:
            return pd.DataFrame()
        if not isinstance(rows, list) or not rows:
            return pd.DataFrame()
        out = []
        for r in rows:
            try:
                out.append({
                    "date": str(r.get("date", "")),
                    "open": float(r.get("open", 0) or 0),
                    "close": float(r.get("close", 0) or 0),
                    "high": float(r.get("high", 0) or 0),
                    "low": float(r.get("low", 0) or 0),
                    "volume": float(r.get("volume", 0) or 0),
                })
            except (ValueError, TypeError):
                continue
        if not out:
            return pd.DataFrame()
        df = pd.DataFrame(out)[["date", "open", "high", "low", "close", "volume"]]
        return df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

class DataProviderManager:
    """数据源管理器：在开启 VPN 环境下优先使用 Yahoo，腾讯/新浪直连无缝兜底。"""

    def __init__(self):
        self.tencent = TencentProvider()
        self.yahoo = YahooProvider()
        self.sina = SinaFuturesProvider()
        self._last_source: Optional[str] = None
        self._mem_cache: dict = {}

    @property
    def last_source(self) -> Optional[str]:
        return self._last_source

    async def fetch_klines(
        self, symbol: str, period: str = '1d', count: int = 320, full: bool = False, bypass_cache: bool = False
    ) -> pd.DataFrame:
        if period not in SUPPORTED_PERIODS:
            raise HTTPException(status_code=400, detail=f"不支持的K线周期: '{period}'")

        cache_key = (symbol.lower(), period, full)
        ttl = 8 if period in ('5m', '15m', '1h', '4h') else 45
        now_ts = datetime.now().timestamp()
        if not bypass_cache and cache_key in self._mem_cache:
            ts, cached_df, src = self._mem_cache[cache_key]
            if now_ts - ts < ttl:
                self._last_source = src
                return cached_df.copy()

        if symbol.lower().startswith(("sh", "sz", "hk")):
            self._last_source = None
            raise HTTPException(
                status_code=404,
                detail=f"A股与港股已停用，无法获取 {symbol} 的 {period} K线数据"
            )

        mkt = market_of(symbol)
        is_crypto = mkt == 'crypto'
        is_futures = mkt == 'futures'
        is_us = mkt == 'us'

        if is_crypto:
            candidates = [self.yahoo]
        elif is_futures:
            # 期货分时走 Yahoo (NQ=F)，日周月走新浪 + Yahoo 双保险
            candidates = [self.yahoo, self.sina] if period in ('5m', '15m', '1h', '4h') else [self.sina, self.yahoo]
        elif is_us:
            candidates = [self.yahoo, self.tencent]
        else:
            candidates = [self.tencent]

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
            best_df = df
            best_source = src.name
            break  # 主源成功即刻返回，不再冗余请求备源拖慢响应

        if best_df is not None and not best_df.empty:
            self._last_source = best_source
            # 仅对腾讯未复权数据执行启发式拆股复权；Yahoo 已含官方拆股调整，跳过二次除权
            if best_source == "tencent" and period in ('1d', '1w', '1M') and not is_futures:
                best_df = apply_forward_adjustment(best_df)

            if len(self._mem_cache) > 60:
                oldest_key = min(self._mem_cache.keys(), key=lambda k: self._mem_cache[k][0])
                self._mem_cache.pop(oldest_key, None)
            self._mem_cache[cache_key] = (now_ts, best_df.copy(), best_source)
            return best_df

        self._last_source = None
        raise HTTPException(
            status_code=404,
            detail=f"无法获取 {symbol} 的 {period} K线数据，请确认股票代码是否正确"
        )

provider_manager = DataProviderManager()
