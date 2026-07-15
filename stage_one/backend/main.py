# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 后端主入口文件
基于 FastAPI 框架，提供股票搜索、多周期K线获取以及支撑阻力位/区间统计接口。

支持的数据源:
  主源: 腾讯证券 (web.ifzq.gtimg.cn)
  备源: Yahoo Finance (yfinance) — 自动故障转移

支持的K线周期:
  4h  -> 4小时K线 (由1小时数据重采样)
  1d  -> 日K线
  1w  -> 周K线
  1M  -> 月K线
  3M  -> 季K线 (由日线重采样, 每根=一个季度)
  6M  -> 半年K线 (由日线重采样, 每根=半年)
  1Y  -> 年K线 (由日线重采样, 每根=一年)
"""

# pyrefly: ignore [missing-import]
from contextlib import asynccontextmanager
import os
import re
import uuid
import json
import asyncio
import pandas as pd
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
import httpx
from fastapi import FastAPI, HTTPException, Query
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import List, Dict, Optional

from analysis import calculate_sr_levels, calculate_range_stats
from data_provider import provider_manager, SUPPORTED_PERIODS
from db_cache import init_db, get_cached_klines, save_klines
# 多市场实时行情模块（腾讯免费公开接口 qt.gtimg.cn/q=）
from quote_provider import quote_provider
from quote_config import (
    MARKET, TICK_MS, ABSOLUTE_MIN_INTERVAL, RATE_LIMIT_COOLDOWN,
    IP_MAX_REQUESTS_PER_WINDOW, IP_WINDOW_SECONDS, ADAPTIVE_COLD_THRESHOLD,
    ADAPTIVE_COLD_FACTOR, ADAPTIVE_MAX_FACTOR,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 确保数据库表存在
    init_db()
    # 后台预热 (不阻塞启动; 无外网时静默失败)
    asyncio.create_task(prewarm_cache())
    yield

app = FastAPI(title="智能股票技术分析平台", lifespan=lifespan)
from fastapi.responses import RedirectResponse

@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")


@app.get("/api/health")
def health_check():
    """轻量级健康检查：前端用于探测后端是否在线，从而自动决定
    演示模式(模拟数据) / 实时模式(真实数据)。不依赖任何外部数据源。"""
    return {"status": "ok", "mode": "real"}


# ============================================================
# 实时行情（多市场：美股 / A股 / 港股）—— 腾讯免费公开接口
# ============================================================

@app.get("/api/quote")
async def get_quote(
    symbols: str = Query(..., description="逗号分隔的带前缀代码, 如 usAAPL,sh600519,hk00700"),
):
    """
    批量获取多市场实时行情（腾讯 qt.gtimg.cn/q=）。

    返回结构:
      {
        "quotes": [ {symbol,name,price,prev_close,open,change,change_pct,
                     update_time,market,delay_label,status} , ... ],
        "engine": { cooling, reason, cooldown_remaining, slowdown, window_requests }
      }
    - 前端「分层刷新」：本地定时器按各市场最低间隔触发请求，本接口内置限流护盾，
      被限流的标的会带 status='cooling'/'rate_limited' 等，前端据此展示冷却状态。
    - 单批上限 50 个标的，避免一次性过大请求。
    """
    # 仅把市场前缀规范为小写（腾讯 q= 接口对大小写敏感：usAAPL 可识别，USAAPL 不行），
    # 其余字符保持原样，避免破坏代码本身。
    import re
    def _norm_code(s: str) -> str:
        s = s.strip()
        return re.sub(r'^(US|SH|SZ|HK)', lambda m: m.group(1).lower(), s)
    syms = [_norm_code(s) for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=400, detail="symbols 不能为空")
    if len(syms) > 50:
        raise HTTPException(status_code=400, detail="单次最多请求 50 个标的")

    quotes = await quote_provider.get_quotes(syms)
    engine = quote_provider.limiter.status()
    return {"quotes": quotes, "engine": engine}


@app.get("/api/quote_config")
async def quote_config():
    """
    下发前端实时行情引擎所需的全部配置（刷新间隔 / 延迟标注 / 限流阈值 / 美股盘前盘后）。
    所有数值集中在后端 quote_config.py，前端只读取、不自行硬编码，保证前后端一致。
    """
    return {
        "tickMs": TICK_MS,
        "absoluteMinInterval": ABSOLUTE_MIN_INTERVAL,
        "rateLimitCooldown": RATE_LIMIT_COOLDOWN,
        "ipMaxRequests": IP_MAX_REQUESTS_PER_WINDOW,
        "ipWindow": IP_WINDOW_SECONDS,
        "adaptive": {
            "coldThreshold": ADAPTIVE_COLD_THRESHOLD,
            "coldFactor": ADAPTIVE_COLD_FACTOR,
            "maxFactor": ADAPTIVE_MAX_FACTOR,
        },
        "markets": {
            k: {
                "name": v["name"],
                "minInterval": v["min_interval"],
                "batchInterval": v["batch_interval"],
                "serverUpdate": v["server_update"],
                "delayLabel": v["delay_label"],
                "delayFull": v["delay_full"],
                "sessions": v.get("sessions", {}),
            }
            for k, v in MARKET.items()
        },
    }


# 启用 CORS 跨域支持，允许前端本地调试
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 市场工具函数 (前后端约定: 带市场前缀的统一代码格式)
#   美股: usAAPL   沪A: sh600000   深A: sz000001   港股: hk00700
# ============================================================
MARKET_LABEL = {"us": "美股", "ash": "沪A", "asz": "深A", "hk": "港股"}


def norm_market_prefix(sym: str) -> str:
    """腾讯 k线 / 行情接口对市场前缀大小写敏感, 统一规范为小写 (HK00700 -> hk00700)。

    这是修复「港股 / A股 K线 404」的根因: 前端与 /api/watchlist 统一返回大写前缀
    (如 HK00700 / SH600519), 但腾讯要求小写 (hk00700 / sh600519), 否则返回
    "param error"。美股分支本身已自动小写 us 前缀, 此处对所有市场统一兜底。
    """
    if not sym:
        return sym
    return re.sub(r'^(US|SH|SZ|HK)', lambda m: m.group(1).lower(), sym, flags=re.IGNORECASE)


def normalize_symbol(raw: str, market: Optional[str] = None) -> Optional[str]:
    """把用户输入归一化为带市场前缀的统一代码。"""
    s = (raw or "").strip().upper()
    if not s:
        return None
    if s.startswith(("US", "SH", "SZ", "HK")):
        return s
    if market == "us":
        return "US" + s
    if market == "ash":
        return "SH" + s
    if market == "asz":
        return "SZ" + s
    if market == "hk":
        digits = "".join(ch for ch in s if ch.isdigit())
        return "HK" + digits.zfill(5)
    # 自动识别
    if s.isdigit():
        if len(s) == 6:
            return ("SH" if s[0] == "6" else "SZ") + s
        if len(s) <= 5:
            return "HK" + s.zfill(5)
    return "US" + s


def market_of(symbol: str) -> Optional[str]:
    s = symbol.upper()
    if s.startswith("US"):
        return "us"
    if s.startswith("SH"):
        return "ash"
    if s.startswith("SZ"):
        return "asz"
    if s.startswith("HK"):
        return "hk"
    return None


def strip_prefix(symbol: str) -> str:
    s = symbol.upper()
    for p in ("US", "SH", "SZ", "HK"):
        if s.startswith(p):
            return s[len(p):]
    return s


# 本地常用股票池 (覆盖美股 / A股 / 港股)，用于模糊匹配
STOCKS_POOL = [
    # 美股
    {"symbol": "usAAPL", "name": "苹果 Apple", "pinyin": "pg", "pinyin_full": "pingguo", "market": "us"},
    {"symbol": "usNVDA", "name": "英伟达 NVIDIA", "pinyin": "ywd", "pinyin_full": "yingweida", "market": "us"},
    {"symbol": "usTSLA", "name": "特斯拉 Tesla", "pinyin": "tsl", "pinyin_full": "tesila", "market": "us"},
    {"symbol": "usAMD", "name": "超微半导体 AMD", "pinyin": "cw", "pinyin_full": "chaowei", "market": "us"},
    {"symbol": "usMSFT", "name": "微软 Microsoft", "pinyin": "wr", "pinyin_full": "weiruan", "market": "us"},
    {"symbol": "usMETA", "name": "Meta", "pinyin": "meta", "pinyin_full": "meta", "market": "us"},
    {"symbol": "usGOOGL", "name": "谷歌 Alphabet", "pinyin": "gg", "pinyin_full": "guge", "market": "us"},
    {"symbol": "usAMZN", "name": "亚马逊 Amazon", "pinyin": "ymx", "pinyin_full": "yamaxun", "market": "us"},
    {"symbol": "usMU", "name": "美光科技 Micron", "pinyin": "mg", "pinyin_full": "meiguang", "market": "us"},
    {"symbol": "usSNDK", "name": "闪迪 SanDisk", "pinyin": "sd", "pinyin_full": "shandi", "market": "us"},
    # A股 (沪市)
    {"symbol": "sh600519", "name": "贵州茅台", "pinyin": "mt", "pinyin_full": "maotai", "market": "ash"},
    {"symbol": "sh601318", "name": "中国平安", "pinyin": "zgap", "pinyin_full": "zhongguopingan", "market": "ash"},
    {"symbol": "sh600036", "name": "招商银行", "pinyin": "zsyh", "pinyin_full": "zhaoshangyinhang", "market": "ash"},
    {"symbol": "sh600276", "name": "恒瑞医药", "pinyin": "hryy", "pinyin_full": "hengruiyiyao", "market": "ash"},
    {"symbol": "sh600900", "name": "长江电力", "pinyin": "cjdl", "pinyin_full": "changjiangdianli", "market": "ash"},
    # A股 (深市)
    {"symbol": "sz000001", "name": "平安银行", "pinyin": "payh", "pinyin_full": "pinganyinhang", "market": "asz"},
    {"symbol": "sz000858", "name": "五粮液", "pinyin": "wly", "pinyin_full": "wuliangye", "market": "asz"},
    {"symbol": "sz300750", "name": "宁德时代", "pinyin": "ndsd", "pinyin_full": "ningdeshidai", "market": "asz"},
    {"symbol": "sz002594", "name": "比亚迪", "pinyin": "byd", "pinyin_full": "biyadi", "market": "asz"},
    {"symbol": "sz000333", "name": "美的集团", "pinyin": "mdjt", "pinyin_full": "meidejituan", "market": "asz"},
    # 港股
    {"symbol": "hk00700", "name": "腾讯控股", "pinyin": "tx", "pinyin_full": "tengxunkonggu", "market": "hk"},
    {"symbol": "hk09988", "name": "阿里巴巴", "pinyin": "albb", "pinyin_full": "alibaba", "market": "hk"},
    {"symbol": "hk03690", "name": "美团", "pinyin": "mt", "pinyin_full": "meituan", "market": "hk"},
    {"symbol": "hk01810", "name": "小米集团", "pinyin": "xm", "pinyin_full": "xiaomi", "market": "hk"},
    {"symbol": "hk00939", "name": "建设银行", "pinyin": "jsyh", "pinyin_full": "jiansheyinhang", "market": "hk"},
]


# ============================================================
# 本地缓存封装 + 启动预热
# ============================================================
# 预热热门股列表 (首次打开页面 / 默认自选常用标的),
# 启动时在后台异步拉取并写入 SQLite, 后续请求直接命中缓存, 大幅提升首屏速度。
PREWARM_SYMBOLS = [
    "usAAPL", "usNVDA", "usTSLA", "usAMD", "usMSFT",
    "usMETA", "usGOOGL", "usAMZN", "usMU",
    "sh600519", "sh601318", "sz000858", "hk00700", "hk09988",
]
PREWARM_PERIODS = ["1d", "1w", "1M", "3M", "6M", "1Y"]
CACHE_TTL_HOURS = 24


async def get_klines_df(symbol: str, period: str, full: bool = True):
    """
    带本地缓存的 K线获取封装。

    返回: (df, source)
      - 命中且未过期的缓存: 从 SQLite 读取, source='cache'
      - 未命中 / 过期:      从数据源拉取并写回缓存, source=实际数据源名
    全量模式 (full=True) 才走缓存; 非全量场景极少, 直接拉取。
    """
    # 规范市场前缀为小写 (腾讯接口大小写敏感: HK00700/SH600519 会 param error)。
    # 统一在此处归一化, 保证缓存键与下游数据源调用一致, 杜绝港股/A股 404。
    symbol = norm_market_prefix(symbol)
    if full:
        cached = get_cached_klines(symbol, period, max_age_hours=CACHE_TTL_HOURS)
        if cached is not None:
            df = pd.DataFrame(cached)
            return df, "cache"

    df = await provider_manager.fetch_klines(symbol, period=period, full=full)
    if df.empty:
        return df, None

    if full:
        klines = [
            {
                "date": str(row["date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            for _, row in df.iterrows()
        ]
        source = provider_manager.last_source or ""
        save_klines(symbol, period, klines, source)
        return df, source

    return df, provider_manager.last_source


async def prewarm_cache():
    """后台预热热门股历史数据到本地缓存 (best-effort, 失败不阻塞主流程)。"""
    for sym in PREWARM_SYMBOLS:
        for period in PREWARM_PERIODS:
            try:
                df, src = await get_klines_df(sym, period, full=True)
                if df is not None and not df.empty:
                    print(f"[Prewarm] 已缓存 {sym} {period} ({len(df)} 根) 来源={src}")
            except Exception as e:
                print(f"[Prewarm] 跳过 {sym} {period}: {e}")





# ============================================================
# 数据模型 (Pydantic)
# ============================================================

class KLinePoint(BaseModel):
    time: str          # 日/周/月线: 'YYYY-MM-DD' | 4小时线: 'YYYY-MM-DD HH:MM'
    open: float
    high: float
    low: float
    close: float
    volume: float


class AnalysisRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    period: str = "1d"   # K线周期: '4h'/'1d'/'1w'/'1M'


class WatchGroupModel(BaseModel):
    id: str
    name: str
    stocks: List[str] = []   # 该分组下的自选股 (带市场前缀, 如 usAAPL)


class WatchlistGroupsRequest(BaseModel):
    groups: List[WatchGroupModel] = []


class SRLevel(BaseModel):
    price: float
    count: int
    type: str           # 'support' 或 'resistance'
    stars: int          # 2, 3, 5 星
    level: str          # 'Weak', 'Medium', 'Strong'


class RangeStat(BaseModel):
    pct: float
    start: str
    end: str


class AnalysisResponse(BaseModel):
    sr_levels: List[SRLevel]
    statistics: Dict[str, RangeStat]
    period: str = "1d"          # 实际使用的K线周期
    data_source: str = ""       # 实际命中的数据源


# ============================================================
# API 端点
# ============================================================

@app.get("/api/search")
async def search_stocks(
    keyword: Optional[str] = Query(None, description="搜索股票名称、英文名称、代码或拼音缩写（全市场范围内）"),
):
    """
    全局证券搜索（系统入口级检索）：
      - 本地常用股票池(美股/A股/港股)优先模糊匹配，覆盖 中文名/英文名/代码/拼音缩写 四维度；
      - 本地池未命中时，异步调用腾讯全量证券搜索兜底，实现「任意证券」定位；
      - 仍无匹配：把输入当作代码，按自动识别归一化为带前缀代码（兼容直接输代码进分析）。
    """
    if not keyword:
        # 空关键词：返回全部在池股票（浏览用）
        return STOCKS_POOL

    kw = keyword.strip().lower()
    # 过滤关键字中的拼音字样以处理诸如 “小米拼音” 的搜索
    kw_clean = kw.replace("拼音", "").strip()
    matched = []

    # 1. 尝试匹配本地常用股票池 (全市场，五维度)
    for stock in STOCKS_POOL:
        if (kw_clean in stock["symbol"].lower() or
            kw_clean in stock["name"].lower() or
            kw_clean in stock.get("pinyin", "").lower() or
            kw_clean in stock.get("pinyin_full", "").lower() or
            kw_clean in stock.get("name_en", "").lower()):
            matched.append(stock)

    if matched:
        return matched

    # 2. 本地池未命中：腾讯全量证券搜索兜底（任意证券）
    try:
        tencent = await _tencent_security_search(kw_clean)
        if tencent:
            return tencent
    except Exception as e:
        print(f"[search] 腾讯全量搜索失败，降级到代码归一化: {e}")

    # 3. 仍无匹配：仅当输入「像代码」(全 ASCII，如纯字母/数字/带前缀) 时按自动识别归一化；
    #    含中文等自然语言输入若本地池与腾讯都无果，直接返回空，避免生成 "US台积电" 这类假代码。
    if kw_clean.isascii():
        norm = normalize_symbol(kw_clean)
        if norm:
            m = market_of(norm)
            label = MARKET_LABEL.get(m, "")
            return [{"symbol": norm, "name": f"{label} {strip_prefix(norm)}"}]

    return []


async def _tencent_security_search(kw: str) -> list:
    """
    腾讯全量证券搜索兜底：覆盖本地池之外的「任意证券」。
    优先用结构化 proxy 接口，失败回退到 smartbox JSONP 接口。
    返回 STOCKS_POOL 同构列表（symbol/market/name/name_en/pinyin?）。
    任何异常/超时均返回 []，由调用方降级。
    """
    # 规范化腾讯返回的各类代码为统一「带市场前缀」形态（去交易所后缀，避免污染缓存键）
    def _norm_code(code: str) -> Optional[str]:
        if not code:
            return None
        c = code.strip().lower()
        # 已带市场前缀：sh/sz/hk/us
        if c.startswith(("sh", "sz", "hk", "us")):
            # 美股可能带 .o/.oq/.n/.nq/.am 等后缀，仅保留前缀+主体
            if c.startswith("us") and "." in c:
                c = c.split(".", 1)[0]
            return c.upper()
        # 纯英文（无前缀）→ 美股
        if re.fullmatch(r"[a-z]+", c):
            return "US" + c.upper()
        # 纯数字 → 自动识别沪深/港股
        if c.isdigit():
            return normalize_symbol(c)
        return None

    def _pool_item(code: str, name: str, pinyin: str = "", type_: str = "") -> Optional[dict]:
        sym = _norm_code(code)
        if not sym:
            return None
        m = market_of(sym)
        label = MARKET_LABEL.get(m, "")
        # 名称中可能含中英文混写，尝试拆出英文名
        name_en = ""
        parts = re.split(r"[\s\-]+", name.strip())
        if len(parts) > 1:
            en = [p for p in parts if re.search(r"[a-zA-Z]", p)]
            if en:
                name_en = " ".join(en)
        return {
            "symbol": sym,
            "name": name.strip(),
            "name_en": name_en,
            "market": m or "",
            "pinyin": pinyin,
            "label": label,
            "type": type_,
        }

    candidates: list = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SecuritySearch/1.0)"}
    try:
        # 唯一可靠兜底源：smartbox.gtimg.cn（返回 v_hint="market~code~name~pinyin~type^..." 赋值形式，非 JSONP）。
        # 注：proxy.finance.qq.com 在本环境经常性超时/返回 code:11（Can't load controller），
        # 且其慢响应会吃掉超时预算、导致兜底源被饿死，故弃用，仅保留 smartbox。
        async with httpx.AsyncClient(timeout=5.0, headers=headers, follow_redirects=True) as client:
            url = f"https://smartbox.gtimg.cn/s3/?t=all&q={kw}"
            try:
                resp = await client.get(url)
                txt = resp.text
                # 提取所有 "..." 内容（腾讯以 v_xxx="..." 赋值返回）
                for q in re.findall(r'"([^"]*)"', txt):
                    try:
                        q = json.loads('"' + q + '"')  # 解码 \uXXXX 转义
                    except Exception:
                        pass
                    if not q or q == "N":
                        continue  # "N" 为腾讯「无结果」标记
                    # 多个证券以 ^ 分隔，每个内部以 ~ 分隔（市场~代码~名称~拼音~类型）
                    for seg in q.split("^"):
                        rows = seg.split("~")
                        if len(rows) >= 3 and rows[0] in ("us", "sh", "sz", "hk"):
                            full_code = rows[0] + rows[1]
                            name = rows[2]
                            pinyin = rows[3] if len(rows) > 3 else ""
                            type_ = rows[4] if len(rows) > 4 else ""
                            item = _pool_item(full_code, name, pinyin, type_)
                            if item and item["symbol"] not in [c["symbol"] for c in candidates]:
                                candidates.append(item)
                                if len(candidates) >= 20:
                                    break
                    if len(candidates) >= 20:
                        break
            except Exception:
                pass
    except Exception:
        return []

    # 优先展示普通股(GP)，指数/权证/基金/窝轮等靠后，结果更贴近「搜股票」预期
    candidates.sort(key=lambda c: (0 if c.get("type") == "GP" else 1))
    return candidates[:20]


@app.get("/api/klines", response_model=List[KLinePoint])
async def get_klines(
    symbol: str = Query(..., description="股票代码，如 usAAPL"),
    period: str = Query("1d", description="K线周期: 4h/1d/1w/1M/3M/6M/1Y"),
    full: bool = Query(True, description="是否拉取上市以来全部历史 (默认 True)")
):
    """
    获取指定美股股票的多周期K线历史数据。

    支持周期:
      - 4h: 4小时K线 (由1小时数据重采样合成)
      - 1d: 日K线 (默认)
      - 1w: 周K线
      - 1M: 月K线
      - 3M: 季K线 (由日线重采样, 每根=一个季度)
      - 6M: 半年K线 (由日线重采样, 每根=半年)
      - 1Y: 年K线 (由日线重采样, 每根=一年)

    full=True 时拉取该股票上市以来的全部历史数据 (优先 Yahoo range=max)。
    数据源自动故障转移: Yahoo(全量优先) -> 腾讯(兜底)
    """
    if period not in SUPPORTED_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的K线周期: '{period}'，支持: {', '.join(SUPPORTED_PERIODS)}"
        )

    df, source = await get_klines_df(symbol, period=period, full=full)

    if df.empty:
        raise HTTPException(status_code=404, detail="无法获取该股票数据")

    points = []
    for _, row in df.iterrows():
        points.append(KLinePoint(
            time=str(row['date']),
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume'])
        ))

    return points


@app.post("/api/analysis", response_model=AnalysisResponse)
async def analyze_stock(request: AnalysisRequest):
    """
    获取股票在特定区间内的支撑阻力位分析结果及涨跌幅区间统计。

    支撑阻力位会根据 K线周期 (period) 自适应调整:
      - 4h:  捕捉短期波段高低点 (半衰期30根)
      - 1d:  日线级别 (半衰期60根)
      - 1w:  周线级别 (半衰期26根)
      - 1M:  月线级别 (半衰期12根)
      - 3M:  季线级别 (半衰期8根)
      - 6M:  半年线级别 (半衰期5根)
      - 1Y:  年线级别 (半衰期4根)
    """
    period = request.period if request.period in SUPPORTED_PERIODS else '1d'

    # 1. 获取 K 线 DataFrame (全量历史，用于支撑阻力识别与时间衰减权重)
    df, source = await get_klines_df(request.symbol, period=period, full=True)

    if df.empty:
        raise HTTPException(status_code=404, detail="分析时获取股票数据失败")

    # 2. 计算支撑与阻力位 (传入 period 使算法自适应)
    sr_levels = calculate_sr_levels(df, period=period)

    # 3. 计算特定日期区间的统计数据
    stats = calculate_range_stats(df, request.start_date, request.end_date)

    return {
        "sr_levels": sr_levels,
        "statistics": stats,
        "period": period,
        "data_source": source or ""
    }


@app.get("/api/periods")
async def get_supported_periods():
    """获取支持的K线周期列表"""
    return {
        "periods": SUPPORTED_PERIODS,
        "descriptions": {
            "4h": "4小时K线 (短期波段, 仅后端)",
            "1d": "日K线 (默认)",
            "1w": "周K线 (中期趋势)",
            "1M": "月K线 (长期结构)",
            "3M": "季K线 (每根=一个季度)",
            "6M": "半年K线 (每根=半年)",
            "1Y": "年K线 (每根=一年)"
        }
    }


# ============================================================
# 自选股持久化 (后端 JSON 文件存储，跨浏览器/origin 生效)
# 数据模型: 用户自创「分组」，前缀/市场不再由系统硬分，而由用户把标的放进哪
#           个分组来表达 (如「港股观察」「美股核心」)。分组结构:
#             { "groups": [ { "id": str, "name": str, "stocks": [str] }, ... ] }
# ============================================================
WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.json")
# 默认分组（首次启动即体现多市场能力，但仅作为示例分组，用户可自由改名/删除/另建）
DEFAULT_GROUP_NAME = "我的自选"
DEFAULT_WATCHLIST = ["usAAPL", "usNVDA", "sh600519", "hk00700"]


def _default_groups() -> List[dict]:
    return [{"id": "default", "name": DEFAULT_GROUP_NAME, "stocks": list(DEFAULT_WATCHLIST)}]


def _load_groups() -> List[dict]:
    """读取分组。兼容旧版扁平 list 文件（归入默认分组）。"""
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 新格式: {"groups": [...]}
            if isinstance(data, dict) and isinstance(data.get("groups"), list):
                return data["groups"]
            # 旧格式兼容: 扁平 list -> 归入默认分组
            if isinstance(data, list):
                stocks = [str(s).upper() for s in data if s]
                if stocks:
                    return [{"id": "default", "name": DEFAULT_GROUP_NAME, "stocks": stocks}]
        # 无文件则写入默认并返回
        groups = _default_groups()
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump({"groups": groups}, f)
        return groups
    except Exception:
        return _default_groups()


def _save_groups(groups: List[dict]) -> List[dict]:
    """规范化分组后落盘: 大写、去首尾空格、去重、保序；缺 id 自动生成。"""
    norm: List[dict] = []
    for g in groups:
        stocks: List[str] = []
        for s in g.get("stocks", []):
            s = str(s).upper().strip()
            if s and s not in stocks:
                stocks.append(s)
        gid = g.get("id") or str(uuid.uuid4())
        gname = (g.get("name") or "").strip() or DEFAULT_GROUP_NAME
        norm.append({"id": gid, "name": gname, "stocks": stocks})
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump({"groups": norm}, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存自选失败: {e}")
    return norm


@app.get("/api/watchlist")
async def get_watchlist():
    """获取用户自选分组 (后端持久化，跨会话/预览生效)。"""
    return {"groups": _load_groups()}


@app.post("/api/watchlist")
async def save_watchlist(req: WatchlistGroupsRequest):
    """保存用户自选分组到后端。"""
    norm = _save_groups([g.dict() for g in req.groups])
    return {"groups": norm}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
