# -*- coding: utf-8 -*-
"""
多市场实时行情拉取与限流防护
============================

数据源：腾讯免费公开实时行情接口  qt.gtimg.cn/q=<代码>
  - 该接口原生支持多市场：usAAPL（美股）/ sh600519（沪A）/ sz000001（深A）/ hk00700（港股）
  - 返回形如：v_sh600519="1~贵州茅台~600519~当前价~昨收~今开~...~涨跌幅~...";（GBK 编码）

本模块职责：
  1. TencentQuoteProvider：批量拉取并解析多市场实时行情。
  2. QuoteRateLimiter：前端「分层刷新」的服务端护盾——
     - 每标的/每市场最低刷新间隔（硬下限，绝不突破）
     - 单 IP 滑动窗口请求计数（超额自动降速，防封禁）
     - 限流(403/429)/空数据/超时 自动冷却 30s 再重试

⚠️ 设计原则：所有「间隔 / 阈值」均取自 quote_config，业务代码不硬编码。
"""
import asyncio
import time
from typing import Dict, List, Optional, Tuple

import httpx

from quote_config import (
    MARKET, ABSOLUTE_MIN_INTERVAL, RATE_LIMIT_COOLDOWN, EMPTY_COOLDOWN,
    REQUEST_TIMEOUT, IP_WINDOW_SECONDS, IP_MAX_REQUESTS_PER_WINDOW,
    IP_OVERLOAD_SLOWDOWN_FACTOR, market_of, get_market_cfg,
)
# 复用 K 线层的新浪期货合约代码表，保证实时行情与历史 K 线用同一套合约映射
from data_provider import SinaFuturesProvider

# 复用主流 UA，降低被反爬概率
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_QUOTE_HOST = "https://qt.gtimg.cn/q="

# 腾讯 q= 接口返回的字段下标（v_xxx="1~名称~代码~..."，以 ~ 分隔）
# 3:最新价 4:昨收 5:今开 30:更新时间(美股=YYYY-MM-DD HH:MM:SS / A股港股=YYYYMMDDHHMMSS)
# 31:涨跌额 32:涨跌幅(%) 1:名称
_IDX_PRICE = 3
_IDX_PREV_CLOSE = 4
_IDX_OPEN = 5
_IDX_NAME = 1
_IDX_CHANGE = 31
_IDX_CHANGE_PCT = 32
_IDX_TIMESTAMP = 30
_IDX_EXT_PRICE = 67       # 美股盘后/夜盘价格（非美股为空或0）


class QuoteRateLimiter:
    """服务端限流护盾：保证请求频率合规，避免触发数据源封禁。

    三重保护：
      1) 全局冷却：限流/异常后进入冷却期，期间拒绝一切请求。
      2) 每标的最低间隔：低于市场合规下限的请求直接拒绝（too_frequent）。
      3) 单 IP 滑动窗口计数：单位时间请求过多 → 降速（放大全局间隔倍率）。
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._last_per_symbol: Dict[str, float] = {}
        self._cooldown_until = 0.0          # 全局冷却截止时间戳
        self._cooldown_reason = ""          # 冷却原因（便于前端提示）
        self._ip_timestamps: List[float] = []  # 滑动窗口内的请求时间戳
        self._slowdown = 1.0                # 超额后的全局间隔放大倍率

    async def allow(self, market: str, symbol: str) -> Tuple[bool, str]:
        """判断该标的此刻是否被允许请求。

        返回 (允许?, 拒绝原因)。原因取值：
          ok         允许
          cooling    全局冷却中（限流/异常）
          ip_overload 单 IP 窗口请求过多，已降速
          too_frequent 该标的低于市场最低刷新间隔
        """
        async with self._lock:
            now = time.time()
            # 1) 全局冷却
            if now < self._cooldown_until:
                return False, "cooling"
            # 2) 单 IP 滑动窗口计数
            self._ip_timestamps = [t for t in self._ip_timestamps if now - t < IP_WINDOW_SECONDS]
            if len(self._ip_timestamps) >= IP_MAX_REQUESTS_PER_WINDOW:
                # 触发降速：进入短时冷却并放大倍率
                self._cooldown_until = now + RATE_LIMIT_COOLDOWN * 0.5
                self._cooldown_reason = "ip_overload"
                self._slowdown = IP_OVERLOAD_SLOWDOWN_FACTOR
                return False, "ip_overload"
            # 3) 每标的/每市场最低间隔（受降速倍率影响）
            min_interval = get_market_cfg(market)["min_interval"] * self._slowdown
            last = self._last_per_symbol.get(symbol, 0.0)
            if now - last < min_interval:
                return False, "too_frequent"
            return True, "ok"

    def record(self, symbol: str) -> None:
        """请求成功后登记时间戳（用于间隔与计数统计）。"""
        now = time.time()
        self._last_per_symbol[symbol] = now
        self._ip_timestamps.append(now)

    def on_rate_limited(self) -> None:
        """触发 403/429 限流：进入 30s 冷却并降速。"""
        self._cooldown_until = time.time() + RATE_LIMIT_COOLDOWN
        self._cooldown_reason = "rate_limited"
        self._slowdown = IP_OVERLOAD_SLOWDOWN_FACTOR

    def on_empty(self) -> None:
        """空数据：进入 10s 冷却（避免对无效标的空转请求）。"""
        self._cooldown_until = time.time() + EMPTY_COOLDOWN
        self._cooldown_reason = "empty_data"

    def status(self) -> Dict:
        """对外暴露引擎状态，供前端展示（正常 / 限流冷却中）。"""
        return {
            "cooling": time.time() < self._cooldown_until,
            "reason": self._cooldown_reason,
            "cooldown_remaining": max(0.0, round(self._cooldown_until - time.time(), 1)),
            "slowdown": round(self._slowdown, 2),
            "window_requests": len([t for t in self._ip_timestamps
                                    if time.time() - t < IP_WINDOW_SECONDS]),
        }


# 模块级共享 HTTP 客户端（懒加载，绑定到 FastAPI 事件循环）
_http_client: Optional[httpx.AsyncClient] = None


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT, "Referer": "https://gu.qq.com/"},
            timeout=REQUEST_TIMEOUT,
            verify=False,  # 沙箱/内网环境常见自签证书，关闭校验以兼容
        )
    return _http_client


class TencentQuoteProvider:
    """腾讯免费公开实时行情 provider（多市场：美股/A股/港股）。"""

    def __init__(self) -> None:
        self.limiter = QuoteRateLimiter()
        # 期货主力合约走新浪实时行情源（腾讯 qt 接口不含期货）
        self.futures_provider = SinaFuturesQuoteProvider()

    async def get_quotes(self, symbols: List[str]) -> List[dict]:
        """批量获取实时行情，内置限流护盾，并按市场路由数据源。

        期货（NQmain/ESmain/YMmain/VXmain）→ 东方财富实时源；
        其余（美股/A股/港股）→ 腾讯 qt 接口。
        返回每个标的的行情 dict；被限流 / 拉取失败的标的会带 status 字段说明原因，
        不会抛异常（前端据此展示「冷却中 / 限流」状态，而非崩溃）。
        """
        futures_syms = [s for s in symbols if market_of(s) == "futures"]
        regular_syms = [s for s in symbols if market_of(s) != "futures"]

        results: List[dict] = []
        if futures_syms:
            results.extend(await self.futures_provider.get_quotes(futures_syms))
        if regular_syms:
            results.extend(await self._get_tencent_quotes(regular_syms))
        return results

    async def _get_tencent_quotes(self, symbols: List[str]) -> List[dict]:
        """腾讯 qt 接口的批量行情（美股/A股/港股）。"""
        # 1) 限流过滤：仅保留此刻被允许的标的
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
            raw_text = await self._fetch_raw(allowed)
            parsed = self._parse(raw_text, allowed)
            for sym in allowed:
                self.limiter.record(sym)
                item = parsed.get(sym)
                if item is None:
                    # 接口返回但解析为空 → 空数据冷却，并标记为 error
                    self.limiter.on_empty()
                    results.append(self._error_item(sym, "empty", "未返回行情数据（可能已退市或无交易）"))
                else:
                    results.append(item)

        # 2) 被限流的标的返回对应状态（前端展示冷却/降速提示）
        for sym, reason in blocked.items():
            msg = "请求过于频繁，已进入冷却" if reason == "cooling" else "请求频次超限，已自动降速"
            results.append(self._error_item(sym, reason, msg))
        return results

    async def _fetch_raw(self, symbols: List[str]) -> str:
        """实际请求腾讯 q= 接口，返回原始文本（GBK）。"""
        url = _QUOTE_HOST + ",".join(symbols)
        try:
            client = await _get_client()
            resp = await client.get(url)
            resp.encoding = "gbk"  # 腾讯行情接口为 GBK 编码
            return resp.text
        except httpx.HTTPStatusError as e:
            # 403/429 等 → 触发限流冷却
            self.limiter.on_rate_limited()
            print(f"[Quote] HTTP 异常 {e.response.status_code}，已触发冷却")
            return ""
        except Exception as e:
            # 超时 / 网络异常 → 视为限流冷却，保护后端不被反复重试拖垮
            self.limiter.on_rate_limited()
            print(f"[Quote] 请求失败: {e}")
            return ""

    def _parse(self, text: str, symbols: List[str]) -> Dict[str, Optional[dict]]:
        """解析 v_xxx="1~名称~代码~..." 格式文本为多市场行情 dict。"""
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
            if len(parts) < 49:
                # 字段不足，视为无效/空数据
                continue
            try:
                price = float(parts[_IDX_PRICE])
                prev_close = float(parts[_IDX_PREV_CLOSE])
                open_ = float(parts[_IDX_OPEN])
                change = _to_float(parts[_IDX_CHANGE])
                change_pct = _to_float(parts[_IDX_CHANGE_PCT])
                m = market_of(code)
                cfg = get_market_cfg(m)
                # 美股扩展交易时段价格（盘后/夜盘）：字段67
                # 非美股或无数据时为 None
                ext_price = None
                if m == 'us' and len(parts) > _IDX_EXT_PRICE:
                    ep = _to_float(parts[_IDX_EXT_PRICE])
                    if ep is not None and ep > 0:
                        ext_price = ep
                out[code] = {
                    "symbol": code,
                    "name": parts[_IDX_NAME],
                    "price": price,
                    "prev_close": prev_close,
                    "open": open_,
                    "change": change,            # 涨跌额
                    "change_pct": change_pct,    # 涨跌幅 %
                    "update_time": _format_update_time(parts[_IDX_TIMESTAMP]),
                    "market": m,
                    "delay_label": cfg["delay_label"],
                    "status": "ok",
                    "extended_price": ext_price,
                }
            except (ValueError, IndexError):
                # 个别字段解析失败 → 该标的视为空
                continue
        return out

    @staticmethod
    def _error_item(symbol: str, status: str, msg: str) -> dict:
        """构造一个带错误状态的行情条目。"""
        m = market_of(symbol)
        cfg = get_market_cfg(m)
        return {
            "symbol": symbol,
            "name": symbol,
            "price": None,
            "prev_close": None,
            "open": None,
            "change": None,
            "change_pct": None,
            "update_time": "",
            "market": m,
            "delay_label": cfg["delay_label"],
            "status": status,
            "message": msg,
            "extended_price": None,
        }


def _to_float(s) -> Optional[float]:
    """安全转 float，兼容数值(东财 fltt=2 返回 float/int)与字符串(腾讯 GBK 解析)。

    None / 空串 / 无法解析 → None；0 这类合法数值正常返回 0.0。
    """
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
    """统一更新时间为 'YYYY-MM-DD HH:MM:SS'。

    腾讯不同市场格式不一：
      - 美股: 已是 '2026-07-14 16:00:01'
      - A股/港股: 紧凑 '20260715120530'（YYYYMMDDHHMMSS）
    无法识别则原样返回或留空。
    """
    s = (raw or "").strip()
    if len(s) == 14 and s.isdigit():
        try:
            return f"{s[0:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}:{s[12:14]}"
        except Exception:
            return s
    return s


def _error_item(symbol: str, status: str, msg: str) -> dict:
    """构造一个带错误状态的行情条目（模块级，供多 provider 复用）。"""
    m = market_of(symbol)
    cfg = get_market_cfg(m)
    return {
        "symbol": symbol,
        "name": symbol,
        "price": None,
        "prev_close": None,
        "open": None,
        "change": None,
        "change_pct": None,
        "update_time": "",
        "market": m,
        "delay_label": cfg["delay_label"],
        "status": status,
        "message": msg,
        "extended_price": None,
    }


# ============================================================
# 新浪财经 国际期货实时行情（国内直连可达，无需 VPN / cookie）
# —— 与 K 线层 SinaFuturesProvider 共用同一套合约代码表
# ============================================================
_SINA_FUTURES_REALTIME_HOST = "https://hq.sinajs.cn/list="
# 平台期货代码(xxxmain) -> 新浪 hf_ 实时行情代码(用于 hq.sinajs.cn/list=hf_xxx)
_SINA_FUTURES_CODE = {
    "nqmain": "hf_NQ",
    "esmain": "hf_ES",
    "ymmain": "hf_YM",
    "vxmain": "hf_VX",
}


class SinaFuturesQuoteProvider:
    """新浪财经国际期货（CME 连续合约）实时行情 provider。

    - 数据源：hq.sinajs.cn/list=hf_NQ,...（GBK 编码，需带 Referer）。
    - 大陆直连可达（无需 cookie / VPN），解决东方财富 push2 需反爬 cookie（连
      接重置 → 404 / Server disconnected）、Yahoo 在沙箱/国内被墙的问题。
    - 复用 K 线层 SinaFuturesProvider.SINA_FUTURES_CODE 的合约映射（本处单独维护
      一份 hf_ 代码表，保持实时源与 K 线源解耦）。
    """

    def __init__(self) -> None:
        self.limiter = QuoteRateLimiter()

    async def get_quotes(self, symbols: List[str]) -> List[dict]:
        """批量获取期货实时行情，内置限流护盾（与 Tencent 共用同一套限流模型）。"""
        allowed: List[str] = []
        blocked: Dict[str, str] = {}
        for sym in symbols:
            ok, reason = await self.limiter.allow("futures", sym)
            if ok:
                allowed.append(sym)
            else:
                blocked[sym] = reason

        results: List[dict] = []
        if allowed:
            fetched = await self._fetch(allowed)
            for sym in allowed:
                self.limiter.record(sym)
                item = fetched.get(sym)
                if item is None:
                    self.limiter.on_empty()
                    results.append(_error_item(sym, "empty", "未返回期货行情（可能合约代码不匹配或暂无交易）"))
                else:
                    results.append(item)

        for sym, reason in blocked.items():
            msg = "请求过于频繁，已进入冷却" if reason == "cooling" else "请求频次超限，已自动降速"
            results.append(_error_item(sym, reason, msg))
        return results

    async def _fetch(self, symbols: List[str]) -> Dict[str, Optional[dict]]:
        """批量拉取新浪期货实时行情，按平台代码回填。"""
        # 平台代码 -> 新浪 hf_ 代码
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
            client = await _get_client()
            # 新浪要求 Referer: finance.sina.com.cn，覆盖共享客户端的默认 Referer
            resp = await client.get(
                _SINA_FUTURES_REALTIME_HOST + ",".join(hf_codes),
                headers={"Referer": "https://finance.sina.com.cn/"},
            )
            resp.encoding = "gbk"  # 新浪行情接口为 GBK 编码
            text = resp.text
        except Exception as e:
            print(f"[Quote-Futures] 新浪请求失败: {e}")
            return out
        for line in text.split(";"):
            line = line.strip()
            if "hq_str" not in line:
                continue
            # 从 "var hq_str_hf_NQ=..." 抽取 hf 代码
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
        """解析单行 var hq_str_hf_NQ="a,b,c,..." 为统一行情 dict。

        字段下标（实测对齐 K 线棒，已交叉验证）：
          [0]  最新价   [4]  最高   [5]  最低   [6]  时间(HH:MM:SS)
          [7]  昨收     [8]  今开   [12] 日期(YYYY-MM-DD)  [13] 名称
        涨跌额/涨跌幅由 最新价 - 昨收 推算。
        """
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
        if price is None:
            return None
        change = None
        change_pct = None
        if prev_close:
            change = round(price - prev_close, 3)
            change_pct = round((price - prev_close) / prev_close * 100, 3)
        update_time = f"{date} {time_}".strip() if (date and time_) else ""
        return {
            "symbol": None,  # 由调用方回填具体合约代码
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
        }


# 后端单例（全局共享限流状态）
quote_provider = TencentQuoteProvider()
