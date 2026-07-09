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
import os
import json
import pandas as pd
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException, Query
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import List, Dict, Optional

from analysis import calculate_sr_levels, calculate_range_stats
from data_provider import provider_manager, SUPPORTED_PERIODS
from db_cache import init_db, get_cached_klines, save_klines

app = FastAPI(title="智能股票技术分析平台")
from fastapi.responses import RedirectResponse

@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")

# 启用 CORS 跨域支持，允许前端本地调试
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 本地美股股票池，用于模糊匹配
STOCKS_POOL = [
    {"symbol": "usAAPL", "name": "苹果 Apple", "pinyin": "pg"},
    {"symbol": "usNVDA", "name": "英伟达 NVIDIA", "pinyin": "ywd"},
    {"symbol": "usTSLA", "name": "特斯拉 Tesla", "pinyin": "tsl"},
    {"symbol": "usAMD", "name": "超微半导体 AMD", "pinyin": "cw"},
    {"symbol": "usMSFT", "name": "微软 Microsoft", "pinyin": "wr"},
    {"symbol": "usMETA", "name": "Meta", "pinyin": "meta"},
    {"symbol": "usGOOGL", "name": "谷歌 Alphabet", "pinyin": "gg"},
    {"symbol": "usAMZN", "name": "亚马逊 Amazon", "pinyin": "ymx"},
    {"symbol": "usMU", "name": "美光科技 Micron", "pinyin": "mg"},
    {"symbol": "usSNDK", "name": "闪迪 SanDisk", "pinyin": "sd"}
]


# ============================================================
# 本地缓存封装 + 启动预热
# ============================================================
# 预热热门股列表 (首次打开页面 / 默认自选常用标的),
# 启动时在后台异步拉取并写入 SQLite, 后续请求直接命中缓存, 大幅提升首屏速度。
PREWARM_SYMBOLS = [
    "usAAPL", "usNVDA", "usTSLA", "usAMD", "usMSFT",
    "usMETA", "usGOOGL", "usAMZN", "usMU",
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


@app.on_event("startup")
async def startup_event():
    # 确保数据库表存在
    init_db()
    # 后台预热 (不阻塞启动; 无外网时静默失败)
    import asyncio
    asyncio.create_task(prewarm_cache())


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


class WatchlistRequest(BaseModel):
    symbols: List[str] = []   # 自选股代码列表 (纯大写，如 AAPL)


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
async def search_stocks(keyword: Optional[str] = Query(None, description="搜索股票名称、代码或拼音缩写")):
    """
    提供本地常用美股股票的模糊匹配。若无匹配，纯字母可以作为美股代码直接加载。
    """
    if not keyword:
        return STOCKS_POOL

    kw = keyword.strip().lower()
    matched = []

    # 1. 尝试匹配本地常用股票池
    for stock in STOCKS_POOL:
        if (kw in stock["symbol"].lower() or
            kw in stock["name"].lower() or
            kw in stock["pinyin"].lower()):
            matched.append(stock)

    if matched:
        return matched

    # 2. 如果无匹配，判定是否为美股代码格式
    if len(kw) > 2 and kw.startswith("us"):
        return [{"symbol": kw, "name": f"美股 {kw[2:].upper()}"}]

    if kw.isalpha():
        symbol_formatted = f"us{kw.upper()}"
        return [{"symbol": symbol_formatted, "name": f"美股 {kw.upper()}"}]

    return []


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
# ============================================================
WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.json")
DEFAULT_WATCHLIST = ["AAPL", "NVDA", "TSLA"]


@app.get("/api/watchlist")
async def get_watchlist():
    """获取用户自选股列表 (后端持久化，跨会话/预览生效)"""
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {"symbols": [str(s).upper() for s in data]}
        # 无文件则写入默认并返回
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_WATCHLIST, f)
        return {"symbols": DEFAULT_WATCHLIST}
    except Exception:
        return {"symbols": DEFAULT_WATCHLIST}


@app.post("/api/watchlist")
async def save_watchlist(req: WatchlistRequest):
    """保存用户自选股列表到后端"""
    # 规范化: 大写、去 US 前缀、去重、保序
    norm: List[str] = []
    for s in req.symbols:
        s = str(s).upper().replace("US", "").strip()
        if s and s not in norm:
            norm.append(s)
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(norm, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存自选失败: {e}")
    return {"symbols": norm}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
