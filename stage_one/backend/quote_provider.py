# -*- coding: utf-8 -*-
"""
多市场实时行情拉取与限流防护（VPN 直连分流 + 零连坐阻塞 + 末次缓存兜底版）
路径: stage_one/backend/quote_provider.py
"""
import asyncio
import time
from typing import Dict, List, Optional, Tuple

import httpx

from quote_config import (
    ABSOLUTE_MIN_INTERVAL, RATE_LIMIT_COOLDOWN, EMPTY_COOLDOWN,
    REQUEST_TIMEOUT, IP_WINDOW_SECONDS, IP_MAX_REQUESTS_PER_WINDOW,
    IP_OVERLOAD_SLOWDOWN_FACTOR, market_of, get_market_cfg,
)
from data_provider import YahooProvider, US_EAST
from datetime import datetime

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_QUOTE_HOST = "https://qt.gtimg.cn/q="

# 腾讯 q= 接口返回字段下标
_IDX_NAME = 1
_IDX_PRICE = 3
_IDX_PREV_CLOSE = 4
_IDX_OPEN = 5
_IDX_TIMESTAMP = 30
_IDX_CHANGE = 31
_IDX_CHANGE_PCT = 32
_IDX_HIGH = 33
_IDX_LOW = 34
_IDX_EXT_PRICE = 67  # 美股盘前/盘后/夜盘价格

class QuoteRateLimiter:
    """服务端限流护盾：消除单股空数据连坐与前后端定时器微秒抢跑。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._last_per_symbol: Dict[str, float] = {}
        self._symbol_cooldown_until: Dict[str, float] = {}
        self._cooldown_until = 0.0
        self._cooldown_reason = ""
        self._ip_timestamps: List[float] = []
        self._slowdown = 1.0

    async def allow(self, market: str, symbol: str) -> Tuple[bool, str]:
        async with self._lock:
            now = time.time()
            if now < self._cooldown_until:
                return False, "cooling"
            if now < self._symbol_cooldown_until.get(symbol, 0.0):
                return False, "empty_cooling"

            self._ip_timestamps = [t for t in self._ip_timestamps if now - t < IP_WINDOW_SECONDS]
            if len(self._ip_timestamps) >= IP_MAX_REQUESTS_PER_WINDOW:
                self._cooldown_until = now + RATE_LIMIT_COOLDOWN * 0.5
                self._cooldown_reason = "ip_overload"
                self._slowdown = IP_OVERLOAD_SLOWDOWN_FACTOR
                return False, "ip_overload"

            # 预留 0.4s 容差（且不低于 0.1s 红线），彻底根除前端定时器准点到达被误判 too_frequent
            raw_min = get_market_cfg(market)["min_interval"] * self._slowdown
            effective_min = max(ABSOLUTE_MIN_INTERVAL, raw_min - 0.4)
            last = self._last_per_symbol.get(symbol, 0.0)
            if now - last < effective_min:
                return False, "too_frequent"
            return True, "ok"

    def record_symbol(self, symbol: str) -> None:
        self._last_per_symbol[symbol] = time.time()

    def record_http_call(self) -> None:
        """按次记录真实 HTTP 批量请求（1 次批量请求记 1 次 IP 请求）。"""
        self._ip_timestamps.append(time.time())

    def on_rate_limited(self) -> None:
        """仅当收到 HTTP 403/429 时进入全局冷却。"""
        self._cooldown_until = time.time() + RATE_LIMIT_COOLDOWN
        self._cooldown_reason = "rate_limited"
        self._slowdown = IP_OVERLOAD_SLOWDOWN_FACTOR

    def on_symbol_empty(self, symbol: str) -> None:
        """仅对无数据的单个标的独立冷却，绝不阻塞其他正常美股。"""
        self._symbol_cooldown_until[symbol] = time.time() + EMPTY_COOLDOWN

    def status(self) -> Dict:
        now = time.time()
        return {
            "cooling": now < self._cooldown_until,
            "reason": self._cooldown_reason if now < self._cooldown_until else "",
            "cooldown_remaining": max(0.0, round(self._cooldown_until - now, 1)),
            "slowdown": round(self._slowdown, 2),
            "window_requests": len([t for t in self._ip_timestamps if now - t < IP_WINDOW_SECONDS]),
        }

# 关键：trust_env=False 强制绕过系统 VPN 代理，让腾讯/新浪接口直接走物理网卡毫秒级直连
_direct_http_client: Optional[httpx.AsyncClient] = None
_direct_http_client_loop = None

async def _get_direct_client() -> httpx.AsyncClient:
    global _direct_http_client, _direct_http_client_loop
    cur_loop = None
    try:
        cur_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass
    if _direct_http_client is None or _direct_http_client.is_closed or _direct_http_client_loop != cur_loop or (cur_loop and cur_loop.is_closed()):
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=40)
        _direct_http_client = httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT, "Referer": "https://gu.qq.com/"},
            timeout=REQUEST_TIMEOUT,
            limits=limits,
            verify=False,
            trust_env=False,  # 核心修复：绕过系统 VPN，直连国内行情源
        )
        _direct_http_client_loop = cur_loop
    return _direct_http_client

_proxy_http_client: Optional[httpx.AsyncClient] = None
_proxy_http_client_loop = None

async def _get_proxy_client() -> httpx.AsyncClient:
    global _proxy_http_client, _proxy_http_client_loop
    cur_loop = None
    try:
        cur_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass
    if _proxy_http_client is None or _proxy_http_client.is_closed or _proxy_http_client_loop != cur_loop or (cur_loop and cur_loop.is_closed()):
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=40)
        _proxy_http_client = httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            timeout=6.0,
            limits=limits,
            verify=False,
            trust_env=True,
        )
        _proxy_http_client_loop = cur_loop
    return _proxy_http_client

class YahooCryptoQuoteProvider:
    """通过 Yahoo Chart API (走 VPN 代理) 获取加密货币 24/7 实时行情。"""

    def __init__(self) -> None:
        self._last_good: Dict[str, dict] = {}

    async def get_quotes(self, symbols: List[str]) -> List[dict]:
        results: List[dict] = []
        client = await _get_proxy_client()
        hosts = [
            "https://query1.finance.yahoo.com/v8/finance/chart",
            "https://query2.finance.yahoo.com/v8/finance/chart",
        ]
        for sym in symbols:
            ticker = YahooProvider._to_yahoo_ticker(sym)
            if not ticker or ticker == sym.upper():
                ticker = sym.upper().replace("/", "-").replace("_", "-")
                if ticker.endswith("-USDT"):
                    ticker = ticker[:-5] + "-USD"
                elif ticker.endswith("USDT"):
                    ticker = ticker[:-4] + "-USD"
                elif "-" not in ticker:
                    ticker = f"{ticker}-USD"

            success = False
            for host in hosts:
                url = f"{host}/{ticker}?range=2d&interval=1m"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        result_list = data.get("chart", {}).get("result")
                        if result_list and len(result_list) > 0:
                            meta = result_list[0].get("meta", {})
                            price = float(meta["regularMarketPrice"])
                            prev_close = float(meta.get("chartPreviousClose") or meta.get("previousClose") or price)
                            change = round(price - prev_close, 2)
                            change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0
                            market_time = meta.get("regularMarketTime")
                            if market_time:
                                u_time = datetime.fromtimestamp(market_time, tz=US_EAST).strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                u_time = datetime.now(tz=US_EAST).strftime("%Y-%m-%d %H:%M:%S")

                            item = {
                                "symbol": sym,
                                "name": ticker,
                                "price": price,
                                "prev_close": prev_close,
                                "open": float(meta.get("regularMarketOpen") or prev_close),
                                "high": float(meta.get("regularMarketDayHigh") or price),
                                "low": float(meta.get("regularMarketDayLow") or price),
                                "change": change,
                                "change_pct": change_pct,
                                "update_time": u_time,
                                "market": "crypto",
                                "delay_label": get_market_cfg("crypto")["delay_label"],
                                "status": "ok",
                                "extended_price": None,
                                "extended_label": "",
                            }
                            self._last_good[sym] = item
                            self._last_good[ticker] = item
                            results.append(item)
                            success = True
                            break
                except Exception as e:
                    print(f"[Quote-Crypto] {sym} ({host}) 获取波动: {e}")

            if not success:
                if sym in self._last_good:
                    results.append(self._last_good[sym])
                elif ticker in self._last_good:
                    fallback_item = dict(self._last_good[ticker])
                    fallback_item["symbol"] = sym
                    results.append(fallback_item)
                else:
                    results.append(_error_item(sym, "empty", "暂未获取到加密货币行情"))
        return results

class TencentQuoteProvider:
    """腾讯免费公开实时行情 provider（带内存末次有效值缓存与盘后快照防冻结兜底）。"""

    def __init__(self) -> None:
        self.limiter = QuoteRateLimiter()
        self.futures_provider = SinaFuturesQuoteProvider()
        self.crypto_provider = YahooCryptoQuoteProvider()
        self._last_good_quotes: Dict[str, dict] = {}
        self._post_close_snapshot: Dict[str, float] = {}

    def _resolve_us_ext_session(self, symbol: str, ext_price: float) -> Tuple[Optional[float], str]:
        """根据美东时间与盘后快照，精确判定美股扩展时段与防冻结标签。"""
        dt = datetime.now(tz=US_EAST)
        wd = dt.weekday()  # 0=Mon ... 4=Fri, 5=Sat, 6=Sun
        mins = dt.hour * 60 + dt.minute

        # 1. 常规盘中 (周一至周五 09:30 - 16:00 ET)：隐藏扩展价
        if wd < 5 and (9 * 60 + 30 <= mins < 16 * 60):
            return None, ""

        # 2. 盘前时段 (周一至周五 04:00 - 09:30 ET)
        if wd < 5 and (4 * 60 <= mins < 9 * 60 + 30):
            return ext_price, "盘前"

        # 3. 盘后时段 (周一至周五 16:00 - 20:00 ET)：持续刷新盘后快照
        if wd < 5 and (16 * 60 <= mins < 20 * 60):
            self._post_close_snapshot[symbol] = ext_price
            return ext_price, "盘后"

        # 4. 周末休市 (周五 20:00 ~ 周日 20:00 ET)：延续显示周五盘后
        if wd == 5 or (wd == 4 and mins >= 20 * 60) or (wd == 6 and mins < 20 * 60):
            return ext_price, "盘后"

        # 5. 夜盘窗口 (周日 20:00 ~ 周五 04:00 ET)：
        # 仅当扩展价格相对 20:00 盘后快照发生真实变动时才标为“夜盘”，否则保持“盘后”
        snap = self._post_close_snapshot.get(symbol)
        if snap is not None and abs(ext_price - snap) >= 0.01:
            return ext_price, "夜盘"
        return ext_price, "盘后"

    async def _fetch_yahoo_premarket(self, us_symbols: List[str]) -> Dict[str, float]:
        """美东盘前 (04:00-09:30 ET) 通过 Yahoo includePrePost=true 获取真实实时盘前价。"""
        out: Dict[str, float] = {}
        if not us_symbols:
            return out
        client = await _get_proxy_client()

        async def _one(sym: str):
            ticker = sym[2:].upper() if sym.lower().startswith("us") else sym.upper()
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1d&interval=1m&includePrePost=true"
            try:
                resp = await client.get(url, timeout=4.0)
                if resp.status_code == 200:
                    res = resp.json().get("chart", {}).get("result")
                    if res:
                        meta = res[0].get("meta", {})
                        pre_p = _to_float(meta.get("preMarketPrice"))
                        if not pre_p or pre_p <= 0:
                            # Yahoo chart API 的 meta.preMarketPrice 在盘前可能为 None，但 1m K 线序列包含实时盘前数据点
                            quotes_list = res[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
                            valid = [c for c in quotes_list if c is not None and c > 0]
                            if valid:
                                pre_p = round(float(valid[-1]), 2)
                        if pre_p and pre_p > 0:
                            out[sym] = pre_p
            except Exception:
                pass

        await asyncio.gather(*[_one(s) for s in us_symbols], return_exceptions=True)
        return out

    async def get_quotes(self, symbols: List[str]) -> List[dict]:
        crypto_syms = [s for s in symbols if market_of(s) == "crypto"]
        futures_syms = [s for s in symbols if market_of(s) == "futures"]
        disabled_syms = [s for s in symbols if s.lower().startswith(("sh", "sz", "hk")) or market_of(s) is None]
        regular_syms = [s for s in symbols if market_of(s) not in ("futures", "crypto") and s not in disabled_syms]

        tasks = []
        if crypto_syms:
            tasks.append(self.crypto_provider.get_quotes(crypto_syms))
        else:
            tasks.append(asyncio.sleep(0, result=[]))

        if futures_syms:
            tasks.append(self.futures_provider.get_quotes(futures_syms))
        else:
            tasks.append(asyncio.sleep(0, result=[]))

        if regular_syms:
            tasks.append(self._get_tencent_quotes(regular_syms))
        else:
            tasks.append(asyncio.sleep(0, result=[]))

        crypto_res, futures_res, regular_res = await asyncio.gather(*tasks)
        results: List[dict] = list(crypto_res) + list(futures_res) + list(regular_res)
        for s in disabled_syms:
            results.append(_error_item(s, "disabled", "A股与港股功能已停用，仅支持美股与期货"))
        return results

    async def _get_tencent_quotes(self, symbols: List[str]) -> List[dict]:
        allowed: List[str] = []
        blocked: Dict[str, str] = {}
        for sym in symbols:
            m = market_of(sym) or "us"
            ok, reason = await self.limiter.allow(m, sym)
            if ok:
                allowed.append(sym)
            else:
                blocked[sym] = reason

        results: List[dict] = []
        if allowed:
            self.limiter.record_http_call()
            raw_text = await self._fetch_raw(allowed)
            parsed = self._parse(raw_text, allowed)

            dt_et = datetime.now(tz=US_EAST)
            is_us_pre = dt_et.weekday() < 5 and (4 * 60 <= dt_et.hour * 60 + dt_et.minute < 9 * 60 + 30)
            us_allowed = [s for s in allowed if market_of(s) == "us"]
            yahoo_pre_map = await self._fetch_yahoo_premarket(us_allowed) if is_us_pre else {}

            for sym in allowed:
                self.limiter.record_symbol(sym)
                item = parsed.get(sym)
                if item is not None and sym in yahoo_pre_map:
                    item["extended_price"] = yahoo_pre_map[sym]
                    item["extended_label"] = "盘前"

                if item is None:
                    self.limiter.on_symbol_empty(sym)
                    if sym in self._last_good_quotes:
                        results.append(self._last_good_quotes[sym])
                    else:
                        results.append(_error_item(sym, "empty", "未返回行情数据"))
                else:
                    self._last_good_quotes[sym] = item
                    results.append(item)

        for sym, reason in blocked.items():
            # 若已有末次有效行情，在任何频控/冷却时均优先返回缓存，彻底消除前端闪烁骨架屏与断流
            if sym in self._last_good_quotes:
                cached_item = dict(self._last_good_quotes[sym])
                if reason == "cooling":
                    cached_item["status"] = "cooling"
                results.append(cached_item)
            else:
                msg = "接口冷却中" if reason == "cooling" else "频次受控"
                results.append(_error_item(sym, reason, msg))
        return results

    async def _fetch_raw(self, symbols: List[str]) -> str:
        url = _QUOTE_HOST + ",".join(symbols)
        try:
            client = await _get_direct_client()
            resp = await client.get(url)
            if resp.status_code in (403, 429):
                self.limiter.on_rate_limited()
                print(f"[Quote] HTTP {resp.status_code} 触发限流冷却")
                return ""
            resp.encoding = "gbk"
            return resp.text
        except Exception as e:
            # 偶发网络抖动不触发 30s 全局锁死
            print(f"[Quote] 瞬时网络波动 (将在下个 tick 自动重试): {e}")
            return ""

    def _parse(self, text: str, symbols: List[str]) -> Dict[str, Optional[dict]]:
        out: Dict[str, Optional[dict]] = {s: None for s in symbols}
        if not text:
            return out
        for line in text.split(";"):
            line = line.strip()
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            code = key.strip().replace("v_", "")
            val = val.strip().strip('"')
            if not val:
                continue
            parts = val.split("~")
            if len(parts) < 35:
                continue
            try:
                price = float(parts[_IDX_PRICE])
                prev_close = float(parts[_IDX_PREV_CLOSE])
                open_ = float(parts[_IDX_OPEN])
                high = _to_float(parts[_IDX_HIGH]) or max(price, open_)
                low = _to_float(parts[_IDX_LOW]) or min(price, open_)
                change = _to_float(parts[_IDX_CHANGE])
                change_pct = _to_float(parts[_IDX_CHANGE_PCT])
                m = market_of(code)
                cfg = get_market_cfg(m)
                ext_price = None
                ext_label = ""
                if m == "us" and len(parts) > _IDX_EXT_PRICE:
                    ep = _to_float(parts[_IDX_EXT_PRICE])
                    if ep is not None and ep > 0:
                        ext_price, ext_label = self._resolve_us_ext_session(code, ep)
                out[code] = {
                    "symbol": code,
                    "name": parts[_IDX_NAME],
                    "price": price,
                    "prev_close": prev_close,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "change": change,
                    "change_pct": change_pct,
                    "update_time": _format_update_time(parts[_IDX_TIMESTAMP]),
                    "market": m,
                    "delay_label": cfg["delay_label"],
                    "status": "ok",
                    "extended_price": ext_price,
                    "extended_label": ext_label,
                }
            except (ValueError, IndexError):
                continue
        return out

def _to_float(s) -> Optional[float]:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None

def _format_update_time(raw: str) -> str:
    s = (raw or "").strip()
    if len(s) == 14 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}:{s[12:14]}"
    return s

def _error_item(symbol: str, status: str, msg: str) -> dict:
    m = market_of(symbol)
    cfg = get_market_cfg(m)
    return {
        "symbol": symbol,
        "name": symbol,
        "price": None,
        "prev_close": None,
        "open": None,
        "high": None,
        "low": None,
        "change": None,
        "change_pct": None,
        "update_time": "",
        "market": m,
        "delay_label": cfg["delay_label"],
        "status": status,
        "message": msg,
        "extended_price": None,
        "extended_label": "",
    }

_SINA_FUTURES_REALTIME_HOST = "https://hq.sinajs.cn/list="
_SINA_FUTURES_CODE = {
    "nqmain": "hf_NQ",
    "esmain": "hf_ES",
    "ymmain": "hf_YM",
    "vxmain": "hf_VX",
}

class SinaFuturesQuoteProvider:
    """新浪财经国际期货实时行情 provider（失败/无数据时自动回退 Yahoo 连续合约）。"""

    def __init__(self) -> None:
        self.limiter = QuoteRateLimiter()
        self._last_good_quotes: Dict[str, dict] = {}
        self._yahoo_fallback = YahooCryptoQuoteProvider()

    async def get_quotes(self, symbols: List[str]) -> List[dict]:
        allowed: List[str] = []
        blocked: Dict[str, str] = {}
        for sym in symbols:
            ok, reason = await self.limiter.allow("futures", sym)
            if ok:
                allowed.append(sym)
            else:
                blocked[sym] = reason

        results: List[dict] = []
        missing_for_yahoo: List[str] = []

        if allowed:
            self.limiter.record_http_call()
            fetched = await self._fetch(allowed)
            for sym in allowed:
                self.limiter.record_symbol(sym)
                item = fetched.get(sym)
                if item is None:
                    missing_for_yahoo.append(sym)
                else:
                    self._last_good_quotes[sym] = item
                    results.append(item)

        if missing_for_yahoo:
            yahoo_res = await self._yahoo_fallback.get_quotes(missing_for_yahoo)
            for sym, y_item in zip(missing_for_yahoo, yahoo_res):
                if y_item.get("status") == "ok" and y_item.get("price") is not None:
                    y_item["market"] = "futures"
                    y_item["delay_label"] = get_market_cfg("futures")["delay_label"]
                    self._last_good_quotes[sym] = y_item
                    results.append(y_item)
                else:
                    self.limiter.on_symbol_empty(sym)
                    if sym in self._last_good_quotes:
                        results.append(self._last_good_quotes[sym])
                    else:
                        results.append(_error_item(sym, "empty", "暂未返回期货行情"))

        for sym, reason in blocked.items():
            if sym in self._last_good_quotes:
                results.append(self._last_good_quotes[sym])
            else:
                results.append(_error_item(sym, reason, "请求频次受控"))
        return results

    async def _fetch(self, symbols: List[str]) -> Dict[str, Optional[dict]]:
        code_map: Dict[str, str] = {}
        hf_codes: List[str] = []
        for sym in symbols:
            hf = _SINA_FUTURES_CODE.get(sym.lower())
            if hf:
                code_map[hf] = sym
                hf_codes.append(hf)
        out: Dict[str, Optional[dict]] = {s: None for s in symbols}
        if not hf_codes:
            return out
        try:
            client = await _get_direct_client()
            resp = await client.get(
                _SINA_FUTURES_REALTIME_HOST + ",".join(hf_codes),
                headers={"Referer": "https://finance.sina.com.cn/"},
            )
            resp.encoding = "gbk"
            text = resp.text
        except Exception as e:
            print(f"[Quote-Futures] 新浪请求波动: {e}")
            return out
        for line in text.split(";"):
            line = line.strip()
            if "hq_str" not in line:
                continue
            key = line.split("hq_str_", 1)[1].split("=")[0].strip()
            sym = code_map.get(key)
            if sym is None:
                continue
            item = self._parse_line(line)
            if item is not None:
                item["symbol"] = sym
                out[sym] = item
        return out

    @staticmethod
    def _parse_line(line: str) -> Optional[dict]:
        if '="' not in line:
            return None
        val = line.split('="', 1)[1].rstrip('";')
        parts = val.split(",")
        if len(parts) < 14:
            return None
        try:
            price = _to_float(parts[0])
            prev_close = _to_float(parts[7])
            open_ = _to_float(parts[8])
            high = _to_float(parts[4])
            low = _to_float(parts[5])
            name = parts[13].strip()
            date = parts[12].strip()
            time_ = parts[6].strip()
        except (ValueError, IndexError):
            return None
        if price is None or price <= 0:
            return None
        change = round(price - prev_close, 3) if prev_close else None
        change_pct = round((price - prev_close) / prev_close * 100, 3) if prev_close else None
        update_time = f"{date} {time_}".strip() if (date and time_) else ""
        return {
            "symbol": None,
            "name": name,
            "price": price,
            "prev_close": prev_close,
            "open": open_,
            "high": high,
            "low": low,
            "change": change,
            "change_pct": change_pct,
            "update_time": update_time,
            "market": "futures",
            "delay_label": get_market_cfg("futures")["delay_label"],
            "status": "ok",
            "extended_price": None,
            "extended_label": "",
        }


quote_provider = TencentQuoteProvider()
