# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 后端主入口文件
基于 FastAPI 框架，提供股票搜索、多周期K线获取、支撑阻力位/区间统计接口及 WebSocket 控制面。
"""

from contextlib import asynccontextmanager
import base64
import os
import re
import uuid
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Any

import httpx
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from analysis import calculate_sr_levels, calculate_range_stats
from data_provider import provider_manager, SUPPORTED_PERIODS
from db_cache import (
    init_db,
    get_cached_klines,
    save_klines,
    save_annotations_batch,
    get_annotations,
    clear_annotations,
)
from quote_provider import quote_provider
from quote_config import (
    MARKET,
    TICK_MS,
    ABSOLUTE_MIN_INTERVAL,
    RATE_LIMIT_COOLDOWN,
    IP_MAX_REQUESTS_PER_WINDOW,
    IP_WINDOW_SECONDS,
    ADAPTIVE_COLD_THRESHOLD,
    ADAPTIVE_COLD_FACTOR,
    ADAPTIVE_MAX_FACTOR,
)
from strategy_adapter import run_strategy_analysis, generate_wave_chart_html
from symbols import (
    MARKET_LABEL,
    norm_market_prefix,
    normalize_symbol,
    market_of,
    strip_prefix,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DATA_DIR = os.path.join(BASE_DIR, "data")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    asyncio.create_task(prewarm_cache())
    yield


app = FastAPI(title="智能股票技术分析平台", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 前端构建产物静态文件托管
DIST_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend", "dist")
if os.path.exists(DIST_DIR):
    assets_dir = os.path.join(DIST_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
def read_root():
    if os.path.exists(DIST_DIR):
        index_file = os.path.join(DIST_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
    return RedirectResponse(url="/docs")


@app.get("/api/health")
def health_check():
    """轻量级健康检查：前端用于探测后端是否在线，自动决定演示/实时模式。"""
    return {"status": "ok", "mode": "real"}


# ============================================================
# 实时行情（多市场：美股 / 期货 / 加密货币）
# ============================================================

@app.get("/api/quote")
async def get_quote(
    symbols: str = Query(..., description="逗号分隔的带前缀代码, 如 usAAPL,BTC-USD"),
):
    syms = [norm_market_prefix(s) for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=400, detail="symbols 不能为空")
    if len(syms) > 50:
        raise HTTPException(status_code=400, detail="单次最多请求 50 个标的")

    quotes = await quote_provider.get_quotes(syms)
    engine = quote_provider.limiter.status()
    return {"quotes": quotes, "engine": engine}


@app.get("/api/quote_config")
async def quote_config():
    """下发前端实时行情引擎所需的全部集中配置。"""
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


# 本地常用股票池 (覆盖美股 / 加密 / 期货)，用于高精度模糊匹配与纠错
STOCKS_POOL = [
    # ── 美股科技七巨头 (Mag 7) ──────────────────────────
    {"symbol": "usAAPL", "name": "苹果 Apple", "pinyin": "pg", "pinyin_full": "pingguo", "aliases": ["APPLE", "AAPL", "IPHONE", "MAC"], "market": "us"},
    {"symbol": "usNVDA", "name": "英伟达 NVIDIA", "pinyin": "ywd", "pinyin_full": "yingweida", "aliases": ["NVIDIA", "NVDA", "GPU", "AI"], "market": "us"},
    {"symbol": "usMSFT", "name": "微软 Microsoft", "pinyin": "wr", "pinyin_full": "weiruan", "aliases": ["MICROSOFT", "MSFT", "WINDOWS", "AZURE"], "market": "us"},
    {"symbol": "usGOOGL", "name": "谷歌 Google Alphabet (A类)", "pinyin": "gg", "pinyin_full": "guge", "aliases": ["GOOGLE", "GOOGL", "ALPHABET"], "market": "us"},
    {"symbol": "usGOOG", "name": "谷歌 Google Alphabet (C类)", "pinyin": "gg", "pinyin_full": "guge", "aliases": ["GOOGLE", "GOOG", "ALPHABET"], "market": "us"},
    {"symbol": "usAMZN", "name": "亚马逊 Amazon", "pinyin": "ymx", "pinyin_full": "yamaxun", "aliases": ["AMAZON", "AMZN", "AWS"], "market": "us"},
    {"symbol": "usMETA", "name": "Meta 脸书 Facebook", "pinyin": "fb", "pinyin_full": "meta", "aliases": ["META", "FACEBOOK", "FB", "INSTAGRAM"], "market": "us"},
    {"symbol": "usTSLA", "name": "特斯拉 Tesla", "pinyin": "tsl", "pinyin_full": "tesila", "aliases": ["TESLA", "TSLA", "ELON"], "market": "us"},

    # ── 美股核心半导体与硬科技 ──────────────────────────
    {"symbol": "usAVGO", "name": "博通 Broadcom", "pinyin": "bt", "pinyin_full": "botong", "aliases": ["BROADCOM", "AVGO"], "market": "us"},
    {"symbol": "usAMD", "name": "超微半导体 AMD", "pinyin": "cw", "pinyin_full": "chaowei", "aliases": ["AMD", "RADEON", "RYZEN"], "market": "us"},
    {"symbol": "usTSM", "name": "台积电 TSMC", "pinyin": "tjd", "pinyin_full": "taijidian", "aliases": ["TSMC", "TSM"], "market": "us"},
    {"symbol": "usQCOM", "name": "高通 Qualcomm", "pinyin": "gt", "pinyin_full": "gaotong", "aliases": ["QUALCOMM", "QCOM", "SNAPDRAGON"], "market": "us"},
    {"symbol": "usINTC", "name": "英特尔 Intel", "pinyin": "yte", "pinyin_full": "yingteer", "aliases": ["INTEL", "INTC"], "market": "us"},
    {"symbol": "usMU", "name": "美光科技 Micron", "pinyin": "mg", "pinyin_full": "meiguang", "aliases": ["MICRON", "MU", "MEMORY"], "market": "us"},
    {"symbol": "usASML", "name": "阿斯麦 ASML", "pinyin": "asm", "pinyin_full": "asimai", "aliases": ["ASML", "LITHOGRAPHY"], "market": "us"},
    {"symbol": "usARM", "name": "安谋 ARM", "pinyin": "am", "pinyin_full": "anmou", "aliases": ["ARM", "SOFTBANK"], "market": "us"},
    {"symbol": "usORCL", "name": "甲骨文 Oracle", "pinyin": "jgw", "pinyin_full": "jiaguwen", "aliases": ["ORACLE", "ORCL"], "market": "us"},
    {"symbol": "usPLTR", "name": "Palantir 帕兰提尔", "pinyin": "plt", "pinyin_full": "palantir", "aliases": ["PLTR", "PALANTIR", "AI"], "market": "us"},
    {"symbol": "usCOIN", "name": "Coinbase 加密货币", "pinyin": "cb", "pinyin_full": "coinbase", "aliases": ["COIN", "COINBASE", "CRYPTO"], "market": "us"},
    {"symbol": "usMSTR", "name": "微策略 MicroStrategy", "pinyin": "wcl", "pinyin_full": "weicelue", "aliases": ["MSTR", "MICROSTRATEGY", "BITCOIN"], "market": "us"},
    {"symbol": "usSNDK", "name": "闪迪 SanDisk", "pinyin": "sd", "pinyin_full": "shandi", "aliases": ["SANDISK", "SNDK"], "market": "us"},

    # ── 美股软件、流媒体与消费龙头 ──────────────────────
    {"symbol": "usNFLX", "name": "奈飞 Netflix", "pinyin": "nf", "pinyin_full": "naifei", "aliases": ["NETFLIX", "NFLX"], "market": "us"},
    {"symbol": "usUBER", "name": "优步 Uber", "pinyin": "yb", "pinyin_full": "youbu", "aliases": ["UBER"], "market": "us"},
    {"symbol": "usABNB", "name": "爱彼迎 Airbnb", "pinyin": "aby", "pinyin_full": "aibiying", "aliases": ["AIRBNB", "ABNB"], "market": "us"},
    {"symbol": "usCRM", "name": "赛富时 Salesforce", "pinyin": "sfs", "pinyin_full": "saifushi", "aliases": ["SALESFORCE", "CRM"], "market": "us"},
    {"symbol": "usADBE", "name": "Adobe 奥多比", "pinyin": "adb", "pinyin_full": "aoduobi", "aliases": ["ADOBE", "ADBE", "PHOTOSHOP"], "market": "us"},
    {"symbol": "usCSCO", "name": "思科 Cisco", "pinyin": "sk", "pinyin_full": "sike", "aliases": ["CISCO", "CSCO"], "market": "us"},
    {"symbol": "usSNOW", "name": "Snowflake", "pinyin": "xue", "pinyin_full": "snowflake", "aliases": ["SNOW", "SNOWFLAKE"], "market": "us"},
    {"symbol": "usDIS", "name": "迪士尼 Disney", "pinyin": "dsn", "pinyin_full": "dishini", "aliases": ["DISNEY", "DIS"], "market": "us"},
    {"symbol": "usNKE", "name": "耐克 Nike", "pinyin": "nk", "pinyin_full": "naike", "aliases": ["NIKE", "NKE"], "market": "us"},
    {"symbol": "usSBUX", "name": "星巴克 Starbucks", "pinyin": "xbk", "pinyin_full": "xingbake", "aliases": ["STARBUCKS", "SBUX"], "market": "us"},
    {"symbol": "usCOST", "name": "开市客 Costco", "pinyin": "ksk", "pinyin_full": "kaishike", "aliases": ["COSTCO", "COST"], "market": "us"},
    {"symbol": "usWMT", "name": "沃尔玛 Walmart", "pinyin": "wem", "pinyin_full": "woerma", "aliases": ["WALMART", "WMT"], "market": "us"},
    {"symbol": "usJPM", "name": "摩根大通 JPMorgan", "pinyin": "mgdt", "pinyin_full": "morgandatong", "aliases": ["JPM", "JPMORGAN"], "market": "us"},
    {"symbol": "usBAC", "name": "美国银行 BofA", "pinyin": "mgyh", "pinyin_full": "meiguoyinhang", "aliases": ["BAC", "BOFA"], "market": "us"},
    {"symbol": "usGS", "name": "高盛 Goldman Sachs", "pinyin": "gs", "pinyin_full": "gaosheng", "aliases": ["GS", "GOLDMAN"], "market": "us"},

    # ── 美股代表性 ETF ──────────────────────────────────
    {"symbol": "usSPY", "name": "标普500 ETF (SPY)", "pinyin": "spy", "pinyin_full": "biaopu500etf", "aliases": ["SPY", "SP500", "S&P500"], "market": "us"},
    {"symbol": "usQQQ", "name": "纳斯达克100 ETF (QQQ)", "pinyin": "qqq", "pinyin_full": "nasidaq100etf", "aliases": ["QQQ", "NASDAQ100", "NDX"], "market": "us"},
    {"symbol": "usDIA", "name": "道琼斯工业 ETF (DIA)", "pinyin": "dia", "pinyin_full": "daoqiongsi", "aliases": ["DIA", "DOW"], "market": "us"},
    {"symbol": "usIWM", "name": "罗素2000小盘股 ETF (IWM)", "pinyin": "iwm", "pinyin_full": "luosu2000", "aliases": ["IWM", "RUSSELL"], "market": "us"},
    {"symbol": "usSOXX", "name": "半导体行业 ETF (SOXX)", "pinyin": "soxx", "pinyin_full": "bandaoti", "aliases": ["SOXX", "SEMI", "CHIPS"], "market": "us"},
    {"symbol": "usTLT", "name": "20年+美债 ETF (TLT)", "pinyin": "tlt", "pinyin_full": "meizhai", "aliases": ["TLT", "BONDS"], "market": "us"},
    {"symbol": "usSQQQ", "name": "3倍做空纳指 ETF (SQQQ)", "pinyin": "sqqq", "pinyin_full": "sanbeizuokongnazhi", "aliases": ["SQQQ", "SHORT"], "market": "us"},
    {"symbol": "usTQQQ", "name": "3倍做多纳指 ETF (TQQQ)", "pinyin": "tqqq", "pinyin_full": "sanbeizuoduonazhi", "aliases": ["TQQQ", "LONG"], "market": "us"},

    # ── 热门中概股 ──────────────────────────────────────
    {"symbol": "usBABA", "name": "阿里巴巴 (美股 BABA)", "pinyin": "albb", "pinyin_full": "alibaba", "aliases": ["BABA", "ALIBABA", "TAOBAO"], "market": "us"},
    {"symbol": "usPDD", "name": "拼多多 PDD Holdings", "pinyin": "pdd", "pinyin_full": "pingduoduo", "aliases": ["PDD", "PINGDUODUO", "TEMU"], "market": "us"},
    {"symbol": "usJD", "name": "京东 JD.com", "pinyin": "jd", "pinyin_full": "jingdong", "aliases": ["JD", "JINGDONG"], "market": "us"},
    {"symbol": "usBILI", "name": "哔哩哔哩 Bilibili (B站)", "pinyin": "blbl", "pinyin_full": "bilibili", "aliases": ["BILI", "BILIBILI", "BZHAN"], "market": "us"},
    {"symbol": "usNIO", "name": "蔚来 NIO", "pinyin": "wl", "pinyin_full": "weilai", "aliases": ["NIO", "WEILAI"], "market": "us"},
    {"symbol": "usLI", "name": "理想汽车 Li Auto", "pinyin": "lx", "pinyin_full": "lixiang", "aliases": ["LI", "LIXIANG"], "market": "us"},
    {"symbol": "usXPEV", "name": "小鹏汽车 Xpeng", "pinyin": "xp", "pinyin_full": "xiaopeng", "aliases": ["XPEV", "XIAOPENG"], "market": "us"},
    {"symbol": "usBIDU", "name": "百度 Baidu", "pinyin": "bd", "pinyin_full": "baidu", "aliases": ["BIDU", "BAIDU"], "market": "us"},
    {"symbol": "usNTES", "name": "网易 NetEase", "pinyin": "wy", "pinyin_full": "wangyi", "aliases": ["NTES", "NETEASE"], "market": "us"},

    # ── 美股单/双倍杠杆 ETF ──────────────────────────────
    {"symbol": "usNVDL", "name": "2倍做多英伟达 ETF (NVDL)", "pinyin": "nvdl", "pinyin_full": "zuoduoyingweida", "aliases": ["NVDL", "NVDA 2X"], "market": "us"},
    {"symbol": "usAMDL", "name": "2倍做多AMD ETF (AMDL)", "pinyin": "amdl", "pinyin_full": "zuoduoamd", "aliases": ["AMDL", "AMD 2X"], "market": "us"},
    {"symbol": "usMUU", "name": "2倍做多美光 ETF (MUU)", "pinyin": "muu", "pinyin_full": "zuoduomeiguang", "aliases": ["MUU", "MU 2X"], "market": "us"},
    {"symbol": "usTSMX", "name": "2倍做多台积电 ETF (TSMX)", "pinyin": "tsmx", "pinyin_full": "zuoduotaijidian", "aliases": ["TSMX", "TSM 2X"], "market": "us"},
    {"symbol": "usSOXL", "name": "3倍做多半导体 ETF (SOXL)", "pinyin": "soxl", "pinyin_full": "sanbeizuoduobandaoti", "aliases": ["SOXL", "SEMI 3X"], "market": "us"},
    {"symbol": "usSOXS", "name": "3倍做空半导体 ETF (SOXS)", "pinyin": "soxs", "pinyin_full": "sanbeizuokongbandaoti", "aliases": ["SOXS", "SHORT SEMI"], "market": "us"},
    {"symbol": "usTSLL", "name": "2倍做多特斯拉 ETF (TSLL)", "pinyin": "tsll", "pinyin_full": "zuoduotesila", "aliases": ["TSLL", "TSLA 2X"], "market": "us"},

    # ── 期货与加密货币 ──────────────────────────────────
    {"symbol": "BTC-USD", "name": "比特币 Bitcoin (USD)", "pinyin": "btb", "pinyin_full": "bitebi", "aliases": ["BTC", "BITCOIN", "BTCUSD", "BTC/USDT", "BTCUSDT", "BTC-USDT", "USBTC"], "market": "crypto"},
    {"symbol": "ETH-USD", "name": "以太坊 Ethereum (USD)", "pinyin": "ytf", "pinyin_full": "yitaifang", "aliases": ["ETH", "ETHEREUM", "ETHUSD", "ETH/USDT", "ETHUSDT", "ETH-USDT", "USETH"], "market": "crypto"},
    {"symbol": "SOL-USD", "name": "索拉纳 Solana (USD)", "pinyin": "sol", "pinyin_full": "suolana", "aliases": ["SOL", "SOLANA", "SOLUSD", "SOL/USDT", "SOLUSDT", "SOL-USDT", "USSOL"], "market": "crypto"},
    {"symbol": "DOGE-USD", "name": "狗狗币 Dogecoin (USD)", "pinyin": "ggb", "pinyin_full": "gougoubi", "aliases": ["DOGE", "DOGECOIN", "DOGEUSD", "DOGE/USDT", "DOGEUSDT", "DOGE-USDT", "USDOGE"], "market": "crypto"},
    {"symbol": "XRP-USD", "name": "瑞波币 Ripple (USD)", "pinyin": "rbb", "pinyin_full": "ruibobi", "aliases": ["XRP", "RIPPLE", "XRPUSD", "XRP/USDT", "XRPUSDT", "XRP-USDT", "USXRP"], "market": "crypto"},
    {"symbol": "BNB-USD", "name": "币安币 BNB (USD)", "pinyin": "bab", "pinyin_full": "bianbi", "aliases": ["BNB", "BINANCE", "BNBUSD", "BNB/USDT", "BNBUSDT", "BNB-USDT", "USBNB"], "market": "crypto"},
    {"symbol": "NQmain", "name": "纳斯达克100期货 主力", "pinyin": "nq", "pinyin_full": "nasidaq100", "aliases": ["NQ", "NQMAIN"], "market": "futures"},
    {"symbol": "ESmain", "name": "标普500期货 主力", "pinyin": "es", "pinyin_full": "biaopu500", "aliases": ["ES", "ESMAIN"], "market": "futures"},
    {"symbol": "YMmain", "name": "道琼斯期货 主力", "pinyin": "ym", "pinyin_full": "daoqiongsi", "aliases": ["YM", "YMMAIN"], "market": "futures"},
    {"symbol": "VXmain", "name": "VIX恐慌指数期货 主力", "pinyin": "vx", "pinyin_full": "vix", "aliases": ["VX", "VXMAIN", "VIX"], "market": "futures"},
]


# ============================================================
# 本地缓存封装 + 启动预热
# ============================================================
PREWARM_SYMBOLS = [
    "usAAPL", "usNVDA", "usTSLA", "usAMD", "usMSFT",
    "usMETA", "usGOOGL", "usAMZN", "usAVGO", "usMU",
    "usQQQ", "usSPY",
]
CACHE_TTL_HOURS = 24


async def _patch_latest_bar_with_quote(symbol: str, period: str, df: pd.DataFrame) -> pd.DataFrame:
    """用实时行情引擎的最新价与高低点，动态校准日/周/月 K 线的最后一根蜡烛。"""
    try:
        live_res = await quote_provider.get_quotes([symbol])
        if not live_res or live_res[0].get("status") != "ok":
            return df
        q = live_res[0]
        price = q.get("price")
        if price is None or price <= 0:
            return df

        price = float(price)
        q_open = float(q["open"]) if q.get("open") else price
        q_high = float(q["high"]) if q.get("high") else price
        q_low = float(q["low"]) if q.get("low") else price
        update_time = str(q.get("update_time") or "")
        quote_date = update_time[:10] if len(update_time) >= 10 else ""

        last_idx = df.index[-1]
        last_date = str(df.at[last_idx, "date"])[:10]

        if period == "1d" and quote_date and quote_date > last_date:
            new_row = pd.DataFrame([{
                "date": quote_date,
                "open": q_open,
                "high": max(q_open, q_high, price),
                "low": min(q_open, q_low, price),
                "close": price,
                "volume": float(df.at[last_idx, "volume"]),
            }])
            df = pd.concat([df, new_row], ignore_index=True)
        elif not quote_date or quote_date >= last_date:
            df.at[last_idx, "close"] = price
            df.at[last_idx, "high"] = max(float(df.at[last_idx, "high"]), price, q_high if period == "1d" else price)
            df.at[last_idx, "low"] = min(float(df.at[last_idx, "low"]), price, q_low if period == "1d" else price)
    except Exception as e:
        print(f"[LivePatch] 缝合跳过: {e}")
    return df


async def get_klines_df(symbol: str, period: str, full: bool = True, bypass_cache: bool = False):
    norm = normalize_symbol(symbol) or symbol
    symbol = norm_market_prefix(norm)
    is_intraday = period in ("5m", "15m", "1h", "4h")

    if full and not bypass_cache:
        ttl = (10 / 3600) if is_intraday else CACHE_TTL_HOURS
        cached = get_cached_klines(symbol, period, max_age_hours=ttl)
        if cached is not None:
            df = pd.DataFrame(cached)
            if not (period == "1d" and len(df) < 30):
                if period in ("1d", "1w", "1M") and not df.empty:
                    df = await _patch_latest_bar_with_quote(symbol, period, df)
                return df, "cache"

    df = await provider_manager.fetch_klines(symbol, period=period, full=full, bypass_cache=bypass_cache)
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
        if period in ("1d", "1w", "1M"):
            df = await _patch_latest_bar_with_quote(symbol, period, df)
        return df, source

    return df, provider_manager.last_source


def _load_local_csv_fallback(norm_sym: str) -> Optional[pd.DataFrame]:
    """当远程数据源不可用时，尝试读取本地 data/<SYMBOL>.csv 兜底。"""
    clean_sym = strip_prefix(norm_sym).upper()
    csv_file = os.path.join(LOCAL_DATA_DIR, f"{clean_sym}.csv")
    if os.path.exists(csv_file):
        try:
            return pd.read_csv(csv_file)
        except Exception:
            return None
    return None


async def prewarm_cache():
    """分级启动预热：首屏报价与默认日K零延迟并发拉取，其余历史K线错峰延后。"""
    groups = _load_groups()
    watch_syms: List[str] = []
    for g in groups:
        for s in g.get("stocks", []):
            norm = norm_market_prefix(s)
            if norm and norm not in watch_syms:
                watch_syms.append(norm)

    # 1. 最高优先级（服务启动即刻并发）：预热全部自选实时报价 + 首只标的日K
    first_sym = watch_syms[0] if watch_syms else "usAAPL"
    boot_tasks = [get_klines_df(first_sym, "1d", full=True)]
    if watch_syms:
        boot_tasks.append(quote_provider.get_quotes(watch_syms))
    await asyncio.gather(*boot_tasks, return_exceptions=True)

    # 2. 低优先级（延迟 8s 错峰）：后台低速补全热门标的周/月线缓存，避免抢占首屏带宽与限流额度
    await asyncio.sleep(8)
    targets = set(PREWARM_SYMBOLS) | set(watch_syms)
    for sym in targets:
        for period in ("1d", "1w", "1M"):
            try:
                await get_klines_df(sym, period, full=True)
                await asyncio.sleep(0.15)
            except Exception:
                pass


# ============================================================
# 数据模型 (Pydantic)
# ============================================================

class KLinePoint(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class AnalysisRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    period: str = "1d"


class WatchGroupModel(BaseModel):
    id: str
    name: str
    stocks: List[str] = []


class WatchlistGroupsRequest(BaseModel):
    groups: List[WatchGroupModel] = []


class SRLevel(BaseModel):
    price: float
    count: int
    type: str
    stars: int
    level: str


class RangeStat(BaseModel):
    pct: float
    start: str
    end: str


class AnalysisResponse(BaseModel):
    sr_levels: List[SRLevel]
    statistics: Dict[str, Any]
    period: str = "1d"
    data_source: str = ""


# ============================================================
# API 端点
# ============================================================

def _score_stock(kw: str, stock: dict) -> int:
    """对搜索关键字与标的进行高精相关度评分与模糊纠错。"""
    kw_upper = kw.upper()
    sym = stock["symbol"].upper()
    raw_code = strip_prefix(sym)
    name = stock["name"].upper()
    pinyin = stock.get("pinyin", "").upper()
    pinyin_full = stock.get("pinyin_full", "").upper()
    aliases = [a.upper() for a in stock.get("aliases", [])]

    if kw_upper == raw_code or kw_upper == sym:
        return 1000
    if raw_code.startswith(kw_upper):
        return 850 - len(raw_code)

    name_words = [w.strip("()") for w in name.split()]
    if kw_upper in name_words:
        return 820
    if kw_upper in aliases:
        return 800
    if kw_upper == pinyin:
        return 750
    if kw_upper == pinyin_full:
        return 700

    clean_name = name.split()[0]
    if kw == clean_name:
        return 720
    if kw in clean_name:
        return 650

    if any(a.startswith(kw_upper) for a in aliases):
        return 600
    if pinyin_full and pinyin_full.startswith(kw.lower()):
        return 500
    if any(kw_upper in a for a in aliases):
        return 450
    if kw_upper in name:
        return 400
    if kw_upper in raw_code:
        return 350

    if len(kw) >= 3 and kw.isascii():
        import difflib
        targets = [raw_code] + aliases + name.split()
        best_ratio = 0.0
        for t in targets:
            if len(t) >= 3:
                r = difflib.SequenceMatcher(None, kw_upper, t.upper()).ratio()
                if r > best_ratio:
                    best_ratio = r
        if best_ratio >= 0.72:
            return int(300 * best_ratio)

    return 0


@app.get("/api/search")
async def search_stocks(
    keyword: Optional[str] = Query(None, description="搜索股票名称、英文名称、代码或拼音缩写（全市场范围内）"),
):
    if not keyword:
        return STOCKS_POOL

    kw = keyword.strip()
    kw_clean = kw.replace("拼音", "").strip()
    if not kw_clean:
        return STOCKS_POOL

    scored_candidates = []
    seen_symbols = set()
    for stock in STOCKS_POOL:
        score = _score_stock(kw_clean, stock)
        if score > 0:
            scored_candidates.append((score, stock))
            seen_symbols.add(stock["symbol"].upper())

    if scored_candidates:
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        if scored_candidates[0][0] >= 750 and len(scored_candidates) >= 3:
            return [c[1] for c in scored_candidates[:20]]

    try:
        tencent_results = await _tencent_security_search(kw_clean)
        for t_item in tencent_results:
            sym_upper = t_item["symbol"].upper()
            if sym_upper in seen_symbols:
                continue
            seen_symbols.add(sym_upper)
            t_score = 300 if t_item.get("type") == "GP" else 180
            if kw_clean.upper() in sym_upper:
                t_score += 150
            scored_candidates.append((t_score, t_item))
    except Exception as e:
        print(f"[search] 腾讯全量搜索异常: {e}")

    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    if scored_candidates:
        return [c[1] for c in scored_candidates[:20]]

    if kw_clean.isascii() and len(kw_clean) <= 10:
        norm = normalize_symbol(kw_clean)
        if norm:
            try:
                q_res = await quote_provider.get_quotes([norm])
                if q_res and q_res[0].get("status") == "ok" and q_res[0].get("price") is not None:
                    m = market_of(norm)
                    label = MARKET_LABEL.get(m, "")
                    real_name = q_res[0].get("name") or strip_prefix(norm)
                    return [{
                        "symbol": norm,
                        "name": f"{real_name} ({strip_prefix(norm)})",
                        "market": m or "us",
                        "label": label,
                        "type": "GP",
                    }]
            except Exception:
                pass

    return []


async def _tencent_security_search(kw: str) -> list:
    """腾讯全量证券搜索兜底：覆盖本地池之外的任意证券。"""
    def _parse_search_code(code: str) -> Optional[str]:
        if not code:
            return None
        c = code.strip().lower()
        if c.startswith("us"):
            if "." in c:
                c = c.split(".", 1)[0]
            return c.upper()
        if re.fullmatch(r"[a-z]+", c):
            return "US" + c.upper()
        return None

    def _pool_item(code: str, name: str, pinyin: str = "", type_: str = "") -> Optional[dict]:
        sym = _parse_search_code(code)
        if not sym:
            return None
        m = market_of(sym)
        label = MARKET_LABEL.get(m, "")
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
        async with httpx.AsyncClient(timeout=5.0, headers=headers, follow_redirects=True) as client:
            url = f"https://smartbox.gtimg.cn/s3/?t=all&q={kw}"
            try:
                resp = await client.get(url)
                txt = resp.text
                for q in re.findall(r'"([^"]*)"', txt):
                    try:
                        q = json.loads('"' + q + '"')
                    except Exception:
                        pass
                    if not q or q == "N":
                        continue
                    for seg in q.split("^"):
                        rows = seg.split("~")
                        if len(rows) >= 3 and rows[0] in ("us",):
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

    candidates.sort(key=lambda c: (0 if c.get("type") == "GP" else 1))
    return candidates[:20]


@app.get("/api/klines", response_model=List[KLinePoint])
async def get_klines(
    symbol: str = Query(..., description="股票代码，如 usAAPL"),
    period: str = Query("1d", description="K线周期"),
    full: bool = Query(True, description="是否拉取上市以来全部历史"),
    fresh: bool = Query(False, description="是否跳过缓存强制拉取最新数据"),
):
    if period not in SUPPORTED_PERIODS:
        raise HTTPException(status_code=400, detail=f"不支持的K线周期: '{period}'")

    df, _ = await get_klines_df(symbol, period=period, full=full, bypass_cache=fresh)
    if df.empty:
        raise HTTPException(status_code=404, detail="无法获取该股票数据")

    return [
        KLinePoint(
            time=str(row["date"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        )
        for _, row in df.iterrows()
    ]


@app.post("/api/analysis", response_model=AnalysisResponse)
async def analyze_stock(request: AnalysisRequest):
    """获取股票在特定区间内的支撑阻力位分析结果及涨跌幅区间统计。"""
    period = request.period if request.period in SUPPORTED_PERIODS else "1d"
    df, source = await get_klines_df(request.symbol, period=period, full=True)

    if df.empty:
        raise HTTPException(status_code=404, detail="分析时获取股票数据失败")

    sr_levels = calculate_sr_levels(df, period=period)
    stats = calculate_range_stats(df, request.start_date, request.end_date)

    return {
        "sr_levels": sr_levels,
        "statistics": stats,
        "period": period,
        "data_source": source or "",
    }


@app.get("/api/periods")
async def get_supported_periods():
    """获取支持的K线周期列表"""
    return {
        "periods": SUPPORTED_PERIODS,
        "descriptions": {
            "5m": "5分钟K线",
            "15m": "15分钟K线",
            "1h": "1小时K线",
            "4h": "4小时K线",
            "1d": "日K线 (默认)",
            "1w": "周K线 (中期趋势)",
            "1M": "月K线 (长期结构)",
            "3M": "季K线 (每根=一个季度)",
            "6M": "半年K线 (每根=半年)",
            "1Y": "年K线 (每根=一年)",
        },
    }


# ============================================================
# 自选股持久化
# ============================================================
WATCHLIST_FILE = os.path.join(BASE_DIR, "watchlist.json")
DEFAULT_GROUP_NAME = "我的自选"
DEFAULT_WATCHLIST = ["usAAPL", "usNVDA", "usAMD", "usTSLA", "usQQQ"]


def _default_groups() -> List[dict]:
    return [{"id": "default", "name": DEFAULT_GROUP_NAME, "stocks": list(DEFAULT_WATCHLIST)}]


def _load_groups() -> List[dict]:
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("groups"), list):
                return data["groups"]
            if isinstance(data, list):
                stocks = [str(s).upper() for s in data if s]
                if stocks:
                    return [{"id": "default", "name": DEFAULT_GROUP_NAME, "stocks": stocks}]
        groups = _default_groups()
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump({"groups": groups}, f)
        return groups
    except Exception:
        return _default_groups()


def _save_groups(groups: List[dict]) -> List[dict]:
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
    return {"groups": _load_groups()}


@app.post("/api/watchlist")
async def save_watchlist(req: WatchlistGroupsRequest):
    norm = _save_groups([g.model_dump() if hasattr(g, "model_dump") else g.dict() for g in req.groups])
    try:
        await ws_manager.broadcast({"action": "refresh_watchlist"})
    except Exception:
        pass
    return {"groups": norm}


# ============================================================
# WebSocket 双向实时管道 + HTTP 控制 API
# ============================================================

class WSManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.capture_futures: Dict[str, asyncio.Future] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)

    async def broadcast(self, data: dict):
        for conn in list(self.active_connections):
            try:
                await conn.send_json(data)
            except Exception:
                self.disconnect(conn)

    def resolve_capture(self, request_id: str, image_base64: str):
        if request_id in self.capture_futures and not self.capture_futures[request_id].done():
            self.capture_futures[request_id].set_result(image_base64)


ws_manager = WSManager()

active_chart_state = {
    "symbol": "usAAPL",
    "period": "1d",
    "current_price": 0.0,
    "last_seen": datetime.now().isoformat(),
}


@app.websocket("/ws/control")
async def websocket_control(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            msg_text = await websocket.receive_text()
            try:
                data = json.loads(msg_text)
                msg_type = data.get("type")
                if msg_type == "client_state_update":
                    active_chart_state["symbol"] = data.get("symbol", active_chart_state["symbol"])
                    active_chart_state["period"] = data.get("period", active_chart_state["period"])
                    if "current_price" in data:
                        active_chart_state["current_price"] = float(data["current_price"])
                    active_chart_state["last_seen"] = datetime.now().isoformat()
                elif msg_type == "capture_result":
                    req_id = data.get("request_id")
                    img = data.get("image_base64")
                    if req_id and img:
                        ws_manager.resolve_capture(req_id, img)
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


class OpenChartRequest(BaseModel):
    symbol: str
    period: Optional[str] = "1d"


class MarkerItem(BaseModel):
    id: Optional[str] = None
    time: Any
    position: str = "aboveBar"
    color: str = "#10b981"
    shape: str = "arrowDown"
    text: str = ""


class AddMarkersRequest(BaseModel):
    symbol: str
    markers: List[MarkerItem]
    source: Optional[str] = "agent"


class LineItem(BaseModel):
    id: Optional[str] = None
    price: float
    color: str = "#3b82f6"
    lineWidth: Optional[int] = 1
    lineStyle: Optional[int] = 2
    title: Optional[str] = ""


class DrawLinesRequest(BaseModel):
    symbol: str
    lines: List[LineItem]
    source: Optional[str] = "agent"


class BoxItem(BaseModel):
    id: Optional[str] = None
    time1: Any
    time2: Any
    price1: float
    price2: float
    fillColor: Optional[str] = "rgba(59, 130, 246, 0.12)"
    borderColor: Optional[str] = "#3b82f6"
    label: Optional[str] = ""


class DrawBoxesRequest(BaseModel):
    symbol: str
    boxes: List[BoxItem]
    source: Optional[str] = "agent"


class RunStrategyRequest(BaseModel):
    symbol: str
    period: Optional[str] = "1d"
    mode: Optional[str] = "swing"
    draw_on_chart: Optional[bool] = True
    klines: Optional[List[Dict[str, Any]]] = None


class ClearAnnotationsRequest(BaseModel):
    symbol: str
    kind: Optional[str] = None
    source: Optional[str] = None


@app.post("/api/control/open")
async def control_open(req: OpenChartRequest):
    norm_sym = normalize_symbol(req.symbol) or req.symbol
    period = req.period or "1d"
    active_chart_state["symbol"] = norm_sym
    active_chart_state["period"] = period
    active_chart_state["last_seen"] = datetime.now().isoformat()

    await ws_manager.broadcast({
        "action": "open",
        "symbol": norm_sym,
        "period": period,
    })
    return {"status": "ok", "state": active_chart_state}


@app.get("/api/control/state")
async def control_get_state():
    sym = active_chart_state["symbol"]
    annos = get_annotations(sym)
    return {
        "status": "ok",
        "state": active_chart_state,
        "connected_clients": len(ws_manager.active_connections),
        "annotations": annos,
    }


@app.post("/api/control/markers")
async def control_add_markers(req: AddMarkersRequest):
    norm_sym = normalize_symbol(req.symbol) or req.symbol
    raw_markers = [m.model_dump() if hasattr(m, "model_dump") else m.dict() for m in req.markers]
    save_annotations_batch(norm_sym, "marker", raw_markers, source=req.source or "agent")
    await ws_manager.broadcast({
        "action": "add_markers",
        "symbol": norm_sym,
        "markers": raw_markers,
    })
    return {"status": "ok", "count": len(raw_markers)}


@app.post("/api/control/lines")
async def control_draw_lines(req: DrawLinesRequest):
    norm_sym = normalize_symbol(req.symbol) or req.symbol
    raw_lines = [l.model_dump() if hasattr(l, "model_dump") else l.dict() for l in req.lines]
    save_annotations_batch(norm_sym, "line", raw_lines, source=req.source or "agent")
    await ws_manager.broadcast({
        "action": "draw_lines",
        "symbol": norm_sym,
        "lines": raw_lines,
    })
    return {"status": "ok", "count": len(raw_lines)}


@app.post("/api/control/boxes")
async def control_draw_boxes(req: DrawBoxesRequest):
    norm_sym = normalize_symbol(req.symbol) or req.symbol
    raw_boxes = [b.model_dump() if hasattr(b, "model_dump") else b.dict() for b in req.boxes]
    save_annotations_batch(norm_sym, "box", raw_boxes, source=req.source or "agent")
    await ws_manager.broadcast({
        "action": "draw_boxes",
        "symbol": norm_sym,
        "boxes": raw_boxes,
    })
    return {"status": "ok", "count": len(raw_boxes)}


@app.post("/api/control/strategy")
async def control_run_strategy(req: RunStrategyRequest):
    norm_sym = normalize_symbol(req.symbol) or req.symbol
    period = req.period or "1d"
    mode = req.mode or "swing"

    df = None
    if req.klines and len(req.klines) > 0:
        try:
            df = pd.DataFrame(req.klines)
        except Exception:
            df = None

    if df is None or df.empty:
        try:
            df, _ = await get_klines_df(norm_sym, period=period, full=True)
        except Exception:
            df = None

    if df is None or df.empty:
        df = _load_local_csv_fallback(norm_sym)

    if df is None or df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"无法获取 {norm_sym} 的 {period} K线用于策略分析，请确认网络连接或传入K线数据",
        )

    res = run_strategy_analysis(norm_sym, period=period, mode=mode, df=df)

    if req.draw_on_chart:
        clear_annotations(norm_sym, source="pa_strategy")
        annos = res.get("annotations", {})
        annotation_channels = [
            ("marker", "add_markers", "markers", annos.get("markers", [])),
            ("line", "draw_lines", "lines", annos.get("lines", [])),
            ("box", "draw_boxes", "boxes", annos.get("boxes", [])),
            ("channel_line", "draw_channel_lines", "channel_lines", annos.get("channel_lines", [])),
            ("time_line", "draw_time_lines", "time_lines", annos.get("time_lines", [])),
            ("fib_line", "draw_fib_lines", "fib_lines", annos.get("fib_lines", [])),
            ("gap_box", "draw_gap_boxes", "gap_boxes", annos.get("gap_boxes", [])),
            ("ema200", "draw_ema200", "ema200_data", annos.get("ema200_data", [])),
        ]
        for db_kind, ws_action, payload_key, items in annotation_channels:
            if items:
                save_annotations_batch(norm_sym, db_kind, items, source="pa_strategy")
            await ws_manager.broadcast({
                "action": ws_action,
                "symbol": norm_sym,
                payload_key: items,
            })

        wave_lines = annos.get("wave_lines", None)
        if wave_lines:
            save_annotations_batch(norm_sym, "wave_line", [wave_lines], source="pa_strategy")
        await ws_manager.broadcast({
            "action": "draw_wave_lines",
            "symbol": norm_sym,
            "wave_lines": wave_lines,
        })

    return res


@app.get("/api/strategy/html")
async def get_strategy_chart_html(symbol: str, period: str = "1d"):
    norm_sym = normalize_symbol(symbol) or symbol
    df = None
    try:
        df, _ = await get_klines_df(norm_sym, period=period, full=True)
    except Exception:
        df = None

    if df is None or df.empty:
        df = _load_local_csv_fallback(norm_sym)

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"无法获取 {norm_sym} 的K线数据")

    html_content = generate_wave_chart_html(norm_sym, period=period, df=df)
    return HTMLResponse(content=html_content, media_type="text/html")


@app.post("/api/control/clear")
async def control_clear_annotations(req: ClearAnnotationsRequest):
    norm_sym = normalize_symbol(req.symbol) or req.symbol
    del_count = clear_annotations(norm_sym, kind=req.kind, source=req.source)
    await ws_manager.broadcast({
        "action": "clear",
        "symbol": norm_sym,
        "kind": req.kind,
    })
    return {"status": "ok", "deleted": del_count}


@app.get("/api/control/annotations")
async def control_get_annotations(
    symbol: str = Query(..., description="股票代码"),
    kind: Optional[str] = Query(None, description="标注类型: marker / line / box"),
):
    norm_sym = normalize_symbol(symbol) or symbol
    return {"symbol": norm_sym, "annotations": get_annotations(norm_sym, kind=kind)}


@app.post("/api/control/capture")
async def control_capture_chart():
    req_id = str(uuid.uuid4())
    future = asyncio.get_event_loop().create_future()
    ws_manager.capture_futures[req_id] = future

    await ws_manager.broadcast({
        "action": "capture_chart",
        "request_id": req_id,
    })

    try:
        base64_data = await asyncio.wait_for(future, timeout=5.0)
    except asyncio.TimeoutError:
        return {"status": "error", "message": "截取图表超时 (可能前端窗口未连接或正在后台休眠)"}
    finally:
        ws_manager.capture_futures.pop(req_id, None)

    app_data = os.environ.get("APPDATA")
    out_dir = (
        os.path.join(app_data, "StockVision", "screenshots")
        if app_data
        else os.path.join(BASE_DIR, "screenshots")
    )
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(
        out_dir,
        f"chart_{active_chart_state['symbol']}_{int(datetime.now().timestamp())}.png",
    )

    raw_b64 = base64_data.split(",")[-1]
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(raw_b64))

    sym = active_chart_state["symbol"]
    return {
        "status": "ok",
        "file_path": out_path,
        "symbol": sym,
        "period": active_chart_state["period"],
        "current_price": active_chart_state["current_price"],
        "annotations": get_annotations(sym),
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
