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

    async def get_quotes(self, symbols: List[str]) -> List[dict]:
        """批量获取实时行情，内置限流护盾。

        返回每个标的的行情 dict；被限流 / 拉取失败的标的会带 status 字段说明原因，
        不会抛异常（前端据此展示「冷却中 / 限流」状态，而非崩溃）。
        """
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


def _to_float(s: str) -> Optional[float]:
    """安全转 float，空字符串返回 None。"""
    s = (s or "").strip()
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


# 后端单例（全局共享限流状态）
quote_provider = TencentQuoteProvider()
